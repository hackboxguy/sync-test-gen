# COUNTER-SENSOR-DESIGN.md — Optical Binary Counter Reader

Hardware design for reading the 32-bit binary counter from a display using phototransistors and an ESP32.

## Overview

The binary counter overlay (8×4 grid) can be read optically by placing a sensor PCB against the display. In `--sensor-mode`, the counter renders as **white=1 / black=0** for maximum brightness contrast. The `--display-size` and `--sensor-pcb` options ensure the rendered grid matches the physical sensor PCB dimensions exactly.

## Use Cases

- **Glass-to-glass latency**: Compare frame number at transmitter display vs receiver display using two sensor arms on one ESP32
- **2×2 video wall sync**: Read all four quad counters simultaneously using four sensor PCBs (star wiring to single ESP32)
- **Encoder/decoder pipeline latency**: Measure frame delay through encode → network → decode chain

## Sensor PCB Specifications

### Dimensions

- **PCB size**: 100mm × 50mm
- **Active area**: 88mm × 38mm (6mm border on each side)
- **Grid**: 8 columns × 4 rows = 32 sensors
- **Horizontal pitch**: 12.57mm (center-to-center)
- **Vertical pitch**: 12.67mm (center-to-center)

### Display Compatibility (1080p)

| Display | Screen width | Bit cell size | Status |
|---------|-------------|---------------|--------|
| 12" | 266mm | ~10.8mm | OK |
| 24" | 531mm | ~10.8mm | OK |
| 32" | 709mm | ~8.0mm | OK |
| 43" | 953mm | ~6.0mm | OK |
| 55" | 1218mm | ~4.7mm | Marginal (use 4K) |

At 4K resolution on 55", bit cell size doubles to ~9.4mm — fully compatible.

### Component Selection

| Component | Part | Qty | Notes |
|-----------|------|-----|-------|
| Phototransistor | TEPT5700 | 32 | 5mm through-hole, visible light optimized, ~15μs response |
| Pull-up resistor | 10kΩ | 32 | 1/8W, 0805 or through-hole |
| Shift register | 74HC165 | 4 | Parallel-in serial-out, daisy-chained |
| Decoupling cap | 100nF | 4 | One per 74HC165 |
| FFC connector | 6-pin, 1mm pitch | 1 | Bottom edge, centered |
| ESP32 DevKit | ESP32-WROOM-32 | 1 | Shared across up to 4 sensor PCBs |

**Estimated BOM cost**: ~$20 for one ESP32 + four sensor PCBs.

## PCB Layout

### Sensor Placement (view from sensor side, facing screen)

```
    ┌──────────────────────────────────────────────────────────────────────────┐
    │                              100mm                                      │
    │  6mm                                                              6mm   │
    │  ├──┤                                                             ├──┤  │
    │                                                                         │
    │     ┌───┐    ┌───┐    ┌───┐    ┌───┐    ┌───┐    ┌───┐    ┌───┐    ┌───┐│
    │     │ 0 │    │ 1 │    │ 2 │    │ 3 │    │ 4 │    │ 5 │    │ 6 │    │ 7 ││ Row3
    │     │MSB│    │   │    │   │    │   │    │   │    │   │    │   │    │   ││ Y=44
50  │     └───┘    └───┘    └───┘    └───┘    └───┘    └───┘    └───┘    └───┘│
mm  │      12.57mm                                                            │
    │     ┌───┐    ┌───┐    ┌───┐    ┌───┐    ┌───┐    ┌───┐    ┌───┐    ┌───┐│
    │     │ 8 │    │ 9 │    │10 │    │11 │    │12 │    │13 │    │14 │    │15 ││ Row2
    │     │   │    │   │    │   │    │   │    │   │    │   │    │   │    │   ││ Y=31.33
    │     └───┘    └───┘    └───┘    └───┘    └───┘    └───┘    └───┘    └───┘│
    │      12.67mm                                                            │
    │     ┌───┐    ┌───┐    ┌───┐    ┌───┐    ┌───┐    ┌───┐    ┌───┐    ┌───┐│
    │     │16 │    │17 │    │18 │    │19 │    │20 │    │21 │    │22 │    │23 ││ Row1
    │     │   │    │   │    │   │    │   │    │   │    │   │    │   │    │   ││ Y=18.67
    │     └───┘    └───┘    └───┘    └───┘    └───┘    └───┘    └───┘    └───┘│
    │                                                                         │
    │     ┌───┐    ┌───┐    ┌───┐    ┌───┐    ┌───┐    ┌───┐    ┌───┐    ┌───┐│
    │     │24 │    │25 │    │26 │    │27 │    │28 │    │29 │    │30 │    │31 ││ Row0
    │     │   │    │   │    │   │    │   │    │   │    │   │    │   │    │LSB││ Y=6
    │     └───┘    └───┘    └───┘    └───┘    └───┘    └───┘    └───┘    └───┘│
    │                                                                         │
    │     X=6     X=18.57  X=31.14  X=43.71  X=56.29  X=68.86  X=81.43  X=94 │
    │                                                                         │
    │                          ┌─────────┐                                    │
    │                          │FFC 6-pin│                                    │
    │                          │connector│                                    │
    └──────────────────────────┴─────────┴────────────────────────────────────┘
```

### KiCad Coordinates (mm, origin = bottom-left)

```
# Row 3 (top, MSB byte0): bits 0-7
S0:  ( 6.00, 44.00)   S1:  (18.57, 44.00)   S2:  (31.14, 44.00)   S3:  (43.71, 44.00)
S4:  (56.29, 44.00)   S5:  (68.86, 44.00)   S6:  (81.43, 44.00)   S7:  (94.00, 44.00)

# Row 2 (byte1): bits 8-15
S8:  ( 6.00, 31.33)   S9:  (18.57, 31.33)   S10: (31.14, 31.33)   S11: (43.71, 31.33)
S12: (56.29, 31.33)   S13: (68.86, 31.33)   S14: (81.43, 31.33)   S15: (94.00, 31.33)

# Row 1 (byte2): bits 16-23
S16: ( 6.00, 18.67)   S17: (18.57, 18.67)   S18: (31.14, 18.67)   S19: (43.71, 18.67)
S20: (56.29, 18.67)   S21: (68.86, 18.67)   S22: (81.43, 18.67)   S23: (94.00, 18.67)

# Row 0 (bottom, LSB byte3): bits 24-31
S24: ( 6.00,  6.00)   S25: (18.57,  6.00)   S26: (31.14,  6.00)   S27: (43.71,  6.00)
S28: (56.29,  6.00)   S29: (68.86,  6.00)   S30: (81.43,  6.00)   S31: (94.00,  6.00)
```

### Bit Numbering

Matches `generate.py` binary counter layout (big-endian, MSB top-left):

| Bit | Byte | Weight | Position |
|-----|------|--------|----------|
| 0 (MSB) | byte0.bit7 | 2^31 | Row3, Col0 |
| 7 | byte0.bit0 | 2^24 | Row3, Col7 |
| 8 | byte1.bit7 | 2^23 | Row2, Col0 |
| 15 | byte1.bit0 | 2^16 | Row2, Col7 |
| 16 | byte2.bit7 | 2^15 | Row1, Col0 |
| 23 | byte2.bit0 | 2^8 | Row1, Col7 |
| 24 | byte3.bit7 | 2^7 | Row0, Col0 |
| 31 (LSB) | byte3.bit0 | 2^0 | Row0, Col7 |

## Circuit Design

### Per-Sensor Circuit (×32)

```
    VCC (3.3V)
      │
     [10kΩ]  pull-up
      │
      ├──────── to 74HC165 input pin
      │
    ┌─┴─┐
    │ C  │  TEPT5700
    │    │  (collector)
    │ E  │  (emitter)
    └─┬──┘
      │
     GND

    Bright (white) → transistor ON → collector LOW  → bit=1
    Dark   (black) → transistor OFF → collector HIGH → bit=0
    (inverted in firmware with XOR)
```

### Shift Register Chain (back side of PCB)

```
    ┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
    │ 74HC165  │     │ 74HC165  │     │ 74HC165  │     │ 74HC165  │
    │ #1       │────>│ #2       │────>│ #3       │────>│ #4       │───> DATA
    │ bits 0-7 │ QH  │ bits 8-15│ QH  │bits 16-23│ QH  │bits 24-31│
    │ (Row3)   │     │ (Row2)   │     │ (Row1)   │     │ (Row0)   │
    └──────────┘     └──────────┘     └──────────┘     └──────────┘
                CLK and LOAD shared across all four ICs
```

### FFC Cable (6-pin, 1mm pitch, up to 1 meter)

| Pin | Signal | Notes |
|-----|--------|-------|
| 1 | GND | Shield for CLK |
| 2 | CLK | SPI clock from ESP32 |
| 3 | GND | Shield between CLK and DATA |
| 4 | DATA | Serial data (MISO) from 74HC165 chain |
| 5 | LOAD | Parallel load / latch pulse |
| 6 | VCC | 3.3V power |

Ground pins flanking CLK prevent crosstalk into DATA at SPI speeds up to 5MHz.

## ESP32 Wiring

### Single Counter (glass-to-glass latency)

```
    ESP32                    Sensor PCB
    ┌──────┐                ┌──────────┐
    │ G16  │── LOAD ───────│ FFC pin 5 │
    │ G18  │── CLK  ───────│ FFC pin 2 │
    │ G19  │── DATA ───────│ FFC pin 4 │
    │ 3.3V │── VCC  ───────│ FFC pin 6 │
    │ GND  │── GND  ───────│ FFC pin 1,3│
    └──────┘                └──────────┘
```

### 2×2 Video Wall (4 sensor PCBs, star wiring)

```
                    Sensor PCB 1 (Q1)
                   ┌──────────┐
              ┌───│ FFC       │
              │    └──────────┘
              │
              │    Sensor PCB 2 (Q2)
              │   ┌──────────┐
    ESP32     ├───│ FFC       │
    ┌──────┐  │    └──────────┘
    │ G16  │──┤ LOAD (shared)
    │ G18  │──┤ CLK  (shared)
    │ G5   │──┤ CS1          Sensor PCB 3 (Q3)
    │ G17  │──┤ CS2         ┌──────────┐
    │ G4   │──┤ CS3    ┌───│ FFC       │
    │ G2   │──┤ CS4    │    └──────────┘
    │ G19  │──┤ DATA   │
    │ 3.3V │──┤ VCC    │    Sensor PCB 4 (Q4)
    │ GND  │──┘ GND    │   ┌──────────┐
    └──────┘           └───│ FFC       │
                            └──────────┘

    Read sequence: for each PCB, assert its CS, pulse LOAD, clock out 32 bits.
    Total read time for all 4: ~160μs at 1MHz SPI.
```

## ESP32 Firmware

### Reading One Sensor PCB

```cpp
#define LOAD_PIN  16
#define CLK_PIN   18
#define DATA_PIN  19

uint32_t read_counter() {
    // Latch all 32 inputs simultaneously
    digitalWrite(LOAD_PIN, LOW);
    delayMicroseconds(1);
    digitalWrite(LOAD_PIN, HIGH);

    // Clock out 32 bits (MSB first)
    uint32_t frame = 0;
    for (int i = 31; i >= 0; i--) {
        frame |= ((uint32_t)digitalRead(DATA_PIN) << i);
        digitalWrite(CLK_PIN, HIGH);
        delayMicroseconds(1);
        digitalWrite(CLK_PIN, LOW);
        delayMicroseconds(1);
    }

    // Invert: bright=LOW at collector, but we want bright=1
    return frame ^ 0xFFFFFFFF;
}
```

### Glass-to-Glass Latency Measurement

```cpp
void loop() {
    uint32_t tx_frame = read_counter_pcb(1);  // transmitter display
    uint32_t rx_frame = read_counter_pcb(2);  // receiver display

    int32_t delta = (int32_t)tx_frame - (int32_t)rx_frame;

    // At 60fps, each frame = 16.67ms
    float latency_ms = delta * (1000.0f / 60.0f);

    Serial.printf("TX=%u RX=%u delta=%d latency=%.1fms\n",
                  tx_frame, rx_frame, delta, latency_ms);

    delay(100);  // sample 10 times per second
}
```

## Software Integration

Generate test video with sensor-compatible counter:

```bash
# Single counter for latency measurement
python3 generate.py generate \
  --sensor-mode --display-size 24 --sensor-pcb 100x50 \
  --no-snow --no-sync-dots \
  --output sensor_test.mkv

# Quad counters for 2x2 video wall
python3 generate.py generate \
  --sensor-mode --display-size 55 --sensor-pcb 100x50 \
  --quad-counters \
  --output wall_test.mkv
```

## Mechanical Mounting

- Mount sensor PCB flush against display with suction cups or 3D-printed clip
- FFC cable exits from bottom edge, routes downward away from display
- For video wall: one sensor PCB per display, FFC cables routed to central ESP32
- Consider light-blocking gasket (foam tape around PCB edge) to prevent ambient light interference
