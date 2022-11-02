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
import argparse
import asyncio
import logging
import time
from threading import Thread
from typing import Any, Callable, List, Optional, Iterable

import sdnotify
import RPi.GPIO as GPIO
from dbus_next.aio import MessageBus
from dbus_next import BusType
from dbus_next.service import ServiceInterface, dbus_property, signal, method
from mycroft_bus_client import MessageBusClient, Message

from .dbus_interfaces import (
    Mark2FanInterface,
    Mark2ButtonInterface,
    Mark2AmpInterface,
    Mark2LedInterface,
)
from .events import (
    SetFanSpeed,
    SetLedColors,
    SetVolume,
    ButtonStateChanged,
    ReportButtonStates,
    ButtonStates,
    Volume,
    GetVolume,
    AnimateLeds,
)
from .mark2 import Mark2

_LOGGER = logging.getLogger("dbus_hal")
NOTIFIER = sdnotify.SystemdNotifier()
WATCHDOG_DELAY = 0.5


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--websocket", action="store_true", help="Connect to Mycroft websocket server"
    )
    parser.add_argument(
        "--debug", action="store_true", help="Print DEBUG messages to the console"
    )
    args = parser.parse_args()

    # Enable logging
    level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(level=level)
    logging.getLogger().setLevel(level)

    # Use BCM pin numbers for GPIO
    GPIO.setwarnings(False)
    GPIO.setmode(GPIO.BCM)

    loop = asyncio.get_running_loop()

    # Connect to system bus
    bus = await MessageBus(bus_type=BusType.SYSTEM).connect()

    event_queue = asyncio.Queue()
    mark2 = Mark2()
    event_handlers = [mark2.handle_event]
    mark2.buttons.on_button_state_changed = (
        lambda name, state: asyncio.run_coroutine_threadsafe(
            event_queue.put(ButtonStateChanged(name, state)), loop
        )
    )
    asyncio.create_task(_process_events(mark2, event_queue, event_handlers))

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
    _LOGGER.info("Connected to DBus")

    def publish_event(event):
        asyncio.run_coroutine_threadsafe(event_queue.put(event), loop)

    mark2.publish_event = publish_event

    # Create interfaces
    fan_interface = Mark2FanInterface()
    fan_interface.publish_event = publish_event
    bus.export("/ai/mycroft/mark2/fan", fan_interface)

    led_interface = Mark2LedInterface()
    led_interface.publish_event = publish_event
    event_handlers.append(led_interface.handle_event)
    bus.export("/ai/mycroft/mark2/led", led_interface)

    button_interface = Mark2ButtonInterface()
    button_interface.publish_event = publish_event
    event_handlers.append(button_interface.handle_event)
    bus.export("/ai/mycroft/mark2/button", button_interface)

    amp_interface = Mark2AmpInterface()
    amp_interface.publish_event = publish_event
    bus.export("/ai/mycroft/mark2/amp", amp_interface)

    if args.websocket:
        websocket_bus = connect_to_websocket(event_queue, loop)
        event_handlers.append(make_websocket_event_handler(websocket_bus))
        _LOGGER.info("Connected to websocket bus")

    # Start watchdog thread
    Thread(target=_watchdog, daemon=True).start()
    _LOGGER.info("Watchdog started")

    # Inform systemd that we successfully started
    NOTIFIER.notify("READY=1")
    _LOGGER.info("Ready")

    try:
        await bus.wait_for_disconnect()
    except KeyboardInterrupt:
        # Graceful exit
        pass
    finally:
        mark2.stop()

    _LOGGER.info("Stopped")


def _watchdog():
    try:
        while True:
            # Prevent systemd from restarting service
            NOTIFIER.notify("WATCHDOG=1")
            time.sleep(WATCHDOG_DELAY)
    except Exception:
        _LOGGER.exception("Unexpected error in watchdog thread")


async def _process_events(
    mark2: Mark2,
    event_queue: asyncio.Queue,
    event_handlers: List[Callable[[Any], Optional[Iterable[Any]]]],
):
    while mark2.is_running:
        try:
            event = await event_queue.get()
            _LOGGER.debug(event)

            for handler in event_handlers:
                result = handler(event)
                if result is not None:
                    for new_event in result:
                        await event_queue.put(new_event)
        except (KeyboardInterrupt, asyncio.exceptions.CancelledError):
            # Graceful exit
            break
        except:
            _LOGGER.exception("Unexpected error while processing events")


# -----------------------------------------------------------------------------
# Websocket Server
# -----------------------------------------------------------------------------


def connect_to_websocket(
    event_queue: asyncio.Queue, loop: asyncio.AbstractEventLoop
) -> MessageBusClient:
    bus = MessageBusClient()
    bus.run_in_thread()
    bus.connected_event.wait()

    def publish_event(event):
        asyncio.run_coroutine_threadsafe(
            event_queue.put(event),
            loop,
        )

    bus.on(
        "mark2.hal.fan.set-speed",
        lambda message: publish_event(
            SetFanSpeed(speed=int(message.data.get("speed", 100)))
        ),
    )
    bus.on(
        "mark2.hal.leds.set-colors",
        lambda message: publish_event(
            SetLedColors(
                rgb=message.data.get("rgb", [0, 0, 0]),
                brightness=int(message.data.get("brightness", 50)),
            )
        ),
    )
    bus.on(
        "mycroft.mic.mute",
        lambda message: publish_event(SetLedColors(rgb=[255, 0, 0])),
    )
    bus.on(
        "mycroft.mic.unmute",
        lambda message: publish_event(SetLedColors(rgb=[0, 0, 0])),
    )
    bus.on(
        "mark2.hal.amp.set-volume",
        lambda message: publish_event(
            SetVolume(volume=int(message.data.get("volume", 60)))
        ),
    )
    bus.on(
        "mycroft.volume.set",
        lambda message: publish_event(
            SetVolume(volume=int(message.data.get("percent", 0.6) * 100))
        ),
    )
    bus.on(
        "mycroft.volume.get",
        lambda message: publish_event(GetVolume()),
    )
    bus.on(
        "mark2.hal.amp.get-volume",
        lambda message: publish_event(GetVolume()),
    )
    bus.on(
        "mark2.hal.buttons.report",
        lambda message: publish_event(ReportButtonStates()),
    )
    bus.on(
        "recognizer_loop:record_begin",
        lambda message: publish_event(AnimateLeds("awake")),
    )
    bus.on(
        "recognizer_loop:record_end",
        lambda message: publish_event(AnimateLeds("thinking")),
    )
    bus.on(
        "recognizer_loop:utterance",
        lambda message: publish_event(AnimateLeds("asleep")),
    )

    return bus


def make_websocket_event_handler(
    bus: MessageBusClient,
) -> Callable[[Any], Optional[Iterable[Any]]]:
    def handle_event(event: Any):
        if isinstance(event, ButtonStateChanged):
            bus.emit(
                Message(
                    "mark2.hal.buttons.state-changed",
                    {"name": event.name, "state": event.state},
                )
            )

            if event.name == "mute":
                if event.state:
                    bus.emit(Message("mycroft.mic.unmute"))
                else:
                    bus.emit(Message("mycroft.mic.mute"))
            elif event.state:
                if event.name == "volume_up":
                    bus.emit(Message("mycroft.volume.increase"))
                elif event.name == "volume_down":
                    bus.emit(Message("mycroft.volume.decrease"))
                elif event.name == "action":
                    bus.emit(Message("mycroft.mic.listen"))
        elif isinstance(event, ButtonStates):
            bus.emit(
                Message(
                    "mark2.hal.buttons.states",
                    {"states": event.states},
                )
            )
        elif isinstance(event, Volume):
            bus.emit(
                Message(
                    "mark2.hal.amp.volume",
                    {"volume": event.volume},
                )
            )
            bus.emit(
                Message(
                    "mycroft.volume.get.response",
                    {"percent": event.volume / 100},
                )
            )

    return handle_event


# -----------------------------------------------------------------------------

if __name__ == "__main__":
    asyncio.run(main())
