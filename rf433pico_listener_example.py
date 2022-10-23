import time
from rf433pico import RFReceiver, RFIncomingMessage

# Creating a new RFReceiver instance
receiver = RFReceiver(pin_number=18, debug=False)
# Enabling receiver
receiver.enable()


def callback(incoming_message: RFIncomingMessage):
    print(f"LISTENER CALLBACK:{incoming_message}")


receiver.add_listener(callback)
