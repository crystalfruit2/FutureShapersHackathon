#include <Arduino.h>
#include <Wire.h>
#include <LiquidCrystal_I2C.h>

// Standard Arduino I2C pins (Uno/Nano):
// Connect LCD SDA to A4
// Connect LCD SCL to A5

// Initialize the LCD address to 0x27 for a 16 chars and 2 line display
LiquidCrystal_I2C lcd(0x27, 16, 2);

const int alarmPin = 13;
const int sensorPin = A0; // Pin for the ADC reading
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
  Serial.begin(9600); 
  pinMode(alarmPin, OUTPUT);
  
  // Initialize standard Hardware I2C (uses A4 and A5 automatically)
  Wire.begin();

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
  lcd.print("    "); // Clear leftover characters

  // Handle the alarm
  check_alarm();
}