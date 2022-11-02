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
from dataclasses import dataclass
from typing import List, Mapping, Optional, Any, Dict


@dataclass
class SetFanSpeed:
    speed: int
    """[0, 100]"""


@dataclass
class SetLedColors:
    rgb: List[int]
    """[r1, g1, b1, r2, g2, b2, ...]"""

    brightness: Optional[int] = None
    """[0, 100]"""


@dataclass
class AnimateLeds:
    name: str


@dataclass
class LedColors:
    rgb: List[int]
    """[r1, g1, b1, r2, g2, b2, ...]"""

    brightness: int
    """[0, 100]"""


@dataclass
class SetVolume:
    volume: int
    """[0, 100]"""


@dataclass
class GetVolume:
    pass


@dataclass
class Volume:
    volume: int
    """[0, 100]"""


@dataclass
class ButtonStateChanged:
    name: str
    state: bool


@dataclass
class ReportButtonStates:
    pass


@dataclass
class ButtonStates:
    states: Mapping[str, bool]
