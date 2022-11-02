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
from typing import Any, Iterable

from .amp import Mark2Amp
from .buttons import Mark2Buttons
from .events import (
    SetFanSpeed,
    SetVolume,
    SetLedColors,
    ButtonStates,
    ReportButtonStates,
    LedColors,
    Volume,
    GetVolume,
    AnimateLeds,
)
from .fan import Mark2Fan
from .leds import Mark2Leds


class Mark2:
    def __init__(self):
        self.fan = Mark2Fan()
        self.buttons = Mark2Buttons()
        self.amp = Mark2Amp()
        self.leds = Mark2Leds()
        self.is_running = True

    def stop(self):
        self.fan.stop()
        self.buttons.stop()
        self.amp.stop()
        self.leds.stop()
        self.is_running = False

    def publish_event(self, event):
        pass

    def handle_event(self, event) -> Iterable[Any]:
        if isinstance(event, SetFanSpeed):
            self.fan.speed = event.speed
        elif isinstance(event, SetVolume):
            self.amp.volume = event.volume
            self.publish_event(Volume(volume=self.amp.volume))
        elif isinstance(event, GetVolume):
            self.publish_event(Volume(volume=self.amp.volume))
        elif isinstance(event, SetLedColors):
            self.leds.clear_animation()
            if event.brightness is not None:
                self.leds.brightness = event.brightness
            self.leds.rgb = event.rgb
            self.publish_event(
                LedColors(rgb=self.leds.rgb, brightness=self.leds.brightness_int)
            )
        elif isinstance(event, AnimateLeds):
            if event.name == "asleep":
                if self.buttons.states.get("mute", True):
                    # Not muted
                    self.publish_event(SetLedColors(rgb=[0, 0, 0]))
                else:
                    # Muted
                    self.publish_event(SetLedColors(rgb=[255, 0, 0]))
            else:
                self.leds.set_animation(event.name)
        elif isinstance(event, ReportButtonStates):
            yield ButtonStates(states=self.buttons.states)
