#!/usr/bin/python3

import logging
import html
from fritzconn import FritzConn

from fritzconnection.lib.fritzphonebook import FritzPhonebook

logging.basicConfig(level=logging.WARNING)
log = logging.getLogger(__name__)

KEEP_INTERNALS = False


class Phonebook(FritzPhonebook):
    """ Unless PR #56 is merged, inherit and extend for required changes. """

    def get_all_contacts(self, id, keep_internals=KEEP_INTERNALS):
        """
        Get a list of contacts for the phonebook with `id`.
        Remove internal numbers like 'Wecker' by keep_internals=False.
        """
        url = self.phonebook_info(id)['url']
        self._read_phonebook(url)
        return [contact for contact in self.phonebook.contacts if
                keep_internals or not contact.numbers[0].startswith('**')]

    def get_all_names(self, id, keep_internals=KEEP_INTERNALS):
        """
        Get a dictionary with all names and their phone numbers for the
        phonebook with `id`.
        Remove internal numbers like 'Wecker' by keep_internals=False.
        """
        url = self.phonebook_info(id)['url']
        self._read_phonebook(url)
        # Add suffix _ for same named entries, 1st dup _, 2nd dup __ etc.
        name_dict = dict()
        for contact in self.get_all_contacts(id, keep_internals):
            name = contact.name
            while name in name_dict:
                name += '_'
            name_dict[name] = contact.numbers
        return name_dict

    def get_all_numbers(self, id, keep_internals=KEEP_INTERNALS):
        """
        Get a dictionary with all phone numbers and the according names
        for the phonebook with `id`.
        Remove internal numbers like 'Wecker' by keep_internals=False.
        """
        reverse_contacts = dict()
        for name, numbers in self.get_all_names(id, keep_internals).items():
            for number in numbers:
                # A number can contain spaces, e.g. like "<area code> <number>"
                nr = number.replace(' ', '')
                reverse_contacts[nr] = name
        return reverse_contacts

    def add_contact(self, pb_id, name, number, skip_existing=True):
        """ Bad style, but works. Should use a fritzconnection's Contact object and Soaper later. """

        # Temporary workaround to cover the Umlaut problem - still not solved perfectly!
        # https://stackoverflow.com/questions/701704/convert-html-entities-to-unicode-and-vice-versa
        # Creates correct &#228; for ä, however Fritzbox displays Ã¤ (&auml; would work instead)
        name = html.escape(name).encode('ascii', 'xmlcharrefreplace').decode()

        arg = {'NewPhonebookID': pb_id,
               'NewPhonebookEntryID': '',
               'NewPhonebookEntryData':
                   # f'<?xml version="1.0" encoding="utf-8"?>'
                   f'<Envelope>'  # xmlns:s="http://www.w3.org/2003/05/soap-envelope" s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">'
                   f'<contact>'
                   f'<category>0</category>'
                   f'<person><realName>{name}</realName></person>'
                   f'<telephony nid="1"><number type="home" prio="1" id="0">{number}</number></telephony>'
                   f'</contact>'
                   f'</Envelope>'}

        if skip_existing:
            pb_number_to_name = self.get_all_numbers(pb_id)  # [{Number: Name}, ..]
            if number in pb_number_to_name.keys():
                log.warning(f'{number} already in phonebook, skipped adding..')
                return {}

        return self.fc.call_action('X_AVM-DE_OnTel:1', 'SetPhonebookEntry', arguments=arg)

    def update_contact(self, pb_id, contact):
        """ Idea: could use contact.uniqueid to update corresponding record in Fritz!Box phonebook with pb_id. """
        raise NotImplementedError()

    def delete_contact(self, pb_id, contact):
        """ Idea: could use contact.uniqueid to delete corresponding record in Fritz!Box phonebook with pb_id. """
        raise NotImplementedError()

    def import_contacts_from_json(self, pb_id, json_file, skip_existing=True):
        """ Idea: could use a json file with a list of contact dict to populate a phonebook with pb_id. """
        raise NotImplementedError()

    def export_contacts_to_json(self, pb_id, json_file):
        """ Idea: could export a phonebook with pb_id to a json file with a list of contact dict. """
        raise NotImplementedError()

    def ensure_pb_ids_valid(self, pb_ids):
        """ Checks a list of phonebook ids. Raise if a phonebook id does not exist. """
        for pb_id in pb_ids:
            if pb_id not in self.phonebook_ids:
                raise Exception(f'The phonebook_id {pb_id} does not exist!')

    def get_all_numbers_for_pb_ids(self, pb_ids):
        """ Retrieve and concatenate number-name-dicts for several phonebook ids. """
        assert(type(pb_ids) == list)
        number_name_dict = dict()
        for pb_id in pb_ids:
            number_name_dict.update(self.get_all_numbers(pb_id))  # [{Number: Name}, ..]
        return number_name_dict

    def get_name_for_number_in_dict(self, number, number_name_dict, area_code=None, country_code=None):
        """ Return first name found for a number_name_dict. Can also find it with/without area or country code. """

        numbers = [number]

        # Try also to find a phonebook entry with or without the country_code
        if country_code:
            if number.startswith(country_code):
                numbers.append(number.replace(country_code, '0'))  # E.g.: 00497191 => 07191
            else:
                numbers.append(country_code + number)

        # Try also to find a phonebook entry with or without the area_code
        if area_code:
            nr = number
            if country_code and number.startswith(country_code):
                nr = number.replace(country_code, '0')
            if nr.startswith(area_code):
                numbers.append(nr.replace(area_code, ''))
            else:
                numbers.append(area_code + nr)

        # Return first match, or None if not found
        for number in numbers:
            if number in number_name_dict.keys():
                return number_name_dict[number]
        return None


if __name__ == "__main__":
    # Quick example how to use only

    # Initialize by using parameters from config file
    fritzconn = FritzConn()
    pb = Phonebook(fc=fritzconn)

    # Print all numbers in whitelist, exists always, but can be empty
    print("Names and numbers in whitelist (first phonebook):")
    contacts = pb.get_all_contacts(0)
    for contact in contacts:
        print(f'{contact.name}: {contact.numbers}')

    # Check that a number without area code is found with or without country and/or area code, needs a mockup later
    numbers = pb.get_all_numbers_for_pb_ids([0])
    nr = '808xxx'  # Set your local phone number here
    area_code = '07191'
    name1 = pb.get_name_for_number_in_dict('0049' + area_code[1:] + nr, numbers, area_code=area_code, country_code='0049')
    name2 = pb.get_name_for_number_in_dict(area_code + nr, numbers, area_code=area_code, country_code='0049')
    name3 = pb.get_name_for_number_in_dict(nr, numbers, area_code=area_code, country_code='0049')
    print(name1, name2, name3)

    # Try to add a number to whitelist which is already existing, should be skipped
    result = pb.add_contact(0, 'CallBlockerTest', nr)

    # Works only if phonebook with id 2 exists and should not be executed too often
    # result = pb.add_contact(2, 'CallBlockerTest', '009912345')
    # result = pb.add_contact(2, 'CallBlockerTest-Umläut', '009912345', skip_existing=False)
