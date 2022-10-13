#!/usr/bin/env python3
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
import asyncio
import functools
import itertools
import logging
import re
import subprocess
import time
from math import exp, log
from threading import Thread
from typing import List

import sdnotify
import board
import neopixel
import RPi.GPIO as GPIO
from dbus_next.aio import MessageBus
from dbus_next.service import ServiceInterface, dbus_property, signal, method
from dbus_next import BusType

_LOGGER = logging.getLogger("mark2-hardware-server")
NOTIFIER = sdnotify.SystemdNotifier()
WATCHDOG_DELAY = 0.5

# -----------------------------------------------------------------------------


async def main():
    logging.basicConfig(level=logging.INFO)

    GPIO.setwarnings(False)
    GPIO.setmode(GPIO.BCM)

    # Connect to system bus
    bus = await MessageBus(bus_type=BusType.SYSTEM).connect()

    # Create interfaces
    fan_interface = Mark2FanInterface()
    bus.export("/ai/mycroft/mark2/fan", fan_interface)

    led_interface = Mark2LedInterface()
    bus.export("/ai/mycroft/mark2/led", led_interface)

    button_interface = Mark2ButtonInterface()
    bus.export("/ai/mycroft/mark2/button", button_interface)

    amp_interface = Mark2AmpInterface()
    bus.export("/ai/mycroft/mark2/amp", amp_interface)

    # In /etc/dbus-1/system.d/mycroft_mark2.conf
    #
    # <!DOCTYPE busconfig PUBLIC
    # "-//freedesktop//DTD D-BUS Bus Configuration 1.0//EN"
    # "http://www.freedesktop.org/standards/dbus/1.0/busconfig.dtd">
    # <busconfig>
    #   <policy user="root">
    #       <allow own="ai.mycroft.mark2"/>
    #   </policy>
    #       <allow send_destination="ai.mycroft.mark2"/>
    #   </policy>
    # </busconfig>
    #
    await bus.request_name("ai.mycroft.mark2")

    # Start watchdog thread
    Thread(target=_watchdog, daemon=True).start()

    # Inform systemd that we successfully started
    NOTIFIER.notify("READY=1")
    _LOGGER.info("Ready")

    try:
        await bus.wait_for_disconnect()
    except KeyboardInterrupt:
        pass
    finally:
        fan_interface.stop()
        led_interface.stop()
        button_interface.stop()

    _LOGGER.info("Stoped")


def _watchdog():
    try:
        while True:
            # Prevent systemd from restarting service
            NOTIFIER.notify("WATCHDOG=1")
            time.sleep(WATCHDOG_DELAY)
    except Exception:
        _LOGGER.exception("Unexpected error in watchdog thread")


# -----------------------------------------------------------------------------


class Mark2FanInterface(ServiceInterface):
    # I2C-based fan control
    BUS_ID = 1
    DEVICE_ADDRESS = 0x04
    FAN_ID = 101
    MIN_HARDWARE_VALUE = 0
    MAX_HARDWARE_VALUE = 255

    # GPIO-based fan control
    FAN_PIN = 13

    MAX_SPEED = 100
    MIN_SPEED = 0

    def __init__(self):
        super().__init__("ai.mycroft.Mark2FanInterface")
        self._speed = 100
        self._is_i2c_fan = self._detect_i2c_fan()

        if self._is_i2c_fan:
            _LOGGER.info("I2C fan detected")
            self._pwm = None
        else:
            _LOGGER.info("GPIO fan detected")
            GPIO.setup(self.FAN_PIN, GPIO.OUT)

            self._pwm = GPIO.PWM(self.FAN_PIN, 1000)
            self._pwm.start(0)

    def stop(self):
        """Releases PWM resource"""
        if self._pwm is not None:
            self._pwm.stop()
            self._pwm = None

    @dbus_property()
    def speed(self) -> "y":
        """Sets current speed in [0, 100]"""
        return self._speed

    @speed.setter
    def speed(self, val: "y"):
        """Sets fan speed in [0, 100]"""
        if self._speed == val:
            return

        _LOGGER.debug("speed: %s", val)
        self._speed = max(self.MIN_SPEED, min(self.MAX_SPEED, val))

        if self._is_i2c_fan:
            self._set_speed_i2c()
        else:
            self._set_speed_gpio()

        self.emit_properties_changed({"speed": self._speed})

    def _set_speed_i2c(self):
        """Sets the fan speed using I2C"""
        hardware_value = int(
            self.MIN_HARDWARE_VALUE
            + (
                (self.MAX_HARDWARE_VALUE - self.MIN_HARDWARE_VALUE)
                * (self._speed / (self.MAX_SPEED - self.MIN_SPEED))
            )
        )

        set_command = [
            "i2cset",
            "-y",  # disable interactive mode
            "-a",  # allow access to LED device range
            str(self.BUS_ID),
            f"0x{self.DEVICE_ADDRESS:02x}",
            f"0x{self.FAN_ID:02x}",
            str(hardware_value),
            "i",  # block data
        ]

        _LOGGER.debug(set_command)
        subprocess.check_call(set_command)
        _LOGGER.debug("Device %s set to %s", self.FAN_ID, hardware_value)

    def _set_speed_gpio(self):
        """Sets the fan speed using GPIO PWM"""
        hardware_value = float(100.0 - (self._speed % 101))
        self._pwm.ChangeDutyCycle(hardware_value)
        _LOGGER.debug("Duty cycle set to %s", hardware_value)

    def _detect_i2c_fan(self) -> bool:
        """Returns True if I2C fan device is detected"""
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
            _LOGGER.exception("Error while detecting I2C fan")

        return False


# -----------------------------------------------------------------------------


class Mark2LedInterface(ServiceInterface):
    """DBus interface for controlling Mark II LEDs"""

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
        super().__init__("ai.mycroft.Mark2LedInterface")
        self._rgb: List[int] = [self.MIN_COLOR] * self.NUM_COLORS * self.NUM_LEDS
        self._rgb_str = ",".join(str(v) for v in self._rgb)
        self._is_i2c_leds = self._detect_i2c_leds()
        self._brightness: float = 0.5

        if self._is_i2c_leds:
            _LOGGER.info("I2C LEDs detected")
            self._pixels = None
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

    def stop(self):
        """Set LEDs to black"""
        if self._pixels is not None:
            for i in range(self.NUM_LEDS):
                self._pixels[i] = [self.MIN_COLOR] * self.NUM_COLORS
            self._pixels.show()
            self._pixels = None

    @property
    def brightness_int(self) -> int:
        """Get brightness value in [0, 100]"""
        return int(100 * max(0.0, min(1.0, self._brightness)))

    @dbus_property()
    def brightness(self) -> "y":
        """Set brightness in [0, 100]"""
        return self.brightness_int

    @brightness.setter
    def brightness(self, val: "y"):
        """Get brightness in [0, 100]"""
        if self.brightness_int == val:
            return

        _LOGGER.debug("brightness: %s", val)
        self._brightness = val / 100
        self._set_rgb()
        self.emit_properties_changed({"brightness": self.brightness_int})

    @dbus_property()
    def rgb(self) -> "s":
        """Set colors as comma-separated RGB string"""
        return self._rgb_str

    @rgb.setter
    def rgb(self, val: "s"):
        """Get colors as comma-separated RGB string"""
        if self._rgb_str == val:
            return

        _LOGGER.debug("rgb: %s", val)
        rgb = [max(self.MIN_COLOR, min(self.MAX_COLOR, int(c))) for c in val.split(",")]

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
        self._rgb_str = ",".join(str(v) for v in self._rgb)
        self._set_rgb()
        self.emit_properties_changed({"rgb": self._rgb_str})

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


# -----------------------------------------------------------------------------


class Mark2ButtonInterface(ServiceInterface):
    """DBus interface for button/switch signals"""

    # sj201Rev4+
    PINS = {"volume_up": 22, "volume_down": 23, "action": 24, "mute": 25}

    # Switch debounce time in milliseconds
    DEBOUNCE = 100

    # Delay after callback before reading switch state in seconds
    WAIT_SEC = 0.05

    # Pin value when switch is active
    ACTIVE = 0

    def __init__(self):
        super().__init__("ai.mycroft.Mark2ButtonInterface")
        self._states = {name: False for name in self.PINS}

        for name, pin in self.PINS.items():
            GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            GPIO.add_event_detect(
                pin,
                GPIO.BOTH,
                callback=functools.partial(self._handle_gpio_event, name, pin),
                bouncetime=self.DEBOUNCE,
            )

    def stop(self):
        pass

    def _handle_gpio_event(self, name, pin, _channel):
        """Read and report the state of a switch that has changed state"""
        time.sleep(self.WAIT_SEC)
        value = GPIO.input(pin)
        new_state = value == self.ACTIVE

        old_state = self._states[name]
        self._states[name] = new_state

        if old_state != new_state:
            if name == "volume_up":
                self.volume_up()
            elif name == "volume_down":
                self.volume_down()
            elif name == "action":
                self.action()
            elif name == "mute":
                self.mute()

        _LOGGER.debug("%s: %s", name, new_state)

    @signal()
    def volume_up(self) -> "b":
        return self._states["volume_up"]

    @signal()
    def volume_down(self) -> "b":
        return self._states["volume_down"]

    @signal()
    def action(self) -> "b":
        return self._states["action"]

    @signal()
    def mute(self) -> "b":
        return self._states["mute"]

    @method()
    def report(self):
        """Report all button states"""
        for name, pin in self.PINS.items():
            value = GPIO.input(pin)
            self._states[name] = value == self.ACTIVE

        self.volume_up()
        self.volume_down()
        self.action()
        self.mute()


# -----------------------------------------------------------------------------


class Mark2AmpInterface(ServiceInterface):
    """DBus interface for amplifier volume"""

    BUS_ID = 1
    DEVICE_ADDRESS = 0x2F
    VOLUME_ADDRESS = 0x4C

    MIN_VOLUME = 0
    MAX_VOLUME = 100

    MIN_HARDWARE_VOLUME = 210
    MAX_HARDWARE_VOLUME = 84

    def __init__(self):
        super().__init__("ai.mycroft.Mark2AmpInterface")
        self._volume: int = 60

    @dbus_property()
    def volume(self) -> "y":
        """Set volume in [0, 100]"""
        return self._volume

    @volume.setter
    def volume(self, val: "y"):
        """Get volume in [0, 100]"""
        val = min(self.MAX_VOLUME, max(self.MIN_VOLUME, val))
        _LOGGER.debug("volume: %s", val)
        self._volume = val
        self._set_volume()
        self.emit_properties_changed({"volume": self._volume})

    def _set_volume(self):
        try:
            tas_volume = self._calc_log_y(self._volume)

            # Double-check volume
            # NOTE: max hardware volume < min hardware volume
            tas_volume = max(
                self.MAX_HARDWARE_VOLUME, min(self.MIN_HARDWARE_VOLUME, tas_volume)
            )

            set_command = [
                "i2cset",
                "-y",  # disable interactive mode
                str(self.BUS_ID),
                f"0x{self.DEVICE_ADDRESS:02x}",
                f"0x{self.VOLUME_ADDRESS:02x}",
                str(tas_volume),
                "i",  # block data
            ]
            _LOGGER.debug(set_command)
            subprocess.check_call(set_command)
        except Exception:
            _LOGGER.exception("Error setting amplifier volume")

    def _calc_log_y(self, x):
        """given x produce y. takes in an int
        0-100 returns a log oriented hardware
        value with larger steps for low volumes
        and smaller steps for loud volumes"""
        x = max(self.MIN_VOLUME, min(self.MAX_VOLUME, x))

        x0 = self.MIN_VOLUME  # input range low
        x1 = self.MAX_VOLUME  # input range hi

        y0 = self.MAX_HARDWARE_VOLUME  # max hw vol
        y1 = self.MIN_HARDWARE_VOLUME  # min hw val

        p1 = (x - x0) / (x1 - x0)
        p2 = log(y0) - log(y1)
        pval = p1 * p2 + log(y1)

        return round(exp(pval))


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


# -----------------------------------------------------------------------------

if __name__ == "__main__":
    asyncio.run(main())
