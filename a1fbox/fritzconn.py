import os
import requests


# Config like in the documentation for fritzconnection, which is also used in this project
FRITZ_IP_ADDRESS = 'fritz.box'
FRITZ_TCP_PORT = 49000
FRITZ_TLS_PORT = 49443
FRITZ_USERNAME = 'dslf-config'
FRITZ_PASSWORD = ''  # Be aware, this is tricky, it's better to pass the password via os env!


class FritzConn:
    """ Helper like in FritzConnection, but intentionally other naming, for simplification stores also user/pass. """

    def __init__(self, address=None, port=None, user=None, password=None,
                       timeout=None, use_tls=False):

        if address is None:
            address = os.getenv('FRITZ_IP_ADDRESS', FRITZ_IP_ADDRESS)
        if user is None:
            user = os.getenv('FRITZ_USERNAME', FRITZ_USERNAME)
        if password is None:
            password = os.getenv('FRITZ_PASSWORD', FRITZ_PASSWORD)
        if port is None and use_tls:
            port = FRITZ_TLS_PORT
        elif port is None:
            port = FRITZ_TCP_PORT

        session = requests.Session()
        session.verify = False
        session.timeout = timeout

        self.address = address
        self.session = session
        self.timeout = timeout
        self.port = port

        self.user = user
        self.password = password
