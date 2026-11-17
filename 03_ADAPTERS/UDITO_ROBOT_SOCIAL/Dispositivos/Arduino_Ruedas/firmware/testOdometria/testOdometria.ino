// ================== PINES ==================
// Motor Izquierdo
const uint8_t PWM_L = 5;
const uint8_t DIR_L = 4;
const uint8_t SC_L  = 2;   // Interrupción externa (INT0)

// Motor Derecho
const uint8_t PWM_R = 6;
const uint8_t DIR_R = 7;
const uint8_t SC_R  = 3;   // Interrupción externa (INT1)

// ================== ENCODER (conteo por hall) ==================
volatile long pulseCountL = 0;
volatile long pulseCountR = 0;
volatile int8_t dirL = 1;   // 1 = adelante, -1 = atrás (lo fijamos nosotros)
volatile int8_t dirR = 1;

void isrLeft()  { pulseCountL += dirL; }
void isrRight() { pulseCountR += dirR; }

// ================== CONTROL DE MOTOR ==================
// speedCmd: rango que ya uses en tu protocolo, aquí ejemplo -255..255
void setMotor(uint8_t pwmPin, uint8_t dirPin, int speedCmd, volatile int8_t &dirFlag) {
  if (speedCmd >= 0) {
    digitalWrite(dirPin, HIGH);   // ajustar polaridad según tu cableado real
    dirFlag = 1;
  } else {
    digitalWrite(dirPin, LOW);
    dirFlag = -1;
    speedCmd = -speedCmd;
  }
  analogWrite(pwmPin, constrain(speedCmd, 0, 255));
}

// ================== REPORTE POR SERIE ==================
unsigned long lastReport = 0;
const unsigned long REPORT_MS = 50;  // 20 Hz, ajustable

void setup() {
  Serial.begin(115200);

  pinMode(PWM_L, OUTPUT);
  pinMode(DIR_L, OUTPUT);
  pinMode(PWM_R, OUTPUT);
  pinMode(DIR_R, OUTPUT);

  pinMode(SC_L, INPUT_PULLUP);
  pinMode(SC_R, INPUT_PULLUP);

  attachInterrupt(digitalPinToInterrupt(SC_L), isrLeft, RISING);
  attachInterrupt(digitalPinToInterrupt(SC_R), isrRight, RISING);
}

void loop() {
  // --- 1. Aquí va tu parser serie actual ---
  // if (Serial.available()) {
  //   ... obtienes cmdL, cmdR desde tu protocolo ...
  //   setMotor(PWM_L, DIR_L, cmdL, dirL);
  //   setMotor(PWM_R, DIR_R, cmdR, dirR);
  // }

  // --- 2. Reporte periódico de ticks acumulados (para odometría en ROS2) ---
  unsigned long now = millis();
  if (now - lastReport >= REPORT_MS) {
    lastReport = now;

    noInterrupts();
    long pL = pulseCountL;
    long pR = pulseCountR;
    interrupts();

    // Enviamos el TOTAL acumulado, no el delta: si se pierde un paquete
    // en la comunicación serie, el nodo ROS2 puede recalcular sin
    // arrastrar error, restando respecto a la última lectura válida.
    Serial.print("ODOM,");
    Serial.print(pL);
    Serial.print(",");
    Serial.println(pR);
  }
}
