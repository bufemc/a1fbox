import csv
import logging
from datetime import datetime

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
        """ Append a line to the log file. """
        filepath = self.get_log_filepath()
        if self.do_anon:
            # Not implemented yet
            pass
        with open(filepath, "a", encoding='utf-8') as f:
            f.write(line + "\n")


class CallerInfo:
    """ Retrieve details for a phone number. Currently scoring via Tellows. Could get score from a dict (caching). """

    def __init__(self, number):
        self.number = number
        self.get_tellows_score()

    def get_tellows_score(self):
        """ Do scoring for a phone number via Tellows.
        https://blog.tellows.de/2011/07/tellows-api-fur-die-integration-in-eigene-programme/ """
        url = f'http://www.tellows.de/basic/num/{self.number}?json=1&partner=test&apikey=test123'
        # ToDo: failed requests, blocked, json malformed..
        req = requests.get(url)
        obj = req.json()['tellows']

        self.score = int(obj['score'])
        self.comment_count = int(obj['comments'])
        self.location = obj['location']
        self.searches = obj['searches']

        # Build smarter name, e.g. from callerTypes":{"caller":[{"name" .. if present & != "Unbekannt" etc.
        caller_name = ''
        if 'callerTypes' in obj:
            if 'caller' in obj['callerTypes']:
                for name_count in obj['callerTypes']['caller']:
                    if name_count['name'] == 'Unbekannt':
                        continue
                    caller_name = name_count['name'] + ' '
                    break
        self.name = f'{caller_name}{self.location}'

    def get_reverse_search_info(self):
        """ Could do reverse search by DasOertliche by use of beautifulsoup4.
        https://www.dasoertliche.de/Controller?form_name=search_inv&ph=07191952xxx """
        pass


class CallBlocker:
    """ Parse call monitor, examine RING event's phone number. """

    def __init__(self, whitelist_pbids, blacklist_pbids, blocklist_pbid,
                 min_score=6, min_comments=3, logger=None):
        """ Provide a whitelist phonebook (normally first index 0) and where blocked numbers should go into. """
        self.whitelist_pbids = whitelist_pbids
        self.blacklist_pbids = blacklist_pbids
        self.blocklist_pbid = blocklist_pbid
        self.min_score = int(min_score)
        self.min_comments = int(min_comments)
        self.logger = logger
        print("Retrieving data from Fritz!Box..")
        self.pb = Phonebook(address=FRITZ_IP_ADDRESS, user=FRITZ_USERNAME, password=FRITZ_PASSWORD)
        self.init_onb()
        self.set_area_and_country_code()
        for pb_id in self.whitelist_pbids + self.blacklist_pbids + [self.blocklist_pbid]:
            if pb_id not in self.pb.phonebook_ids:
                raise Exception(f'The phonebook_id {pb_id} does not exist!')
        self.whitelist = self.get_number_name_dict_for_pb_ids(self.whitelist_pbids)
        self.blacklist = self.get_number_name_dict_for_pb_ids(self.blacklist_pbids)
        area_name = self.area['name'] if self.area else 'UNKNOWN'
        print(f'Call blocker initialized.. '
              f'country_code:{self.country_code} area_code:{self.area_code} area_name:{area_name} '
              f'whitelisted:{len(self.whitelist)} blacklisted:{len(self.blacklist)}')

    def get_number_name_dict_for_pb_ids(self, pb_ids):
        """ Retrieve and concatenate number-name-dicts for several phonebook ids. """
        number_name_dict = dict()
        for pb_id in pb_ids:
            number_name_dict.update(self.pb.get_all_numbers(pb_id))  # [{Number: Name}, ..]
        return number_name_dict

    def set_area_and_country_code(self):
        """ Retrieve area and country code via the Fritzbox. """
        res = self.pb.fc.call_action('X_VoIP', 'X_AVM-DE_GetVoIPCommonAreaCode')
        self.area_code = res['NewX_AVM-DE_OKZPrefix'] + res['NewX_AVM-DE_OKZ']
        res = self.pb.fc.call_action('X_VoIP', 'X_AVM-DE_GetVoIPCommonCountryCode')
        self.country_code = res['NewX_AVM-DE_LKZPrefix'] + res['NewX_AVM-DE_LKZ']
        self.area = self.onb_dict[self.area_code] if self.area_code in self.onb_dict else None

    def init_onb(self):
        """ Read the area codes into a dict. provided by BNetzA as CSV, separated by ';'. """
        self.onb_dict = dict()
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

            # Simulate similar logging style to call monitor
            dt = datetime.today().strftime('%d.%m.%y %H:%M:%S')

            number = cm_line.caller
            # Number can be with area_code or without! Both variants can be in phonebook, too..
            number_variant = number  # Only used for search in whitelist or blacklist
            if number.startswith(self.area_code):
                number_variant = number.replace(self.area_code, '')  # Number wo AC
            if number.startswith('0'):
                full_number = number
            else:
                number_variant = self.area_code + number
                full_number = number_variant

            # 1. Is either full number 071..123... or short number 123... in the whitelist?
            if number in self.whitelist.keys() or number_variant in self.whitelist.keys():
                log_str = f'{dt};WHITELISTED:{full_number};'
                log.debug(log_str)
                print(log_str)
                if self.logger:
                    self.logger(log_str)
                return

            # 2. Already in blacklist? Unsure, if short numbers can happen here, too?
            if number in self.blacklist.keys() or number_variant in self.blacklist.keys():
                log_str = f'{dt};BLACKLISTED:{full_number};'
                log.debug(log_str)
                print(log_str)
                if self.logger:
                    self.logger(log_str)
                return

            # 3. Get ratio for full_number
            ci = CallerInfo(full_number)
            score_str = f'name:{ci.name};score:{ci.score};comments:{ci.comment_count};searches:{ci.searches};'

            # 4. Block if bad ratio
            if ci.score >= self.min_score and ci.comment_count >= self.min_comments:
                name = "[CallBlocker] " + ci.name
                result = self.pb.add_contact(self.blocklist_pbid, name, full_number)
                if result:  # If not {} returned, it's an error
                    print(result)
                action = "BLOCKED"
            else:
                action = "PASSED"
            log_str = f'{dt};{action}:{full_number};{score_str}'
            log.debug(log_str)
            print(log_str)
            if self.logger:
                self.logger(log_str)


if __name__ == "__main__":
    # Quick example how to use only
    cb_log = CallBlockerLog(daily=True, anonymize=False)
    cb = CallBlocker(whitelist_pbids=[0], blacklist_pbids=[1, 2], blocklist_pbid=2,
                     min_score=6, min_comments=3, logger=cb_log.log_line)
    cm_log = CallMonitorLog(daily=True, anonymize=False)
    cm = CallMonitor(logger=cm_log.log_line, parser=cb.parse_and_examine_line)

    # Provoke whitelist test
    # test_line = '17.06.20 10:28:29;RING;0;07191952xxx;69xxx;SIP0;'
    # cb.parse_and_examine_line(test_line)
    # Provoke blacklist test
    # test_line = '17.06.20 10:28:29;RING;0;0781968053101;69xxx;SIP0;'
    # cb.parse_and_examine_line(test_line)

    # cm.stop()
