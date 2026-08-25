#![no_std]
#![no_main]

mod state;
mod lcd;
mod telemetry;
mod gas;

use defmt_rtt as _;
use panic_probe as _;

use embassy_executor::Spawner;

use embassy_rp::bind_interrupts;
use embassy_rp::adc::{Adc, Channel, Config as AdcConfig, InterruptHandler as AdcInterruptHandler};
use embassy_rp::gpio::{Level, Output, Pull};
use embassy_rp::i2c::{Config as I2cConfig, I2c, InterruptHandler as I2cInterruptHandler};
use embassy_rp::peripherals;

use defmt::info;

bind_interrupts!(struct Irqs {
    ADC_IRQ_FIFO => AdcInterruptHandler;
    I2C0_IRQ => I2cInterruptHandler<peripherals::I2C0>;
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
    let i2c = I2c::new_async(p.I2C0, scl, sda, Irqs, I2cConfig::default());
    spawner.spawn(lcd::display_task(i2c).unwrap());

    // Setup telemetry broker
    spawner.spawn(telemetry::gather().unwrap());

    // Setup gas sensor
    let adc = Adc::new(p.ADC, Irqs, AdcConfig::default());
    let adc_pin = Channel::new_pin(p.PIN_26, Pull::Down);
    spawner.spawn(gas::read_gas(adc, adc_pin).unwrap());
}
