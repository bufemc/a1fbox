# General methods should go here


def anonymize_number(number):
    """ Anonymize 3 last digits of a number, provided as string. """
    if number.isdigit() and len(number) >= 3:
        return number[:-3] + "xxx"
    else:
        # Not a number or e.g. "unknown" if caller uses CLIR
        return number
