/*   Hoverboard_Speed_Sync
 *   Measures the speed of a hoverboard motor synchronously
 *   using the pulseIn function.  Uses the SC speed pulse output of the
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
const double BAUD_RATE = 115200;  // Serial port baud rate
const double WHEEL_DIAMETER_IN = 6.5;            // Motor wheel diamater (inches)
const double WHEEL_CIRCUMFERENCE_IN = 22.25;     // Motor wheel circumference (inches)
const double WHEEL_DIAMETER_CM = 16.5;           // Motor wheel diamater (centimeters)
const double WHEEL_CIRCUMFERENCE_CM = 56.5;      // Motor wheel circumference (centimeters)

// Pin declarations for UNO board
const int PIN_SPEED = 12;         // SC Speed Pulse Output from RioRand board

void setup() 
{
    // Set pin directions
    pinMode(PIN_SPEED, INPUT);

    // Initialize serial port
    Serial.begin(BAUD_RATE);
    Serial.println("---- Program Started ----");
}

void loop() 
{
    double freq = 0;
    double rpm = 0;
    double mph = 0;
    double kph = 0;
  
    // Measure the time the pulse is Hi
    // If pulseIn times out then ontime will equal 0
    unsigned long ontime = pulseIn(PIN_SPEED, HIGH);

    // Only run calculations if ontime > 0
    if (ontime > 0)
    {
        // Calculate the period of the signal
        unsigned long period = ontime * 2;
    
        // Calculate the frequency
        freq = 1000000.0 / period;
    
        // Calculate the revolutions per minute
        rpm = freq / 45 * 60; 
    
        // Calculate the miles per hour (mph) based on the wheel diameter or circumference
        //mph = (WHEEL_DIAMETER_IN * PI * rpm * 60) / 63360;
        mph = (WHEEL_CIRCUMFERENCE_IN * rpm * 60) / 63360; 
    
        // Calculate the miles per hour (kph) based on the wheel diameter or circumference
        //kph = (WHEEL_DIAMETER_CM * PI * rpm * 60) / 1000;
        kph = (WHEEL_CIRCUMFERENCE_CM * rpm * 60) / 100000; 
    }   

    // Write data to the serial port
    Serial.print((String)"Freq:" + freq + " ");
    Serial.print((String)"RPM:" + rpm + " ");
    Serial.print((String)"MPH:" + mph + " ");
    Serial.println((String)"KPH:" + kph + " ");
}