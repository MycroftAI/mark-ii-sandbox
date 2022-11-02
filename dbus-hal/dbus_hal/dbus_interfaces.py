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
import itertools
from collections import defaultdict

from dbus_next.service import ServiceInterface, dbus_property, signal, method

from .events import (
    SetFanSpeed,
    ReportButtonStates,
    ButtonStateChanged,
    SetVolume,
    LedColors,
    SetLedColors,
)

_LOGGER = logging.getLogger("dbus")

# -----------------------------------------------------------------------------


class Mark2FanInterface(ServiceInterface):
    """DBus interface to Mark 2 fan"""

    def __init__(self):
        super().__init__("ai.mycroft.Mark2FanInterface")
        self._speed = 100

    @dbus_property()
    def speed(self) -> "y":
        """Gets current speed in [0, 100]"""
        return self._speed

    @speed.setter
    def speed(self, val: "y"):
        """Sets fan speed in [0, 100]"""
        self._speed = val
        self.publish_event(SetFanSpeed(speed=self._speed))
        self.emit_properties_changed({"speed": self._speed})

    def publish_event(self, event):
        pass


# -----------------------------------------------------------------------------


class Mark2ButtonInterface(ServiceInterface):
    """DBus interface for button/switch signals"""

    def __init__(self):
        super().__init__("ai.mycroft.Mark2ButtonInterface")
        self._states = defaultdict(bool)

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
        self.publish_event(ReportButtonStates())

    def publish_event(self, event):
        pass

    def handle_event(self, event):
        if isinstance(event, ButtonStateChanged):
            self._states[event.name] = event.state
            if event.name == "volume_up":
                self.volume_up()
            elif event.name == "volume_down":
                self.volume_down()
            elif event.name == "action":
                self.action()
            elif event.name == "mute":
                self.mute()
        elif isinstance(event, ReportButtonStates):
            self.volume_up()
            self.volume_down()
            self.action()
            self.mute()


# -----------------------------------------------------------------------------


class Mark2AmpInterface(ServiceInterface):
    """DBus interface for amplifier volume"""

    def __init__(self):
        super().__init__("ai.mycroft.Mark2AmpInterface")
        self._volume: int = 60

    @dbus_property()
    def volume(self) -> "y":
        """Get volume in [0, 100]"""
        return self._volume

    @volume.setter
    def volume(self, val: "y"):
        """Set volume in [0, 100]"""
        self._volume = val
        self.publish_event(SetVolume(self._volume))
        self.emit_properties_changed({"volume": self._volume})

    def publish_event(self, event):
        pass


# -----------------------------------------------------------------------------


class Mark2LedInterface(ServiceInterface):
    """DBus interface for controlling Mark II LEDs"""

    MAX_COLOR = 255
    MIN_COLOR = 0
    NUM_COLORS = 3

    NUM_LEDS = 12

    def __init__(self):
        super().__init__("ai.mycroft.Mark2LedInterface")
        self._rgb: List[int] = [self.MIN_COLOR] * self.NUM_COLORS * self.NUM_LEDS
        self._rgb_str = ",".join(str(v) for v in self._rgb)
        self._brightness: float = 0.5

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

        self._brightness = val / 100
        self._set_rgb()
        self.emit_properties_changed({"brightness": self.brightness_int})

    @dbus_property()
    def rgb(self) -> "s":
        """Get colors as comma-separated RGB string"""
        return self._rgb_str

    @rgb.setter
    def rgb(self, val: "s"):
        """Set colors as comma-separated RGB string"""
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
        self.publish_event(SetLedColors(rgb=self._rgb, brightness=self.brightness_int))

    def publish_event(self, event):
        pass

    def handle_event(self, event):
        if isinstance(event, LedColors):
            self._rgb = event.rgb
            self._brightness = event.brightness / 100
