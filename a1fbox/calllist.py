#!/usr/bin/python3

from collections import Counter
from time import sleep
from xml.etree import ElementTree as ET

from fritzconnection.lib.fritzcall import FritzCall
from fritzconnection.cli.fritzinspection import FritzInspection

from callinfo import CallInfo
from callprefix import CallPrefix
from fritzconn import FritzConn
from phonebook import Phonebook

if __name__ == "__main__":
    # Quick example how to use only

    # Initialize by using parameters from config file
    fritzconn = FritzConn()

    fc = FritzCall(fc=fritzconn)
    cp = CallPrefix(fc=fritzconn)
    pb = Phonebook(fc=fritzconn)

    fi = FritzInspection(fc=fritzconn)
    # print(fi.view_servicenames())

    anylist = pb.get_all_numbers_for_pb_ids([0, 1, 2], keep_internals=False)  # White- or blacklist

    print("VoIP numbers (XML):")
    res = pb.get_voip_numbers()
    print(res)

    print("Adding to whitelist internal numbers:")
    tree = ET.fromstring(res)
    iphones = dict()
    for node in tree.iter('Number'):
        nr = cp.area_code + node.text
        iphones.update({nr: 'intern'})
    anylist.update(iphones)
    print(iphones)

    print('Internal active handset devices:')
    res = pb.get_handset_info(keep_phone_only=False)
    print(res)

    print('Internal active handset phone numbers:')
    res = pb.get_handset_info(keep_phone_only=True)
    print(res)

    calls = fc.get_missed_calls(update=True)
    missed_list = []
    for call in calls:
        number = call.Called if call.type == 3 else call.Caller
        missed_list.append(number)
    counts = Counter(missed_list)
    print("\nMissed calls, ordered by count:")
    print(counts)

    calls = fc.get_calls(update=True)
    numbers = set()
    for call in calls:
        number = call.Called if call.type == 3 else call.Caller
        if number:  # If CLIR / Anon, there is no number
            if not number.startswith('0'):
                number = cp.area_code + number
            numbers.add(number)

    print(f'\nLast {len(calls)} calls, uniqued: {len(numbers)}')
    print(numbers)

    print('\nWhite- or blacklisted:')
    unknowns = set()
    for number in numbers:
        name = pb.get_name_for_number_in_dict(number, anylist, area_code=cp.area_code)
        if name:
            print(f'{number} {name}')
        else:
            unknowns.add(number)

    # Sort them on purpose to find nearly identical numbers by eye
    unknowns = sorted(list(unknowns))

    # Idea: rate & info ... auto-block .. or add good names to whitelist?
    print(f'\nResolving Unknowns: {len(unknowns)}')
    for unknown in unknowns:
        # Skip those starting with a prefix in phonebooks, e.g. 0039(*) for Italy, 069660(*), 0211945(*)
        if any(known in unknown for known in anylist):
            print("skipped as prefix found in phonebook: " + unknown)
            continue
        ci = CallInfo(unknown)
        ci.get_cascade_score()
        if not ci.location:
            ci.location = cp.get_prefix_name(unknown)
        print(ci)
        sleep(4)  # Anti-DDOS needed for tellows (and if used, wemgehoert), otherwise you get blocked or captcha

    print('\nREADY.')
