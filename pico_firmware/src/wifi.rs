//! WiFi access point + telemetry-on-request server.

use core::fmt::Write as _;
use embedded_io_async::Write; // Required for socket.write_all()

use cyw43_pio::{PioSpi, DEFAULT_CLOCK_DIVIDER};

use embassy_executor::Spawner;

use embassy_net::tcp::TcpSocket;
use embassy_net::{Ipv4Address, Ipv4Cidr, Stack, StackResources};

use embassy_rp::bind_interrupts;
use embassy_rp::dma;
use embassy_rp::gpio::{Level, Output};
use embassy_rp::peripherals::{DMA_CH0, PIN_23, PIN_24, PIN_25, PIN_29, PIO0};
use embassy_rp::pio::{InterruptHandler as PioInterruptHandler, Pio};
use embassy_rp::Peri; // Using Peri explicitly matching the reference project

use embassy_time::Duration;

use heapless::String;

use static_cell::StaticCell;

use crate::telemetry::{Telemetry, TELEMETRY};

// Added DMA interrupt handler for PioSpi
bind_interrupts!(struct Irqs {
    PIO0_IRQ_0 => PioInterruptHandler<PIO0>;
    DMA_IRQ_0 => dma::InterruptHandler<DMA_CH0>;
});

const WIFI_AP_SSID: &str = "BioGuard";
const WIFI_AP_PASSWORD: &str = "claude_plan";
const WIFI_AP_CHANNEL: u8 = 5;

const AP_IP: Ipv4Address = Ipv4Address::new(192, 168, 4, 1);
const AP_PREFIX_LEN: u8 = 24;
const TELEMETRY_PORT: u16 = 80;

// Notice: DMA_CH0 is removed from the generic parameters here!
#[embassy_executor::task]
async fn cyw43_task(
    runner: cyw43::Runner<'static, cyw43::SpiBus<Output<'static>, PioSpi<'static, PIO0, 0>>>,
) -> ! {
    runner.run().await
}

#[embassy_executor::task]
async fn net_task(mut runner: embassy_net::Runner<'static, cyw43::NetDriver<'static>>) -> ! {
    runner.run().await
}

fn telemetry_json(t: &Telemetry) -> String<192> {
    let mut body: String<192> = String::new();

    let _ = body.push_str("{\"gas\":");
    match t.gas {
        Some(v) => {
            let _ = write!(body, "{}", v);
        }
        None => {
            let _ = body.push_str("null");
        }
    }

    let _ = body.push_str(",\"temperature\":");
    match t.temperature {
        Some(v) => {
            let _ = write!(body, "{}", v);
        }
        None => {
            let _ = body.push_str("null");
        }
    }

    let _ = body.push_str(",\"humidity\":");
    match t.humidity {
        Some(v) => {
            let _ = write!(body, "{}", v);
        }
        None => {
            let _ = body.push_str("null");
        }
    }

    let _ = body.push_str(",\"water_level\":");
    match t.water_level {
        Some(v) => {
            let _ = write!(body, "{}", v);
        }
        None => {
            let _ = body.push_str("null");
        }
    }
    let _ = body.push_str(",\"sound_level\":");
    match t.sound_level {
        Some(v) => {
            let _ = write!(body, "{}", v);
        }
        None => {
            let _ = body.push_str("null");
        }
    }

    let _ = body.push_str("}");
    body
}

#[embassy_executor::task]
async fn telemetry_server_task(stack: Stack<'static>) {
    let mut rx_buffer = [0u8; 1024];
    let mut tx_buffer = [0u8; 1024];
    let mut request_buffer = [0u8; 512];

    loop {
        let mut socket = TcpSocket::new(stack, &mut rx_buffer, &mut tx_buffer);
        socket.set_timeout(Some(Duration::from_secs(10)));

        if socket.accept(TELEMETRY_PORT).await.is_err() {
            continue;
        }

        let _ = socket.read(&mut request_buffer).await;

        let t = { TELEMETRY.lock().await.clone() };
        let body = telemetry_json(&t);

        let mut response: String<512> = String::new();
        let _ = write!(
            response,
            "HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{}",
            body.len(),
            body.as_str(),
        );

        // write_all is now available because embedded_io_async::Write is in scope
        let _ = socket.write_all(response.as_bytes()).await;
        let _ = socket.flush().await;
        socket.close();
    }
}

// Function signature explicitly expects `Peri` matching the reference project
pub async fn init(
    spawner: Spawner,
    pio0: Peri<'static, PIO0>,
    pin_23: Peri<'static, PIN_23>,
    pin_24: Peri<'static, PIN_24>,
    pin_25: Peri<'static, PIN_25>,
    pin_29: Peri<'static, PIN_29>,
    dma_ch0: Peri<'static, DMA_CH0>,
) -> Stack<'static> {
    let pwr = Output::new(pin_23, Level::Low);
    let cs = Output::new(pin_25, Level::High);

    let mut pio = Pio::new(pio0, Irqs);
    let spi = PioSpi::new(
        &mut pio.common,
        pio.sm0,
        DEFAULT_CLOCK_DIVIDER,
        pio.irq0,
        cs,
        pin_24,
        pin_29,
        dma::Channel::new(dma_ch0, Irqs),
    );

    static STATE: StaticCell<cyw43::State> = StaticCell::new();
    let state = STATE.init(cyw43::State::new());

    // NOTE: You MUST download these 3 files and place them in the 'cyw43-firmware' folder next to Cargo.toml
    let fw = cyw43::aligned_bytes!("../cyw43_firmware/43439A0.bin");
    let clm = cyw43::aligned_bytes!("../cyw43_firmware/43439A0_clm.bin");
    let nvram = cyw43::aligned_bytes!("../cyw43_firmware/nvram_rp2040.bin");

    let (net_device, mut control, runner) = cyw43::new(state, pwr, spi, fw, nvram).await;
    spawner.spawn(cyw43_task(runner).unwrap());

    control.init(clm).await;
    control
        .set_power_management(cyw43::PowerManagementMode::PowerSave)
        .await;

    let config = embassy_net::Config::ipv4_static(embassy_net::StaticConfigV4 {
        address: Ipv4Cidr::new(AP_IP, AP_PREFIX_LEN),
        gateway: Some(AP_IP),
        dns_servers: Default::default(),
    });

    static RESOURCES: StaticCell<StackResources<4>> = StaticCell::new();
    let resources = RESOURCES.init(StackResources::new());
    let seed: u64 = 0x0123_4567_89AB_CDEF;

    let (stack, runner) = embassy_net::new(net_device, config, resources, seed);
    spawner.spawn(net_task(runner).unwrap());

    control
        .start_ap_wpa2(WIFI_AP_SSID, WIFI_AP_PASSWORD, WIFI_AP_CHANNEL)
        .await;

    spawner.spawn(telemetry_server_task(stack).unwrap());

    stack
}