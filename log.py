import os
from datetime import datetime


class Log:
    """ General logger to log to a file, to be used e.g. by CallMonitor and CallBlocker. """

    def __init__(self, file_prefix, log_folder=None, daily=False, anonymize=False):
        """ Where to log the call monitor lines, optionally file for each day or phone numbers anonymized. """
        self.do_daily = daily
        self.do_anon = anonymize
        self.file_prefix = file_prefix
        if log_folder:
            self.log_folder = log_folder
        else:
            self.log_folder = os.path.join(os.path.dirname(__file__), "log")
        os.makedirs(self.log_folder, exist_ok=True)

    def get_log_filepath(self, log_folder, file_prefix, do_daily):
        """ Build the file path, one log or daily log. """
        if self.do_daily:
            dt = datetime.today().strftime('%Y%m%d')
            return os.path.join(self.log_folder, f'{self.file_prefix}-{dt}.log')
        else:
            return os.path.join(self.log_folder, f'{self.file_prefix}.log')

    def log_line(self, line):
        raise NotImplementedError("log_line not implemented")
