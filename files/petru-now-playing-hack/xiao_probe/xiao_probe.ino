// XIAO ESP32-S3 pin-fingerprint probe, to identify an unlabeled ESP32 programming header.
//
// Wiring:  XIAO GND -> target GND (WROOM metal lid or USB-C shell)
//          XIAO D2  -> touch each header hole in turn
//
// Per cycle, the probe pin is read through the S3's internal ~45k pulldown, then
// ~45k pullup, then floating, and finally listened to as a 115200-baud UART RX.
// Expected signatures on an ESP32-WROOM-32 target:
//   GND      PD~0     PU~0
//   air/NC   PD~0     PU~3100
//   IO0/RX   PD~1600  PU~3100   (weak internal pullup)
//   EN       PD~2700  PU~3100   (10k external pullup)
//   3V3/TX   PD~3100  PU~3100   (TX also shows UART bytes, esp. on target power-cycle)

#include "driver/gpio.h"

#define PROBE      D2
#define PROBE_GPIO GPIO_NUM_3

static int read_with_pull(gpio_pull_mode_t mode) {
  gpio_set_pull_mode(PROBE_GPIO, mode);
  delay(30);
  long acc = 0;
  for (int i = 0; i < 8; i++) acc += analogReadMilliVolts(PROBE);
  return (int)(acc / 8);
}

void setup() {
  Serial.begin(115200);
  delay(300);
  Serial.println("PROBE READY");
}

void loop() {
  analogReadMilliVolts(PROBE);  // (re)attach ADC; this clears pulls
  int pd = read_with_pull(GPIO_PULLDOWN_ONLY);
  int pu = read_with_pull(GPIO_PULLUP_ONLY);
  int fl = read_with_pull(GPIO_FLOATING);

  Serial1.begin(115200, SERIAL_8N1, PROBE, -1);
  unsigned long t0 = millis();
  int n = 0;
  String txt;
  while (millis() - t0 < 350) {
    while (Serial1.available()) {
      char c = Serial1.read();
      n++;
      if (isprint((unsigned char)c) && txt.length() < 48) txt += c;
    }
  }
  Serial1.end();

  Serial.printf("PD=%4d PU=%4d FL=%4d UART=%3d %s\n", pd, pu, fl, n, txt.c_str());
}
