#!/usr/bin/python3

import logging
from enum import Enum

import requests

logging.basicConfig(level=logging.WARNING)
log = logging.getLogger(__name__)

UNKNOWN_NAME = 'UNKNOWN'
UNKNOWN_LOCATION = 'UNKNOWN'


class CallInfoType(Enum):
    """ Which method has been used to enrich the data, if none it's 0. """

    INIT = 0
    TELLOWS_SCORE = 1
    WEMGEHOERT_SCORE = 2
    REV_SEARCH = 100
    CASCADE = 101


class CallInfo:
    """ Retrieve details for a phone number. Currently scoring via Tellows or naming a number via reverse search. """

    def __init__(self, number, name=None, location=None):
        """ Might enrich information about a phone number. Caches not used yet. """
        self.number = number
        self.name = name if name else UNKNOWN_NAME
        self.location = location if location else UNKNOWN_LOCATION
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
        if self.score == 5 and self.name == UNKNOWN_NAME:
            self.get_wemgehoert_score()
        self.method = CallInfoType.CASCADE.value

    def get_tellows_score(self):
        """ Do scoring for a phone number via Tellows - extract score, comments, build a name:
        https://blog.tellows.de/2011/07/tellows-api-fur-die-integration-in-eigene-programme/ """
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
        """ Do scoring for a phone number via wemgehoert.de - extract percentage as score. """
        self.method = CallInfoType.WEMGEHOERT_SCORE.value
        url = f'https://www.wemgehoert.de/nummer/{self.number}'

        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

        try:
            req = requests.get(url, headers=headers)
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

    def get_revsearch_info(self):
        """ Do reverse search via DasOertliche, currently ugly parsing, which might fail if name has commas? """
        self.method = CallInfoType.REV_SEARCH.value
        url = f'https://www.dasoertliche.de/Controller?form_name=search_inv&ph={self.number}'
        try:
            req = requests.get(url)
            req.raise_for_status()
            content = req.text
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
        except requests.exceptions.HTTPError as err:
            log.warning(err)

    def __str__(self):
        """ To relevant properties shortened output. """
        start = f'number:{self.number} name:{self.name} location:{self.location}'
        if int(self.method) in [CallInfoType.TELLOWS_SCORE.value, CallInfoType.WEMGEHOERT_SCORE.value,
                                CallInfoType.CASCADE.value]:
            return f'{start} score:{self.score}'
        else:
            return start


if __name__ == "__main__":
    # Quick example how to use only
    # Warning: the object ci is re-used here all the time, but not reverted, should be solved better in unit tests.
    number = "004922189920"  # BzGA
    ci = CallInfo(number)
    assert ci.method == CallInfoType.INIT.value
    print(ci)
    ci.get_tellows_score()
    assert ci.method == CallInfoType.TELLOWS_SCORE.value
    print(ci)
    ci.get_wemgehoert_score()
    assert ci.method == CallInfoType.WEMGEHOERT_SCORE.value
    print(ci)
    ci.get_revsearch_info()
    assert ci.method == CallInfoType.REV_SEARCH.value
    print(ci)
    ci.get_cascade_score()
    assert ci.method == CallInfoType.CASCADE.value
    print(ci)
