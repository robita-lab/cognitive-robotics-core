/*   
 Control 2 Wheels from I2C messages from a microBit
 TODO: 
*/
#include <Wire.h>
#define INPUT_BUFFER_SIZE  32
#define V_MAX 50 // 70
#define V_MIN 30 
#define V_THRES 10

// Constants
#define SPEED_TIMEOUT 600000       // Time used to determine wheel is not spinning
#define UPDATE_TIME 100            // Time used to output serial data
#define BUFFER_SIZE 16              // Serial receive buffer size
#define BAUD_RATE 115200                  // Serial port baud rate

// Pin Declarations

#define R_PIN_DIR 2      // Motor direction signal
#define R_PIN_PWM 3      // PWM motor speed control
#define R_PIN_SPEED 4   // SC Speed Pulse Output from RioRand board
#define R_PIN_BRAKE 5    // Motor brake signal (true frena)

#define L_PIN_DIR 7      // Motor direction signal
#define L_PIN_PWM 9      // PWM motor speed control
#define L_PIN_SPEED 10   // SC Speed Pulse Output from RioRand board
#define L_PIN_BRAKE 11    // Motor brake signal (active wheel low)

// vars for microBit com
char robotID = 'A';  // A - robot_tarta; B - robot_barco; C - robot_torre
byte buffer[INPUT_BUFFER_SIZE]; // format: robotID stop_flag x y // e.g: A false 36 567 
unsigned int buffer_size = 0;
String input;
int v_left = 0;// = random(50);
int v_right = 0;// = random(50);
int v_left_old = 0;// = random(50);
int v_right_old = 0;// = random(50);
int x = 0, y = 0; // valores de los pots del mando remoto
bool stop_flag;

// Variables used in ReadFromSerial function
String _command = "";       // Command received in Serial read command
int _data = 0;              // Data received in Serial read command

bool l_status = 0; // break ON
bool r_status = 0; // break ON

#define l_min_freq 0 // stopped
// PWM = 30 más o menos es freq = 6000cHz
#define l_max_freq 9000 // max velocity 16000 us period ( 1/ T ) * 1E6 * 1E2 (añade 2 cifras significativas al Hz)
#define r_min_freq 0 // stopped
#define r_max_freq 9000 // max velocity 16000 us period
#define max_pwm 60.0
// Variables used in ReadSpeed function
double l_freq;               // Frequency of the signal on the speed pin. in centiHerz (100cHz = 1Hz)
double l_freq_old;               // Frequency for filter
double l_sp = l_min_freq; // set point
double l_err; // error 
double l_err_old = 0; // error periodo antiguo
double l_err_sum = 0; // suma del error
double l_err_dev = 0; // derivada del error
double l_pwm = 0; // final PWM controlled
unsigned long l_now, l_before;
double l_ellapsed_time;

double r_freq;               // Frequency of the signal on the speed pin
double r_sp = r_min_freq; // set point
double r_err; // error 
double r_err_old = 0; // error periodo antiguo
double r_err_sum = 0; // suma del error
double r_err_dev = 0; // derivada del error
double r_pwm = 0; // final PWM controlled
unsigned long r_now, r_before;
double r_ellapsed_time;


double l_freq_mean;
const int l_numReadings = 1;

double l[l_numReadings];
double l_total = 0.0;
int l_readIndex = 0;

double r_freq_mean;

const int r_numReadings = 1;
double r[r_numReadings];
double r_total = 0.0;
int r_readIndex = 0;
bool noLoop = false;

double Kp = 1E-6;//0.02;
double Kd = 6E-7;//0.7;//0.05;//0.1;//0.01;//30;//0.5;//2;
double Ki = 1E-13;
 

// This is ran only once at startup
void setup()  {
    // Set pin directions
    pinMode(L_PIN_SPEED, INPUT);
    pinMode(L_PIN_PWM, OUTPUT);
    pinMode(L_PIN_BRAKE, OUTPUT);
    pinMode(L_PIN_DIR, OUTPUT);

    pinMode(R_PIN_SPEED, INPUT);
    pinMode(R_PIN_PWM, OUTPUT);
    pinMode(R_PIN_BRAKE, OUTPUT);
    pinMode(R_PIN_DIR, OUTPUT);
    
    // Set initial pin states
    digitalWrite(L_PIN_BRAKE, 1);
    digitalWrite(L_PIN_DIR, 1);
    analogWrite(L_PIN_PWM, 0);

    digitalWrite(R_PIN_BRAKE, 1);
    digitalWrite(R_PIN_DIR, 0);  //   1- bwd, 0-fwd
    analogWrite(R_PIN_PWM, 0);
    delay(2000);

    Wire.begin(8);
    Wire.onReceive( receiveEvent );

    // Initialize serial port
    Serial.begin(BAUD_RATE);
    Serial.println("ACK");
//    Serial.print("l_freq - l_freq_mean - l_sp - l_error - l_error_sum - l_pwm");
//    Serial.println(" | r_freq - r_freq_mean - r_sp - r_error - r_error_sum - r_pwm");
//    test_motors();
}


// control by I2C messages
void loop() {
  if( buffer[0] == robotID ) {
      parse_buffer( buffer );
      x = map(x, 0, 1023, -V_MIN, V_MIN); // giro
      y = map(y, 0, 1023, -V_MAX, V_MAX); // norte-sur
      v_left = x + y;
      v_right = -x + y;
      move_motors( v_left, v_right ); 
      if( stop_flag ) stop_motors();
      Serial.print( "x = " ); Serial.println( x ); 
      Serial.print( "y = " ); Serial.println( y );    
      reset();    
  }
}

void move_motors( int v_left, int v_right ) {
  digitalWrite(L_PIN_BRAKE, false);
  digitalWrite(R_PIN_BRAKE, false);

  v_left = constrain( v_left, -V_MAX, V_MAX );
  v_right = constrain( v_right, -V_MAX, V_MAX );
  
  if( v_left >= 0 ) {
    digitalWrite( L_PIN_DIR, HIGH );      
  } else {
    digitalWrite( L_PIN_DIR, LOW );      
  }
  
  v_left = abs(v_left);
  if(v_left_old < V_THRES & v_left > 1 & v_left < V_MIN) v_left = V_MIN;
  analogWrite( L_PIN_PWM, v_left );
  
  if( v_right >= 0 ) {
    digitalWrite( R_PIN_DIR, LOW );      
  } else {
    digitalWrite( R_PIN_DIR, HIGH );      
  } 
  v_right = abs(v_right);
  if(v_right_old < V_THRES & v_right > 1 & v_right < V_MIN) v_right= V_MIN;
 
  analogWrite( R_PIN_PWM, v_right );
  Serial.print(v_left);   Serial.print(" "); Serial.println(v_right);
  v_left_old = v_left;
  v_right_old = v_right;

}

void test_motors() {
  digitalWrite(L_PIN_BRAKE, false);
  digitalWrite(R_PIN_BRAKE, false);
  
  digitalWrite( L_PIN_DIR, HIGH );      
  analogWrite( L_PIN_PWM, V_MAX );
  delay(1000);
  analogWrite( L_PIN_PWM, 0 );
  delay(1000);
  digitalWrite( L_PIN_DIR, LOW );      
  analogWrite( L_PIN_PWM, V_MAX );
  delay(1000);
  analogWrite( L_PIN_PWM, 0 );
  delay(1000);
  digitalWrite( R_PIN_DIR, HIGH );      
  analogWrite( R_PIN_PWM, V_MAX );
  delay(1000);
  analogWrite( R_PIN_PWM, 0 );
  delay(1000);
  digitalWrite( R_PIN_DIR, LOW );      
  analogWrite( R_PIN_PWM, V_MAX );
  delay(1000);
  analogWrite( R_PIN_PWM, 0 );
  delay(1000);
  
  digitalWrite(L_PIN_BRAKE, true);
  digitalWrite(R_PIN_BRAKE, true);
}


void stop_motors() {
  analogWrite(L_PIN_PWM, 0);
  analogWrite(R_PIN_PWM, 0);
  digitalWrite(L_PIN_BRAKE, true);
  digitalWrite(R_PIN_BRAKE, true);
  delay(10000);
}

void reset() {
  buffer[0] = '0';
  x = 522;
  y = 526;
  stop_flag = 0;
}

void receiveEvent( int howMany ) {
  int i = 0;
  while( 0 < Wire.available() ) { // loop through all but the last
    buffer[i] = Wire.read();
//    Serial.print(i); Serial.print( " " ); Serial.println(buffer[i]);         // print the character
    i++;
  }
  buffer_size = i;
}

void parse_buffer( const char buffer[INPUT_BUFFER_SIZE] ) {
  unsigned char dig[4];
  unsigned char temp;

  if(buffer[2] == '0') stop_flag = false;
  else stop_flag = true;
  
  int j = buffer_size - 1;
  int i = 0;
  y = 0;
  while( buffer[j] != 32 ) {  // 32- ascii for [space]
    dig[i] = buffer[j] - 48; // ascii to int;
    y += dig[i] * pow(10, i);
    i++;
    j--;
  }
  j--;
  i = 0;
  x = 0;
  while( buffer[j] != 32 ) {  // 32- ascii for [space]
    dig[i] = buffer[j] - 48; // ascii to int;
    x += dig[i] * pow(10, i);
    i++;
    j--;
  }
}

// control by serial messages
void loop_serial() {
    // Read serial data and set dataReceived to true if command is ready to be processed
  bool dataReceived = ReadFromSerial();

    // Process the received command if available
  if (dataReceived == true)
      ProcessCommand(_command, _data);

    // Read the speed from input pin (sets _rpm and _mph)
  ReadSpeed();

    // Control loop
  if( noLoop == false ) { // if PWM, no control Loop is made
    if(l_status) leftControlLoop();
    else l_pwm = 0;
    if(r_status) rightControlLoop();
    else r_pwm = 0;
    analogWrite( L_PIN_PWM, constrain(round(l_pwm), 0, max_pwm)); 
    analogWrite( R_PIN_PWM, constrain(round(r_pwm), 0, max_pwm));
  }
    // Outputs the speed data to the serial port 
    WriteToSerial(); 
//   logData();
//  delay(60);
}

void rightControlLoop() {
//  r_now = millis();
  r_ellapsed_time = (double)( r_now - r_before);
  
  r_err = r_sp -  r_freq;
  r_err_dev = (r_err - r_err_old);// (l_ellapsed_time + 1);   
  r_err_sum = r_err + r_err_old;// * r_ellapsed_time;
  r_pwm = r_pwm + Kp * r_err + Ki * (r_err_sum) + Kd * r_err_dev / (r_ellapsed_time + 1);
  
  r_err_old = r_err;
  r_before = r_now;
  
  if(r_pwm > max_pwm ) r_pwm = max_pwm;
  if(r_pwm < 0 ) r_pwm = 0.0;
}

void leftControlLoop() {
  l_now = millis();
  l_ellapsed_time = (double)( l_now - l_before);
  
  l_err = l_sp - l_freq; 
  l_err_dev = (l_err - l_err_old);// (l_ellapsed_time + 1);
  l_err_sum = l_err + l_err_old;// l_ellapsed_time;
  l_pwm = l_pwm + Kp * l_err + Ki * l_err_sum + Kd * l_err_dev;
//  Serial.print("l_pwm = "); Serial.println(l_pwm);
  l_err_old = l_err;
  l_before = l_now;
  
  if(l_pwm > max_pwm ) l_pwm = max_pwm;
  if(l_pwm < 0 ) l_pwm = 0.0;
}

bool ReadFromSerial() {    
    // Local variables   
    static String cmdBuffer;        // Stores the received command
    static String dataBuffer;       // Stores the received data
    static bool isCommand = true;   // Flag to store received bytes in command or data buffer
    byte recByte;                   // Byte received from the serial port
    
    if (Serial.available() == false) return false;
    
    recByte = Serial.read();
    
    if (recByte == '\r') {
        cmdBuffer.toUpperCase();
        _command = cmdBuffer;
        _data = dataBuffer.toInt();
      
//        Serial.print("Received: "); 
//        Serial.print(_command); 
//        Serial.print(",");
  //      Serial.println(_data);
      
        cmdBuffer = "";
        dataBuffer = "";
        isCommand = true;
  
        return true;
    }
    
    if ((char)recByte == ',') {
        isCommand = false;  // Next byte will be a data byte
        return false;
    }

    if (isCommand) cmdBuffer += (char)recByte;
    else dataBuffer += (char)recByte;

    return false;
}

void ProcessCommand(String command, int data) {  
    if (command == "PWM") {
      digitalWrite(L_PIN_BRAKE, false);
      digitalWrite(R_PIN_BRAKE, false);
      l_status = 1;
      r_status = 1;
      l_pwm = data;
      r_pwm = data;
      analogWrite(L_PIN_PWM, data);
      analogWrite(R_PIN_PWM, data);
      noLoop = true;
    } 
    if (command == "R_PWM") {
      digitalWrite(R_PIN_BRAKE, false);
      r_status = 1;
      r_pwm = data;
      analogWrite(R_PIN_PWM, data);
      noLoop = true;
    } 
    if (command == "L_PWM") {
      digitalWrite(L_PIN_BRAKE, false);
      l_status = 1;
      l_pwm = data;
      analogWrite(L_PIN_PWM, data);
      noLoop = true;
    } 
    if (command == "R_V") {
      Serial.print("Setting right:  ");
      Serial.println(data);
      r_sp = map(data, 0, 100, r_min_freq, r_max_freq);
      digitalWrite(R_PIN_BRAKE, false);
      r_status = 1;
      noLoop = false;
    }
    if (command == "L_V") {
      Serial.print("Setting left:  ");
      Serial.println(data);
      l_sp = map(data, 0, 100, l_min_freq, l_max_freq);
      Serial.println(l_sp);
      digitalWrite(L_PIN_BRAKE, false);
      l_status = 1;
      noLoop = false;
    }
    if (command == "V") {
//      Serial.print("Setting velocity right left:  ");
//      Serial.println(data);
      r_sp = map(data, 0, 100, r_min_freq, r_max_freq);
      l_sp = map(data, 0, 100, l_min_freq, l_max_freq);
      digitalWrite(L_PIN_BRAKE, false);
      digitalWrite(R_PIN_BRAKE, false);
      r_status = 1;
      l_status = 1;
      noLoop = false;
    }
        
    // Process BRAKE command
    if (command == "BRAKE") {
      Serial.print("Setting brake:  ");
      Serial.println(data);
      digitalWrite(R_PIN_BRAKE, data);
      digitalWrite(L_PIN_BRAKE, data);
      r_status = data;
      l_status = data;
    }

    // Process DIR command
    if (command == "R_DIR") {
      Serial.print("Setting direction right:  ");
      Serial.println(data);
      digitalWrite(R_PIN_DIR, data);
    }
    if (command == "L_DIR") {
      Serial.print("Setting direction left:  ");
      Serial.println(data);
      digitalWrite(L_PIN_DIR, data);
    }
    if (command == "KP") {
      Serial.print("Kp =   ");
      Kp = data * 1E-6;
      Serial.println(Kp,4);
    }
    if (command == "KD") {
      Serial.print("Kd =   ");
      Kd = data;
      Serial.println(Kd,4);
    }
    if (command == "KI") {
      Serial.print("Ki =   ");
      Ki = data * 1E-12;
      Serial.println(Ki,12);
    }
}

// Reads the speed from the input pin and calculates RPM and MPH
// Monitors the state of the input pin and measures the time (µs) between pin transitions
void ReadSpeed() {
    static bool leftLastState = false;    // Saves the last state of the speed pin
    static bool rightLastState = false;    // Saves the last state of the speed pin
    static unsigned long left_last_uS;     // The time (µs) when the speed pin changes
    static unsigned long right_last_uS;     // The time (µs) when the speed pin changes
    static unsigned long left_timeout_uS;  // Timer used to determine the wheel is not spinning
    static unsigned long right_timeout_uS;  // Timer used to determine the wheel is not spinning

    bool left_state = digitalRead(L_PIN_SPEED);
    bool right_state = digitalRead(R_PIN_SPEED);

    if (left_state != leftLastState) {
      unsigned long current_uS = micros();
      unsigned long elapsed_uS = current_uS - left_last_uS;
//      if(abs(l_freq - l_freq_old) < 10000)
      if( elapsed_uS > 15E3)
        l_freq = 1E8/ elapsed_uS; // centiHz
      left_last_uS = current_uS;
      leftLastState = left_state;
    } else if ((micros() - left_last_uS) > SPEED_TIMEOUT) {
        l_freq = l_min_freq;
//        left_last_uS = micros();
    }
    // Check if the pin has changed state
    if (right_state != rightLastState) {
      // Calculate how long has passed since last transition
      unsigned long current_uS = micros();
      unsigned long elapsed_uS = current_uS - right_last_uS;

      if( elapsed_uS > 15E3)
        r_freq = 1E8/ elapsed_uS; // centiHz
      right_last_uS = current_uS;
      right_timeout_uS = right_last_uS + SPEED_TIMEOUT;
      rightLastState = right_state;
    } else if (micros() > right_timeout_uS) {
        r_freq = r_min_freq;
//        right_last_uS = micros();
    }
/*      l_total = l_total - l[l_readIndex];
      l[l_readIndex] = l_freq;
      l_total = l_total + l[l_readIndex];
      l_readIndex ++;
      if(l_readIndex >= l_numReadings) l_readIndex = 0;
      l_freq_mean = l_total / l_numReadings;

      r_total = r_total - r[r_readIndex];
      r[r_readIndex] = r_freq;
      r_total = r_total + r[r_readIndex];
      r_readIndex ++;
      if(r_readIndex >= r_numReadings) r_readIndex = 0;
      r_freq_mean = r_total / r_numReadings;
      */
}

// Writes the RPM and MPH to the serial port at a set interval
void WriteToSerial() {
    static unsigned long updateTime;
    
//    Serial.println("l_freq - l_freq_mean - l_sp - l_error - l_error_sum - l_pwm");
    if (millis() > updateTime) {
        Serial.print((String)millis() + ", ");
        Serial.print((String)l_freq + ", ");
//        Serial.print((String)l_freq_mean + ", ");
        Serial.print((String)l_sp + ", ");
        Serial.print((String)l_err + ", ");
        Serial.print((String)l_err_sum + ", ");
        Serial.print(l_err_dev );Serial.print(",");
        Serial.print((String)l_pwm + "  |  ");

        Serial.print((String)r_freq + ", ");
//        Serial.print((String)r_freq_mean + ", ");
        Serial.print((String)r_sp + ", ");
        Serial.print((String)r_err + ", ");
        Serial.print((String)r_err_sum + ", ");
        Serial.println((String)r_pwm);

        updateTime = millis() + UPDATE_TIME;
    }
}
