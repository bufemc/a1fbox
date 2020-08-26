#!/usr/bin/python3

import csv
import json
import logging
import os
from enum import Enum

from fritzconn import FritzConn

logging.basicConfig(level=logging.WARNING)
log = logging.getLogger(__name__)

ONB_FILE = os.path.join(os.path.dirname(__file__), '../data/onb.csv')
RNB_FILE = os.path.join(os.path.dirname(__file__), '../data/rnb.csv')

COUNTRY_NAMES_FILE = os.path.join(os.path.dirname(__file__), '../data/countryio-names.json')
COUNTRY_CODES_FILE = os.path.join(os.path.dirname(__file__), '../data/countryio-phone.json')


class CallPrefixType(Enum):
    """ Distinguish the prefix types. """

    UNKNOWN = 0
    DE_LANDLINE = 1
    DE_LANDLINE_INACTIVE = 2
    DE_MOBILE = 10
    DE_SPECIAL = 20
    INT_SPECIAL = 21
    DE_FREEPHONE = 30
    INT_FREEPHONE = 31
    DE_PAYPHONE = 40
    DE_RESERVE = 50
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
        self.country_code_dict = self.get_prefix_dict(self.country_code)
        self.country_code_name = self.get_prefix_name(self.country_code)

    def add_prefix(self, area_code, name, kind):
        self.prefix_dict[area_code] = {'code': area_code, 'name': name, 'kind': kind}

    def init_prefix_dict(self):
        """ Read the area codes into a dict. ONB provided by BNetzA as CSV, separated by ';', RNB created manually.
        And country codes. Detect type by kind. Initialize with German prefix codes not available as JSON/CSV. """
        self.prefix_dict = dict()

        # Special prefixes in Germany and later international - taken German wording from:
        # https://www.bundesnetzagentur.de/DE/Sachgebiete/Telekommunikation/Unternehmen_Institutionen/Nummerierung/Rufnummern/Rufnummern_node.html
        self.add_prefix('0800', 'FreePhone-0800-Germany', CallPrefixType.DE_FREEPHONE)
        self.add_prefix('010', 'Betreiberkennzahlen für Betreiberauswahl oder -vorauswahl', CallPrefixType.DE_SPECIAL)
        self.add_prefix('018', 'Nationale virtuelle Private Netze (VPN)', CallPrefixType.DE_SPECIAL)
        self.add_prefix('0700', 'Persönliche Rufnummern', CallPrefixType.DE_SPECIAL)  # DE_PAYPHONE if forwarded
        self.add_prefix('031', 'Testrufnummern', CallPrefixType.DE_SPECIAL)
        self.add_prefix('032', 'Nationale Teilnehmerrufnummern', CallPrefixType.DE_SPECIAL)

        # Extra payment: https://www.verivox.de/internet/themen/sonderrufnummern/
        self.add_prefix('019', 'Online-Dienste und Verkehrslenkung', CallPrefixType.DE_PAYPHONE)
        self.add_prefix('0900', 'Premium-Dienste', CallPrefixType.DE_PAYPHONE)
        self.add_prefix('09009', 'Anwählprogramme (Dialer)', CallPrefixType.DE_PAYPHONE)
        self.add_prefix('0137', 'Kurzzeitiger Massenverkehr', CallPrefixType.DE_PAYPHONE)
        self.add_prefix('0180', 'Service-Dienste', CallPrefixType.DE_PAYPHONE)

        # As longer numbers like 0175 are found first, this is just a fallback
        for area_code in ['015', '016', '017']:
            self.add_prefix(area_code, 'Mobile Dienste', CallPrefixType.DE_MOBILE)

        # International special numbers
        self.add_prefix('00800', 'FreePhone-00800-International', CallPrefixType.INT_FREEPHONE)
        self.add_prefix('001800', 'FreePhone-001800-International', CallPrefixType.INT_FREEPHONE)
        self.add_prefix('0181', 'Internationale virtuelle private Netze (VPN)', CallPrefixType.INT_SPECIAL)

        # More German prefixes found here:
        # https://www.bundesnetzagentur.de/SharedDocs/Downloads/DE/Sachgebiete/Telekommunikation/Unternehmen_Institutionen/Nummerierung/Rufnummern/NP_Nummernraum.pdf?__blob=publicationFile&v=3
        self.add_prefix('0115', 'Behoerdenruf, internationaler Zugang', CallPrefixType.DE_SPECIAL)
        self.add_prefix('0116', 'Harmonisierte Dienste von sozialem Wert, internationaler Zugang',
                        CallPrefixType.DE_SPECIAL)
        self.add_prefix('0118', 'Vermittlungsdienste, internationaler Zugang', CallPrefixType.DE_SPECIAL)

        for area_code in ['011', '012', '013', '014', '019',
                          '0161', '0165', '0166', '0167',
                          '0312', '0313', '0314', '0315', '0316', '0317', '0318', '0319',
                          '0500', '0501', '0701', '0801', '0901', '0902',
                          '09000', '09002', '09004', '09006', '09007', '09008']:
            self.add_prefix(area_code, 'Reserve', CallPrefixType.DE_RESERVE)

        for area_code in ['0164', '0168', '0169']:
            self.add_prefix(area_code, 'e*Message Wireless Information Services Deutschland GmbH (Funkruf)',
                            CallPrefixType.DE_SPECIAL)

        self.add_prefix('0199', 'Verkehrslenkungsnummern für netzinterne Verkehrslenkung', CallPrefixType.DE_SPECIAL)

        # Landline prefixes for Germany, including CSV header, see https://tinyurl.com/y7648pc9
        with open(ONB_FILE, encoding='utf-8') as csv_file:
            csvreader = csv.reader(csv_file, delimiter=';')
            for i, row in enumerate(csvreader):
                if i == 0:
                    # This is for prevention only, if the order is changed it will fail here intentionally
                    assert row[0] == 'Ortsnetzkennzahl'
                    assert row[1] == 'Ortsnetzname'
                    assert row[2] == 'KennzeichenAktiv'
                    continue
                if len(row) == 3:  # Prevent processing last line, which is ['\x1a']
                    area_code = '0' + row[0]
                    name = row[1]
                    kind = CallPrefixType.DE_LANDLINE if row[2] == '1' else CallPrefixType.DE_LANDLINE_INACTIVE
                    self.add_prefix(area_code, name, kind)

        # Mobile prefixes for Germany, no CSV header
        with open(RNB_FILE, encoding='utf-8') as csv_file:
            csvreader = csv.reader(csv_file, delimiter=';')
            for row in csvreader:
                if len(row) == 2:
                    area_code = row[0].replace('-', '').replace('(0)', '0')
                    name = row[1]
                    kind = CallPrefixType.DE_MOBILE
                    self.add_prefix(area_code, name, kind)

        # Country code prefixes: combine iso2_code, prefix_code and country_name
        with open(COUNTRY_CODES_FILE, encoding='utf-8') as json_file:
            iso2_code_dict = json.load(json_file)  # ISO2-name: number, e.g. "BB": "+1-246" or "DO": "+1-809 and 1-829"

        with open(COUNTRY_NAMES_FILE, encoding='utf-8') as json_file:  # ISO2-name: name, e.g. "DE": "Germany"
            iso2_name_dict = json.load(json_file)

        cc_name_dict = {}
        for iso2, code in iso2_code_dict.items():
            if code.strip():  # Few iso2 have NO codes, like BV, GS, HM (has " "), XK, TF, AQ
                name = iso2_name_dict[iso2]
                code = code.replace('+', '').replace('-', '')
                # Special cases: "1787 and 1939": "Puerto Rico" & "1809 and 1829": "Dominican Republic"
                if " and " in code:
                    codes = code.split(" and ")
                else:
                    codes = [code]
                for code in codes:
                    #  Several matches like '1': 'Canada, United States, United States Minor Outlying Islands'
                    if code in cc_name_dict:
                        name = cc_name_dict[code] + ", " + name
                    cc_name_dict[code] = name

        kind = CallPrefixType.COUNTRY
        for cc, name in cc_name_dict.items():
            code = '00' + cc
            self.add_prefix(code, name, kind)

    def get_prefix_dict(self, number):
        """ Return a dict for a prefix, with code, name, kind (DE_landline, DE_mobile, abroad). """
        if self.country_code != '0049':
            log.warning('This method could return wrong prefix names if used outside Germany!')
        # "0049" is Germany, but "00497191" should get converted to "07191"
        if number.startswith(self.country_code) and len(number) > len(self.country_code):
            number = '0' + number.replace(self.country_code, '')
        # In Germany landline area codes are exclusive, either 3 (030 Berlin), 4 (0201 Essen), but most are 5 digits
        # (07151 Waiblingen). Mobile area codes can even have 6 digits, e.g. TelcoVillage, but are rare.
        # Country codes: min 3 digits, like "001", max is Jersey with 8 digits: 00441534. 0035818 has 7 digits.
        for prefix in [number[:8], number[:7], number[:6], number[:5], number[:4], number[:3]]:
            if prefix in self.prefix_dict:
                return self.prefix_dict[prefix]
        return None

    def get_prefix_name(self, number):
        """ Return name for a prefix, if found, else None. """
        prefix_dict = self.get_prefix_dict(number)
        if prefix_dict:
            return prefix_dict['name']
        else:
            return None

    # Further ideas: do auto download und double unzip of onb csv?


if __name__ == "__main__":
    # Quick example how to use only

    # Initialize by using parameters from config file
    fritzconn = FritzConn()
    cp = CallPrefix(fc=fritzconn)

    number = "07191"
    res = cp.get_prefix_dict(number)
    assert res['name'] == 'Backnang'
    assert res['kind'] == CallPrefixType.DE_LANDLINE
    res = cp.get_prefix_name(number)
    assert res == 'Backnang'

    number = "0175"
    res = cp.get_prefix_dict(number)
    assert res['kind'] == CallPrefixType.DE_MOBILE

    number = "0049"
    res = cp.get_prefix_dict(number)
    assert res['name'] == 'Germany'
    assert res['kind'] == CallPrefixType.COUNTRY

    number = "00226"
    res = cp.get_prefix_dict(number)
    assert res['name'] == 'Burkina Faso'
    assert res['kind'] == CallPrefixType.COUNTRY

    # Edge case: max 8 digits
    number = "00441534"
    res = cp.get_prefix_dict(number)
    assert res['name'] == 'Jersey'
    assert res['kind'] == CallPrefixType.COUNTRY

    # Edge case: 7 digits
    number = "0035818"
    res = cp.get_prefix_dict(number)
    assert res['name'] == 'Aland Islands'
    assert res['kind'] == CallPrefixType.COUNTRY

    # Combination: country code and local area code
    number = "00497191"
    res = cp.get_prefix_dict(number)
    assert res['name'] == 'Backnang'
    assert res['kind'] == CallPrefixType.DE_LANDLINE

    # Special numbers
    number = "0800"
    res = cp.get_prefix_dict(number)
    assert res['name'] == 'FreePhone-0800-Germany'
    assert res['kind'] == CallPrefixType.DE_FREEPHONE

    number = "09008"
    res = cp.get_prefix_dict(number)
    assert res['name'] == 'Reserve'
    assert res['kind'] == CallPrefixType.DE_RESERVE
