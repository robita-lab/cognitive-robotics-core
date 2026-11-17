/**
 * changes unsigned int x, y, to int x, y 
 */
#include <Wire.h>
//#include <Adafruit_NeoPixel.h>
//#include "clases.h"

#define INPUT_BUFFER_SIZE  32
//#define DEBUG

#define OUT1 9 //connect to L298 IN1
#define OUT2 3 //connect to L298 IN2 
#define OUT3 10 //connect to L298 IN3 
#define OUT4 5 //connect to L298 IN4 

// values for N1
#define TRIG_LEFT  12 // SONAR
#define ECHO_LEFT  13
#define TRIG_CENTER  8 // SONAR
#define ECHO_CENTER  7
#define TRIG_RIGHT  2 // SONAR
#define ECHO_RIGHT  4

#define WONDERING  0
#define REMOTE_CONTROL  1

#define V_MAX 60 // 70
#define V_MIN 40

#define PIXEL_PIN    0
#define PIXEL_COUNT 12
#define NUM_GOTAS 2

int Gota::N = 12;
byte Gota::shape[5] = {255, 100, 10, 4, 0};

//Adafruit_NeoPixel strip = Adafruit_NeoPixel(PIXEL_COUNT, PIXEL_PIN, NEO_GRB + NEO_KHZ800);

Gota g[NUM_GOTAS];

char robotID = 'A';  // A - robot_tarta; B - robot_barco; C - robot_torre
//char robotID = 'B';  // A - robot_tarta; B - robot_barco; C - robot_torre

byte buffer[INPUT_BUFFER_SIZE]; // format: robotID fog x y // e.g: A false 36 567 
unsigned int buffer_size = 0;
String input;

//unsigned int x = 0, y = 0; in v1 is unsigned int, and it works!???
int x = 0, y = 0;
bool fog;

int v_max = V_MAX;

const int trig_pin[3] = { TRIG_LEFT, TRIG_CENTER, TRIG_RIGHT };
const int echo_pin[3] = { ECHO_LEFT, ECHO_CENTER, ECHO_RIGHT };

const int air_bomb_pin = 6; //12;
const int resistor_pin = 11; //13;

const int close_thres = 40; // cm is considered close

unsigned int d[3];
int max_sensor_id = 0;
int min_sensor_id = 0;

int v_left = 0;// = random(50);
int v_right = 0;// = random(50);
int state;

void setup() {
  Wire.begin(8);                // join i2c bus with address #8 //  A4 - SDA  A5 - SCL
  Wire.onReceive(receiveEvent); // register event
  Serial.begin( 9600 );
  Serial.println( "setup" );

 // strip.begin();
 // strip.show(); // Initialize all pixels to 'off'
  for(int i = 0; i < NUM_GOTAS; i++) {
    int t = random( 40, 300 );
  //  g[i].begin( strip, 0, t );
  }


  pinMode( air_bomb_pin, OUTPUT );
  pinMode( resistor_pin, OUTPUT );
  pinMode(OUT1, OUTPUT); 
  pinMode(OUT2, OUTPUT); 
  pinMode(OUT3, OUTPUT); 
  pinMode(OUT4, OUTPUT); 
  state = WONDERING;

  if( robotID == 'A' ) {
    int pot = analogRead( A0 );
    v_max = map( pot, 0, 1023, 0, 100 );    
  }

//  move_motors( v_max, v_max);
  
  digitalWrite( air_bomb_pin, LOW );
  analogWrite( resistor_pin, 0 ); 
  make_fog( 2000, 120 );

//  move_motors( -v_max, -v_max ); 
//  delay(1000);
  move_motors( 0, 0 ); 
  delay(1000);
//  test_motors();
}

void loop() {
  switch( check_state() ) {
    case WONDERING :
      wondering_control();
      break;
    case REMOTE_CONTROL:
      remote_control();
      break;
  }
//  sparkling( strip.numPixels(), strip.numPixels() / 3   );
//  int pot = analogRead( A0 );
//  v_max = map( pot, 0, 1023, 0, 100 );
//  Serial.println(".");
//  delay( 100 );
}

void remote_control() {
  if( buffer[0] == robotID ) {
    parse_buffer( buffer );
    x = map(x, 0, 1023, -100, 100);
    y = map(y, 0, 1023, -100, 100);
    v_left = -x + y;
    v_right = y + x;
    move_motors( v_left, v_right ); 
    if( fog ) fog_on( 120 );
    else fog_off();
    Serial.print( "fog = " ); Serial.println( fog ); 
    Serial.print( "x = " ); Serial.println( x ); 
    Serial.print( "y = " ); Serial.println( y ); 
    
    reset();    
  }
}

void reset() {
  buffer[0] = '0';
  x = 522;
  y = 526;
  fog = 0;
}

int check_state() {
  if( buffer[0] == robotID ) state = REMOTE_CONTROL;
  else state = WONDERING;
  return state;
}

void wondering_control(){
  int d_min = 4;
  int d_max = 2;
    read_distances();
    switch( max_sensor_id ) {
      case 0:  //LEFT
        v_left += d_max;    
        v_right -= d_max;    
        break;
      case 1:  // CENTER
        v_left = V_MIN;    
        v_right = V_MIN;
        break;
      case 2:  // RIGHT
        v_left -= d_max;    
        v_right += d_max;    
        break;
    }

    if( d[min_sensor_id] < close_thres ) {
      switch( min_sensor_id ) {
        case 0:
          v_left -= d_min;    
          v_right += d_min;    
          if(d[1] < close_thres) turn_back_2(1);
          break;
        case 1:        
//          turn_back_2(random(0, 2));
          break;
        case 2:
          v_left += d_min;    
          v_right -= d_min;    
          if(d[1] < close_thres) turn_back_2(0);
          break;
      }
    }
    /*
    Serial.print( d[0] );  Serial.print( " " );
    Serial.print( d[1] );  Serial.print( " " );
    Serial.print( d[2] );  Serial.print( " " );
    Serial.print( max_sensor_id ); Serial.print( " " ); 
    Serial.print( min_sensor_id ); Serial.print( " " );
    Serial.print(v_left); Serial.print("  ");
    Serial.print(v_right); Serial.println( " " );
*/
    move_motors( v_left, v_right );
 // }
  
}
int min_distance() {
  int id = 0;
  if(d[1] < d[0]) id = 1; 
  if(d[2] < d[id]) id = 2;
   
  return id;
}

int max_distance() {
  int id = 0;
  if(d[1] > d[0]) id = 1; 
  if(d[2] > d[id]) id = 2;
  
  return id;
}


void turn_back_2(int side) {
  move_motors( -v_max, -v_max );
  make_fog( 500, 160  );  
  delay(250);
  if(side == 0) move_motors( v_max, -v_max );
  else move_motors( -v_max, v_max );
  delay(500);
}

void turn_back(int side) {
  if(side == 0) move_motors( v_max, -v_max );
  else move_motors( -v_max, v_max );
  make_fog( 1000, 180  );  
}


void fog_on( int res ) {
  digitalWrite( air_bomb_pin, HIGH );
  analogWrite( resistor_pin, res );   
}

void fog_off() {
  digitalWrite( air_bomb_pin, LOW );
  analogWrite( resistor_pin, 0 );   
}

void make_fog( int tau, int res ) {
  fog_on(res);
  delay(tau);
  fog_off();
}

void callibrate_fog_machine() {
  int pot = analogRead(A0);
  int res = map( pot, 0, 1023, 0, 255 );
  if( pot > 10 ) {
    digitalWrite( air_bomb_pin, HIGH );
    analogWrite( resistor_pin, res ); 
  }
  else digitalWrite( air_bomb_pin, LOW );  
  Serial.print( "pot = " );
  Serial.print( pot );
  Serial.print( "  res = " );
  Serial.println( res );
  
  delay( 100 );
}

void move_motors( int v_left, int v_right ) {
  int v_n_left = 0;
  int v_n_right = 0;
  v_left = constrain( v_left, -v_max, v_max );
  v_right = constrain( v_right, -v_max, v_max );
//  Serial.print(v_left);   Serial.print(" "); Serial.println(v_right);
  
  if( v_left >= 0 ) {
    v_n_left = map( v_left, 0, 100, 0, 255 );
    analogWrite( OUT1, v_n_left );
    analogWrite( OUT2, LOW );      
  } else {
    v_n_left = map( v_left, -100, 0, 255, 0 );
    analogWrite( OUT1, LOW );
    analogWrite( OUT2, v_n_left );          
  }
  
  if( v_right >= 0 ) {
    v_n_right = map( v_right, 0, 100, 0, 255 );
    analogWrite( OUT3, LOW );
    analogWrite( OUT4, v_n_right  );    
  } else {
    v_n_right = map( v_right, -100, 0, 255, 0 );
    analogWrite( OUT3, v_n_right );
    analogWrite( OUT4, LOW );        
  }
  
}


void stop() {
  digitalWrite( OUT1, LOW );
  digitalWrite( OUT2, LOW );
  digitalWrite( OUT3, LOW );
  digitalWrite( OUT4, LOW );
}

void read_distances() {
  for( int i = 0; i < 3; i ++ ) {
    d[i] = read_sonar( i );
//    delay(6);
  }
  max_sensor_id = max_distance();
  min_sensor_id = min_distance();
}

/*
  0 - LEFT sonar
  1 - CENTER
  2 - RIGHT
*/

unsigned int read_sonar(int sensor_id) {
  
  pinMode( trig_pin[sensor_id], OUTPUT );
  digitalWrite( trig_pin[sensor_id], LOW );
  delayMicroseconds(2);
  digitalWrite( trig_pin[sensor_id], HIGH );
  delayMicroseconds(5);
  digitalWrite( trig_pin[sensor_id], LOW );

  int duration = pulseIn( echo_pin[sensor_id], HIGH, 30000 ); // 30.000 is aprox 3m
  if( duration == 0 ) duration =  1000 * 29 * 2; // if sensor fails, d = 20m

  // convert the time into a distance in cm
  return duration /29 /2;
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

  if(buffer[2] == '0') fog = false;
  else fog = true;
  
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



int sparkling( int N, int M ) { /*
  uint32_t white = strip.Color( 127, 127, 127 );
  int n = random( 1, N );
  int m = random(1, M ); //     
  do {
    m = random(1, M ); //     
  } while (m == n);
  
  for (int i=0; i < strip.numPixels(); i++) {
    if( random( n ) < ( n - m) )
      strip.setPixelColor( i, 0 );    
    else
      strip.setPixelColor( i, white );  
  }
  int d = map(n, 1, strip.numPixels(), 10, 300);
  strip.show();
  delay( d );
  */
}




