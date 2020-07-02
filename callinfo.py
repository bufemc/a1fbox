import logging
from enum import Enum

import requests

logging.basicConfig(level=logging.WARNING)
log = logging.getLogger(__name__)


class CallInfoType(Enum):
    """ Which method has been used to enrich the data, if none it's 0. """

    INIT = 0
    TELLOWS_SCORE = 1
    TEL_AND_REV = 2
    REV_SEARCH = 3


class CallInfo:
    """ Retrieve details for a phone number. Currently scoring via Tellows or naming a number via reverse search. """

    def __init__(self, number, unknown_name='UNKNOWN'):
        """ Might enrich information about a phone number. Caches not used yet. """
        self.number = number
        self.name = unknown_name
        self.method = CallInfoType.INIT.value

    def get_tellows_and_revsearch(self):
        """ Combine tellows and rev search. If name of rev search is longer than tellows, it will be used. """
        self.get_revsearch_info()
        rev_name = self.name
        self.get_tellows_score()
        if len(rev_name) > len(self.name):
            self.name = rev_name
        self.method = CallInfoType.TEL_AND_REV.value

    def get_tellows_score(self):
        """ Do scoring for a phone number via Tellows - extract score, comments, build a name:
        https://blog.tellows.de/2011/07/tellows-api-fur-die-integration-in-eigene-programme/ """
        url = f'http://www.tellows.de/basic/num/{self.number}?json=1&partner=test&apikey=test123'
        try:
            req = requests.get(url)
            req.raise_for_status()

            obj = req.json()['tellows']
            self.score = int(obj['score'])
            self.comments = int(obj['comments'])
            self.searches = obj['searches']
            self.location = obj['location']

            # Build smarter name, iff name can be retrieved: "name, location"
            caller_name = ''
            if 'callerTypes' in obj:
                if 'caller' in obj['callerTypes']:
                    for name_count in obj['callerTypes']['caller']:
                        if name_count['name'] == 'Unbekannt':
                            continue
                        caller_name = name_count['name'] + ', '
                        break  # Stop for first meaningful name
            self.name = f'{caller_name}{self.location}'
            self.method = CallInfoType.TELLOWS_SCORE.value
        except requests.exceptions.HTTPError as err:
            log.warning(err)

    def get_revsearch_info(self):
        """ Do reverse search via DasOertliche, currently ugly parsing, which might fail if name has commas? """
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
                    self.method = CallInfoType.REV_SEARCH.value
        except requests.exceptions.HTTPError as err:
            log.warning(err)

    def __str__(self):
        """ To relevant properties shortened output. """
        start = f'number:{self.number} name:{self.name}'
        if int(self.method) in [CallInfoType.TELLOWS_SCORE.value, CallInfoType.TEL_AND_REV.value]:
            return f'{start} score:{self.score}'
        else:
            return start


if __name__ == "__main__":
    # Quick example how to use only
    number = "022189920"  # BzGA
    ci = CallInfo(number)
    assert(ci.method == CallInfoType.INIT.value)
    print(ci)
    ci.get_tellows_score()
    assert (ci.method == CallInfoType.TELLOWS_SCORE.value)
    print(ci)
    ci.get_revsearch_info()
    assert (ci.method == CallInfoType.REV_SEARCH.value)
    print(ci)
    ci.get_tellows_and_revsearch()
    assert (ci.method == CallInfoType.TEL_AND_REV.value)
    print(ci)
