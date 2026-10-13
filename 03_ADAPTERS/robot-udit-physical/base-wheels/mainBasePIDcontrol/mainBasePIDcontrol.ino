// ============================================================
//  Control de velocidad en bucle cerrado (PID) para 2 ruedas
//  motorizadas con BLDC + driver ZS-X11H (salida SC = pulso hall)
//
//  Protocolo serie:
//    Entrada  (PC -> Arduino): "V <setpointL> <setpointR>\n"
//                               valores en rad/s de la RUEDA, con signo
//    Salida   (Arduino -> PC): "O <ticksL> <ticksR> <measL> <measR>\n"
//                               ticksL/R: contador acumulado de pulsos (con signo)
//                               measL/R : velocidad medida en rad/s
// ============================================================

#include <math.h>

// ---------------- PINES ----------------
const uint8_t PWM_L = 5;
const uint8_t DIR_L = 4;
const uint8_t SC_L  = 2;   // INT0 en Uno/Nano

const uint8_t PWM_R = 6;
const uint8_t DIR_R = 7;
const uint8_t SC_R  = 3;   // INT1 en Uno/Nano

// ---------------- CALIBRACIÓN (AJUSTAR EXPERIMENTALMENTE) ----------------
// Gira la rueda una vuelta completa a mano/baja velocidad y cuenta cuántos
// pulsos SC se generan (ya con la reducción de la caja de engranajes incluida).
const float PULSES_PER_WHEEL_REV = 45.0;

const int   PWM_MAX = 255;
const float INTEGRAL_LIMIT = 150.0;   // anti-windup
const float STOP_THRESHOLD = 0.05;    // rad/s por debajo del cual se considera "parado"

// ---------------- GANANCIAS PID (PUNTO DE PARTIDA, HAY QUE AJUSTAR) ----------------
float Kff = 1.6;
float Kp = 1.5;
float Ki = 2.0;
float Kd = 0.05;

// ---------------- TEMPORIZACIÓN ----------------
const unsigned long CONTROL_DT_MS   = 20;   // 50 Hz bucle de control
const unsigned long TELEMETRY_DT_MS = 20;   // 20 Hz telemetría
const unsigned long CMD_TIMEOUT_MS  = 500;  // watchdog: para motores si no llegan comandos

unsigned long lastControlMs   = 0;
unsigned long lastTelemetryMs = 0;
unsigned long lastCmdMs       = 0;

// ---------------- MÉTODO DE MEDICIÓN: PERIODO ENTRE PULSOS (T) ----------------
// En vez de contar pulsos en una ventana fija (método M, cuantiza mucho a baja
// velocidad), medimos el tiempo entre pulsos consecutivos con micros().
// Un único pulso ya da una medida de velocidad instantánea precisa.
const unsigned long MIN_VALID_PERIOD_US = 300;     // filtro de rebotes/ruido eléctrico
const unsigned long STALE_TIMEOUT_US    = 300000UL; // 300 ms sin pulsos => velocidad 0

// ---------------- ESTRUCTURA DE CADA RUEDA ----------------
struct Wheel {
  uint8_t pwmPin, dirPin, scPin;
  volatile long pulseCount;            // ticks acumulados, con signo (para joint_states/odom)
  volatile int8_t dirSign;             // 1 adelante, -1 atrás (fijado por el PID, leído en la ISR)
  volatile unsigned long lastPulseUs;  // instante (micros) del último pulso válido
  volatile unsigned long lastPeriodUs; // duración (us) entre los 2 últimos pulsos válidos
  float measured;                      // rad/s, con signo
  float setpoint;                      // rad/s, con signo (objetivo)
  float integral;
  float lastError;

  Wheel(uint8_t pwm, uint8_t dir, uint8_t sc)
    : pwmPin(pwm), dirPin(dir), scPin(sc),
      pulseCount(0), dirSign(1), lastPulseUs(0), lastPeriodUs(0),
      measured(0.0), setpoint(0.0), integral(0.0), lastError(0.0) {}
};

Wheel wL(PWM_L, DIR_L, SC_L);
Wheel wR(PWM_R, DIR_R, SC_R);

// ---------------- ISR: registrar periodo entre pulsos hall ----------------
void handlePulse(Wheel &w) {
  unsigned long now = micros();
  unsigned long period = now - w.lastPulseUs;

  if (w.lastPulseUs != 0 && period < MIN_VALID_PERIOD_US) {
    return; // rebote o ruido: descartar, no actualizar lastPulseUs
  }

  if (w.lastPulseUs != 0) {
    w.lastPeriodUs = period;
  }
  w.lastPulseUs = now;
  w.pulseCount += w.dirSign;
}

void isrL() { handlePulse(wL); }
void isrR() { handlePulse(wR); }

// ---------------- MEDICIÓN DE VELOCIDAD (método T con decaimiento a cero) ----------------
void updateMeasured(Wheel &w) {
  unsigned long now = micros();

  noInterrupts();
  unsigned long lastPulseUs  = w.lastPulseUs;
  unsigned long lastPeriodUs = w.lastPeriodUs;
  int8_t sign = w.dirSign;
  interrupts();

  if (lastPulseUs == 0) {
    w.measured = 0.0;
    return;
  }

  unsigned long sinceLastPulse = now - lastPulseUs;

  // Si ha pasado más tiempo del que duró el último periodo, la rueda va
  // MÁS LENTA de lo que ese periodo indicaba (o se ha parado): usamos el
  // tiempo transcurrido como estimación conservadora del periodo actual.
  unsigned long effectivePeriodUs = (sinceLastPulse > lastPeriodUs) ? sinceLastPulse : lastPeriodUs;

  if (sinceLastPulse > STALE_TIMEOUT_US) {
    w.measured = 0.0;
    return;
  }

  float angularStep = (2.0 * PI) / PULSES_PER_WHEEL_REV;
  float periodSeconds = effectivePeriodUs / 1000000.0;
  w.measured = sign * (angularStep / periodSeconds);
}

// ---------------- PID + ACTUACIÓN ----------------
void updatePID(Wheel &w, float dt) {
  // Parada limpia si el setpoint es prácticamente cero
  if (fabs(w.setpoint) < STOP_THRESHOLD) {
    w.integral  = 0;
    w.lastError = 0;
    analogWrite(w.pwmPin, 0);
    return;
  }

  int8_t newDir = (w.setpoint >= 0) ? 1 : -1;
  if (newDir != w.dirSign) {
    w.dirSign = newDir;
    w.integral  = 0;   // evita arrastrar windup de la dirección anterior
    w.lastError = 0;
//    digitalWrite(w.dirPin, newDir ); // AJUSTAR si la polaridad real es al revés
    if(w.dirPin == DIR_R) digitalWrite(w.dirPin, newDir > 0 ? HIGH : LOW); // AJUSTAR si la polaridad real es al revés
    else digitalWrite(w.dirPin, newDir > 0 ? LOW : HIGH); 
  }

  float error = fabs(w.setpoint) - fabs(w.measured);
  w.integral = constrain(w.integral + error * dt, -INTEGRAL_LIMIT, INTEGRAL_LIMIT);
  float derivative = (error - w.lastError) / dt;
  w.lastError = error;

  float output = Kff * fabs(w.setpoint) + Kp * error + Ki * w.integral + Kd * derivative;
  output = constrain(output, 0, PWM_MAX);

  analogWrite(w.pwmPin, (int)output);
}

// ---------------- PROTOCOLO SERIE ----------------
void readSerialCommands() {
  static String line = "";
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\n') {
      if (line.startsWith("V")) {
        int firstSpace  = line.indexOf(' ');
        int secondSpace = line.indexOf(' ', firstSpace + 1);
        if (firstSpace > 0 && secondSpace > firstSpace) {
          wL.setpoint = line.substring(firstSpace + 1, secondSpace).toFloat();
          wR.setpoint = line.substring(secondSpace + 1).toFloat();
          lastCmdMs = millis();
        }
      }
      line = "";
    } else if (c != '\r') {
      line += c;
    }
  }
}

void sendTelemetry() {
  noInterrupts();
  long tL = wL.pulseCount;
  long tR = wR.pulseCount;
  interrupts();

  Serial.print("O ");
  Serial.print(tL);
  Serial.print(" ");
  Serial.print(tR);
  Serial.print(" ");
  Serial.print(wL.measured, 4);
  Serial.print(" ");
  Serial.println(wR.measured, 4);
}

// ---------------- SETUP ----------------
void setup() {
  Serial.begin(115200);

  pinMode(wL.pwmPin, OUTPUT);
  pinMode(wL.dirPin, OUTPUT);
  pinMode(wR.pwmPin, OUTPUT);
  pinMode(wR.dirPin, OUTPUT);
  wL.dirSign = 1;
  wR.dirSign = 0;
  pinMode(wL.scPin, INPUT_PULLUP);
  pinMode(wR.scPin, INPUT_PULLUP);

  attachInterrupt(digitalPinToInterrupt(wL.scPin), isrL, RISING);
  attachInterrupt(digitalPinToInterrupt(wR.scPin), isrR, RISING);

  lastCmdMs = millis();
}

// ---------------- LOOP ----------------
void loop() {
  readSerialCommands();

  unsigned long now = millis();

/*
  // Watchdog de seguridad: si no llegan comandos, parar
  if (now - lastCmdMs > CMD_TIMEOUT_MS) {
    wL.setpoint = 0;
    wR.setpoint = 0;
  }
*/
  if (now - lastControlMs >= CONTROL_DT_MS) {
    float dt = (now - lastControlMs) / 1000.0;
    lastControlMs = now;

    updateMeasured(wL);
    updateMeasured(wR);

    updatePID(wL, dt);
    updatePID(wR, dt);
  }

  if (now - lastTelemetryMs >= TELEMETRY_DT_MS) {
    lastTelemetryMs = now;
    sendTelemetry();
  }
}
