#!/usr/bin/python3

import logging
import os
import sys
from enum import Enum
from time import time
from urllib.parse import quote

from callinfo import CallInfo, CallInfoType, UNKNOWN_NAME
from callmonitor import CallMonitor, CallMonitorType, CallMonitorLine, CallMonitorLog
from callprefix import CallPrefix
from fritzconn import FritzConn
from phonebook import Phonebook

sys.path.append(os.path.dirname(__file__))
from utils import Log, anonymize_number

sys.path.append("..")
from config import TELEGRAM_BOT_URL

import requests


logging.basicConfig(level=logging.WARNING)
log = logging.getLogger(__name__)

FAKE_PREFIX = 'FAKE_PREFIX'  # E.g. prefix 09460 does not exist in Germany, regarding to ONB


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
        if int(self.method) in [CallInfoType.WEMGEHOERT_SCORE.value]:
            self.score = more[0]
        elif int(self.method) in [CallInfoType.TELLOWS_SCORE.value, CallInfoType.CASCADE.value]:
            self.score, self.comments, self.searches = more[0], more[1], more[2]

    def __str__(self):
        """ Pretty print a line from call blocker (ignoring method), by considering the method. """
        # caller = self.caller if self.caller else 'CLIR'
        start = f'date:{self.date} time:{self.time} rate:{self.rate} caller:{self.caller} name:{self.name}'
        if int(self.method) in [CallInfoType.WEMGEHOERT_SCORE.value]:
            return f'{start} score:{self.score}'
        elif int(self.method) in [CallInfoType.TELLOWS_SCORE.value, CallInfoType.CASCADE.value]:
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

    def __init__(self, fc,
                 whitelist_pbids, blacklist_pbids, blocklist_pbid, blockname_prefix='',
                 min_score=6, min_comments=3,
                 block_abroad=False, block_illegal_prefix=True,
                 logger=None):
        """ Provide a whitelist phonebook (normally first index 0) and where blocked numbers should go into. """
        self.whitelist_pbids = whitelist_pbids
        self.blacklist_pbids = blacklist_pbids
        self.blocklist_pbid = blocklist_pbid
        self.blockname_prefix = blockname_prefix
        self.min_score = int(min_score)
        self.min_comments = int(min_comments)
        # self.block_anon = block_anon  # How should that work? Impossible?
        self.block_abroad = block_abroad
        self.block_illegal_prefix = block_illegal_prefix
        self.logger = logger
        print("Retrieving data from Fritz!Box..")
        self.pb = Phonebook(fc=fc)
        fritz_model = self.pb.fc.modelname
        fritz_os = self.pb.fc.system_version
        self.cp = CallPrefix(fc=self.pb.fc)
        self.pb.ensure_pb_ids_valid(self.whitelist_pbids + self.blacklist_pbids + [self.blocklist_pbid])
        self.reload_phonebooks()
        if self.cp.country_code != '0049':
            log.warning('This script was developed for usage in Germany - please contact the author!')
        print(f'Call blocker initialized.. '
              f'model:{fritz_model} ({fritz_os}) '
              f'country:{self.cp.country_code_name} ({self.cp.country_code}) '
              f'area:{self.cp.area_code_name} ({self.cp.area_code}) '
              f'whitelisted:{len(self.whitelist)} blacklisted:{len(self.blacklist)} prefixes:{len(self.cp.prefix_dict)}')

    def reload_phonebooks(self):
        """ Whitelist should be reloaded e.g. every day, blacklist after each entry added. """
        self.whitelist = self.pb.get_all_numbers_for_pb_ids(self.whitelist_pbids)
        self.blacklist = self.pb.get_all_numbers_for_pb_ids(self.blacklist_pbids)
        self.list_age = time()

    def parse_and_examine_line(self, raw_line):
        """ Parse call monitor line, if RING event not in lists, rate and maybe block the number. """
        if time() - self.list_age >= 3600:  # Reload phonebooks if list is outdated
            self.reload_phonebooks()
        log.debug(raw_line)
        cm_line = CallMonitorLine(raw_line)
        print(cm_line)

        # New: also examine calls from inside to outside (CallMonitorType.CALL)
        if cm_line.type in [CallMonitorType.RING.value, CallMonitorType.CALL.value]:
            dt = cm_line.datetime  # Use same datetime for exact match

            if cm_line.type == CallMonitorType.RING.value:
                number = cm_line.caller  # Incoming call
            else:
                number = cm_line.callee  # Outgoing call

            if not number:  # Caller uses NO number (so called CLIR feature)

                # We cannot block anon numbers, except you could add a rule in Fritzbox to do so?
                rate = CallBlockerRate.PASS.value  # CallBlockerRate.BLOCK.value if self.block_anon else CallBlockerRate.PASS.value
                raw_line = f'{dt};{rate};0;;ANON;' + "\n"

            else:  # Caller WITH phone number

                is_abroad = number.startswith('00') and not number.startswith(self.cp.country_code)

                if number.startswith('0'):
                    full_number = number  # Number with either country code or area code
                else:
                    full_number = self.cp.area_code + number  # Number in same area network

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
                    ci.get_cascade_score()

                    # ToDo: check also if e.g. the prefix is inactive, e.g. DE_LANDLINE_INACTIVE
                    # Is the prefix (Vorwahl) valid, existing country code OR area code?
                    prefix_name = self.cp.get_prefix_name(full_number)
                    if not prefix_name and not number.startswith('00'):  # Do not block e.g. Inmarsat or similar
                        prefix_name = FAKE_PREFIX

                    # If there is no other information name at least the country or area
                    if ci.name == UNKNOWN_NAME:
                        ci.name = prefix_name

                    # Adapt to logging style of call monitor. Task of logger to parse the values to keys/names?
                    score_str = f'"{ci.name}";{ci.score};{ci.comments};{ci.searches};'

                    # Bad code style here - should be rewritten soon
                    if (self.block_illegal_prefix and prefix_name == FAKE_PREFIX) \
                            or (self.block_abroad and is_abroad) \
                            or (ci.score >= self.min_score and ci.comments >= self.min_comments):
                        name = self.blockname_prefix + ci.name
                        # Precaution: should only happen if this is a call from outside, not from inside
                        if cm_line.type == CallMonitorType.RING.value:
                            # ToDo: should go in extra method
                            result = self.pb.add_contact(self.blocklist_pbid, name, full_number)
                            if result:  # If not {} returned, it's an error
                                log.warning("Adding to phonebook failed:")
                                print(result)
                            else:
                                # Reload phonebook to prevent re-adding number for next ring event
                                # self.blacklist = self.pb.get_all_numbers_for_pb_ids(self.blacklist_pbids)
                                self.reload_phonebooks()
                            rate = CallBlockerRate.BLOCK.value
                        else:
                            rate = CallBlockerRate.PASS.value
                    else:
                        rate = CallBlockerRate.PASS.value
                    raw_line = f'{dt};{rate};1;{full_number};{score_str}' + "\n"

            log.debug(raw_line)
            parsed_line = CallBlockerLine(raw_line)
            print(parsed_line)
            if self.logger:
                self.logger(raw_line)

            if TELEGRAM_BOT_URL:
                requests.get(TELEGRAM_BOT_URL + quote("CallBlocker: " + raw_line))


if __name__ == "__main__":
    # Quick example how to use only

    # Initialize by using parameters from config file
    fritzconn = FritzConn()

    # There are two loggers. cm_log logs the raw line from call monitor of Fritzbox,
    # cb_log logs the actions of the call blocker. The CallMonitor uses the
    # CallBlocker and it's parse_and_examine_line method to examine the raw line.

    # Idea: could also define which rating method should be used?

    cb_log = CallBlockerLog(daily=True, anonymize=False)
    cb = CallBlocker(fc=fritzconn,
                     whitelist_pbids=[0], blacklist_pbids=[1, 2], blocklist_pbid=2, blockname_prefix='[Spam] ',
                     min_score=6, min_comments=2,
                     block_illegal_prefix=True, block_abroad=False,
                     logger=cb_log.log_line)

    cm_log = CallMonitorLog(daily=True, anonymize=False)
    cm = CallMonitor(host=fritzconn.address, logger=cm_log.log_line, parser=cb.parse_and_examine_line)

    # Provoke whitelist test
    # test_line = '17.06.20 10:28:29;RING;0;07191952xxx;69xxx;SIP0;'; cb.parse_and_examine_line(test_line)
    # Provoke blacklist test
    # test_line = '17.06.20 10:28:29;RING;0;09912568741xxx;69xxx;SIP0;'; cb.parse_and_examine_line(test_line)
    # cm.stop()

    # Provoke CLIR (caller number suppressed)
    # test_line = '11.07.20 14:10:13;RING;0;;69xxx;SIP0;'; cb.parse_and_examine_line(test_line)

    # Provoke abroad call and call from Germany with faked numbers, show at least country or area then
    # test_line = '11.07.20 14:10:13;RING;0;00226123xxx;69xxx;SIP0;'; cb.parse_and_examine_line(test_line)
    # test_line = '11.07.20 14:10:13;RING;0;07151123xxx;69xxx;SIP0;'; cb.parse_and_examine_line(test_line)

    # Outgoing call
    # test_line = '17.06.20 10:31:08;CALL;1;11;69xxx;952xxx;SIP0;'; cb.parse_and_examine_line(test_line)

    # Fake prefix call
    # test_line = '11.07.20 14:10:13;RING;0;094609xxx;69xxx;SIP0;'; cb.parse_and_examine_line(test_line)

    # Abroad cold call
    # test_line = '11.07.20 14:10:13;RING;0;003449xxx;69xxx;SIP0;'; cb.parse_and_examine_line(test_line)

    # Wrong block, allow special prefix numbers like 0800, 0180 etc. (add in CallPrefix)
    # test_line = '11.07.20 14:10:13;RING;0;08004400xxx;69xxx;SIP0;'; cb.parse_and_examine_line(test_line)
