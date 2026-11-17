// Pin Declarations

#define R_PIN_DIR 8//2      // Motor direction signal
#define R_PIN_PWM 9//3      // PWM motor speed control
#define R_PIN_SPEED 10//4   // SC Speed Pulse Output from RioRand board
#define R_PIN_BRAKE 11//5    // Motor brake signal (active low)

#define L_PIN_DIR 2//8      // Motor direction signal
#define L_PIN_PWM 3//9      // PWM motor speed control
#define L_PIN_SPEED 4//10   // SC Speed Pulse Output from RioRand board
#define L_PIN_BRAKE 5//11    // Motor brake signal (active low)
#define TAU 100

void setup() {
  Serial.begin(115200);
    pinMode(L_PIN_SPEED, INPUT);
    pinMode(L_PIN_PWM, OUTPUT);
    pinMode(L_PIN_BRAKE, OUTPUT);
    pinMode(L_PIN_DIR, OUTPUT);

    pinMode(R_PIN_SPEED, INPUT);
    pinMode(R_PIN_PWM, OUTPUT);
    pinMode(R_PIN_BRAKE, OUTPUT);
    pinMode(R_PIN_DIR, OUTPUT);
    
    // Set initial pin states
    digitalWrite(L_PIN_BRAKE, true);
    digitalWrite(L_PIN_DIR, false);
    analogWrite(L_PIN_PWM, 0);

    digitalWrite(R_PIN_BRAKE, true);
    digitalWrite(R_PIN_DIR, false);
    analogWrite(R_PIN_PWM, 0);
    Serial.println("ACK");
    delay(2000);

  simpleTest();
}

void loop() {
//  testMotor();
  delay(1000);
  
}

void simpleTest() {
  Serial.println("Moving Left");
  digitalWrite(L_PIN_BRAKE, false);
  analogWrite(L_PIN_PWM, 50);
  delay(3000);
  analogWrite(L_PIN_PWM, 0);
  Serial.println("STOP");
  delay(500);  
  Serial.println("Moving Right");
  digitalWrite(R_PIN_BRAKE, false);
  analogWrite(R_PIN_PWM, 50);
  delay(3000);
  analogWrite(R_PIN_PWM, 0);
  Serial.println("STOP");
  delay(500);  
}

void testMotor(){
  Serial.println("Moving Right");
  digitalWrite(R_PIN_DIR, LOW);
  for(int v = 0; v < 255; v++){
    analogWrite(R_PIN_PWM, v);
    Serial.println(analogRead(A1));
    delay(TAU);
  }
  for(int v = 255; v >=0; v--){
    analogWrite(R_PIN_PWM, v);
    Serial.println(analogRead(A1));
    delay(TAU);
  }
  Serial.println("Moving Left");
  digitalWrite(L_PIN_DIR, HIGH);
  for(int v = 0; v < 255; v++){
    analogWrite(L_PIN_PWM, v);
    Serial.println(analogRead(A1));
    delay(TAU);
  }
  for(int v = 255; v >=0; v--){
    analogWrite(L_PIN_PWM, v);
    Serial.println(analogRead(A1));
    delay(TAU);
  }
}
