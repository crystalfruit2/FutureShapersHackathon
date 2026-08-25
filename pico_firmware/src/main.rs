#![no_std]
#![no_main]

mod state;
mod lcd;

use defmt_rtt as _;
use panic_probe as _;

use embassy_executor::Spawner;

use embassy_rp::bind_interrupts;
use embassy_rp::gpio::{Level, Output};
use embassy_rp::i2c::{Config, I2c, InterruptHandler};
use embassy_rp::peripherals;

use defmt::info;

bind_interrupts!(struct Irqs {
    I2C0_IRQ => InterruptHandler<peripherals::I2C0>;
});

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

    // LCD setup
    let sda = p.PIN_16;
    let scl = p.PIN_17;
    let i2c = I2c::new_async(p.I2C0, scl, sda, Irqs, Config::default());
    spawner.spawn(lcd::display_task(i2c).unwrap());
}
