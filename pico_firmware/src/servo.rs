//! Servo motor door driver

use embassy_rp::pwm::{Config as PwmConfig, Pwm};
use crate::state::{State, STATE};

const SERVO_CLOSED_DUTY: u16 = 3276;
const SERVO_OPEN_DUTY: u16 = 6553;

#[embassy_executor::task]
pub async fn door_controller(mut pwm: Pwm<'static>, mut config: PwmConfig) {
    // Hook into the shared state channel[cite: 5]
    let mut rx = STATE.receiver().unwrap();

    loop {
        let state = rx.get().await;

        match state {
            State::Alert(_) => {
                config.compare_a = SERVO_OPEN_DUTY;
            }
            State::Idle | State::Warning => {
                config.compare_a = SERVO_CLOSED_DUTY;
            }
        }

        // Apply the modified configuration
        pwm.set_config(&config);

        // Wait for the state to change before looping again[cite: 5]
        rx.changed().await;
    }
}