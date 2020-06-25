import logging
import requests

logging.basicConfig(level=logging.WARNING)
log = logging.getLogger(__name__)


class CallInfo:
    """ Retrieve details for a phone number. Currently scoring via Tellows. Could get score from a dict (caching). """

    def __init__(self, number):
        """ Might enrich information about a phone number. Caches not used yet. RevSearch not implemented yet. """
        self.number = number
        self.name = 'UNKNOWN'
        self.method = 0

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
            self.method = 1
        except requests.exceptions.HTTPError as err:
            log.warning(err)

    def get_revsearch_info(self):
        """ Do reverse search via DasOertliche, currently ugly parsing, which might fail if name has commas? """
        url = f'https://www.dasoertliche.de/Controller?form_name=search_inv&ph={self.number}'
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
                self.method = 2
        except requests.exceptions.HTTPError as err:
            log.warning(err)

    def __str__(self):
        """ To relevant properties shortened output. """
        start = f'number:{self.number} name:{self.name}'
        if int(self.method) == 1:
            return f'{start} score:{self.score}'
        else:
            return start


if __name__ == "__main__":
    # Quick example how to use only
    number = "022189920"
    ci = CallInfo(number)
    ci.get_tellows_score()
    print(ci)
    ci.get_revsearch_info()
    print(ci)
