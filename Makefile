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

.PHONY: maker browser

SHELL := bash

DOCKER_PLATFORM ?= linux/arm64

maker:
	docker buildx build . -f Dockerfile --platform $(DOCKER_PLATFORM) --tag mycroftai/mark-ii-maker --output 'type=tar,dest=mycroft.tar'

browser:
	docker buildx build . -f Dockerfile.browser --platform $(DOCKER_PLATFORM) --tag mycroftai/mark-ii-browser --output 'type=tar,dest=mycroft.tar'

camera:
	docker buildx build . -f Dockerfile.camera --platform $(DOCKER_PLATFORM) --tag mycroftai/mark-ii-camera --output 'type=tar,dest=mycroft.tar'
