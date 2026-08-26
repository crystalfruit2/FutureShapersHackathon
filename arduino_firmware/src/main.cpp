#include <Arduino.h>
#include <Wire.h>
#include <LiquidCrystal_I2C.h>
#include <IRremote.hpp>

LiquidCrystal_I2C lcd(0x27, 16, 2);

const int alarmPin = 13;
const int sensorPin = A0; 
const int IRPin = 2;      
const int ALARM_TIMEOUT = 250;

bool alarmFlag = false;
bool lastAlarmState = false; // Used to prevent LCD flickering
int gasLevelValue = 0;
const int GAS_ALERT_THRESHOLD = 600;

// Variables for non-blocking alarm (replaces delay)
unsigned long previousAlarmMillis = 0;
bool alarmLedState = false;

// Variables for non-blocking LCD updates
unsigned long previousLcdMillis = 0;
const int LCD_UPDATE_INTERVAL = 500; // Update LCD twice a second

// Function declarations
void start_alarm();
void stop_alarm();
void check_alarm();
void check_gas();
void lcd_task();
void check_ir();

void start_alarm() {
  alarmFlag = true;
}

void stop_alarm() {
  alarmFlag = false;
  digitalWrite(alarmPin, LOW);
  alarmLedState = false;
}

// Non-blocking alarm using millis() instead of delay()
void check_alarm() {
  if (alarmFlag) {
    unsigned long currentMillis = millis();
    if (currentMillis - previousAlarmMillis >= ALARM_TIMEOUT) {
      previousAlarmMillis = currentMillis;
      // Toggle the alarm pin state
      alarmLedState = !alarmLedState;
      digitalWrite(alarmPin, alarmLedState ? HIGH : LOW);
    }
  }
}

void check_gas() {
  if (gasLevelValue >= GAS_ALERT_THRESHOLD) {
    start_alarm();
  } else {
    stop_alarm();
  }
}

void lcd_task() {
  // If the alarm state just changed, clear the screen once
  if (alarmFlag != lastAlarmState) {
    lcd.clear();
    lastAlarmState = alarmFlag;
  }

  // Update LCD every 500ms to avoid freezing the Arduino
  unsigned long currentMillis = millis();
  if (currentMillis - previousLcdMillis >= LCD_UPDATE_INTERVAL) {
    previousLcdMillis = currentMillis;

    if (!alarmFlag) {
      lcd.setCursor(0, 0);
      lcd.print("Gas Level:      ");
      lcd.setCursor(0, 1);
      lcd.print(gasLevelValue);
      lcd.print("    "); 
    } else {
      lcd.setCursor(0, 0);
      lcd.print("ALERT!!!        ");
      lcd.setCursor(0, 1);
      lcd.print("Gas level HIGH  ");
    }
  }
}

void check_ir() {
  if (IrReceiver.decode()) {
    // Grab the raw 32-bit data instead of the standard command
    uint32_t rawValue = IrReceiver.decodedIRData.decodedRawData;
    
    // Ignore 0x0 values (which happen if you hold the button down too long)
    if (rawValue != 0) {
      Serial.print("Raw Hex for this button: 0x");
      Serial.println(rawValue, HEX);

      // --- HOW TO USE THIS ---
      // 1. Press a button on your remote.
      // 2. Look at the Serial Monitor to find its Raw Hex (e.g., 0xFFA25D).
      // 3. Paste that hex code into an if-statement like the one below:

      
      if (rawValue == 0x5B1EDECC) {
        Serial.println("You pressed Button 1!");
        // Add your logic here
      } 
      else if (rawValue == ) { // Replace with another button's code
        Serial.println("You pressed Button 2!");
      }
    }

    IrReceiver.resume(); // Receive the next value
  }
}

void setup() {
  Serial.begin(9600); 
  pinMode(alarmPin, OUTPUT);
  Wire.begin();

  lcd.init();
  lcd.backlight();
  
  IrReceiver.begin(IRPin, ENABLE_LED_FEEDBACK); 

  lcd.setCursor(0, 0);
  lcd.print("Team 2 presents");
  delay(2000);
  lcd.clear();
}

void loop() {
  gasLevelValue = analogRead(sensorPin);

  check_ir();
  check_gas();
  check_alarm();
  lcd_task();
}

/*
TODO:
remote accessible interface

*/