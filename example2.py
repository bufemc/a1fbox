#!/usr/bin/python3

# This more complex example shows how to connect the modules aka building blocks.
# It listens to the call monitor of the Fritz!Box, and will examine the calls.
# If the score is too bad it will block the call (for the next time) by adding it
# to the blacklisted (has to be configured to do so!) phonebook.

# REQUIRED: To enable call monitor dial #96*5* and to disable dial #96*4.
# REQUIRED: A phonebook id where bad calls should be added. Configure it in Fritzbox to decline calls!

# To see some action e.g. call from intern phone 1 to phone 2,
# or use your mobile phone to call the landline. This will print and log the calls.

from a1fbox.fritzconn import FritzConn
from a1fbox.callmonitor import CallMonitor, CallMonitorLog
from a1fbox.callblocker import CallBlocker, CallBlockerLog

if __name__ == "__main__":

    # Initialize by using parameters from config file
    fritzconn = FritzConn()

    # There are two loggers. cm_log logs the raw line from call monitor of Fritzbox,
    # cb_log logs the actions of the call blocker. The CallMonitor uses the
    # CallBlocker and it's parse_and_examine_line method to examine the raw line.

    # Idea: could also define which rating method should be used?

    cb_log = CallBlockerLog(daily=True, anonymize=False)
    cb = CallBlocker(fc=fritzconn, whitelist_pbids=[0], blacklist_pbids=[1, 2], blocklist_pbid=2,
                     blockname_prefix='[Spam] ', min_score=6, min_comments=2, logger=cb_log.log_line)

    cm_log = CallMonitorLog(daily=True, anonymize=False)
    cm = CallMonitor(host=fritzconn.address, logger=cm_log.log_line, parser=cb.parse_and_examine_line)
