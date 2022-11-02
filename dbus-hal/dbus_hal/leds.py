# Copyright 2022 Mycroft AI Inc.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# -----------------------------------------------------------------------------
import logging
import subprocess
import itertools
import re
import time
from typing import List, Optional, Tuple
from threading import Thread

import board
import neopixel
import RPi.GPIO as GPIO

from .led_animation import color
from .led_animation.animation import Animation
from .led_animation.animation.comet import Comet
from .led_animation.animation.pulse import Pulse
from .led_animation.animation.solid import Solid

_LOGGER = logging.getLogger("leds")


class MycroftColor:
    RED = (236, 100, 75)  # EC644B
    OLD_RED = (235, 87, 87)  # EB5757
    GREEN = (64, 219, 176)  # 40DBB0
    BLUE = (34, 167, 240)  # 22A7F0


class Mark2Leds:
    # I2C-based LED control
    BUS_ID = 1
    DEVICE_ADDRESS = 0x04
    FIRST_LED = 0
    MAX_LEDS_PER_WRITE = 10

    MAX_COLOR = 255
    MIN_COLOR = 0
    NUM_COLORS = 3

    NUM_LEDS = 12

    def __init__(self):
        self._rgb: List[int] = [self.MIN_COLOR] * self.NUM_COLORS * self.NUM_LEDS
        self._rgb_str = ",".join(str(v) for v in self._rgb)
        self._is_i2c_leds = self._detect_i2c_leds()
        self._brightness: float = 0.5
        self._last_pixels: Optional[List[Tuple[int, int, int]]] = None
        self._pixels: List[Tuple[int, int, int]] = [color.BLACK] * self.NUM_LEDS

        if self._is_i2c_leds:
            _LOGGER.info("I2C LEDs detected")
        else:
            _LOGGER.info("GPIO LEDs detected")

            # Use Adafruit library (requires root)
            self._pixels = neopixel.NeoPixel(
                board.D12,
                self.NUM_LEDS,
                brightness=self._brightness,
                auto_write=False,
                pixel_order=neopixel.GRB,
            )
            self._set_rgb_gpio()

        self._animation: Optional[Animation] = None
        self._is_running = True
        Thread(target=self._animate, daemon=True).start()

    def stop(self):
        """Set LEDs to black"""
        self.rgb = [0, 0, 0]

    @property
    def brightness_int(self) -> int:
        """Get brightness value in [0, 100]"""
        return int(100 * max(0.0, min(1.0, self._brightness)))

    @property
    def brightness(self) -> int:
        """Get brightness value in [0, 100]"""
        return int(100 * max(0.0, min(1.0, self._brightness)))

    @brightness.setter
    def brightness(self, val: int):
        """Get brightness in [0, 100]"""
        _LOGGER.debug("brightness: %s", val)
        self._brightness = val / 100
        self._set_rgb()

    @property
    def rgb(self) -> List[int]:
        return self._rgb

    @rgb.setter
    def rgb(self, val: List[int]):
        if self._rgb == val:
            return

        _LOGGER.debug("rgb: %s", val)
        rgb = [max(self.MIN_COLOR, min(self.MAX_COLOR, int(c))) for c in val]

        # Default to black if no data
        rgb = rgb or [self.MIN_COLOR]

        # Ensure a full triplet
        while (len(rgb) % self.NUM_COLORS) != 0:
            rgb.append(self.MIN_COLOR)

        # Repeat color for all leds, if necessary
        self._rgb = list(
            itertools.islice(
                itertools.cycle(rgb),
                0,
                self.NUM_LEDS * self.NUM_COLORS,
            )
        )
        self._set_rgb()

    # Pixel object
    def __len__(self):
        return self.NUM_LEDS

    def __setitem__(self, index, value):
        self._pixels[index] = value

    def __getitem__(self, index):
        return self._pixels[index]

    def __iter__(self):
        return iter(self._pixels)

    def show(self):
        """Sets the LED colors using the pixels"""
        try:
            if self._last_pixels == self._pixels:
                return

            self._last_pixels = list(self._pixels)
            self.rgb = [
                max(self.MIN_COLOR, min(self.MAX_COLOR, c))
                for c in itertools.chain.from_iterable(self._pixels)
            ]
        except Exception:
            _LOGGER.exception("Error setting LEDs")

    def fill(self, fill_color):
        """Fill all leds with the same color"""
        self._pixels = [fill_color] * self.NUM_LEDS

    def _set_rgb(self):
        """Show colors"""
        if self._is_i2c_leds:
            self._set_rgb_i2c()
        else:
            self._set_rgb_gpio()

    def _set_rgb_i2c(self):
        """Show colors using I2C"""
        rgb = [int(c * self._brightness) for c in self._rgb]

        # Write in blocks to avoid overloading i2cset
        last_value = self.MAX_LEDS_PER_WRITE * self.NUM_COLORS
        write_offset = 0
        while rgb:
            set_command = [
                "i2cset",
                "-y",  # disable interactive mode
                "-a",  # allow access to LED device range
                str(self.BUS_ID),
                f"0x{self.DEVICE_ADDRESS:02x}",
                f"0x{self.FIRST_LED + write_offset:02x}",
                *(str(value) for value in rgb[:last_value]),
                "i",  # block data
            ]

            _LOGGER.debug(set_command)
            subprocess.check_call(set_command)

            # Next block
            rgb = rgb[last_value:]
            write_offset += self.MAX_LEDS_PER_WRITE

    def _set_rgb_gpio(self):
        """Show colors using GPIO neopixel"""
        assert self._pixels is not None, "neopixel was not initialized"

        rgb = [int(c * self._brightness) for c in self._rgb]
        colors = grouper(rgb, n=3, incomplete="fill", fillvalue=0)
        for i, color in enumerate(colors):
            self._pixels[i] = color

        self._pixels.show()

    def _detect_i2c_leds(self) -> bool:
        """Returns True if I2C led device is detected"""
        detect_command = [
            "i2cdetect",
            "-a",
            "-y",
            "1",
            str(self.DEVICE_ADDRESS),
            str(self.DEVICE_ADDRESS),
        ]
        _LOGGER.debug(detect_command)

        try:
            detect_text = subprocess.check_output(detect_command).decode()
            for line in detect_text.splitlines():
                if re.match(r"^00:\s+04\s*$", line):
                    return True
        except Exception:
            _LOGGER.exception("Error while detecting I2C leds")

        return False

    def set_animation(self, name: str):
        if name == "awake":
            self._animation = Pulse(
                self, speed=0.05, color=MycroftColor.GREEN, period=2
            )
        elif name == "thinking":
            self._animation = Comet(
                self, speed=0.1, color=MycroftColor.BLUE, ring=True, tail_length=10
            )

    def clear_animation(self):
        self._animation = None

    def _animate(self):
        """Run animation in separate thread"""
        try:
            while self._is_running:
                if self._animation is not None:
                    self._animation.animate()

                time.sleep(0.001)
        except Exception:
            _LOGGER.exception("Error in LED animation thread")


# -----------------------------------------------------------------------------

# https://docs.python.org/3/library/itertools.html
def grouper(iterable, n, *, incomplete="fill", fillvalue=None):
    "Collect data into non-overlapping fixed-length chunks or blocks"
    # grouper('ABCDEFG', 3, fillvalue='x') --> ABC DEF Gxx
    # grouper('ABCDEFG', 3, incomplete='strict') --> ABC DEF ValueError
    # grouper('ABCDEFG', 3, incomplete='ignore') --> ABC DEF
    args = [iter(iterable)] * n
    if incomplete == "fill":
        return itertools.zip_longest(*args, fillvalue=fillvalue)
    if incomplete == "strict":
        return zip(*args, strict=True)
    if incomplete == "ignore":
        return zip(*args)
    else:
        raise ValueError("Expected fill, strict, or ignore")
