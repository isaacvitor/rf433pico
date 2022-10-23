"""
RF433pico is a Micropython library to connect RF433mhz receivers such as MX-05V, and remote control transmitters.
The code was based on https://github.com/AdrianCX/pico433mhz library and contains little modifications.
"""

import time
from machine import Pin
from micropython import schedule
from collections import namedtuple

MAX_CHANGES: int = 67
DEFAULT_TRANSMITTER_PIN: int = 27
DEFAULT_RECEIVER_PIN: int = 22

Protocol = namedtuple(
    "Protocol",
    [
        "pulse_length",
        "sync_high",
        "sync_low",
        "zero_high",
        "zero_low",
        "one_high",
        "one_low",
    ],
)
PROTOCOLS = (
    None,
    Protocol(350, 1, 31, 1, 3, 3, 1),
    Protocol(650, 1, 10, 1, 2, 2, 1),
    Protocol(100, 30, 71, 4, 11, 9, 6),
    Protocol(380, 1, 6, 1, 3, 3, 1),
    Protocol(500, 6, 14, 1, 2, 2, 1),
    Protocol(200, 1, 10, 1, 5, 1, 1),
)


class RFBase:
    def __init__(self, pin_number: int = None, debug: bool = True):
        self.gpio: Pin = None
        self.pin_number: int = pin_number
        self.enabled: bool = False
        self.debug: bool = debug

    def print(self, *args, **kwargs):
        if self.debug:
            print(*args, **kwargs)


class RFIncomingMessage:
    def __init__(
        self,
        code: int = None,
        timestamp: int = None,
        bitlength=None,
        pulse_length=None,
        proto=None,
    ) -> None:
        self.code = code
        self.code_timestamp = timestamp
        self.bitlength = bitlength
        self.pulse_length = pulse_length
        self.proto = proto

    def __repr__(self) -> str:
        _msg = f"RFIncomingMessage:(CODE:{self.code},"
        _msg = _msg + f" CODE_TIMESTAMP:{self.code_timestamp},"
        _msg = _msg + f" BITLENGTH:{self.bitlength},"
        _msg = _msg + f" PULSE_LENGTH:{self.pulse_length}, PROTO:{self.proto})"
        return _msg


class RFReceiver(RFBase):
    def __init__(
        self,
        pin_number: int = DEFAULT_RECEIVER_PIN,
        max_changes: int = MAX_CHANGES,
        tolerance=80,
        debug: bool = True,
        enable_on_create: bool = True,
    ):
        """Initialize the RF device."""
        super().__init__(pin_number=pin_number, debug=debug)
        self.tolerance: int = tolerance
        # internal values
        self._timings: int = [0] * (max_changes + 1)
        self._last_timestamp: int = 0
        self._change_count: int = 0
        self._repeat_count: int = 0
        # successful values
        self.code = None
        self.code_timestamp = None
        self.proto = None
        self.bitlength = None
        self.pulse_length = None
        self.listeners = []
        if enable_on_create:
            self.enable()

    def enable(self):
        """Enable Receiver, set up GPIO and add event detection."""
        if not self.pin_number:
            raise OSError(f"pin_number is required")

        if not self.enabled:
            self.enabled = True
            self.gpio = Pin(self.pin_number, Pin.IN, Pin.PULL_DOWN)
            self.gpio.irq(
                handler=self._callback, trigger=Pin.IRQ_FALLING | Pin.IRQ_RISING
            )
            self.print(f"Receiver enabled, pin: {self.pin_number}")
        return True

    def disable(self):
        """Disable Receiver, remove GPIO event detection."""
        if self.enabled:
            self.gpio.irq(None)
            self.enabled = False
            self.print("Receiver disabled")
        return True

    # pylint: disable=unused-argument
    def _callback(self, gpio):
        """Receiver callback for GPIO event detection. Handle basic signal detection."""
        global PROTOCOLS
        timestamp = time.ticks_us()
        duration = timestamp - self._last_timestamp
        if duration > 5000:
            if abs(duration - self._timings[0]) < 200:
                self._repeat_count += 1
                self._change_count -= 1
                if self._repeat_count == 2:
                    for pnum in range(1, len(PROTOCOLS)):
                        if self._waveform(pnum, self._change_count, timestamp):
                            break
                    self._repeat_count = 0
            self._change_count = 0

        if self._change_count >= MAX_CHANGES:
            self._change_count = 0
            self._repeat_count = 0
        self._timings[self._change_count] = duration
        self._change_count += 1
        self._last_timestamp = timestamp

    def _waveform(self, pnum, change_count, timestamp):
        """Detect waveform and format code."""
        global PROTOCOLS
        code = 0
        delay = int(self._timings[0] / PROTOCOLS[pnum].sync_low)
        delay_tolerance = delay * self.tolerance / 100

        for i in range(1, change_count, 2):
            if (
                abs(self._timings[i] - delay * PROTOCOLS[pnum].zero_high)
                < delay_tolerance
                and abs(self._timings[i + 1] - delay * PROTOCOLS[pnum].zero_low)
                < delay_tolerance
            ):
                code <<= 1
            elif (
                abs(self._timings[i] - delay * PROTOCOLS[pnum].one_high)
                < delay_tolerance
                and abs(self._timings[i + 1] - delay * PROTOCOLS[pnum].one_low)
                < delay_tolerance
            ):
                code <<= 1
                code |= 1
            else:
                return False

        if self._change_count > 6 and code != 0:
            self.code = code
            self.code_timestamp = timestamp
            self.bitlength = int(change_count / 2)
            self.pulse_length = delay
            self.proto = pnum
            schedule(self._notify, None)
            return True
        return False

    def clear(self):
        self.code = None
        self.code_timestamp = 0
        self.proto = None
        self.bitlength = None
        self.pulse_length = None

    def add_listener(self, listener):
        #         if hasattr(listener, "__call__"): # doesn't work in MPy
        if "function" in str(type(listener)):
            self.print("Added new listener")
            self.listeners.append(listener)

    def remove_listener(self, listener):
        for i, _listener in enumerate(self.listeners):
            if _listener == listener:
                self.print("Removed listener")
                del self.listeners[i]

    def clear_listeners(self):
        self.listeners = []

    def _notify(self, _):
        new_incoming = RFIncomingMessage(
            code=self.code,
            timestamp=self.code_timestamp,
            bitlength=self.bitlength,
            pulse_length=self.pulse_length,
            proto=self.proto,
        )
        if self.listeners:
            self.print(f"Notify new message to {len(self.listeners)} listeners")
            for listener in self.listeners:
                self.print(f"Calling {listener}")
                listener(new_incoming)


""" Transmitter is a work in progress """


class RFTransmitter(RFBase):
    def __init__(
        self,
        pin_number: int = DEFAULT_TRANSMITTER_PIN,
        proto_number: int = 1,
        pulse_length=None,
        repeat: int = 10,
        length: int = 24,
        debug: bool = True,
        enable_on_create: bool = True,
    ):
        global PROTOCOLS
        super().__init__(pin_number=pin_number, debug=debug)
        self.proto_number = proto_number
        self.pulse_length = PROTOCOLS[self.proto_number].pulse_length
        if pulse_length:
            self.pulse_length = pulse_length

        self.repeat = repeat
        self.length = length
        if enable_on_create:
            self.enable()

    def enable(self):
        """Enable Transmitter, set up GPIO."""
        if not self.pin_number:
            raise OSError(f"pin_number is required.")

        if not self.enabled:
            self.enabled = True
            self.gpio = Pin(self.tx_pin_number, Pin.OUT)
            self.print("Transmitter enabled")
        return True

    def disable(self):
        """Disable Transmitter, reset GPIO."""
        if self.enabled:
            self.gpio = None
            self.enabled = False
            self.print("Transmitter disabled")
        return True

    def send_code(self, code, proto_number=None, pulse_length=None, length=None):
        """
        Send a decimal code.

        Optionally set protocol, pulse_length and code length.
        When none given reset to default protocol, default pulse_length and set code length to 24 bits.
        """
        self.us_sleep = 0
        self.start = time.ticks_us()

        if proto_number:
            self.proto_number = proto_number

        if pulse_length:
            self.pulse_length = pulse_length

        if length:
            self.length = length
        elif self.proto_number == 6:
            self.length = 32
        elif code > 16777216:
            self.length = 32
        else:
            self.length = 24
        raw_code = "{{0:{}b}}".format(self.length + 2).format(code)[2:]
        if self.proto_number == 6:
            nexacode = ""
            for b in raw_code:
                if b == "0":
                    nexacode = nexacode + "01"
                if b == "1":
                    nexacode = nexacode + "10"
            raw_code = nexacode
            self.length = 64
        self.print("Transmitter code: ", str(code), " binary: ", raw_code)
        status = self.send_binary(raw_code)

        # We must not transmit too often, we also need to make sure we don't corrupt our current message, so wait a bit more between messages if some are chained by caller
        # 500ms seems excessive, should test and reduce when time allows.
        self.us_sleep = self.us_sleep + 500000

        # finish up any pending sleep for 0 bytes - so next transmit code doesn't mess our currently sent one.
        while time.ticks_us() - self.start < self.us_sleep:
            time.sleep_us(1)

        return status

    def send_binary(self, raw_code):
        """Send a binary code."""
        for _ in range(0, self.repeat):
            if self.proto_number == 6:
                if not self.send_sync():
                    return False
            for byte in range(0, self.length):
                if raw_code[byte] == "0":
                    if not self.send_l0():
                        return False
                else:
                    if not self.send_l1():
                        return False
            if not self.send_sync():
                return False

        return True

    def send_l0(self):
        """Send a '0' bit."""
        global PROTOCOLS
        if not 0 < self.proto_number < len(PROTOCOLS):
            self.print("Unknown Transmitter protocol")
            return False
        return self.send_waveform(
            PROTOCOLS[self.proto_number].zero_high,
            PROTOCOLS[self.proto_number].zero_low,
        )

    def send_l1(self):
        """Send a '1' bit."""
        global PROTOCOLS
        if not 0 < self.proto_number < len(PROTOCOLS):
            self.print("Unknown Transmitter protocol")
            return False
        return self.send_waveform(
            PROTOCOLS[self.proto_number].one_high, PROTOCOLS[self.proto_number].one_low
        )

    def send_sync(self):
        """Send a sync."""
        global PROTOCOLS
        if not 0 < self.proto_number < len(PROTOCOLS):
            self.print("Unknown Transmitter protocol")
            return False
        return self.send_waveform(
            PROTOCOLS[self.proto_number].sync_high,
            PROTOCOLS[self.proto_number].sync_low,
        )

    def send_waveform(self, high_pulses, low_pulses):
        """Send basic waveform."""
        if not self.enabled:
            self.print("Transmitter is not enabled, not sending data")
            return False

        while time.ticks_us() - self.start < self.us_sleep:
            time.sleep_us(1)

        self.gpio.value(1)
        self.start = time.ticks_us()

        self.us_sleep = int(
            high_pulses * self.pulse_length
        )  # - int(int(high_pulses * self.pulse_length)/100)
        while time.ticks_us() - self.start < self.us_sleep:
            time.sleep_us(1)

        self.gpio.value(0)
        self.start = time.ticks_us()
        self.us_sleep = int(
            low_pulses * self.pulse_length
        )  # - int(int(low_pulses * self.pulse_length)/100)

        return True
