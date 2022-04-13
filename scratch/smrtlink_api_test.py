# See https://www.pacb.com/wp-content/uploads/Sequel-SMRT-Link-Web-Services-API-Use-Cases-v8.0.pdf
# for the original.
import os, sys, re
import base64
from pprint import pprint, pformat

import configparser
import requests

import logging
L = logging.getLogger(__name__)

class Wso2Constants(object):
    """ These client registration credentials are valid for every SMRT Link
     server (and are also used by the SL UI)
    """
    SECRET = "KMLz5g7fbmx8RVFKKdu0NOrJic4a"
    CONSUMER_KEY = "6NjRXBcFfLZOwHc0Xlidiz4ywcsa"
    SCOPES = ("welcome", "run-design", "run-qc", "openid", "analysis",
              "sample-setup", "data-management", "userinfo")

    @classmethod
    def auth(cls):
        # Returns auth header as bytes
        return base64.b64encode(f"{cls.SECRET}:{cls.CONSUMER_KEY}".encode())

    @classmethod
    def scope_str(cls):
        return " ".join(cls.SCOPES)

#print(Wso2Constants.auth())

def get_access_token(url, user, password, constants, verify_ssl=False):
    """Generic OATH token getter
    """
    headers = { "Authorization": b"Basic " + constants.auth(),
                "Content-Type":  b"application/x-www-form-urlencoded" }

    scope_str = constants.scope_str()

    payload = dict( grant_type = "password",
                    username = user,
                    password = password,
                    scope = scope_str )

    # set verify to false to disable the SSL cert verification
    r = requests.post(url, payload, headers=headers, verify=verify_ssl)

    # Any other errors?
    r.raise_for_status()
    return r.json()

def get_smrtlink_wso2_token(user, password, host, port=8243, verify_ssl=False):
    """Token getter that uses Wso2Constants
    """
    token_url = f"https://{host}:{port}/token"

    try:
        j = get_access_token(token_url, user, password, Wso2Constants, verify_ssl=verify_ssl)
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 400:
            L.error("Error 400 when getting token normally indicates incorrect credentials")
        raise

    # We should get back some yummy JSON
    assert j['access_token']
    assert j['refresh_token']
    j['scopes'] = j['scope'].split()

    return j

def token_to_headers(access_token):
    """ Once we have authenticated and have a token, we can use it for actual requests
    """
    return { "Authorization": f"Bearer {access_token}".encode(),
             "Content-type":  b"application/json" }

def get_endpoint(api_path, host, access_token, verify_ssl):
    """Having got a token, we probably want to wrap this in a Class to bake the last
       three parameters in.
       No point worrying about token expiry since we are authenticating when the script runs,
       and not hanging around once our queries are complete. The notes say this is fine.
    """
    api_url = f"https://{host}:8243/SMRTLink/1.0.0/{api_path.lstrip('/')}"
    headers = token_to_headers(access_token)

    # verify=False disables SSL verification
    response = requests.get(api_url, headers=headers, verify=verify_ssl)
    response.raise_for_status()

    return response.json()

def get_status(host, user, password, verify_ssl=False):
    """This functions as a basic 'ping' test
    """
    token = get_smrtlink_wso2_token(user, password, host, verify_ssl=verify_ssl)['access_token']
    return get_endpoint("/status", host, token, verify_ssl)

# So let's test this. Want to avoid typing the password or saving it in a file, so
# let's make it a .ini file like .genologicsrc

def get_rc_credentials(section="smrtlink"):
    """Returns a dict with keys {'host', 'user', 'password'} and maybe
       'verify_ssl'
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

creds = get_rc_credentials()
pprint(creds)

pprint(get_status(**creds))
