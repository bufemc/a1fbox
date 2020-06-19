import csv
import logging

import requests
from callmonitor import CallMonitor, CallMonitorType, CallMonitorLine, CallMonitorLog
from config import FRITZ_IP_ADDRESS, FRITZ_USERNAME, FRITZ_PASSWORD
from log import Log
from phonebook import Phonebook

logging.basicConfig(level=logging.WARNING)
log = logging.getLogger(__name__)


class CallBlockerLog(Log):
    """ Call monitor lines are logged to a file. So far call monitor uses method log_line only. """

    def __init__(self, file_prefix="callblocker", log_folder=None, daily=False, anonymize=False):
        super().__init__(file_prefix, log_folder, daily, anonymize)

    def log_line(self, line):
        """ Appends a line to the log file. """
        filepath = self.get_log_filepath()
        if self.do_anon:
            # Not implemented yet
            pass
        with open(filepath, "a", encoding='utf-8') as f:
            f.write(line + "\n")


class CallBlocker:
    """ Parse call monitor, examine RING event's phone number. """

    def __init__(self, whitelist_pbid, blacklist_pbid, min_score=6, min_comments=3, logger=None):
        """ Provide a whitelist phonebook (normally first index 0) and where blocked numbers should go into. """
        self.whitelist_pbid = whitelist_pbid
        self.blacklist_pbid = blacklist_pbid
        self.min_score = int(min_score)
        self.min_comments = int(min_comments)
        self.logger = logger
        self.pb = Phonebook(address=FRITZ_IP_ADDRESS, user=FRITZ_USERNAME, password=FRITZ_PASSWORD)
        self.onb_dict = dict()
        self.init_onb()
        self.set_area_and_country_code()
        for pb_id in [self.whitelist_pbid, self.blacklist_pbid]:
            if pb_id not in self.pb.phonebook_ids:
                raise Exception(f'The phonebook_id {pb_id} does not exist!')
        self.whitelist = self.pb.get_all_numbers(self.whitelist_pbid)  # [{Number: Name}, ..]
        self.blacklist = self.pb.get_all_numbers(self.blacklist_pbid)  # [{Number: Name}, ..]
        area_name = self.area['name'] if self.area else 'UNKNOWN'
        print(f'Call blocker initialized.. '
              f'country_code:{self.country_code} area_code:{self.area_code} area_name:{area_name} '
              f'whitelisted:{len(self.whitelist)} blacklisted:{len(self.blacklist)}')

    def set_area_and_country_code(self):
        """ Retrieve area and country code via the Fritzbox. """
        res = self.pb.fc.call_action('X_VoIP', 'X_AVM-DE_GetVoIPCommonAreaCode')
        self.area_code = res['NewX_AVM-DE_OKZPrefix'] + res['NewX_AVM-DE_OKZ']
        res = self.pb.fc.call_action('X_VoIP', 'X_AVM-DE_GetVoIPCommonCountryCode')
        self.country_code = res['NewX_AVM-DE_LKZPrefix'] + res['NewX_AVM-DE_LKZ']
        self.area = self.onb_dict[self.area_code] if self.area_code in self.onb_dict else None

    def init_onb(self):
        """ Read the area codes into a dict. provided by BNetzA as CSV, separated by ';'. """
        with open('./data/onb.csv', encoding='utf-8') as csvfile:
            line_nr = 0
            csvreader = csv.reader(csvfile, delimiter=';')
            for row in csvreader:
                if line_nr == 0:
                    # This is for prevention only, if the order is changed it will fail here intentionally
                    assert (row[0] == 'Ortsnetzkennzahl')
                    assert (row[1] == 'Ortsnetzname')
                    assert (row[2] == 'KennzeichenAktiv')
                    line_nr += 1
                    continue
                if len(row) == 3:  # Last line is ['\x1a']
                    area_code = '0' + row[0]
                    name = row[1]
                    active = True if row[2] == '1' else False
                    self.onb_dict[area_code] = {'code': area_code, 'name': name, 'active': active}
                line_nr += 1

    def parse_and_examine_line(self, raw_line):
        """ Parse call monitor line, if RING event not in lists, rate and maybe block the number. """
        log.debug(raw_line)
        cm_line = CallMonitorLine(raw_line)
        print(cm_line)

        if cm_line.type == CallMonitorType.RING.value:

            number = cm_line.caller
            # Number can be with area_code or without! Both variants can be in phonebook, too..
            number_variant = number  # Only used for search in whitelist
            if number.startswith(self.area_code):
                number_variant = number.replace(self.area_code, '')  # Number wo AC
            if number.startswith('0'):
                full_number = number
            else:
                number_variant = self.area_code + number
                full_number = number_variant

            # 1. Is either full number 071..123... or short number 123... in the whitelist?
            if number in self.whitelist.keys() or number_variant in self.whitelist.keys():
                log.debug(f'{number} in whitelist, skipping..')
                if self.logger:
                    self.logger(f'WHITELISTED:{number}')
                return

            # 2. Already in blacklist?
            if full_number in self.blacklist.keys():
                log.warning(f'{number} in blacklist, skipping..')
                if self.logger:
                    self.logger(f'BLACKLISTED:{number}')
                return

            # 3. Get ratio for full_number, deserves maybe an extra method rate_number
            # https://blog.tellows.de/2011/07/tellows-api-fur-die-integration-in-eigene-programme/
            url = f'http://www.tellows.de/basic/num/{full_number}?json=1&partner=test&apikey=test123'
            # ToDo: failed requests, blocked, json malformed..
            req = requests.get(url)
            obj = req.json()['tellows']
            # print(obj)
            score = int(obj['score'])
            comment_count = int(obj['comments'])
            location = obj['location']
            searches = obj['searches']

            # ToDo: instead of re-rate could cache ratings in a file? dict(full_number: object, ..)

            # 4. Block if bad ratio
            if score >= self.min_score and comment_count >= self.min_comments:
                # ToDo: try to build a smarter name, e.g. add first callerTypes":{"caller":[{"name" .. if != Unbekannt
                name = f'CallBlock {location} ({searches})'
                result = self.pb.add_contact(self.blacklist_pbid, name, full_number)
                if result:
                    print(result)
                # ToDo: log blocking
                print(f'{full_number} BLOCKED')
                if self.logger:
                    self.logger(f'BLOCKED:{number};name:{name};score:{score};comments:{comment_count};')

    # Ideas: reverse search via dasoertliche? Is there an API?


if __name__ == "__main__":
    # Quick example how to use only
    cb_log = CallBlockerLog(daily=True, anonymize=False)
    cb = CallBlocker(whitelist_pbid=0, blacklist_pbid=2, min_score=6, min_comments=3, logger=cb_log.log_line)
    cm_log = CallMonitorLog(file_prefix="callmonitor", daily=True, anonymize=False)
    cm = CallMonitor(logger=cm_log.log_line, parser=cb.parse_and_examine_line)

    # Provoke by test
    # test_line = '17.06.20 10:28:29;RING;0;0781968053101;69xxx;SIP0;'
    # cb.parse_and_examine_line(test_line)

    # cm.stop()
