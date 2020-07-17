#!/usr/bin/python3

import contextlib
import logging
import os
import platform
import socket
import sys
import threading
import time
from enum import Enum

sys.path.append(os.path.dirname(__file__))
from fritzconn import FritzConn
from utils import anonymize_number
from log import Log

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
        """ Replace last 3 chars of phone numbers with xxx. Nothing to do for the disconnect event. """
        params = raw_line.strip().split(';', 7)
        type = params[1]
        if type == CallMonitorType.DISCONNECT.value:
            return raw_line
        elif type == CallMonitorType.CONNECT.value:
            params[4] = anonymize_number(params[4])
        elif type == CallMonitorType.RING.value:
            params[3] = anonymize_number(params[3])
            params[4] = anonymize_number(params[4])
        elif type == CallMonitorType.CALL.value:
            params[4] = anonymize_number(params[4])
            params[5] = anonymize_number(params[5])
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


class CallMonitorLog(Log):
    """ Call monitor lines are logged to a file, optionally anonymized. Use log_line as logger for callmonitor. """

    def __init__(self, file_prefix="callmonitor", log_folder=None, daily=False, anonymize=False):
        super().__init__(file_prefix, log_folder, daily, anonymize)

    def log_line(self, line):
        """ Append a raw call monitor line to the log file. Optionally anonymize phone numbers. """
        filepath = self.get_log_filepath()
        if self.do_anon:
            line = CallMonitorLine.anonymize(line)
        with open(filepath, "a", encoding='utf-8') as f:
            f.write(line)

    def parse_from_file(self, raw_file_path, print_raw=False, anonymize=False):
        """ Read from raw file and parse each line. For unit tests OR EVEN INJECTION (instead of socket) later. """
        with open(raw_file_path, "r", encoding='utf-8') as f:
            for line in f.readlines():
                # Remove comments
                hash_pos = line.find('#')
                if hash_pos != -1:
                    line = line[:hash_pos]
                # Remove newline, skip empty lines
                line = line.strip()
                if not line:
                    continue
                # Re-append previously stripped newline
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

    def __init__(self, host=None, port=1012, autostart=True, logger=None, parser=None):
        """ By default will start the call monitor automatically and parse the lines. """
        self.host = host.replace('https://', '').replace('http://', '')
        self.port = port
        self.socket = None
        self.thread = None
        self.parser = parser if parser else self.parse_line
        self.logger = logger
        if autostart:
            self.start()

    def parse_line(self, raw_line):
        """ Default parser method for received call monitor lines. """
        log.debug(raw_line)
        parsed_line = CallMonitorLine(raw_line)
        print(parsed_line)

    def connect_tcp_keep_alive_socket(self):
        """ Socket has to use tcp keep-alive, otherwise call monitor from Fritzbox stops reporting after some time. """
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
            self.socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, after_idle_sec)
            self.socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, interval_sec)
            self.socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, max_fails)
        else:
            print("You use an unidentified operating system: {}".format(op_sys))
        self.socket.connect((self.host, self.port))

    def start(self):
        """ Start the socket connection and the listener thread. """
        try:
            msg = "Call monitor connection {h}:{p} ".format(h=self.host, p=self.port)
            self.connect_tcp_keep_alive_socket()
            log.info(msg + "established..")
            self.thread = threading.Thread(target=self.listen_thread)
            self.thread.start()
        except socket.error as e:
            self.socket = None
            log.error(msg + "FAILED!")
            log.error("Error: {}\nDid you enable the call monitor by 'dialing' #96*5*?".format(e))

    def stop(self):
        """ Stop the socket connection and the listener thread. """
        log.info("Stop listening..")
        self.thread.do_run = False  # More reliable than while (self.active)
        if self.socket:
            self.socket.shutdown(socket.SHUT_RDWR)
        if self.thread and self.thread.is_alive():
            self.thread.join()

    def listen_thread(self):
        """ Listen to the call monitor socket connection. Have to be TCP keep alive enabled. """
        log.info("Start listening..")
        print("Call monitor listening started..")
        # https://stackoverflow.com/questions/18018033/how-to-stop-a-looping-thread-in-python
        t = threading.currentThread()
        while getattr(t, "do_run", True):
            try:
                if not self.socket or self.socket._closed:
                    log.warning("Socket closed - reconnecting..")
                    self.connect_tcp_keep_alive_socket()
                    # Socket is reconnected even if network cable is unplugged, continues to work after plugged in
                    if self.socket:
                        print("Socket reconnected..")
                with contextlib.closing(self.socket.makefile()) as file:
                    line_generator = (line for line in file if file)
                    for raw_line in line_generator:
                        self.parser(raw_line)
                        if self.logger:
                            self.logger(raw_line)
            # socket.py L668: handling errorTab[10051] = "Network is unreachable."
            except OSError as e:
                log.warning(e)
                print("Network unreachable, trying to reconnect..")
                self.socket = None
                time.sleep(3)


if __name__ == "__main__":
    # Quick example how to use only

    # Initialize by using parameters from config file
    fritzconn = FritzConn()

    # Quick example how to use only
    cm_log = CallMonitorLog(daily=True, anonymize=False)
    cm = CallMonitor(host=fritzconn.address, logger=cm_log.log_line)
    # cm.stop()
