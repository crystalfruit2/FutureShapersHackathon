#![no_std]
#![no_main]

use defmt_rtt as _;
use panic_probe as _;

use embassy_executor::Spawner;

use defmt::info;
use embassy_time::Timer;

#[embassy_executor::main]
async fn main(_spawner: Spawner) {
    let _p = embassy_rp::init(Default::default());
    info!("Hello world!");

    loop {
        Timer::after_millis(500).await;
        info!("Loop!");
    }
}
