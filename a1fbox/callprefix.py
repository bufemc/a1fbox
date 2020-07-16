import csv
import logging
from enum import Enum

logging.basicConfig(level=logging.WARNING)
log = logging.getLogger(__name__)


class CallPrefixType(Enum):
    """ Distinguish the prefix types. Not used yet. """

    LANDLINE = 0
    MOBILE = 1
    OTHER = 2
    COUNTRY = 99


# class CallPrefix:
#    """ Should a call prefix be an instance of this instead, the other class be renamed to e.g. CallPrefixManager? """


# class CallPrefixFritzbox:
#     """ Only used for retrieving Fritzbox's country and area code. """
#     def __init__(self, fc):
#         """ Provide a fc = fritz connection, required to retrieve area and country code. """
#         self.fc = fc


class CallPrefix:
    """ Rename to Manager? Retrieves country code, area code from Fritzbox and provides German area codes plus country codes. """

    def __init__(self, fc):
        """ Provide a fc = fritz connection, required to retrieve area and country code. """
        self.fc = fc
        self.init_prefix_dict()
        self.init_area_and_country_code()

    def init_area_and_country_code(self):
        """ Retrieve area and country code via the Fritzbox. Prefixes have to be loaded before. """
        res = self.fc.call_action('X_VoIP', 'X_AVM-DE_GetVoIPCommonAreaCode')
        self.area_code = res['NewX_AVM-DE_OKZPrefix'] + res['NewX_AVM-DE_OKZ']
        res = self.fc.call_action('X_VoIP', 'X_AVM-DE_GetVoIPCommonCountryCode')
        self.country_code = res['NewX_AVM-DE_LKZPrefix'] + res['NewX_AVM-DE_LKZ']
        self.area_code_dict = self.get_prefix_dict(self.area_code)
        self.area_code_name = self.get_prefix_name(self.area_code)

    def init_prefix_dict(self):
        """ Read the area codes into a dict. ONB provided by BNetzA as CSV, separated by ';', RNB created manually. """
        self.prefix_dict = dict()

        # Landline prefixes for Germany, including CSV header, see https://tinyurl.com/y7648pc9
        with open('../data/onb.csv', encoding='utf-8') as csvfile:
            csvreader = csv.reader(csvfile, delimiter=';')
            for i, row in enumerate(csvreader):
                if i == 0:
                    # This is for prevention only, if the order is changed it will fail here intentionally
                    assert (row[0] == 'Ortsnetzkennzahl')
                    assert (row[1] == 'Ortsnetzname')
                    assert (row[2] == 'KennzeichenAktiv')
                    continue
                if len(row) == 3:  # Last line is ['\x1a']
                    area_code = '0' + row[0]
                    name = row[1]
                    active = True if row[2] == '1' else False
                    self.prefix_dict[area_code] = {'code': area_code, 'name': name, 'active': active, 'mobile': False}

        # Mobile prefixes for Germany, no CSV header
        with open('../data/rnb.csv', encoding='utf-8') as csvfile:
            csvreader = csv.reader(csvfile, delimiter=';')
            for row in csvreader:
                if len(row) == 2:
                    area_code = row[0].replace('-', '').replace('(0)', '0')
                    name = row[1]
                    self.prefix_dict[area_code] = {'code': area_code, 'name': name, 'active': True, 'mobile': True}

        # ToDo: country code prefixes? Combine phone - iso2 - country name!

    def get_prefix_dict(self, number):
        """ Return a dict for a prefix, with code, name, active, mobile. """
        if self.country_code != '0049':
            log.warning('This method could return wrong prefix names if used outside Germany!');
        # In Germany landline area codes are exclusive, either 3 (030 Berlin), 4 (0201 Essen), but most are 5 digits
        # (07151 Waiblingen). Mobile area codes can even have 6 digits, e.g. TelcoVillage, but are rare.
        for prefix in [number[:6], number[:5], number[:4], number[:3]]:
            if prefix in self.prefix_dict:
                return self.prefix_dict[prefix]
        return None

    def get_prefix_name(self, number):
        """ Return name for a prefix, if found and in Germany. """
        prefix_dict = self.get_prefix_dict(number)
        if prefix_dict:
            return prefix_dict['name']
        elif number.startswith('00'):
            return 'ABROAD'
        else:
            return 'UNKNOWN'

    # Further ideas:
    # do auto download und double unzip of onb csv?
    # get country name? needs another list of country codes, e.g. json files from country.io
