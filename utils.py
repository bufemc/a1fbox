# General methods should go here
import os
from datetime import datetime


def anonymize_number(number):
    """ Anonymizes 3 last digits of a number, provided as string. """
    if number.isdigit() and len(number) >= 3:
        return number[:-3] + "xxx"
    else:
        # Not a number or e.g. "unknown" if caller uses CLIR
        return number
