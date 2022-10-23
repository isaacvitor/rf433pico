# RF433pico

RF433pico is a Micropython library to connect RF433mhz receivers such as MX-05V, and remote control transmitters.

> The code was based on https://github.com/AdrianCX/pico433mhz library and contains some modifications.

## WARNING

MX-05V voltage operation is 5v and Raspberry Pi Pico 3v3, to avoid burning your gpio use a [logic level converter](https://www.sparkfun.com/products/12009).

> You could try to connect the MX-05V in 3.3v but the receiver will work only at a short distance, such as 10cm. If it's enough for your case, go ahead!

This library was tested only in a Raspberry Pi Pico with Micropython 1.19.1v, It means lower versions or another devices could have some problem.

## How to use

### Receiver

Simple example:

```python
import time
from rf433pico import RFReceiver

# Creating a new RFReceiver instance
receiver = RFReceiver(pin_number=18, debug=True)
# Enabling receiver
receiver.enable()


while True:
    if receiver.code and receiver.code_timestamp:
        print(
            '{ "code": "'
            + str(receiver.code)
            + '", "pulse_length": "'
            + str(receiver.pulse_length)
            + '", "protocol": "'
            + str(receiver.proto)
            + '" }'
        )
        receiver.clear()
    time.sleep(0.05)
```

Listener example:

```python
from rf433pico import RFReceiver, RFIncomingMessage

# Creating a new RFReceiver instance
receiver = RFReceiver(pin_number=18, debug=True)
# Enabling receiver
receiver.enable()


def callback(incoming_message: RFIncomingMessage):
    print(f"LISTENER CALLBACK:{incoming_message}")


receiver.add_listener(callback)

# To remove a listener:
# receiver.remove_listener(callback)

# or to remove all listeners
# receiver.clear_listeners()
```

By default, `debug` parameter is `False`, `debug` active a internal function using `print` nothing else.
When you use `listeners`, behind the scenes the library uses a `micropython.schedule` inside of a IRQ callback. That was my attempt to follow the [Mycropython recommendations of IRQ](https://docs.micropython.org/en/latest/reference/isr_rules.html).

### Transmitter

ToDo
