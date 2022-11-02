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
import re

import RPi.GPIO as GPIO

_LOGGER = logging.getLogger("fan")


class Mark2Fan:
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

    # -------------------------------------------------------------------------

    def __init__(self):
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

    @property
    def speed(self) -> int:
        return self._speed

    @speed.setter
    def speed(self, val: int):
        _LOGGER.debug("speed: %s", val)
        self._speed = max(self.MIN_SPEED, min(self.MAX_SPEED, val))

        if self._is_i2c_fan:
            self._set_speed_i2c()
        else:
            self._set_speed_gpio()

    # -------------------------------------------------------------------------

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
