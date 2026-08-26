//! LCD control

use core::fmt::Write;

use embassy_rp::i2c::{I2c, Async};
use embassy_rp::peripherals::I2C0;

use embassy_time::{Delay, Timer};

use heapless::String;

use hd44780_driver::{Cursor, CursorBlink, HD44780};
use hd44780_driver::bus::I2CBus;

use crate::state::{AlertType, STATE, State};
use crate::telemetry::TELEMETRY;

/// i2c address of the display
const ADDR: u8 = 0x27;
const EMPTY_LINE: &str = "                "; // 16 spaces for clearing the line

#[derive(Clone, Copy)]
enum DisplayLine {
    Top,
    Bottom,
}

async fn clean_line(
    line: DisplayLine,
    lcd: &mut HD44780<I2CBus<I2c<'static, I2C0, Async>>>,
    delay: &mut Delay
) {
    match line {
        DisplayLine::Top => { let _ = lcd.set_cursor_pos(0, delay); },
        // Notice I changed 40 to 0x40 below! See Bonus Bug 1.
        DisplayLine::Bottom => { let _ = lcd.set_cursor_pos(0x40, delay); },
    }
    let _ = lcd.write_str(EMPTY_LINE, delay);
}

async fn write_line(
    line: DisplayLine,
    text: &str,
    lcd: &mut HD44780<I2CBus<I2c<'static, I2C0, Async>>>,
    delay: &mut Delay
) {
    clean_line(line, lcd, delay).await;
    match line {
        DisplayLine::Top => { let _ = lcd.set_cursor_pos(0, delay); },
        DisplayLine::Bottom => { let _ = lcd.set_cursor_pos(0x40, delay); },
    }
    let _ = lcd.write_str(text, delay);
}

async fn display_gas(
    lcd: &mut HD44780<I2CBus<I2c<'static, I2C0, Async>>>,
    delay: &mut Delay
) {
    write_line(DisplayLine::Top, "Gas Level:", lcd, delay).await;
    let level = {
        let t = TELEMETRY.lock().await;
        t.gas
    };

    if level.is_none() {
        write_line(DisplayLine::Bottom, "---", lcd, delay).await;
    } else {
        let mut string: String<32> = String::new();
        write!(string, "{}", level.unwrap()).unwrap();
        write_line(DisplayLine::Bottom, string.as_str(), lcd, delay).await;
    }
}

#[embassy_executor::task]
pub async fn display_task(i2c: I2c<'static, I2C0, Async>) {
    // initial setup
    let mut delay = Delay;
    let mut lcd = HD44780::new_i2c(i2c, ADDR, &mut delay).unwrap();

    // clear the previous state
    lcd.reset(&mut delay).unwrap();
    lcd.clear(&mut delay).unwrap();

    // turn off the blinking cursor
    lcd.set_cursor_blink(CursorBlink::Off, &mut delay).unwrap();
    lcd.set_cursor_visibility(Cursor::Invisible, &mut delay).unwrap();

    lcd.write_str("Welcome!", &mut delay).unwrap();
    Timer::after_secs(2).await;
    lcd.clear(&mut delay).unwrap();

    let mut rx = STATE.receiver().unwrap();
    loop {
        Timer::after_secs(2).await;
        let state = rx.get().await;
        match state {
            State::Alert(alert_type) => {
                write_line(DisplayLine::Top, "ALERT!!!", &mut lcd, &mut delay).await;
                match alert_type {
                    AlertType::Gas => {
                        write_line(DisplayLine::Bottom, "Gas level danger", &mut lcd, &mut delay).await;
                    },
                    AlertType::Temperature => {
                        write_line(DisplayLine::Bottom, "Temperature danger", &mut lcd, &mut delay).await;
                    }
                    AlertType::Humidity => {
                        write_line(DisplayLine::Bottom, "Humidity level danger", &mut lcd, &mut delay).await;
                    }
                }
                continue;
            },
            _ => {}
        }
        display_gas(&mut lcd, &mut delay).await;
    }
}