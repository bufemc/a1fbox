import csv
import logging
from enum import Enum

import requests
from callmonitor import CallMonitor, CallMonitorType, CallMonitorLine, CallMonitorLog
from config import FRITZ_IP_ADDRESS, FRITZ_USERNAME, FRITZ_PASSWORD
from log import Log
from phonebook import Phonebook
from utils import anonymize_number

logging.basicConfig(level=logging.WARNING)
log = logging.getLogger(__name__)


class CallBlockerRate(Enum):
    """ Custom blocker rates. Not used yet, as method is sufficient for the method to distinguish rated entries. """

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
        if int(self.method) == 1:  # Rating by Tellows
            self.score, self.comments, self.searches = more[0], more[1], more[2]
        if int(self.method) == 2:  # Reverse search
            raise NotImplementedError

    def __str__(self):
        """ Pretty print a line from call blocker (ignoring method), by considering the method. """
        start = f'date:{self.date} time:{self.time} rate:{self.rate} caller:{self.caller} name:{self.name}'
        if int(self.method) == 1:
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


class CallBlockerInfo:
    """ Retrieve details for a phone number. Currently scoring via Tellows. Could get score from a dict (caching). """

    def __init__(self, number):
        """ Might enrich information about a phone number. Caches not used yet. RevSearch not implemented yet. """
        self.number = number
        self.name = 'UNKNOWN'

    def get_tellows_score(self):
        """ Do scoring for a phone number via Tellows.
        https://blog.tellows.de/2011/07/tellows-api-fur-die-integration-in-eigene-programme/ """
        url = f'http://www.tellows.de/basic/num/{self.number}?json=1&partner=test&apikey=test123'
        try:
            req = requests.get(url)
            req.raise_for_status()
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
                        caller_name = name_count['name'] + ', '
                        break
            self.name = f'{caller_name}{self.location}'
        except requests.exceptions.HTTPError as err:
            log.warning(err)

    def get_revsearch_info(self):
        """ Do reverse search via DasOertliche, currently ugly parsing, which might fail if name has commas? """
        url = f'https://www.dasoertliche.de/Controller?form_name=search_inv&ph={self.number}'
        req = requests.get(url)
        try:
            req = requests.get(url)
            req.raise_for_status()
            content = req.text
            str_begin = 'var handlerData = [['
            str_end = ']]'
            pos_1 = content.find(str_begin)
            if pos_1 != -1:
                content = content[pos_1 + len(str_begin):]
                pos_n = content.find(str_end)
                content = content[:pos_n]
                parts = content.split(',')
                city = parts[5].strip("' ")
                name = parts[14].strip("' ")
                self.name = name + ", " + city
        except requests.exceptions.HTTPError as err:
            log.warning(err)

    def __str__(self):
        return f'number:{self.number} name:{self.name}'


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

    def numbers_in_list(self, numbers, phonelist):
        """ Return first name found for a list of numbers in phone list. """
        for number in numbers:
            if number in phonelist.keys():
                return phonelist[number]
        return None

    def parse_and_examine_line(self, raw_line):
        """ Parse call monitor line, if RING event not in lists, rate and maybe block the number. """
        log.debug(raw_line)
        cm_line = CallMonitorLine(raw_line)
        print(cm_line)

        if cm_line.type == CallMonitorType.RING.value:

            # Simulate similar logging style to call monitor
            # dt = datetime.today().strftime('%d.%m.%y %H:%M:%S')
            dt = cm_line.datetime  # Use same datetime for exact match

            number = cm_line.caller
            number_variant = number  # Only used for search in whitelist or blacklist
            # Number can be with area_code or without! Both variants can be in phonebook, too..
            if number.startswith(self.area_code):
                number_variant = number.replace(self.area_code, '')  # Number without area code
            if number.startswith('0'):
                full_number = number
            else:
                number_variant = self.area_code + number
                full_number = number_variant

            # 1. Is either full number 071..123... or short number 123... in the white- or blacklist?
            name_white = self.numbers_in_list([number, number_variant], self.whitelist)
            name_black = self.numbers_in_list([number, number_variant], self.blacklist)

            if name_white and name_black:
                raise Exception(f'Problem in your phonebooks detected: '
                                f'a number should not be on white- and blacklist. Please fix! Details: '
                                f'whitelist:{name_white} blacklist:{name_black}')

            if name_white or name_black:
                name = name_black if name_black else name_white  # Reason: black might win over white
                rate = 'BLACKLIST' if name_black else 'WHITELIST'
                raw_line = f'{dt};{rate};0;{full_number};"{name}";' + "\n"

            else:
                ci = CallBlockerInfo(full_number)
                ci.get_tellows_score()
                # Adapt to logging style of call monitor. Task of logger to parse the values to keys/names?
                score_str = f'"{ci.name}";{ci.score};{ci.comment_count};{ci.searches};'

                if ci.score >= self.min_score and ci.comment_count >= self.min_comments:
                    name = self.blockname_prefix + ci.name
                    result = self.pb.add_contact(self.blocklist_pbid, name, full_number)
                    if result:  # If not {} returned, it's an error
                        log.warning("Adding to phonebook failed:")
                        print(result)
                    rate = "BLOCK"
                else:
                    rate = "PASS"
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
    cb_log = CallBlockerLog(daily=True, anonymize=False)
    cb = CallBlocker(whitelist_pbids=[0], blacklist_pbids=[1, 2], blocklist_pbid=2,
                     blockname_prefix='[Spam] ', min_score=6, min_comments=3, logger=cb_log.log_line)
    cm_log = CallMonitorLog(daily=True, anonymize=False)
    cm = CallMonitor(logger=cm_log.log_line, parser=cb.parse_and_examine_line)

    # Provoke whitelist test
    # test_line = '17.06.20 10:28:29;RING;0;07191952xxx;69xxx;SIP0;'
    # cb.parse_and_examine_line(test_line)
    # Provoke blacklist test
    # test_line = '17.06.20 10:28:29;RING;0;09912568741596;69xxx;SIP0;'
    # cb.parse_and_examine_line(test_line)
    # cm.stop()
