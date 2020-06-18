#!/usr/bin/python3

from config import FRITZ_IP_ADDRESS, FRITZ_USERNAME, FRITZ_PASSWORD
from fritzconnection.lib.fritzphonebook import FritzPhonebook

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
                reverse_contacts[number] = name
        return reverse_contacts

    def add_contact(self, id, name, number):
        """ ToDo: Temporary solution only. Add an entry to the phonebook with `ìd`.
        Should use a fritzconnection's Contact object and Soaper later. """

        arg = {'NewPhonebookID': id,
               'NewPhonebookEntryID': '',
               'NewPhonebookEntryData':
                   f'<Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope">'
                   f'<contact>'
                   f'<category>0</category>'
                   f'<person><realName>{name}</realName></person>'
                   f'<telephony nid="1"><number type="home" prio="1" id="0">{number}</number></telephony>'
                   f'</contact>'
                   f'</Envelope>'}

        return self.fc.call_action('X_AVM-DE_OnTel:1', 'SetPhonebookEntry', arguments=arg)

    # Ideas: reverse search?


if __name__ == "__main__":
    # Quick test only
    pb = Phonebook(address=FRITZ_IP_ADDRESS, user=FRITZ_USERNAME, password=FRITZ_PASSWORD)
    contacts = pb.get_all_contacts(0)  # Exists always, but can be empty
    for contact in contacts:
        print(f'{contact.name}: {contact.numbers}')

    # result = pb.add_contact(2, 'CallBlockerTest', '009912345')
