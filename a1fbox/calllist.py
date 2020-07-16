from collections import Counter
from time import sleep
from callprefix import CallPrefix
from callinfo import CallInfo
from phonebook import Phonebook
from fritzconnection.lib.fritzcall import FritzCall


if __name__ == "__main__":

    # ToDo: Config & init is still a mess
    import sys
    sys.path.append("..")
    from config import FRITZ_IP_ADDRESS, FRITZ_USERNAME, FRITZ_PASSWORD

    fc = FritzCall(address=FRITZ_IP_ADDRESS, user=FRITZ_USERNAME, password=FRITZ_PASSWORD)
    cp = CallPrefix(fc=fc.fc)

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

    pb = Phonebook(address=FRITZ_IP_ADDRESS, user=FRITZ_USERNAME, password=FRITZ_PASSWORD)
    anylist = pb.get_all_numbers_for_pb_ids([0,1,2])  # White- or blacklist

    print('\nWhite- or blacklisted:')
    unknowns = set()
    for number in numbers:
        name = pb.get_name_for_number_in_dict(number, anylist, area_code=cp.area_code)
        if name:
            print(f'{number} {name}')
        else:
            unknowns.add(number)

    print('\nResolving Unknowns:')
    for unknown in unknowns:
        ci = CallInfo(unknown)
        ci.get_tellows_and_revsearch()
        print(ci)
        sleep(5)

    # ToDo: check if in white or blacklist.. then print name & skip,
    # otherwise: rate & info ... auto-block .. or add good names to whitelist?
