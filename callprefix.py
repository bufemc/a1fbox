import csv


class CallPrefix:
    """ Provides country code, area code and a list of ONB. """

    def __init__(self, fc):
        """ Mandatory: provide a fc = fritz connection. """
        self.fc = fc
        self.init_onb()
        self.set_area_and_country_code()

    def set_area_and_country_code(self):
        """ Retrieve area and country code via the Fritzbox. """
        res = self.fc.call_action('X_VoIP', 'X_AVM-DE_GetVoIPCommonAreaCode')
        self.area_code = res['NewX_AVM-DE_OKZPrefix'] + res['NewX_AVM-DE_OKZ']
        res = self.fc.call_action('X_VoIP', 'X_AVM-DE_GetVoIPCommonCountryCode')
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
