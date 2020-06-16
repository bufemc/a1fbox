#!/usr/bin/python3

import contextlib
import logging
import socket
import threading
import time
from enum import Enum

# ToDo: provide a config.py - with user & pass for other services
FRITZ_HOST = "fritz.box"

logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger(__name__)


class CallMonitorType(Enum):
    """ Relevant call types in received lines from call monitor. """

    RING = "RING"
    CALL = "CALL"
    CONNECT = "CONNECT"
    DISCONNECT = "DISCONNECT"


class CallMonitorLine:
    """ Parses a received line from call monitor, parameters are separated by ';' finished by a newline '\n'. """

    def __init__(self, line):
        """ A line from call monitor has min 4 and max 7 parameters, but the order depends on the type. """
        self.duration = 0
        self.ext_id, self.caller, self.callee, self.device = None, None, None, None
        self.timestamp, self.type, self.conn_id, param, *more = line.strip().split(';', 7)
        if self.type == CallMonitorType.DISCONNECT.value:
            self.duration = param
        elif self.type == CallMonitorType.CONNECT.value:
            self.ext_id, self.caller = param, more[0]
        elif self.type == CallMonitorType.RING.value:
            self.caller, self.callee, self.device = param, more[0], more[1]
        elif self.type == CallMonitorType.CALL.value:
            self.ext_id, self.caller, self.callee, self.device = param, more[0], more[1], more[2]

    def __str__(self):
        """ Pretty print a line from call monitor, by considering the type. """
        start = f'{self.timestamp} type:{self.type} conn_id:{self.conn_id}'
        switcher = {
            CallMonitorType.RING.value: f'{start} from:{self.caller} to:{self.callee} device:{self.device}',
            CallMonitorType.CALL.value: f'{start} from:{self.caller} to:{self.callee} device:{self.device}',
            CallMonitorType.CONNECT.value: f'{start} to:{self.caller}',
            CallMonitorType.DISCONNECT.value: f'{start} duration:{self.duration}',
        }
        return switcher.get(self.type, 'NOT IMPLEMENTED CALL TYPE {}'.format(self.type))


class CallMonitor:
    """ Connect and listen to call monitor of Fritzbox, port is by default 1012. Enable it by dialing #96*5*. """

    def __init__(self, host=FRITZ_HOST, port=1012, autostart=True):
        """ By default will start the call monitor automatically and parse the lines. """
        self.host = host
        self.port = port
        self.socket = None
        self.thread = None
        self.active = False
        self.callback = self.parse_line
        if autostart:
            self.start()

    def parse_line(self, raw_line):
        """ Default callback method, will parse and print the received lines. """
        log.debug(raw_line)
        parsed_line = CallMonitorLine(raw_line)
        print(parsed_line)

    def set_callback(self, callback_method):
        """ Optionally override the callback method to parse the raw_line yourself or with help of CallMonitorLine. """
        self.callback = callback_method

    def start(self):
        """ Starts the socket connection and the listener thread. """
        if self.socket:
            log.warning("Call monitor already started")
            return
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setblocking(True)
        try:
            msg = "Call monitor connection {h}:{p} ".format(h=self.host, p=self.port)
            self.socket.connect((self.host, self.port))
            log.info(msg + "established..")
            self.thread = threading.Thread(target=self.listen_thread)
            self.thread.start()
        except socket.error as e:
            self.socket = None
            log.error(msg + "FAILED!")
            log.error("Error: {}\nDid you enable the call monitor by 'dialing' #96*5*?".format(e))

    def stop(self):
        """ Tries to stop the socket connection and the listener thread. Will sometimes fail. """
        log.info("Listening stopped..\n")
        self.active = False
        time.sleep(1)  # Give thread some time to recognize !self.active, better solution required
        if self.socket:
            self.socket.shutdown(socket.SHUT_RDWR)
        if self.thread and self.thread.is_alive():
            self.thread.join()

    def listen_thread(self):
        """ Listens to the socket connection, however at some time socket does not send anymore. """
        if self.active:
            log.warning("Listen thread already started")
            return
        log.info("Listening started..\n")
        print("Call monitor listening started..\n")
        self.active = True
        with contextlib.closing(self.socket.makefile()) as file:
            while (self.active):
                line_generator = (line for line in file if file)
                for line in line_generator:
                    self.callback(line)


if __name__ == "__main__":
    # Just a quick and dirty example how to use the call monitor until a setup is provided
    cm = CallMonitor(host='192.168.1.1')
