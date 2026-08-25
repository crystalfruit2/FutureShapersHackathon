#include <Arduino.h>
#include <Wire.h>
#include <LiquidCrystal_I2C.h>

// Define custom I2C pins (Works on ESP32/ESP8266/RP2040)
// Note: If using Arduino Uno/Nano, use A4 (SDA) and A5 (SCL) instead.
const int SDA_PIN = 6;
const int SCL_PIN = 7;

// Initialize the LCD address to 0x27 for a 16 chars and 2 line display
// (If 0x27 doesn't work, try 0x3F)
LiquidCrystal_I2C lcd(0x27, 16, 2);

const int alarmPin = 13;
const int sensorPin = A0;
const int ALARM_TIMEOUT = 250;

bool alarmFlag = false;
int gasLevelValue = 0;

// Function declarations
void start_alarm();
void stop_alarm();
void check_alarm();

// Start an alarm
void start_alarm() {
  alarmFlag = true;
}

// Stop the alarm
void stop_alarm() {
  alarmFlag = false;
}

// Buzz in case of alarm
void check_alarm() {
  if (alarmFlag) {
    digitalWrite(alarmPin, HIGH);
    delay(ALARM_TIMEOUT);
    digitalWrite(alarmPin, LOW);
    delay(ALARM_TIMEOUT);
  }
}

void setup() {
  // Initialize serial communication
  Serial.begin(9600); 
  pinMode(alarmPin, OUTPUT);
  
  // Initialize I2C communication with custom pins 
  // (Remove SDA_PIN and SCL_PIN arguments if using a standard Arduino Uno/Nano)
  Wire.begin(SDA_PIN, SCL_PIN);

  // Initialize the LCD and turn on the backlight
  lcd.init();
  lcd.backlight();
  
  // Print a startup test message
  lcd.setCursor(0, 0);
  lcd.print("Gas Sensor Test");
  delay(2000);
  lcd.clear();
}

void loop() {
  // Read the analog value
  gasLevelValue = analogRead(sensorPin);
  
  // Print to Serial Monitor
  Serial.print("Gas level ADC: ");
  Serial.println(gasLevelValue);

  // Display the data on the LCD
  lcd.setCursor(0, 0);
  lcd.print("Gas Level:");
  
  // Print the value on the second line
  lcd.setCursor(0, 1);
  lcd.print(gasLevelValue);
  
  // Print extra spaces to clear any leftover characters if the number drops from 1000 to 99
  lcd.print("    "); 

  // Handle the alarm
  check_alarm();
}