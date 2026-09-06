// XIAO ESP32-S3 -> UART passthrough bridge, for flashing a target ESP32-WROOM-32
// (the "Now Playing Control V1.1" board) that has no USB-UART bridge of its own.
//
// Wiring (XIAO -> target):
//   D6 (TX)  -> target RX   (WROOM RXD0 / GPIO3)
//   D7 (RX)  -> target TX   (WROOM TXD0 / GPIO1)
//   D0       -> target EN
//   D1       -> target IO0
//   GND      -> target GND
// Target is powered by its own USB-C. Do NOT connect 3V3/5V between the boards.
//
// On boot the bridge holds IO0 low and pulses EN, leaving the target parked in
// its ROM download mode (it waits forever for esptool). Then it forwards bytes
// USB <-> UART at a fixed BAUD. Use esptool with:
//   --baud 115200 --before no-reset --after no-reset
// (fixed baud, because the S3's native USB CDC can't report host baud changes,
//  and DTR/RTS must stay untouched or the S3 resets *itself*).
//
// To re-arm download mode: unplug and replug the XIAO.

#define PIN_TX  D6
#define PIN_RX  D7
#define PIN_EN  D0
#define PIN_IO0 D1
#define BAUD    115200

// EN / IO0 are driven open-drain style: LOW = pull down, released = hi-Z so the
// target's own pull-ups take over. Never drive them HIGH.
static void pull_low(int pin) { pinMode(pin, OUTPUT); digitalWrite(pin, LOW); }
static void release(int pin)  { pinMode(pin, INPUT); }

static void target_enter_download() {
  pull_low(PIN_IO0);
  delay(10);
  pull_low(PIN_EN);
  delay(100);
  release(PIN_EN);     // ROM samples IO0 as it comes out of reset
  delay(100);
  release(PIN_IO0);
}

void setup() {
  release(PIN_EN);
  release(PIN_IO0);
  // USB delivers esptool's ~6 KB stub/flash blocks in a millisecond; the UART
  // drains them at 115200. Buffer deep enough that nothing is dropped meanwhile.
  Serial.setRxBufferSize(65536);
  Serial.begin(BAUD);                                // USB CDC to host
  Serial1.setRxBufferSize(8192);
  Serial1.setTxBufferSize(32768);
  Serial1.begin(BAUD, SERIAL_8N1, PIN_RX, PIN_TX);   // UART to target
  target_enter_download();
}

void loop() {
  uint8_t buf[256];
  int n;
  while ((n = Serial.available()) > 0) {
    n = Serial.readBytes(buf, min(n, (int)sizeof buf));
    Serial1.write(buf, n);
  }
  while ((n = Serial1.available()) > 0) {
    n = Serial1.readBytes(buf, min(n, (int)sizeof buf));
    Serial.write(buf, n);
  }
}
