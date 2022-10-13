#!/usr/bin/env python3
import argparse
import subprocess
import time
from pathlib import Path

import RPi.GPIO as GPIO
import spidev

PIN_BOOT_SEL = 26
PIN_RST_N = 27

BUS_SPI = 0
DEVICE_SPI = 0
SPI_BLOCK_SIZE = 4096
MAX_SPI_SPEED_MHZ = 5
BLOCK_TRANSFER_PAUSE_MS = 1


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "firmware", help="Path to .bin file with XMOS XVF3510-INT firmware"
    )
    args = parser.parse_args()

    GPIO.setwarnings(False)
    GPIO.setmode(GPIO.BCM)

    # Set XMOS chip into programming mode
    GPIO.setup(16, GPIO.OUT)
    GPIO.setup(PIN_RST_N, GPIO.OUT)
    GPIO.output(16, 1)
    GPIO.output(PIN_RST_N, 1)
    time.sleep(1)

    # Setup SPI
    spi = spidev.SpiDev()
    spi.open(BUS_SPI, DEVICE_SPI)
    spi.max_speed_hz = int(MAX_SPI_SPEED_MHZ * 1000000)
    spi.mode = 0b00  # XMOS supports 00 or 11

    # Direct firmware upload
    GPIO.setup(PIN_BOOT_SEL, GPIO.IN)
    GPIO.setup(PIN_RST_N, GPIO.OUT, initial=GPIO.HIGH)

    GPIO.output(PIN_RST_N, 0)
    GPIO.setup(PIN_BOOT_SEL, GPIO.OUT, initial=GPIO.HIGH)
    GPIO.output(PIN_RST_N, 1)

    bin_filename = args.firmware

    # Create a table to map byte values to their bit-reversed values
    reverse_table = [bit_reversed_byte(byte) for byte in range(256)]

    data = []
    with open(bin_filename, "rb") as f:
        bytes_read = f.read()
        data = list(bytes_read)
        binary_size = len(data)
        block_count = 0
        print('Read file "{0}" size: {1} Bytes'.format(bin_filename, binary_size))
        if (binary_size % SPI_BLOCK_SIZE) != 0:
            print(
                "Warning - binary file not a multiple of {} - {} remainder".format(
                    SPI_BLOCK_SIZE, binary_size % SPI_BLOCK_SIZE
                )
            )
        while binary_size > 0:
            block = [reverse_table[byte] for byte in data[:SPI_BLOCK_SIZE]]
            del data[:SPI_BLOCK_SIZE]
            binary_size = len(data)
            spi.xfer(block)

            if block_count == 0:
                # Long delay for PLL reboot
                time.sleep(0.1)
            elif binary_size > 0:
                time.sleep(BLOCK_TRANSFER_PAUSE_MS / 1000)
            block_count += 1
    print("Sending complete")

    GPIO.setup(PIN_BOOT_SEL, GPIO.IN)
    GPIO.setup(PIN_RST_N, GPIO.OUT, initial=GPIO.HIGH)

    print("DONE")


def bit_reversed_byte(byte_to_reverse):
    """
    Function to reverse the bit-order of a byte

    Args:
        byte_to_reverse: byte to process

    Retruns:
        byte in reversed order
    """
    return int("{:08b}".format(byte_to_reverse)[::-1], 2)


if __name__ == "__main__":
    main()
