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
from math import exp, log

import RPi.GPIO as GPIO

_LOGGER = logging.getLogger("amp")


class Mark2Amp:
    BUS_ID = 1
    DEVICE_ADDRESS = 0x2F
    VOLUME_ADDRESS = 0x4C

    MIN_VOLUME = 0
    MAX_VOLUME = 100

    MIN_HARDWARE_VOLUME = 210
    MAX_HARDWARE_VOLUME = 84

    def __init__(self):
        self._volume: int = 60

    def stop(self):
        pass

    @property
    def volume(self) -> int:
        """Set volume in [0, 100]"""
        return self._volume

    @volume.setter
    def volume(self, val: int):
        """Get volume in [0, 100]"""
        val = min(self.MAX_VOLUME, max(self.MIN_VOLUME, val))
        _LOGGER.debug("volume: %s", val)
        self._volume = val
        self._set_volume()

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
        """given x produce y. takes in an int 0-100 returns a log oriented
        hardware value with larger steps for low volumes and smaller steps for
        loud volumes"""
        x = max(self.MIN_VOLUME, min(self.MAX_VOLUME, x))

        x0 = self.MIN_VOLUME  # input range low
        x1 = self.MAX_VOLUME  # input range hi

        y0 = self.MAX_HARDWARE_VOLUME  # max hw vol
        y1 = self.MIN_HARDWARE_VOLUME  # min hw val

        p1 = (x - x0) / (x1 - x0)
        p2 = log(y0) - log(y1)
        pval = p1 * p2 + log(y1)

        return round(exp(pval))
