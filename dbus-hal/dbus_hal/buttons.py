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
import functools
import logging
import subprocess
import time
from typing import Mapping

import RPi.GPIO as GPIO

_LOGGER = logging.getLogger("buttons")


class Mark2Buttons:

    # sj201Rev4+
    PINS = {"volume_up": 22, "volume_down": 23, "action": 24, "mute": 25}

    # Switch debounce time in milliseconds
    DEBOUNCE = 100

    # Delay after callback before reading switch state in seconds
    WAIT_SEC = 0.05

    # Pin value when switch is active
    ACTIVE = 0

    def __init__(self):
        self._states = {name: False for name in self.PINS}

        for name, pin in self.PINS.items():
            GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            GPIO.add_event_detect(
                pin,
                GPIO.BOTH,
                callback=functools.partial(self._handle_gpio_event, name, pin),
                bouncetime=self.DEBOUNCE,
            )
            self._states[name] = GPIO.input(pin) == self.ACTIVE

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
            self.on_button_state_changed(name, new_state)

        _LOGGER.debug("%s: %s", name, new_state)

    def on_button_state_changed(self, name: str, state: bool):
        pass

    @property
    def states(self) -> Mapping[str, bool]:
        return self._states
