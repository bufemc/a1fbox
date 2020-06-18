#!/usr/bin/python3

import contextlib
import logging
import os
import platform
import socket
import threading
import time
from datetime import datetime
from enum import Enum

from config import FRITZ_IP_ADDRESS

logging.basicConfig(level=logging.WARNING)
log = logging.getLogger(__name__)


class CallMonitorType(Enum):
    """ Relevant call types in received lines from call monitor. """

    RING = "RING"
    CALL = "CALL"
    CONNECT = "CONNECT"
    DISCONNECT = "DISCONNECT"


class CallMonitorLine:
    """ Parse or anonymize a line from call monitor, parameters are separated by ';' finished by a newline '\n'. """

    @staticmethod
    def anonymize(raw_line):
        """ Replaces last 3 chars of phone numbers with xxx. Nothing to do for the disconnect event. """
        params = raw_line.strip().split(';', 7)
        type = params[1]
        if type == CallMonitorType.DISCONNECT.value:
            return raw_line
        elif type == CallMonitorType.CONNECT.value:
            params[4] = params[4][:-3] + "xxx"
        elif type == CallMonitorType.RING.value:
            params[3] = params[3][:-3] + "xxx"
            params[4] = params[4][:-3] + "xxx"
        elif type == CallMonitorType.CALL.value:
            params[4] = params[4][:-3] + "xxx"
            params[5] = params[5][:-3] + "xxx"
        return ';'.join(params) + "\n"

    def __init__(self, raw_line):
        """ A line from call monitor has min. 4 and max. 7 parameters, but the order depends on the type. """
        self.duration = 0
        self.ext_id, self.caller, self.callee, self.device = None, None, None, None
        self.datetime, self.type, self.conn_id, *more = raw_line.strip().split(';', 7)
        self.date, self.time = self.datetime.split(' ')
        if self.type == CallMonitorType.DISCONNECT.value:
            self.duration = more[0]
        elif self.type == CallMonitorType.CONNECT.value:
            self.ext_id, self.caller = more[0], more[1]
        elif self.type == CallMonitorType.RING.value:
            self.caller, self.callee, self.device = more[0], more[1], more[2]
        elif self.type == CallMonitorType.CALL.value:
            self.ext_id, self.caller, self.callee, self.device = more[0], more[1], more[2], more[3]

    def __str__(self):
        """ Pretty print a line from call monitor (ignoring conn_id/ext_id/device), by considering the type. """
        start = f'date:{self.date} time:{self.time} type:{self.type}'
        switcher = {
            CallMonitorType.RING.value: f'{start} caller:{self.caller} callee:{self.callee}',
            CallMonitorType.CALL.value: f'{start} caller:{self.caller} callee:{self.callee}',
            CallMonitorType.CONNECT.value: f'{start} caller:{self.caller}',
            CallMonitorType.DISCONNECT.value: f'{start} duration:{self.duration}',
        }
        return switcher.get(self.type, 'NOT IMPLEMENTED CALL TYPE {}'.format(self.type))


class CallMonitorLog:
    """ Call monitor lines are logged to a file. So far call monitor uses method log_line only. """

    def __init__(self, file_prefix="callmonitor", log_folder=None, daily=False, anonymize=False):
        """ Where to log the call monitor lines, optionally file for each day or phone numbers anonymized. """
        self.do_daily = daily
        self.do_anon = anonymize
        self.file_prefix = file_prefix
        if log_folder:
            self.log_folder = log_folder
        else:
            self.log_folder = os.path.join(os.path.dirname(__file__), "log")
        os.makedirs(self.log_folder, exist_ok=True)

    def get_log_filepath(self):
        """ Build the file path, one log or daily log. """
        if self.do_daily:
            dt = datetime.today().strftime('%Y%m%d')
            return os.path.join(self.log_folder, f'{self.file_prefix}-{dt}.log')
        else:
            return os.path.join(self.log_folder, f'{self.file_prefix}.log')

    def log_line(self, raw_line):
        """ Appends a raw line to the log. """
        filepath = self.get_log_filepath()
        if self.do_anon:
            raw_line = CallMonitorLine.anonymize(raw_line)
        with open(filepath, "a", encoding='utf-8') as f:
            f.write(raw_line)

    def parse_from_file(self, raw_file_path, print_raw=False, anonymize=False):
        """ Read from raw file and parse each line. For unit tests OR EVEN INJECTION (instead of socket) later. """
        with open(raw_file_path, "r", encoding='utf-8') as f:
            for line in f.readlines():
                hash_pos = line.find('#')
                if hash_pos != -1:
                    line = line[:hash_pos]
                line = line.strip()
                if not line:  # Skip empty lines
                    continue
                line += "\n"
                if anonymize:
                    CallMonitorLine.anonymize(line)
                if print_raw:
                    print(line.strip())
                else:
                    cm_line = CallMonitorLine(line)
                    print(cm_line)


class CallMonitor:
    """ Connect and listen to call monitor of Fritzbox, port is by default 1012. Enable it by dialing #96*5*. """

    def __init__(self, host=FRITZ_IP_ADDRESS, port=1012, autostart=True, logger=None, callback=None):
        """ By default will start the call monitor automatically and parse the lines. """
        self.host = host
        self.port = port
        self.socket = None
        self.thread = None
        self.active = False
        self.callback = callback if callback else self.parse_line
        self.logger = logger
        if autostart:
            self.start()

    def parse_line(self, raw_line):
        """ Default callback method, will parse, print and optionally log the received lines. """
        log.debug(raw_line)
        parsed_line = CallMonitorLine(raw_line)
        print(parsed_line)
        if self.logger:
            self.logger.log_line(raw_line)

    def connect_socket(self):
        """ Socket has to be keep-alive, otherwise call monitor from Fritzbox stops reporting after some time. """
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # See: https://stackoverflow.com/questions/12248132/how-to-change-tcp-keepalive-timer-using-python-script
        keep_alive_sec = 10
        after_idle_sec = 1
        interval_sec = 3
        max_fails = 5
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        op_sys = platform.system()
        if op_sys == 'Windows':
            self.socket.ioctl(socket.SIO_KEEPALIVE_VALS, (1, keep_alive_sec * 1000, interval_sec * 1000))
        elif op_sys == 'Darwin':  # Mac
            TCP_KEEPALIVE = 0x10
            self.socket.setsockopt(socket.IPPROTO_TCP, TCP_KEEPALIVE, interval_sec)
        elif op_sys == 'Linux':
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
            self.socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, after_idle_sec)
            self.socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, interval_sec)
            self.socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, max_fails)
        else:
            print("You use an unidentified operating system: {}".format(op_sys))
        # Connect to Fritzbox call monitor port - might raise an exception, e.g. if port closed or host/port are wrong
        self.socket.connect((self.host, self.port))

    def start(self):
        """ Starts the socket connection and the listener thread. """
        try:
            msg = "Call monitor connection {h}:{p} ".format(h=self.host, p=self.port)
            self.connect_socket()
            log.info(msg + "established..")
            self.thread = threading.Thread(target=self.listen_thread)
            self.thread.start()
        except socket.error as e:
            self.socket = None
            log.error(msg + "FAILED!")
            log.error("Error: {}\nDid you enable the call monitor by 'dialing' #96*5*?".format(e))

    def stop(self):
        """ Stop the socket connection and the listener thread. Will sometimes fail. """
        log.info("Stop listening..")
        self.active = False
        time.sleep(1)  # Give thread some time to recognize !self.active, better solution required
        if self.socket:
            self.socket.shutdown(socket.SHUT_RDWR)
        if self.thread and self.thread.is_alive():
            self.thread.join()

    def listen_thread(self):
        """ Listen to the call monitor socket connection. Have to be TCP keep alive enabled. """
        log.info("Start listening..")
        print("Call monitor listening started..")
        self.active = True
        while (self.active):
            if (self.socket._closed):  # Reconnect in case socket was closed
                self.connect_socket()
            with contextlib.closing(self.socket.makefile()) as file:
                line_generator = (line for line in file if self.active and file)
                for raw_line in line_generator:
                    self.callback(raw_line)


if __name__ == "__main__":
    # Quick test only
    cm_log = CallMonitorLog(daily=True, anonymize=False)
    cm = CallMonitor(logger=cm_log)

    #cm.stop()