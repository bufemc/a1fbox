import logging

import requests
from callmonitor import CallMonitor, CallMonitorType, CallMonitorLine, CallMonitorLog
from config import FRITZ_IP_ADDRESS, FRITZ_USERNAME, FRITZ_PASSWORD
from phonebook import Phonebook

logging.basicConfig(level=logging.WARNING)
log = logging.getLogger(__name__)


class CallBlocker:
    def __init__(self, whitelist_pbid, blacklist_pbid, area_code, min_score=6, min_comments=3):
        self.whitelist_pbid = whitelist_pbid
        self.blacklist_pbid = blacklist_pbid
        self.area_code = area_code
        self.min_score = min_score
        self.min_comments = min_comments
        self.pb = Phonebook(address=FRITZ_IP_ADDRESS, user=FRITZ_USERNAME, password=FRITZ_PASSWORD)
        self.whitelist = self.pb.get_all_numbers(self.whitelist_pbid)  # [{Number: Name}, ..]
        self.blacklist = self.pb.get_all_numbers(self.blacklist_pbid)  # [{Number: Name}, ..]
        print("Call blocker initialized..")

    def parse_and_examine_line(self, raw_line):
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
                return

            # 2. Already in blacklist?
            if full_number in self.blacklist.keys():
                log.warning(f'{number} in blacklist, skipping..')
                return

            # 3. Get ratio for full_number
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

            # 4. Block if bad ratio
            if score >= self.min_score and comment_count >= self.min_comments:
                # ToDo: try to build a smarter name, e.g. add first callerTypes":{"caller":[{"name" .. if != Unbekannt
                name = f'CallBlock {location} ({searches})'
                result = self.pb.add_contact(self.blacklist_pbid, name, full_number)
                if result:
                    print(result)
                print(f'{full_number} BLOCKED')


if __name__ == "__main__":
    # Quick example how to use only

    # Area code could maybe be retrieved via Telefonie->Eigene Rufnummern->Anschlusseinstellungen
    # X_AVM-DE_GetVoIPCommonAreaCode (x_voip)

    cb = CallBlocker(whitelist_pbid=0, blacklist_pbid=2, area_code='07191', min_score=6, min_comments=3)
    cm_log = CallMonitorLog(daily=True, anonymize=False)
    cm = CallMonitor(logger=cm_log.log_line, parser=cb.parse_and_examine_line)

    # Provoke by test
    # test_line = '17.06.20 10:28:29;RING;0;0781968053101;69xxx;SIP0;'
    # cb.parse_and_examine_line(test_line)
