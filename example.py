from config import FRITZ_IP_ADDRESS
from a1fritzbox.callmonitor import CallMonitor, CallMonitorLog

if __name__ == "__main__":
    print("To stop enter '!' (exclamation mark) followed by ENTER key..")

    cm_log = CallMonitorLog(daily=True, anonymize=False)
    cm = CallMonitor(host=FRITZ_IP_ADDRESS, logger=cm_log)
    # cm_log.parse_from_file('log/callmonitor-test.log')

    key = ""
    while key != "!":
        key = input()

    cm.stop()
