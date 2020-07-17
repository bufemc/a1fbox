#!/usr/bin/python3

# General methods and classes should go here

import os
from abc import abstractmethod
from datetime import datetime


class Log:
    """ General logger to one|daily file, with possibility to anonymize whatever wished. """

    def __init__(self, file_prefix, log_folder=None, daily=False, anonymize=False):
        """ Where to log lines, file_prefix is mandatory. If log_folder not given, will use './log/'. """
        self.do_daily = daily
        self.do_anon = anonymize
        self.file_prefix = file_prefix
        if log_folder:
            self.log_folder = log_folder
        else:
            self.log_folder = os.path.join(os.path.dirname(__file__), "../log")
        os.makedirs(self.log_folder, exist_ok=True)

    def get_log_filepath(self):
        """ Build the file path, one|daily log to log_folder/file_prefix(-suffix).log. """
        if self.do_daily:
            dt = datetime.today().strftime('%Y%m%d')
            return os.path.join(self.log_folder, f'{self.file_prefix}-{dt}.log')
        else:
            return os.path.join(self.log_folder, f'{self.file_prefix}.log')

    @abstractmethod
    def log_line(self, line):
        """ Append a line to the log file. To do so use (self.)log_folder, file_prefix, do_daily, do_anon. """
        raise NotImplementedError("log_line not implemented")


class Caches:
    """ General temporary caches, like Caches['tellows'][nr] = CallerInfo - or source could be 'revsearch'..
    Have to be initialized before, then passed to CallerInfo. Not used yet. """

    def __init__(self, sources):
        for source in sources:
            self[source] = dict()

    def add_source_key_obj(self, source, key, obj):
        self[source][key] = obj

    def get_source_key_obj(self, source, key):
        if source not in self:
            raise Exception(f'Source {source} does not exist or was not initialized!')
        return self[source][key] if key in self[source] else None


def anonymize_number(number):
    """ Anonymize 3 last digits of a number, provided as string. """
    if number.isdigit() and len(number) >= 3:
        return number[:-3] + "xxx"
    else:
        # Not a number or e.g. "unknown" if caller uses CLIR
        return number
