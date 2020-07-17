#!/usr/bin/python3

# This very basic example listens to the call monitor of the Fritz!Box.
# It does not need to utilize FritzConn(ection), just the ip address is enough.

# REQUIRED: To enable call monitor dial #96*5* and to disable dial #96*4.

# To see some action e.g. call from intern phone 1 to phone 2,
# or use your mobile phone to call the landline. This will print and log the calls.

from a1fbox.callmonitor import CallMonitor, CallMonitorLog
from config import FRITZ_IP_ADDRESS

if __name__ == "__main__":
    print("To stop enter '!' (exclamation mark) followed by ENTER key..")

    cm_log = CallMonitorLog(daily=True, anonymize=False)
    cm = CallMonitor(host=FRITZ_IP_ADDRESS, logger=cm_log)

    key = ""
    while key != "!":
        key = input()

    cm.stop()
