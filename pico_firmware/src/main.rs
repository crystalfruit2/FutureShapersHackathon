#![no_std]
#![no_main]

mod state;
mod lcd;
mod telemetry;
mod gas;
mod temp_hum;
mod wifi;

use defmt_rtt as _;
use panic_probe as _;

use embassy_executor::Spawner;

use embassy_rp::bind_interrupts;
use embassy_rp::adc::{Adc, Channel, Config as AdcConfig, InterruptHandler as AdcInterruptHandler};
use embassy_rp::gpio::{Flex, Level, Output, Pull};
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
    let gas_pin = Channel::new_pin(p.PIN_26, Pull::None);
    let water_pin = Channel::new_pin(p.PIN_27, Pull::None);
    spawner.spawn(gas::read_gas_water(adc, gas_pin, water_pin).unwrap());

    // Setup DHT11
    let dht_flex_pin = Flex::new(p.PIN_15);
    spawner.spawn(temp_hum::read_dht11(dht_flex_pin).unwrap());

    // Wifi AP + telemetry-on-request server
    wifi::init(
        spawner,
        p.PIO0,
        p.PIN_23,
        p.PIN_24,
        p.PIN_25,
        p.PIN_29,
        p.DMA_CH0,
    )
        .await;
}