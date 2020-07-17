#!/usr/bin/python3

# General methods and classes should go here


class Caches:
    """ General temporary caches, like Caches['tellows'][nr] = CallerInfo - or source could be 'revsearch'..
    Have to be initialized before, then passed to CallerInfo. Not used yet. """

    def __init__(self, sources):
        for source in sources:
            self[source] = dict()

    def add_source_key_obj(self, source, key, obj):
        self[source][key] = obj

    def get_source_key_obj(self, source, key):
        if source not in self:
            raise Exception(f'Source {source} does not exist or was not initialized!')
        return self[source][key] if key in self[source] else None


def anonymize_number(number):
    """ Anonymize 3 last digits of a number, provided as string. """
    if number.isdigit() and len(number) >= 3:
        return number[:-3] + "xxx"
    else:
        # Not a number or e.g. "unknown" if caller uses CLIR
        return number
