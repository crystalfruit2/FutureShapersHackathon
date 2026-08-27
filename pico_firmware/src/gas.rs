//! Gas sensor

use embassy_rp::adc::{Adc, Async, Channel};

use embassy_time::Timer;

use crate::telemetry::TELEMETRY;
use crate::state::{STATE, State, AlertType};

const GAS_ALERT_THRESHOLD: u16 = 3000;
const WATER_ALERT_THRESHOLD: u16 = 10;

#[embassy_executor::task]
pub async fn read_gas_water(
    mut adc: Adc<'static, Async>,
    mut gas_pin: Channel<'static>,
    mut water_pin: Channel<'static>,
    mut sound_pin: Channel<'static>,
) {
    let tx = STATE.sender();

    loop {
        // 1. Read both analog values sequentially
        let gas_level = adc.read(&mut gas_pin).await.unwrap();
        let water_level = adc.read(&mut water_pin).await.unwrap();
        let sound_level = adc.read(&mut sound_pin).await.unwrap();

        // 2. Update telemetry state together
        {
            let mut t = TELEMETRY.lock().await;
            t.gas = Some(gas_level);
            t.water_level = Some(water_level);
            t.sound_level = Some(sound_level);
        }

        // 3. Trigger alerts if thresholds are exceeded
        if gas_level > GAS_ALERT_THRESHOLD {
            tx.send(State::Alert(AlertType::Gas));
        }
        else {
            tx.send(State::Idle);
        }

        if water_level < WATER_ALERT_THRESHOLD {
            tx.send(State::Alert(AlertType::WaterLevel));
        }
        else {
            tx.send(State::Idle);
        }

        // 4. Delay until next reading
        Timer::after_millis(500).await;
    }
}