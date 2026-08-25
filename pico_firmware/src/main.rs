#![no_std]
#![no_main]

mod state;

use defmt_rtt as _;
use panic_probe as _;

use embassy_executor::Spawner;
use embassy_rp::gpio::{Level, Output};

use defmt::info;

#[embassy_executor::main]
async fn main(spawner: Spawner) {
    let p = embassy_rp::init(Default::default());
    info!("Hello world!");

    // Buzzer alert setup
    let buzzer = Output::new(p.PIN_2, Level::Low);
    spawner.spawn(state::buzzer_alert(buzzer).unwrap());

    // Status LED setup
    let red = Output::new(p.PIN_3, Level::Low);
    let green = Output::new(p.PIN_4, Level::Low);
    let blue = Output::new(p.PIN_5, Level::Low);
    spawner.spawn(state::rgb_status(red, green, blue).unwrap());
}
