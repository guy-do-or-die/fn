from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import NoAlertPresentException
from selenium.webdriver.remote.remote_connection import LOGGER

import subprocess
import datetime
import logging
import config


def now():
    return datetime.datetime.now().strftime('%Y.%m.%d %H:%M:%S')


logging.basicConfig(filename='logs/{}.log'.format(now()),
                    format=config.LOG_FORMAT,
                    level=logging.DEBUG)

logger = logging.getLogger(__name__)


if config.DEBUG:
    LOGGER.setLevel(logging.WARNING)


def log(message, **kwargs):
    guy = kwargs.get('guy', '')
    type = kwargs.get('type', 'info')

    print('{}: {} {}'.format(now(), message, guy))
    getattr(logger, type)(message, extra=kwargs)

    if config.DEBUG and type == 'error':
        print('Error on line {}'.format(sys.exc_info()[-1].tb_lineno))


def send_message(message):
    subprocess.Popen(['notify-send', message])
    return


class element_has_attribute(object):
    def __init__(self, locator, attribute):
        self.attribute = attribute
        self.locator = locator

    def __call__(self, driver):
        element = driver.find_element(*self.locator)
        return element.get_attribute(self.attribute)


def wait(driver, *args, **kwargs):
    try:
        timeout = config.PROXY_LOAD_TIMEOUT if driver.proxy else config.LOAD_TIMEOUT
        return WebDriverWait(driver, timeout).until(*args, **kwargs)
    except Exception as e:
        try:
            driver.switch_to.alert.accept()
        except NoAlertPresentException:
            pass
        log(e, type='error')


def alarm(driver, message, guy=None):
    send_message('{} {}'.format(message, guy))
    driver.execute_script('alert("HERE I AM! {}")'.format(guy))
