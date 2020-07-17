#!/usr/bin/python3

import os

from fritzconnection import FritzConnection


# Config goes like in the documentation for fritzconnection, which is also used in this project
# FRITZ_IP_ADDRESS = 'fritz.box'
# FRITZ_TCP_PORT = 49000
# FRITZ_TLS_PORT = 49443
# FRITZ_USERNAME = 'dslf-config'
# FRITZ_PASSWORD = ''  # Be aware, this is tricky, it might be a little safer to pass the password via os env!


class FritzConn(FritzConnection):
    """
    Helper like in FritzConnection, but intentionally other naming, for simplification stores also user/pass.
    Initialization signature is exactly the same, but some fallbacks are implemented, so behavior might be different.
    """

    __instance = None  # Singleton
    __ensure_singleton = True

    @staticmethod
    def set_singleton(bool_state):
        """ Make it optional if this class should be a Singleton. """
        FritzConn.__ensure_singleton = bool_state

    @staticmethod
    def get_instance(address=None, user=None, password=None, port=None, timeout=None, use_tls=False):
        """ Static access method to ensure Singleton, if wished. """
        if FritzConn.__instance == None:
            FritzConn(address, port, user, password, timeout, use_tls)
        return FritzConn.__instance

    def __init__(self, address=None, port=None, user=None, password=None,
                 timeout=None, use_tls=False):
        """ Initializes the Fritzbox connection by base class, but using fallback parameters. """

        # Ensure singleton if wished, so to re-use same connection all the time
        if self.__ensure_singleton and FritzConn.__instance != None:
            raise Exception("FritzConn is a singleton! Use get_instance() instead.")
        else:
            FritzConn.__instance = self

        # Fallback: if parameters are not given and constants not defined, use the config.py in the upper folder
        if not address and not (os.getenv('FRITZ_IP_ADDRESS', None)) and not 'FRITZ_IP_ADDRESS' in globals():
            import sys
            sys.path.append("..")
            from config import FRITZ_IP_ADDRESS, FRITZ_USERNAME, FRITZ_PASSWORD, FRITZ_TLS_PORT, FRITZ_TCP_PORT

        # Fallback if user and pass are not given, as they are not required always
        fritz_user = FRITZ_USERNAME if 'FRITZ_USERNAME' in globals() else 'dslf-config'
        fritz_pass = FRITZ_PASSWORD if 'FRITZ_PASSWORD' in globals() else ''

        if address is None:
            address = os.getenv('FRITZ_IP_ADDRESS', FRITZ_IP_ADDRESS)

        if user is None:
            user = os.getenv('FRITZ_USERNAME', fritz_user)
        if password is None:  # This is somehow risky, but doing it for simplification
            password = os.getenv('FRITZ_PASSWORD', fritz_pass)

        if port is None and use_tls:
            port = FRITZ_TLS_PORT if 'FRITZ_TLS_PORT' in globals() else 49443
        elif port is None:
            port = FRITZ_TCP_PORT if 'FRITZ_TCP_PORT' in globals() else 49000

        super().__init__(address, port, user, password, timeout, use_tls)

    def __repr__(self):
        """ Return a readable representation. 1:1 copy from base class so far. """
        return f"{self.modelname} at {self.soaper.address}\n" \
               f"FRITZ!OS: {self.system_version}"


if __name__ == "__main__":
    # You can either connect by giving parameters, at least the address
    # fc = FritzConn.get_instance(address='fritz.box')

    # Or, if given no parameters the config.py in the upper directory is used
    fc = FritzConn.get_instance()
    print(fc)
