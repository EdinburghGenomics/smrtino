# See https://www.pacb.com/wp-content/uploads/Sequel_SMRT_Link_Web_Services_API_Use_Cases_v10.2.pdf
# for the original.
import os, sys, re
import base64
from pprint import pprint

import configparser
import requests

import logging
L = logging.getLogger(__name__)

class Wso2Constants(object):
    """ These client registration credentials are valid for every SMRT Link
        server (and are also used by the SL UI)
    """
    DEFAULT_PORT = "8243"
    SECRET = "KMLz5g7fbmx8RVFKKdu0NOrJic4a"
    CONSUMER_KEY = "6NjRXBcFfLZOwHc0Xlidiz4ywcsa"
    SCOPES = ("welcome", "run-design", "run-qc", "openid", "analysis",
              "sample-setup", "data-management", "userinfo")

class APIConnectionError(RuntimeError):
    pass

class OAUTHClient:

    def __init__(self):
        """No auto connecting.
        """
        self.host = None
        self.verify_ssl = True
        self.access_token = None
        self.refresh_token = None
        self.scopes = ()

    def get_auth(self, secret, key):
        """ Returns auth header for token call as bytes
        """
        return base64.b64encode(f"{secret}:{key}".encode())

    def get_access_token(self, url, user, password, scopes, auth):
        """Generic OATH token getter
        """
        headers = { "Authorization": b"Basic " + auth,
                    "Content-Type":  b"application/x-www-form-urlencoded" }

        scope_str = " ".join(scopes)

        payload = dict( grant_type = "password",
                        username = user,
                        password = password,
                        scope = scope_str )

        # If SSL verification has been turned off, we'll suppress these and future
        # warnings.
        if not self.verify_ssl:
            import urllib3
            urllib3.disable_warnings()

        # set verify to false to disable the SSL cert verification
        r = requests.post(url, payload, headers=headers, verify=self.verify_ssl)

        # Any other errors?
        r.raise_for_status()
        j = r.json()

        self.access_token = j['access_token']
        self.refresh_token = j.get('refresh_token')
        self.scopes = tuple(j['scope'].split())

        self.api_base = self.get_api_base(self.host)

        return j

    def get_api_base(self, host=None):
        """ Subclass should override this to provide the right API base
        """
        return host or self.host

    def check_token(self):
        """Check we are actually logged in
        """
        # TODO - we should take action if the token has expired, or is about to expire,
        # but for now just check we hold a token.
        if not self.access_token:
            raise APIConnectionError("No token. You need to log in.")

    def token_to_headers(self, overrides=None):
        """ Once we have authenticated and have a token, we can use it for actual requests
        """
        self.check_token()

        headers = { "Authorization": f"Bearer {self.access_token}".encode(),
                    "Content-type":  b"application/json" }

        if overrides:
            headers.update(overrides)

        return headers


    def get_endpoint(self, path):
        """Having logged in and got a token, we can actually make calls.
        """
        headers = self.token_to_headers()

        full_url = f"{self.api_base}/{path.lstrip('/')}"

        # verify=False disables SSL verification
        response = requests.get(full_url, headers=headers, verify=self.verify_ssl)
        response.raise_for_status()

        return response.json()


class SMRTLinkClient(OAUTHClient):

    def __init__(self, host, verify_ssl=False):
        """Set up a client for a given host. Connection must be done explicitly.
        """
        assert not '/' in host, "Host should not include https:// part or any path info"

        super().__init__()

        self.constants = Wso2Constants

        if ':' in host:
            # Default port
            self.host = f"https://{host}"
        else:
            self.host = f"https://{host}:{self.constants.DEFAULT_PORT}"

        self.verify_ssl = bool(verify_ssl)

    def login(self, user, password):
        """Token getter that uses Wso2Constants
           We're not worrying about token refresh just now. Tokens should be valid for ~2 hours
        """
        token_url = f"{self.host}/token"
        auth = self.get_auth(secret = self.constants.SECRET,
                             key    = self.constants.CONSUMER_KEY)

        try:
            j = self.get_access_token( url = token_url,
                                       user = user,
                                       password = password,
                                       auth = auth,
                                       scopes = self.constants.SCOPES )
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 400:
                L.error("Error 400 when getting token normally indicates incorrect credentials")
                raise APIConnectionError("Login failed")
            else:
                # Just raise the error as-is
                raise

        # Save this just in case
        self._access_json = j

    @classmethod
    def connect_with_creds(cls, creds=None):
        """Convenience method yields a connection with the credentials from get_rc_credentials()
        """
        if not creds:
            creds = cls.get_rc_credentials()

        if 'verify_ssl' in creds:
            client = cls(creds['host'], creds['verify_ssl'])
        else:
            client = cls(creds['host'])

        client.login(creds['user'], creds['password'])

        return client

    def get_api_base(self, host=None):
        """Provide the API base needed for SMRTLink
        """
        host = host or self.host
        return f"{host}/SMRTLink/1.0.0"

    def get_status(self):
        """This functions as a basic 'ping' test
        """
        return self.get_endpoint("/status")

    @classmethod
    def get_rc_credentials(cls, section="smrtlink"):
        """Reads credentials from the standard .ini style file
           Returns a dict with keys {'host', 'user', 'password'} and maybe
           'verify_ssl'. 'host' may incorporate a port number (default is 8243)
        """
        config = configparser.SafeConfigParser()
        conf_file = config.read(os.environ.get('SMRTLINKRCRC',
                                [os.path.expanduser('~/.smrtlinkrc'), 'smrtlink.conf']))

        assert conf_file, "No config file found for SMRTLink API credentials"

        res = dict(host="smrtlink", user="guest")
        for k in "host user password verify_ssl".split():
            try:
                res[k] = config[section][k]
            except KeyError:
                pass

        if 'verify_ssl' in res:
            # Allow '0', 'n[o]', 'f[alse]'
            res['verify_ssl'] = not(res['verify_ssl'][0] in '0nNFf')

        # Special for password
        if "password" not in res:
            try:
                res["password"] = config[section]["pass"]
            except KeyError:
                raise RuntimeError("No password found in file for {res['user']}@{res['host']}")

        # Host should not have 'https://' part.
        assert not '/' in res['host']

        return res

def test_connect():
    creds = SMRTLinkClient.get_rc_credentials()

    creds_copy = creds.copy()
    creds_copy["password"] = '*' * len(creds_copy["password"])
    pprint(creds_copy)

    # Construct connection and connect
    conn = SMRTLinkClient.connect_with_creds(creds)

    pprint(conn.get_status())

# If script is run directly, test connect with default creds.
if __name__ == '__main__':
    test_connect()

