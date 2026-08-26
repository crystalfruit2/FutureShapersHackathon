use embassy_dht_sensor::DHTSensor;
use embassy_rp::gpio::Flex;
use embassy_time::{Duration, Timer};
use crate::telemetry::TELEMETRY;
use crate::state::{State, STATE, AlertType};

const HUMIDITY_ALERT_THRESHOLD: u8 = 40;
const TEMPERATURE_ALERT_THRESHOLD: u8 = 32;


#[embassy_executor::task]
pub async fn read_dht11(flex_pin: Flex<'static>) {
    // We receive the Flex pin already initialized and ready to go!
    let mut dht = DHTSensor::new(flex_pin);

    let tx = STATE.sender();

    loop {
        Timer::after(Duration::from_secs(2)).await;

        match dht.read() {
            Ok(reading) => {
                let mut t = TELEMETRY.lock().await;
                t.temperature = Some(reading.temperature);
                t.humidity = Some(reading.humidity);

                if reading.temperature > TEMPERATURE_ALERT_THRESHOLD as f32 {
                    tx.send(State::Alert(AlertType::Temperature));
                }
                if reading.humidity > HUMIDITY_ALERT_THRESHOLD as f32 {
                    tx.send(State::Alert(AlertType::Humidity));
                }
            }
            Err(_) => {
                // Ignore read errors
            }
        }
    }
}