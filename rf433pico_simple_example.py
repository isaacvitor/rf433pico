import time
from rf433pico import RFReceiver, RFIncomingMessage

# Creating a new RFReceiver instance
receiver = RFReceiver(pin_number=18, debug=False)
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
