DEBUG = False

SLEEP_ON_ERROR = 15

LOAD_TIMEOUT = 30
PROXY_LOAD_TIMEOUT = 180

LOG_FORMAT = '%(asctime)-15s %(message)s'

THREADS_NUM = 2

DB = {
    'name': 'booster',
    'host': '127.0.0.1',
    'port': 27018
}

PROXY = '127.0.0.1:8118'
TOR_PORT = 9051

# hush!

import secrets

GUYS = secrets.GUYS
LEAD = secrets.LEAD

API_KEY = secrets.API_KEY
SITE_KEY = secrets.SITE_KEY

URL = secrets.URL
REG_URL = secrets.REG_URL
LOGIN_URL = secrets.LOGIN_URL
LOGOUT_URL = secrets.LOGOUT_URL

PASSWORD = getattr(secrets, 'PASSWORD')
