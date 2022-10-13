#!/usr/bin/env python3

from smbus import SMBus

DEVICE_ADDRESS = 0x2F


def main():
    bus = SMBus(1)
    bus.write_byte_data(DEVICE_ADDRESS, 0x01, 0x11)  # reset chip
    bus.write_byte_data(DEVICE_ADDRESS, 0x78, 0x80)  # clear fault - works
    bus.write_byte_data(DEVICE_ADDRESS, 0x01, 0x00)  # remove reset
    bus.write_byte_data(DEVICE_ADDRESS, 0x78, 0x00)  # remove clear fault

    bus.write_byte_data(DEVICE_ADDRESS, 0x33, 0x03)  # 32-bit
    bus.write_byte_data(DEVICE_ADDRESS, 0x4C, 121)  # set volume
    bus.write_byte_data(
        DEVICE_ADDRESS, 0x30, 0x00
    )  # SDOUT is the DSP input (post-processing)
    bus.write_byte_data(DEVICE_ADDRESS, 0x03, 0x00)  # Deep Sleep

    bus.write_byte_data(DEVICE_ADDRESS, 0x03, 0x02)  # HiZ

    bus.write_byte_data(
        DEVICE_ADDRESS, 0x5C, 0x01
    )  # Indicate the first coefficient of a BQ is starting to write

    bus.write_byte_data(DEVICE_ADDRESS, 0x03, 0x03)  # Play


if __name__ == "__main__":
    main()
