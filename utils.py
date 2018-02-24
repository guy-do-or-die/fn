from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import NoAlertPresentException

import config


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
    except:
        try:
            driver.switch_to.alert.accept()
        except NoAlertPresentException:
            pass
