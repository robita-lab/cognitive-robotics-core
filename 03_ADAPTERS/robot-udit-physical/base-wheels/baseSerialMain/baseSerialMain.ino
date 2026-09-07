/*   Hoverboard_Serial_Test
 *   Controls the speed, brake, and direction of a single hoverboard motor
 *   via commands sent through the serial port.
 *   Measures the speed of a hoverboard motor asynchronously
 *   using a custom ReadSpeed function.  Uses the SC speed pulse output of the
 *   RioRand 400W 6-60V PWM DC Brushless Electric Motor Speed Controller with Hall.
 *   Outputs the speed data to the serial port.
 *     
 *   created 2021
 *   Mad-EE  (Mad Electrical Engineer)
 *   www.mad-ee.com
 *   
 *   This example code is in the public domain.
 *   
 *   Platform:  Arduino UNO
 */

// Constants
const unsigned long SPEED_TIMEOUT = 500000;       // Time used to determine wheel is not spinning
const unsigned int UPDATE_TIME = 500;             // Time used to output serial data
const unsigned int BUFFER_SIZE = 16;              // Serial receive buffer size
const double BAUD_RATE = 115200;                  // Serial port baud rate
const double WHEEL_DIAMETER_IN = 6.5;            // Motor wheel diamater (inches)
const double WHEEL_CIRCUMFERENCE_IN = 22.25;     // Motor wheel circumference (inches)
const double WHEEL_DIAMETER_CM = 16.5;           // Motor wheel diamater (centimeters)
const double WHEEL_CIRCUMFERENCE_CM = 56.5;      // Motor wheel circumference (centimeters)

// Pin Declarations
const int PIN_DIR = 2;      // Motor direction signal
const int PIN_BRAKE = 3;    // Motor brake signal (active low)
const int PIN_PWM = 9;      // PWM motor speed control
const int PIN_SPEED = 12;   // SC Speed Pulse Output from RioRand board

// Variables used in ReadFromSerial function
String _command = "";       // Command received in Serial read command
int _data = 0;              // Data received in Serial read command

// Variables used in ReadSpeed function
double _freq;               // Frequency of the signal on the speed pin
double _rpm;                // Wheel speed in revolutions per minute
double _mph;                // Wheel speed in miles per hour
double _kph;                // Wheel speed in kilometers per hour

// This is ran only once at startup
void setup() 
{
    // Set pin directions
    pinMode(PIN_SPEED, INPUT);
    pinMode(PIN_PWM, OUTPUT);
    pinMode(PIN_BRAKE, OUTPUT);
    pinMode(PIN_DIR, OUTPUT);
    
    // Set initial pin states
    digitalWrite(PIN_BRAKE, false);
    digitalWrite(PIN_DIR, false);
    analogWrite(PIN_PWM, 0);
    
    // Initialize serial port
    Serial.begin(BAUD_RATE);
    Serial.println("---- Program Started ----");
}

// This is the main program loop that runs repeatedly
void loop() 
{
    // Read serial data and set dataReceived to true if command is ready to be processed
    bool dataReceived = ReadFromSerial();

    // Process the received command if available
    if (dataReceived == true)
        ProcessCommand(_command, _data);

    // Read the speed from input pin (sets _rpm and _mph)
    ReadSpeed();

    // Outputs the speed data to the serial port 
    WriteToSerial(); 
}

// Receives string data from the serial port
// Data should be in the format <command>,<data>
// Data should be terminated with a carriage return
// Function returns true if termination character received 
bool ReadFromSerial()
{    
    // Local variables   
    static String cmdBuffer;        // Stores the received command
    static String dataBuffer;       // Stores the received data
    static bool isCommand = true;   // Flag to store received bytes in command or data buffer
    byte recByte;                   // Byte received from the serial port
    
    // Check if any new data is available, if not exit
    if (Serial.available() == false)
      return false;
    
    // Read single byte from serial port
    recByte = Serial.read();
    
    // Check if byte is termination character (carriage return)
    if (recByte == '\r')
    {
        // Save buffers to global variables
        cmdBuffer.toUpperCase();
        _command = cmdBuffer;
        _data = dataBuffer.toInt();
      
        // Write what was received back to the serial port
        Serial.print("Received: "); 
        Serial.print(_command); 
        Serial.print(",");
        Serial.println(_data);
      
        // Clear local variables
        cmdBuffer = "";
        dataBuffer = "";
        isCommand = true;
      
        return true;
    }
    
    // Check if byte is a comma which separates the command from the data
    if ((char)recByte == ',')
    {
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

// Processes the command and data, sends result to serial port
void ProcessCommand(String command, int data)
{  
    // Process SPEED command
    if (command == "PWM")
    {
      Serial.print("Setting speed:  ");
      Serial.println(data);
      analogWrite(PIN_PWM, data);
    }
        
    // Process BRAKE command
    if (command == "BRAKE")
    {
      Serial.print("Setting brake:  ");
      Serial.println(data);
      digitalWrite(PIN_BRAKE, data);
    }

    // Process DIR command
    if (command == "DIR")
    {
      Serial.print("Setting direction:  ");
      Serial.println(data);
      digitalWrite(PIN_DIR, data);
    }
}

// Reads the speed from the input pin and calculates RPM and MPH
// Monitors the state of the input pin and measures the time (µs) between pin transitions
void ReadSpeed()
{
    static bool lastState = false;    // Saves the last state of the speed pin
    static unsigned long last_uS;     // The time (µs) when the speed pin changes
    static unsigned long timeout_uS;  // Timer used to determine the wheel is not spinning

    // Read the current state of the input pin
    bool state = digitalRead(PIN_SPEED);

    // Check if the pin has changed state
    if (state != lastState)
    {
      // Calculate how long has passed since last transition
      unsigned long current_uS = micros();
      unsigned long elapsed_uS = current_uS - last_uS;

      // Calculate the frequency of the input signal
      double period_uS = elapsed_uS * 2.0;
      _freq = (1 / period_uS) * 1E6;

      // Calculate the RPM
      _rpm = _freq / 45 * 60;

      // If RPM is excessively high then ignore it.
      if (_rpm > 5000) _rpm = 0;

      // Calculate the miles per hour (mph) based on the wheel diameter or circumference
      //_mph = (WHEEL_DIAMETER_IN * PI * _rpm * 60) / 63360;
      _mph = (WHEEL_CIRCUMFERENCE_IN * _rpm * 60) / 63360; 
  
      // Calculate the miles per hour (kph) based on the wheel diameter or circumference
      //_kph = (WHEEL_DIAMETER_CM * PI * _rpm * 60) / 1000;
      _kph = (WHEEL_CIRCUMFERENCE_CM * _rpm * 60) / 100000; 

      // Save the last state and next timeout time
      last_uS = current_uS;
      timeout_uS = last_uS + SPEED_TIMEOUT;
      lastState = state;
    }
    // If too long has passed then the wheel has probably stopped
    else if (micros() > timeout_uS)
    {
        _freq = 0;
        _rpm = 0;
        _mph = 0;
        _kph = 0;
        last_uS = micros();
    }
}

// Writes the RPM and MPH to the serial port at a set interval
void WriteToSerial()
{
    // Local variables
    static unsigned long updateTime;
    
    if (millis() > updateTime)
    {
        // Write data to the serial port
        Serial.print((String)"Freq:" + _freq + " ");
        Serial.print((String)"RPM:" + _rpm + " ");
        Serial.print((String)"MPH:" + _mph + " ");
        Serial.println((String)"KPH:" + _kph + " ");

        // Calculate next update time
        updateTime = millis() + UPDATE_TIME;
    }
}