//! Gas sensor

use embassy_rp::adc::{Adc, Async, Channel};

use embassy_time::Timer;

use crate::telemetry::TELEMETRY;
use crate::state::{STATE, State, AlertType};

const GAS_ALERT_THRESHOLD: u16 = 3000;

#[embassy_executor::task]
pub async fn read_gas(
    mut adc: Adc<'static, Async>,
    mut pin: Channel<'static>
) {
    let tx = STATE.sender();
    loop {
        let level = adc.read(&mut pin).await.unwrap();
        {
            let mut t = TELEMETRY.lock().await;
            t.gas = Some(level);
        }
        if level > GAS_ALERT_THRESHOLD {
            tx.send(State::Alert(AlertType::Gas));
        }
        Timer::after_millis(500).await;
    }
}