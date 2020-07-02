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
