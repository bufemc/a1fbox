import logging
from enum import Enum

from callinfo import CallInfo, CallInfoType
from callmonitor import CallMonitor, CallMonitorType, CallMonitorLine, CallMonitorLog
from callprefix import CallPrefix
from config import FRITZ_IP_ADDRESS, FRITZ_USERNAME, FRITZ_PASSWORD
from log import Log
from phonebook import Phonebook
from utils import anonymize_number

logging.basicConfig(level=logging.WARNING)
log = logging.getLogger(__name__)


class CallBlockerRate(Enum):
    """ Custom blocker rates. Currently method is sufficient to distinguish rated entries. """

    WHITELIST = "WHITELIST"
    BLACKLIST = "BLACKLIST"
    BLOCK = "BLOCK"
    PASS = "PASS"


class CallBlockerLine:
    """ Parse or anonymize a line from call blocker, parameters are separated by ';' finished by a newline '\n'. """

    @staticmethod
    def anonymize(raw_line):
        """ Replace last 3 chars of phone numbers with xxx. Overwrite Name. """
        params = raw_line.strip().split(';')
        params[3] = anonymize_number(params[3])
        params[4] = '"Anonymized"'
        return ';'.join(params) + "\n"

    def __init__(self, raw_line):
        """ A line from call blocker has min. 5 and ATM max. 8 parameters, but the order is constant.
        Trying to use same style logging like call monitor: date time; type;
        method_used (0=none, bit0=1=tellows, bit1=2=revsearch); full_number; name; score; comments(; searches;).
        Type is renamed to rate intentionally to distinguish both easily. """
        self.score, self.comments, self.searches = None, None, None
        self.datetime, self.rate, self.method, self.caller, self.name, *more = raw_line.strip().split(';', 8)
        self.name = self.name.strip('"')  # "ab"cd" => ab"cd
        self.date, self.time = self.datetime.split(' ')
        if int(self.method) in [CallInfoType.TELLOWS_SCORE.value, CallInfoType.TEL_AND_REV.value]:
            self.score, self.comments, self.searches = more[0], more[1], more[2]

    def __str__(self):
        """ Pretty print a line from call blocker (ignoring method), by considering the method. """
        start = f'date:{self.date} time:{self.time} rate:{self.rate} caller:{self.caller} name:{self.name}'
        if int(self.method) in [CallInfoType.TELLOWS_SCORE.value, CallInfoType.TEL_AND_REV.value]:
            return f'{start} score:{self.score} comments:{self.comments} searches:{self.searches}'
        else:
            return start


class CallBlockerLog(Log):
    """ Call blocker lines are logged to a file. So far call blocker uses method log_line only. """

    def __init__(self, file_prefix="callblocker", log_folder=None, daily=False, anonymize=False):
        super().__init__(file_prefix, log_folder, daily, anonymize)

    def log_line(self, line):
        """ Append a line to the log file. """
        filepath = self.get_log_filepath()
        if self.do_anon:
            line = CallBlockerLine.anonymize(line)
        with open(filepath, "a", encoding='utf-8') as f:
            f.write(line)


class CallBlocker:
    """ Parse call monitor, examine RING event's phone number. """

    def __init__(self, whitelist_pbids, blacklist_pbids, blocklist_pbid, blockname_prefix='',
                 min_score=6, min_comments=3, logger=None):
        """ Provide a whitelist phonebook (normally first index 0) and where blocked numbers should go into. """
        self.whitelist_pbids = whitelist_pbids
        self.blacklist_pbids = blacklist_pbids
        self.blocklist_pbid = blocklist_pbid
        self.blockname_prefix = blockname_prefix
        self.min_score = int(min_score)
        self.min_comments = int(min_comments)
        self.logger = logger
        print("Retrieving data from Fritz!Box..")
        self.pb = Phonebook(address=FRITZ_IP_ADDRESS, user=FRITZ_USERNAME, password=FRITZ_PASSWORD)
        self.cp = CallPrefix(fc=self.pb.fc)
        self.pb.ensure_pb_ids_valid(self.whitelist_pbids + self.blacklist_pbids + [self.blocklist_pbid])
        self.whitelist = self.pb.get_all_numbers_for_pb_ids(self.whitelist_pbids)
        self.blacklist = self.pb.get_all_numbers_for_pb_ids(self.blacklist_pbids)
        print(f'Call blocker initialized.. '
              f'country_code:{self.cp.country_code} area_code:{self.cp.area_code} area_name:{self.cp.area_code_name} '
              f'whitelisted:{len(self.whitelist)} blacklisted:{len(self.blacklist)}')

    def parse_and_examine_line(self, raw_line):
        """ Parse call monitor line, if RING event not in lists, rate and maybe block the number. """
        log.debug(raw_line)
        cm_line = CallMonitorLine(raw_line)
        print(cm_line)

        if cm_line.type == CallMonitorType.RING.value:
            dt = cm_line.datetime  # Use same datetime for exact match

            number = cm_line.caller
            if number.startswith('0'):
                full_number = number
            else:
                full_number = self.cp.area_code + number

            # 1. Is either full number 071..123... or short number 123... in the white- or blacklist?
            name_white = self.pb.get_name_for_number_in_dict(number, self.whitelist, area_code=self.cp.area_code)
            name_black = self.pb.get_name_for_number_in_dict(number, self.blacklist, area_code=self.cp.area_code)

            if name_white and name_black:
                raise Exception(f'Problem in your phonebooks detected: '
                                f'a number should not be on white- and blacklist. Please fix! Details: '
                                f'whitelist:{name_white} blacklist:{name_black}')

            if name_white or name_black:
                name = name_black if name_black else name_white  # Reason: black might win over white by blocking it
                rate = CallBlockerRate.BLACKLIST.value if name_black else CallBlockerRate.WHITELIST.value
                raw_line = f'{dt};{rate};0;{full_number};"{name}";' + "\n"

            else:
                ci = CallInfo(full_number)
                ci.get_tellows_and_revsearch()
                # Adapt to logging style of call monitor. Task of logger to parse the values to keys/names?
                score_str = f'"{ci.name}";{ci.score};{ci.comments};{ci.searches};'

                if ci.score >= self.min_score and ci.comments >= self.min_comments:
                    name = self.blockname_prefix + ci.name
                    result = self.pb.add_contact(self.blocklist_pbid, name, full_number)
                    if result:  # If not {} returned, it's an error
                        log.warning("Adding to phonebook failed:")
                        print(result)
                    rate = CallBlockerRate.BLOCK.value
                else:
                    rate = CallBlockerRate.PASS.value
                raw_line = f'{dt};{rate};1;{full_number};{score_str}' + "\n"

            log.debug(raw_line)
            parsed_line = CallBlockerLine(raw_line)
            print(parsed_line)
            if self.logger:
                self.logger(raw_line)


if __name__ == "__main__":
    # Quick example how to use only
    # There are two loggers. cm_log logs the raw line from call monitor of Fritzbox,
    # cb_log logs the actions of the call blocker. The CallMonitor uses the
    # CallBlocker and it's parse_and_examine_line method to examine the raw line.

    # ToDo: could also define which rating method should be used?

    cb_log = CallBlockerLog(daily=True, anonymize=False)
    cb = CallBlocker(whitelist_pbids=[0], blacklist_pbids=[1, 2], blocklist_pbid=2,
                     blockname_prefix='[Spam] ', min_score=6, min_comments=3, logger=cb_log.log_line)
    cm_log = CallMonitorLog(daily=True, anonymize=False)
    cm = CallMonitor(logger=cm_log.log_line, parser=cb.parse_and_examine_line)

    # Provoke whitelist test
    # test_line = '17.06.20 10:28:29;RING;0;07191952xxx;69xxx;SIP0;'; cb.parse_and_examine_line(test_line)
    # Provoke blacklist test
    # test_line = '17.06.20 10:28:29;RING;0;09912568741596;69xxx;SIP0;'; cb.parse_and_examine_line(test_line)
    # cm.stop()
