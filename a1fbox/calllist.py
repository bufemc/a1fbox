#!/usr/bin/python3

from collections import Counter
from time import sleep

from callinfo import CallInfo
from callprefix import CallPrefix
from fritzconn import FritzConn
from fritzconnection.lib.fritzcall import FritzCall
from phonebook import Phonebook

if __name__ == "__main__":
    # Quick example how to use only

    # Initialize by using parameters from config file
    fritzconn = FritzConn()

    fc = FritzCall(fc=fritzconn)
    cp = CallPrefix(fc=fritzconn)
    pb = Phonebook(fc=fritzconn)

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

    print(f'\nAll {len(calls)} calls, uniqued {len(numbers)}:')
    print(numbers)

    anylist = pb.get_all_numbers_for_pb_ids([0, 1, 2])  # White- or blacklist

    print('\nWhite- or blacklisted:')
    unknowns = set()
    for number in numbers:
        name = pb.get_name_for_number_in_dict(number, anylist, area_code=cp.area_code)
        if name:
            print(f'{number} {name}')
        else:
            unknowns.add(number)

    # Idea: rate & info ... auto-block .. or add good names to whitelist?
    print('\nResolving Unknowns:')
    for unknown in unknowns:
        ci = CallInfo(unknown)
        ci.get_cascade_score()
        print(ci)
        sleep(10)  # Anti-DDOS needed for tellows and wemgehoert, otherwise you get blocked or captcha
