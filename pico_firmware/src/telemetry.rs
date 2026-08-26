//! Gather all telemetry

use embassy_sync::mutex::Mutex;
use embassy_sync::blocking_mutex::raw::ThreadModeRawMutex;

use defmt::info;
use embassy_time::Timer;

#[derive(Clone, Debug, defmt::Format)]
pub struct Telemetry {
    pub gas: Option<u16>,
    pub temperature: Option<f32>,
    pub humidity: Option<f32>,
    pub water_level: Option<u16>,
}

impl Telemetry {
    pub const fn new() -> Self {
        Self {
            gas: None,
            temperature: None,
            humidity: None,
            water_level: None,
        }
    }
}

/// Shared telemetry mutex
pub static TELEMETRY: Mutex<ThreadModeRawMutex, Telemetry> = Mutex::new(Telemetry::new());

#[embassy_executor::task]
pub async fn gather() {
    loop {
        // Needed to drop the lock
        let t = {
            let t = TELEMETRY.lock().await;
            t.clone()
        };
        info!("Telemetry gathered: {}", t);
        Timer::after_secs(1).await;
    }
}
