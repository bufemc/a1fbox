#!/usr/bin/python3

import json5
import logging
from enum import Enum

import requests

logging.basicConfig(level=logging.WARNING)
log = logging.getLogger(__name__)

UNKNOWN_NAME = 'UNKNOWN'
UNKNOWN_LOCATION = 'UNKNOWN'
UNRESOLVED_PREFIX_NAME = 'UNRESOLVED'  # Dependency: callprefix & ONB/RNB!
UNRESOLVED_PREFIX_CODE = 'UNRESOLVED'
UNRESOLVED_PREFIX_KIND = 'UNRESOLVED'

session = requests.session()  # Re-use for wemgehoert.de, ToDo: should be a singleton for the class


class CallInfoType(Enum):
    """ Which method has been used to enrich the data, if none it's 0. For name use CallInfoType(index).name. """

    INIT = 0
    TELLOWS_SCORE = 1
    WEMGEHOERT_SCORE = 2
    REV_SEARCH = 100
    CASCADE = 101


class CallInfo:
    """ Retrieve details for a phone number. Currently scoring via Tellows or naming a number via reverse search. """

    def __init__(self, number, name=None, location=None, cp=None):
        """ Might enrich information about a phone number. Caches not used yet. """
        self.number = number
        self.cp = cp if cp else None
        self.name = name if name else UNKNOWN_NAME
        self.location = location if location else UNKNOWN_LOCATION
        self.prefix_name = UNRESOLVED_PREFIX_NAME
        self.prefix_code = UNRESOLVED_PREFIX_CODE
        self.prefix_kind = UNRESOLVED_PREFIX_KIND
        self.method = CallInfoType.INIT.value

    def get_cascade_score(self):
        """ Combine tellows, wemgehoert and rev search. If tellows score is <= 5, try also wemgehoert.de.
        If name of rev search is longer than the one returned from tellows, first will be used. """
        self.get_revsearch_info()
        rev_name = self.name
        self.get_tellows_score()
        if len(rev_name) > len(self.name):
            self.name = rev_name
        # If Tellows has no information or the name is UNKNOWN, try also WemGehoert.de
        # Deactivated ATM, as too many captchas required
        # if self.score == 5 and self.name == UNKNOWN_NAME:
        #     self.get_wemgehoert_score()
        # If CallPrefix has been passed in Init use it to improve location and kind
        if self.cp:
            self.get_prefix_dict(update_unknown_location=True, update_unknown_name=False)
        self.method = CallInfoType.CASCADE.value  # Has to be overrided at the end

    def get_prefix_dict(self, update_unknown_location=True, update_unknown_name=False):
        """ Will use CallPrefix class to retrieve location, name, code, kind. Examples:
        {'code': '07191', 'name': 'Backnang', 'kind': <CallPrefixType.DE_LANDLINE: 1>} or
        {'code': '0175', 'name': 'Telekom Deutschland GmbH', 'kind': <CallPrefixType.DE_MOBILE: 10>}. """
        res = self.cp.get_prefix_dict(self.number)
        if update_unknown_location and self.location == UNKNOWN_LOCATION:
            self.location = res['name']
        if update_unknown_name and self.name == UNKNOWN_NAME:
            self.name = res['name']
        self.prefix_name = res['name']
        self.prefix_code = res['code']
        self.prefix_kind = res['kind']

    def get_location(self, unknown_only=True):
        """ Fallback to retrieve location by using ONB list. Optionally only if not retrieved otherwise before.
        Obsolete if you use get_prefix_dict, will also set the location. """
        if unknown_only and self.location != UNKNOWN_LOCATION:
            return
        elif self.cp:  # Only if callprefix has been passed in init
            self.location = self.cp.get_prefix_name(self.number)

    def get_tellows_score(self):
        """ Do scoring for a phone number via Tellows - extract score, comments, build a name:
        https://blog.tellows.de/2011/07/tellows-api-fur-die-integration-in-eigene-programme/ -
        use only if country is in list of https://www.tellows.de/api/getsupportedcountries ?
        Unfortunately the company name is missing in JSON/XML output, but present in HTML? """
        self.method = CallInfoType.TELLOWS_SCORE.value
        url = f'http://www.tellows.de/basic/num/{self.number}?json=1&partner=test&apikey=test123'
        try:
            req = requests.get(url)
            req.raise_for_status()

            obj = req.json()['tellows']
            self.score = int(obj['score'])
            self.comments = int(obj['comments'])
            self.searches = obj['searches']
            self.location = obj['location']

            caller_name = ''
            if 'numberDetails' in obj and 'name' in obj['numberDetails']:
                caller_name = obj['numberDetails']['name']

            if 'callerNames' in obj and 'caller' in obj['callerNames']:
                caller_name = obj['callerNames']['caller'][0]

            # Build smarter name, iff name can be retrieved: "name, location"
            if not caller_name:
                if 'callerTypes' in obj:
                    if 'caller' in obj['callerTypes']:
                        for name_count in obj['callerTypes']['caller']:
                            if name_count['name'] == 'Unbekannt':
                                continue
                            caller_name = name_count['name']
                            break  # Stop for first meaningful name
            # Do not set just the location, this is the task of ONB/RNB etc. "T-Mobile" is reported as location..
            if caller_name:
                self.name = f'{caller_name}, {self.location}'
        except requests.exceptions.HTTPError as err:
            log.warning(err)

    def get_wemgehoert_score(self):
        """ Do scoring for a phone number via wemgehoert.de - extract percentage as score. CURRENTLY DOES NOT WORK! """
        self.method = CallInfoType.WEMGEHOERT_SCORE.value
        url = f'https://www.wemgehoert.de/nummer/{self.number}'

        headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/86.0.4240.111 Safari/537.36",
            "Accept-Encoding": "gzip, deflate, br",
            "Accept-Language": "de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7",
        }

        try:
            req = session.get(url, headers=headers)
            req.raise_for_status()
            content = req.text
            # Extract 84 from e.g. <div id="progress-bar-inner" class="progress-bar-rank5">84</div>
            str_begin = '<div id="progress-bar-inner" class="progress-bar-rank'  # followed by 1"> or 5"> etc.
            str_end = '</div>'
            pos_1 = content.find(str_begin)
            if pos_1 != -1:
                content = content[pos_1 + len(str_begin) + 3:]
                pos_n = content.find(str_end)
                if pos_n != -1:
                    content = content[:pos_n]
                    self.score = round(int(content) / 10)  # e.g. 84% becomes score = 8
        except requests.exceptions.HTTPError as err:
            log.warning(err)

    def get_numreport_name(self):
        """ PLANNED: POST SearchForm[phone]=07191xxx to https://de.numreport.com/site/search ..
        follow redirect, then grab e.g. from data-name="Kaufland Backnang".
        Requires _csrf from e.g. https://de.numreport.com/ and there <input type="hidden" name="_csrf" value="..",
        and many other checks are done (origin/referer?), returns otherwise http 400. """
        pass

    def get_revsearch_info(self):
        """ Do reverse search via DasOertliche, currently ugly parsing, which might fail if name has commas? """
        self.method = CallInfoType.REV_SEARCH.value
        code_2020 = False
        if code_2020:
            url = f'https://www.dasoertliche.de/Controller?form_name=search_inv&ph={self.number}'
        else:
            url = f'https://www.dasoertliche.de/rueckwaertssuche/?ph={self.number}&pa=&address='
        try:
            req = requests.get(url)
            req.raise_for_status()
            content = req.text

            if code_2020:
                # Extract only the javascript line "handlerData", precisely the content between [[ .. ]
                str_begin = 'var handlerData = [['
                str_end = ']'  # Ends with ]] if one match only, but can contain several names, e.g. 071919524xx
                pos_1 = content.find(str_begin)
                if pos_1 != -1:
                    content = content[pos_1 + len(str_begin):]
                    pos_n = content.find(str_end)
                    if pos_n != -1:
                        content = content[:pos_n]
                        parts = content.split(',')
                        city = parts[5].strip("' ")  # "ci" in source view
                        name = parts[14].strip("' ")  # "na" in source view
                        self.name = name + ", " + city
                        # self.location = city

            else:
                str_begin = 'generic: {'
                str_end = '}'
                pos_1 = content.find(str_begin)
                if pos_1 != -1:
                    content = content[pos_1 + len(str_begin)-1:]
                    pos_n = content.find(str_end)
                    if pos_n != -1:
                        content = content[:pos_n+1]
                        # Convert to valid JSON, either manually or by using json5 instead of json
                        # content = re.sub('(?i)([a-z_].*?):', r'"\1":', content)
                        res = json5.loads(content)
                        city = res['city']
                        name = res['name']
                        # More data would be available: street, zip, phones, email
                        self.name = name + ", " + city
                        # self.location = city

        except requests.exceptions.HTTPError as err:
            log.warning(err)

    def __str__(self, add_link=True, add_kind=True, add_method=True):
        """ To relevant properties shortened output. ToDo: output the full prefix dict? """
        start = f'number:{self.number} name:{self.name} location:{self.location}'
        if add_kind:
            start = f'{start} kind:{self.prefix_kind}'
        if add_link:
            start = f'{start} link:http://www.google.com/search?q={self.number}'
        if add_method:
            start = f'{start} method:{CallInfoType(self.method).name}'
        if int(self.method) in [CallInfoType.TELLOWS_SCORE.value, CallInfoType.WEMGEHOERT_SCORE.value,
                                CallInfoType.CASCADE.value]:
            return f'{start} score:{self.score}'
        else:
            return start


if __name__ == "__main__":
    # Quick example how to use only
    # Warning: the object ci is re-used here all the time, but not reverted, should be solved better in unit tests.

    from time import sleep

    # Initialize by using parameters from config file
    from fritzconn import FritzConn
    from callprefix import CallPrefix, CallPrefixType
    fritzconn = FritzConn()
    cp = CallPrefix(fc=fritzconn)


    # Testing CallInfo with using CallPrefix
    print("\nTest by including CallPrefix:\n")

    number = "07191000"  # Fake number just to test call prefix location resolving
    ci = CallInfo(number, cp=cp)
    ci.get_cascade_score()
    print(ci)
    assert ci.method == CallInfoType.CASCADE.value
    assert ci.location == 'Backnang'
    assert ci.prefix_name == 'Backnang'
    assert ci.prefix_code == '07191'
    assert ci.prefix_kind == CallPrefixType.DE_LANDLINE

    number = "0175000"  # Fake number just to test call prefix type resolving
    ci = CallInfo(number, cp=cp)
    ci.get_cascade_score()
    print(ci)
    assert ci.method == CallInfoType.CASCADE.value
    assert ci.location == 'T-Mobile'
    assert ci.prefix_name == 'Telekom Deutschland GmbH'
    assert ci.prefix_code == '0175'
    assert ci.prefix_kind == CallPrefixType.DE_MOBILE

    sleep(1)  # tellows rate limiting, throws 429 Client Error: Too Many Requests for url

    # Testing CallInfo WITHOUT CallPrefix
    print("\nTest by using CallInfo alone, without CallPrefix:\n")

    number = "004922189920"  # BzGA

    ci = CallInfo(number)
    print(ci)
    assert ci.method == CallInfoType.INIT.value

    ci = CallInfo(number)
    ci.get_tellows_score()
    print(ci)
    assert ci.method == CallInfoType.TELLOWS_SCORE.value

    ci = CallInfo(number)
    ci.get_wemgehoert_score()
    print(ci)
    assert ci.method == CallInfoType.WEMGEHOERT_SCORE.value

    ci = CallInfo(number)
    ci.get_revsearch_info()
    print(ci)
    assert ci.method == CallInfoType.REV_SEARCH.value

    ci = CallInfo(number)
    ci.get_cascade_score()
    print(ci)
    assert ci.method == CallInfoType.CASCADE.value
