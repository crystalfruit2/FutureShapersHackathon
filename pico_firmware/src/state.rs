//! State control

use embassy_futures::select::{Either, select};

use embassy_rp::gpio::Output;

use embassy_sync::blocking_mutex::raw::CriticalSectionRawMutex;
use embassy_sync::watch::Watch;

use embassy_time::Timer;

const BUZZER_TIMEOUT_MS: u64 = 250;

pub enum AlertType {
    Gas,
    Temperature,
}

#[derive(Clone)]
pub enum State {
    /// Default state
    Idle,

    /// Mid-level
    Warning,

    /// Son...
    Alert,
}

/// Current state
pub static STATE: Watch<CriticalSectionRawMutex, State, 1> = Watch::new();

#[embassy_executor::task]
pub async fn buzzer_alert(mut pin: Output<'static>) {
    let mut rx = STATE.receiver().unwrap();
    let tx = STATE.sender();

    tx.send(State::Idle);

    let mut state = rx.get().await;

    loop {
        match state {
            State::Idle => {

            },
            State::Warning => {

            }
            State::Alert => {
                let buzzer_future = async {
                    pin.set_high();
                    Timer::after_millis(BUZZER_TIMEOUT_MS).await;
                    pin.set_low();
                    Timer::after_millis(BUZZER_TIMEOUT_MS).await;
                };
                match select(buzzer_future, rx.changed()).await {
                    Either::First(_) => unreachable!(),
                    Either::Second(new) => {
                        state = new;
                        continue;
                    }
                }
            }
        }

        state = rx.changed().await;
    }
}