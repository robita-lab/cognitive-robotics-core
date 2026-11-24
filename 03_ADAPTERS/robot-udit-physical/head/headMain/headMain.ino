/*
Head Main.
Conexión via Serial con un servidor de ROS.
TODO:
- para evitar el shake del principio, utilizar un rele o un transistor en la alimentación del servo, para retrasar el encendido 
- coordinar las animaciones de los ojos con los servos. Hacer que las animaciones no sean bloqueantes (threads?)
*/

#include <Adafruit_NeoPixel.h>
#include "eyes_data.h"
#include <Servo.h>

#define PAN_PIN 2
#define LEFT_PIN  3
#define RIGHT_PIN 4
#define LED_PIN    5
#define LED_COUNT 128
#define RELE  7

#define UPDATE_TIME 300;             // Time used to output serial data

Adafruit_NeoPixel strip(LED_COUNT, LED_PIN, NEO_GRB + NEO_KHZ800);
static uint32_t r = strip.Color(255,   0,   60);
static uint32_t b = strip.Color( 60,   0,   255);
static uint32_t color = strip.Color( 0,   0,   255);
int tau = 40;

int min_left_servo = 1100;
int max_left_servo = 1800;
int min_right_servo = 1200;
int max_right_servo = 2000;
int min_pan_servo = 1000;
int max_pan_servo = 2000;
int middle_servo = 1500;

int min_tau = 10; // minimum time in gestures
int max_tau = 100;  // maximum time

float pot1 = middle_servo, pot2 = middle_servo, pot3 = middle_servo;
float pot1Smoothed = middle_servo, pot2Smoothed = middle_servo, pot3Smoothed = middle_servo;
float pot1SmoothedPrev = middle_servo, pot2SmoothedPrev = middle_servo, pot3SmoothedPrev = middle_servo;
float alpha = 0.999;

bool pot1_end = true, pot2_end = true, pot3_end = true;

unsigned long currentMillis;
long previousMillis = 0;    // set up timers
long interval = 5;        // time constant for timer

int stepFlag = 0;
long previousStepMillis = 0;

Servo pan_servo;
Servo left_servo;
Servo right_servo;

String _command = "";       // Command received in Serial read command
int _data = 0;              // Data received in Serial read command

void setup() {

  Serial.begin(115200);

  pinMode( RELE, OUTPUT );
  digitalWrite(RELE, LOW); // OFF
  
  pan_servo.attach( PAN_PIN ); // pan
  left_servo.attach( LEFT_PIN ); //
  right_servo.attach( RIGHT_PIN );

/*  softAttach( pan_servo, PAN_PIN );
  softAttach( left_servo, LEFT_PIN );
  softAttach( right_servo, RIGHT_PIN );
*/
  pan_servo.writeMicroseconds(1500);
  left_servo.writeMicroseconds(1700);
  right_servo.writeMicroseconds(1700);
  move_servos();
  update_servos_state(); // test if servos have reached pot1 value

//[1000, 2000] // [CCW, CW], 1500 - middle  //[700, 2300]

  strip.begin();           // INITIALIZE NeoPixel strip object (REQUIRED)
  strip.show();            // Turn OFF all pixels ASAP
  strip.setBrightness(255); // Set BRIGHTNESS to about 1/5 (max = 255)
  clear(0);
  clear(1);
  delay(1000);
  digitalWrite(RELE, HIGH); // ON
  blink(tau);
  show_love(tau);
//  test();
}

void loop() {
  bool dataReceived = read_from_serial();

  if (dataReceived == true) {
    parse_command(_command, _data);
    Serial.println("ACK");
  }

  move_servos();
  update_servos_state(); // test if servos have reached pot1 value
//  print_to_serial();

  delay(1);
}

// No funciona. Al revés: multiplica los shocks iniciales
void softAttach( Servo s, int pin ) {
  for( int i = 0; i < 10; i++ ){
    s.attach(pin);
    delay(10);
    s.detach();
    delay(100);
  }
  s.attach(pin);
}

void initServos() {
  pot1 = 1500;
  pot2 = 1700;
  pot3 = 1700;
  move_servos();
}

/**
 Comandos:
  "PAN, angle", siendo angle [-60, 60] 
*/
void parse_command( String command, int data ) {  
    if (command == "PAN") {
//      Serial.print("Setting pan:  ");
//      Serial.println(data);
      pot1 = map( data, -60, 60, min_pan_servo, max_pan_servo );
//      Serial.println(pot1);
    } else if(command == "L_TILT") {
//      Serial.print("Setting left tilt to   ");
//      Serial.println(data);
      pot2 = map( data, -10, 10, min_left_servo, max_left_servo );
    } else if(command == "R_TILT") {
//      Serial.print("Setting right tilt to   ");
//      Serial.println(data);
      pot3 = map( data, 10, -10, min_right_servo, max_right_servo );
    } else if( command == "LOVE" ){
//      data = map(data, -10, 10, min_tau, max_tau);
      data = map(abs(data), 0, 10, min_tau, max_tau);
      show_love(data);
    } else if( command == "LAUGH" ){
      data = map(abs(data), 0, 10, min_tau, max_tau);
      laugh(data);
    } else if( command == "SAD" ){
      data = map(abs(data), 0, 10, min_tau, max_tau);
      sad(data);
    } else if( command == "HAPPY" ){
      data = map(data, -10, 10, min_tau, max_tau);
      happy(data);
    } else if( command == "ANGRY" ){
      data = map(abs(data), 0, 10, min_tau, max_tau);
      angry( tau);
    } else if( command == "BLINK" ){
      data = map(data, -10, 10, min_tau, max_tau);
      blink(data);
    } else if( command == "WINK" ){
      data = map(abs(data), 0, 10, min_tau, max_tau);
      wink_right(data);
    } else if( command == "CELEBRATION" ){
      data = map(abs(data), 0, 10, min_tau, max_tau);
      celebration(data);
    } else if( command == "BLINK_CIRCLE" ){
      data = map(abs(data), 0, 10, min_tau, max_tau);
      blink(data);
    } else if( command == "BLINK_LINE" ){
      data = map(abs(data), 0, 10, min_tau, max_tau);
      blink_line(data);
    } else if( command == "LOGO" ){
      data = map(abs(data), 0, 10, min_tau, max_tau);
      show_logo_3(data);
    }
}

void update_servos_state() {
  float thres = 0.99;
  if( abs(pot1Smoothed - pot1) < thres ) pot1_end = true; 
  else pot1_end = false;
  if( abs(pot2Smoothed - pot2) < thres ) pot2_end = true; 
  else pot2_end = false;
  if( abs(pot3Smoothed - pot3) < thres ) pot3_end = true; 
  else pot3_end = false;
}

void move_servos() {
      pot1Smoothed = (pot1  * (1.0 - alpha)) + (pot1SmoothedPrev * alpha);
      pot2Smoothed = (pot2  * (1.0 - alpha)) + (pot2SmoothedPrev * alpha);
      pot3Smoothed = (pot3  * (1.0 - alpha)) + (pot3SmoothedPrev * alpha);

      pot1SmoothedPrev = pot1Smoothed;
      pot2SmoothedPrev = pot2Smoothed;
      pot3SmoothedPrev = pot3Smoothed;

      pot1Smoothed = constrain(pot1Smoothed, min_pan_servo, max_pan_servo);
      pot2Smoothed = constrain(pot2Smoothed, min_left_servo, max_left_servo);
      pot3Smoothed = constrain(pot3Smoothed, min_right_servo, max_right_servo);

      pan_servo.writeMicroseconds(pot1Smoothed);  // neck rotate
      left_servo.writeMicroseconds(pot2Smoothed); // neck left
      right_servo.writeMicroseconds(pot3Smoothed);  // neck right
} 

/**
* Lee formato COMMAND, value 
*/
bool read_from_serial() {
    static String cmdBuffer;        // Stores the received command
    static String dataBuffer;       // Stores the received data
    static bool isCommand = true;   // Flag to store received bytes in command or data buffer
    byte recByte;                   // Byte received from the serial port
    
    if (Serial.available() == false)
      return false;
    
    recByte = Serial.read();
    
    // Check if byte is termination character (carriage return)
    if (recByte == '\r') {
        // Save buffers to global variables
        cmdBuffer.toUpperCase();
        _command = cmdBuffer;
        _data = dataBuffer.toInt();
      
        // Write what was received back to the serial port
        /*
        Serial.print("Received: "); 
        Serial.print(_command); 
        Serial.print(",");
        Serial.println(_data);
        */
        // Clear local variables
        cmdBuffer = "";
        dataBuffer = "";
        isCommand = true;
      
        return true;
    }
        // Check if byte is a comma which separates the command from the data
    if ((char)recByte == ',') {
        isCommand = false;  // Next byte will be a data byte
        return false;
    }

    // Save data to one of the receive buffers
    if (isCommand)
        cmdBuffer += (char)recByte;
    else
        dataBuffer += (char)recByte;
    
    return false;
}

void print_to_serial() {
    static unsigned long updateTime;
    
    if (millis() > updateTime) {
      Serial.print(pot1Smoothed);
      Serial.print(" , ");
      Serial.print(pot2Smoothed);
      Serial.print(" , ");
      Serial.println(pot3Smoothed);
      Serial.print(pot1_end);
      Serial.print(" , ");
      Serial.print(pot2_end);
      Serial.print(" , ");
      Serial.println(pot3_end);

        // Calculate next update time
      updateTime = millis() + UPDATE_TIME;
    }
}

void show_love(int tau) {
  color = r;
  showShape(heart_1, 0);
  showShape(heart_1, 1);
  delay( tau );
  showShape(heart_2, 0);
  showShape(heart_2, 1);
  delay( tau );
  showShape(heart_3, 0);
  showShape(heart_3, 1);
  delay( tau );
  showShape(heart_2, 0);
  showShape(heart_2, 1);
  delay( tau );
  showShape(heart_1, 0);
  showShape(heart_1, 1);
  delay( tau );
  showShape(heart_2, 0);
  showShape(heart_2, 1);
  delay( tau );
  showShape(heart_3, 0);
  showShape(heart_3, 1);
  delay( tau );
  color = b;
}

void show_logo_1(int tau) {
  showShape(letter_u, 0);
  showShape(letter_u, 1);
  delay( tau );
  showShape(letter_d, 0);
  showShape(letter_d, 1);
  delay( tau );
  showShape(letter_i, 0);
  showShape(letter_i, 1);
  delay( tau );
  showShape(letter_t, 0);
  showShape(letter_t, 1);
  delay( tau );
}

void show_logo_2(int tau) {
  showShape(letter_u, 0);
  showShape(letter_d, 1);
  delay( tau );
  showShape(letter_d, 0);
  showShape(letter_i, 1);
  delay( tau );
  showShape(letter_i, 0);
  showShape(letter_t, 1);
  delay( tau );
//  showShape(letter_t, 0);
//  showShape(letter_t, 1);
//  delay( tau );
}

void show_logo_3(int tau) {
  showShape(letter_u, 0);
  showShape(letter_d, 1);
  delay( tau );
  showShape(letter_i, 0);
  showShape(letter_t, 1);
  delay( tau );
}

void laugh(int tau){
  showShape(laugh_left, 0);
  showShape(laugh_right, 1);
}

void sad( int tau ){
  showShape(sad_1_left, 0);
  showShape(sad_1_right, 1);
  delay(tau);
  showShape(sad_2_left, 0);
  showShape(sad_2_right, 1);
  delay(tau);
  showShape(sad_1_left, 0);
  showShape(sad_1_right, 1);
  delay(tau);
  showShape(sad_2_left, 0);
  showShape(sad_2_right, 1);
  delay(tau);
}

void happy(int tau) {
  showShape(happy_1, 0);
  showShape(happy_1, 1);
}

void angry(int tau){
  showShape(angry_1_left, 0);
  showShape(angry_1_right, 1);
  delay(tau);
  showShape(angry_2_left, 0);
  showShape(angry_2_right, 1);
  delay(tau);
  showShape(angry_1_left, 0);
  showShape(angry_1_right, 1);
  delay(tau);
  showShape(angry_2_left, 0);
  showShape(angry_2_right, 1);
  delay(tau);
}

void celebration(int tau){
  showShape( neutral_1_medium, 0 );
  showShape( neutral_1_medium, 1 );
  delay(2*tau);
  showShape( neutral_1_big, 0 );
  showShape( neutral_1_small, 1 );
  delay(5*tau);
  showShape( neutral_1_medium, 0 );
  showShape( neutral_1_medium, 1 );
  delay(2*tau);
  showShape( neutral_1_small, 0 );
  showShape( neutral_1_big , 1 );
  delay(5*tau);
  showShape( neutral_1_medium, 0 );
  showShape( neutral_1_medium, 1 );
  delay(2*tau);
}

void blink_line( int tau ) {
  showShape( t_1_line, 0 );
  showShape( t_1_line, 1 );
  delay(tau);
  showShape( t_2_line, 0 );
  showShape( t_2_line, 1 );
  delay(tau);
  showShape( t_3_line, 0 );
  showShape( t_3_line, 1 );
  delay(tau);
  showShape( t_4_line, 0 );
  showShape( t_4_line, 1 );
  delay(tau);
  showShape( t_4_line, 0 );
  showShape( t_4_line, 1 );
  delay(tau);
  showShape( t_3_line, 0 );
  showShape( t_3_line, 1 );
  delay(tau);
  showShape( t_2_line, 0 );
  showShape( t_2_line, 1 );
  delay(tau);
  showShape( t_1_line, 0 );
  showShape( t_1_line, 1 );  
  delay(tau);
}

void blink( int tau ){
  showShape( t_1, 0 );
  showShape( t_1, 1 );
  delay(tau);
  showShape( t_2, 0 );
  showShape( t_2, 1 );
  delay(tau);
  showShape( t_3, 0 );
  showShape( t_3, 1 );
  delay(tau);
  showShape( t_4, 0 );
  showShape( t_4, 1 );
  delay(tau);
  showShape( t_4, 0 );
  showShape( t_4, 1 );
  delay(tau);
  showShape( t_3, 0 );
  showShape( t_3, 1 );
  delay(tau);
  showShape( t_2, 0 );
  showShape( t_2, 1 );
  delay(tau);
  showShape( t_1, 0 );
  showShape( t_1, 1 );
}

void wink_right(int tau ){
  wink(tau, 0);
}

void wink_left(int tau ){
  wink(tau, 1);
}

void wink( int tau, int eyeID ) {
  showShape( t_1, eyeID );
  delay(tau);
  showShape( t_2, eyeID );
  delay(tau);
  showShape( t_3, eyeID );
  delay(tau);
  showShape( t_4, eyeID );
  delay(tau);
  showShape( t_4, eyeID );
  delay(tau);
  showShape( t_3, eyeID );
  delay(tau);
  showShape( t_2, eyeID );
  delay(tau);
  showShape( t_1, eyeID );
}

void showShape(int (&shape)[N][N], int eyeID) {
  clear( eyeID );
  for(int i = 0; i < N; i++) {
    for(int j = 0; j < N; j ++) {
      int k = toVector(j,i, eyeID);
      if(shape[i][j]  == 1) strip.setPixelColor(k, color);         //  Set pixel's color (in RAM)
    }
  }
  strip.show();                          //  Update strip to match
}

void clear(int eyeID) {
  for(int i = eyeID*N*N; i < eyeID*N*N + N*N; i++) strip.setPixelColor(i,strip.Color(0, 0, 0)) ;
  strip.show();
}

int toVector(int i, int j, int eyeID ) {
  return j*N+i + eyeID*N*N;
}

void test() {
  int data = 50;
  while( 1 ) {
    move_servos();
    update_servos_state(); // test if servos have reached pot1 value
    print_to_serial();
    if( pot1_end ) {
      data = -data;
      pot1 = map( data, -60, 60, min_pan_servo, max_pan_servo );
      update_servos_state(); // test if servos have reached pot1 value
      delay(1000);
    }
  }
}
