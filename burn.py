import re
import sys
import ipdb
import time
import signal
import logging
import subprocess

from datetime import datetime
from itertools import cycle

from selenium import webdriver
from selenium.webdriver import DesiredCapabilities, ActionChains

from selenium.webdriver.chrome.options import Options
from selenium.webdriver.remote.remote_connection import LOGGER
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.proxy import Proxy, ProxyType
from selenium.webdriver.common.by import By

from python_anticaptcha import AnticaptchaClient, NoCaptchaTaskProxylessTask

from stem.control import Controller
from stem import Signal

from utils import wait, element_has_attribute

import config


SPECIAL_GUYS = cycle(config.GUYS)

anticpatcha_client = AnticaptchaClient(config.API_KEY)
solved_captchas = 0


def now():
    return datetime.now().strftime('%Y.%m.%d %H:%M:%S')


def send_message(message):
    subprocess.Popen(['notify-send', message])
    return


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
        driver = kwargs.get('driver')
        #config.DEBUG and ipdb.set_trace()


def surf_url(guy):
    return config.SURF_URL.format(guy.ref_id)


def reconn():
    with Controller.from_port(port=config.TOR_PORT) as controller:
        controller.authenticate()
        controller.signal(Signal.NEWNYM)


def setup_driver(proxy=False, detached=False, driver=None):
    try:
        chrome_options = Options()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--mute-audio')

        prefs = {'profile.managed_default_content_settings.images': 2}
        chrome_options.add_experimental_option('prefs', prefs)
        chrome_options.add_experimental_option('detach', False)

        dc = DesiredCapabilities.CHROME
        dc['loggingPrefs'] = {'browser': 'ALL'}

        if proxy:
            proxy = Proxy()
            proxy.proxy_type = ProxyType.MANUAL
            proxy.socks_proxy = config.PROXY
            proxy.http_proxy = config.PROXY
            proxy.ssl_proxy = config.PROXY
            proxy.add_to_capabilities(dc)

        driver = webdriver.Chrome(chrome_options=chrome_options,
                                  desired_capabilities=dc)

        max_wait = config.PROXY_LOAD_TIMEOUT if proxy else config.LOAD_TIMEOUT
        driver.set_window_size(500, 500)
        driver.set_page_load_timeout(max_wait)
        driver.set_script_timeout(max_wait)
    except Exception as e:
        log(e, type="error")

    if not detached:
        def handler(*args, **kwargs):
            try:
                if driver:
                    driver.stop_client()
                    driver.close()
                    driver.quit()
            except:
                log('quitting')

            signal.signal(signal.SIGINT, signal.SIG_IGN)

        signal.signal(signal.SIGINT, handler)

    return driver


def captcha_requested(driver):
    if driver.find_elements_by_css_selector('iframe[title*="recaptcha"]'):
        return (driver.execute_script('return window.grecaptcha')
                and 'visibility: visible' in driver.find_element_by_xpath(
                    '//iframe[@title="recaptcha challenge"]/ancestor::div[2]').get_attribute('style'))


def solve_captcha(driver):
    try:
        log('solving recaptcha')
        # driver.switch_to.frame(driver.find_element_by_css_selector('iframe[title*="recaptcha"]'))
        # rc = driver.find_elements_by_css_selector('#rc-imageselect')

        site_key = re.search(r"sitekey: '(.*?)'", driver.page_source).group(1)
        task = NoCaptchaTaskProxylessTask( website_url=driver.current_url, website_key=site_key)

        job = anticpatcha_client.createTask(task)
        job.join()

        token = job.get_solution_response()

        driver.execute_script('sendRegister(arguments[0])', token)

        global solved_captchas
        solved_captchas += 1

        log('recaptcha solved ({})'.format(solved_captchas))
        return True

    except Exception as e:
        check_for_alert(driver)
        log(e, type='error')


def alarm(driver, message, guy=None):
    send_message('{} {}'.format(message, guy))
    driver.execute_script('alert("HERE I AM! {}")'.format(guy))


def check_for_alert(driver):
    try:
        alert = None
        alert = driver.switch_to.alert.ignore()
    except:
        alert and log(alert.text)


def switch_tab(driver):
    main, *trash = driver.window_handles

    for tab in trash:
        driver.switch_to.window(tab)
        driver.close()

    driver.switch_to.window(main)


def make_a_guy(n):
    if n < 0:
        return next(SPECIAL_GUYS)

    return config.LEAD.format(n)


def reg(start, end=None):
    for n in range(start, end or start + 1):
        guy = make_a_guy(n)
        log('registering', guy=guy)

        shots = 5
        while shots:
            shots -= 1

            try:
                driver = None; reconn()
                driver = setup_driver(proxy=True)
                driver.get(config.REG_URL)

                reg_btn = wait(driver, EC.presence_of_element_located(
                    (By.CLASS_NAME, 'register-link')))

                if not reg_btn.is_displayed():
                    driver.find_element_by_css_selector('.navbar-toggle').click()
                    reg_btn = wait(driver, EC.visibility_of_element_located(
                        (By.CLASS_NAME, 'register-link')))

                reg_btn.click()
                time.sleep(5)

                email = driver.find_element_by_css_selector('.register-wrapper .email')
                password = driver.find_element_by_css_selector('.register-wrapper .password')
                repassword = driver.find_element_by_css_selector('.register-wrapper .confirm-password')

                email.send_keys(guy)
                password.send_keys(config.PASSWORD)
                repassword.send_keys(config.PASSWORD)

                reg_btn = driver.find_element_by_css_selector('.register-wrapper button.register')
                ActionChains(driver).move_to_element(reg_btn).click().perform()

                switch_tab(driver)

                if captcha_requested(driver):
                    if solve_captcha(driver):
                        time.sleep(5)

                        if driver.find_elements_by_css_selector('.register-wrapper .error'):
                            error = driver.find_element_by_css_selector('.register-wrapper .error')
                            if error.is_displayed() and error.text:
                                break

                        log('registered', guy=guy)
                        break

            except Exception as e:
                check_for_alert(driver)
                log(e, guy=guy, type='error')
            finally:
                driver.close()


def login(driver, guy):
    shots = 5
    while shots:
        log('{}: trying to login for {}'.format(shots, guy))
        shots -= 1

        try:
            driver.get(config.LOGIN_URL)

            email = driver.find_element_by_css_selector('.login-wrapper .email')
            password = driver.find_element_by_css_selector('.login-wrapper .password')
            error = driver.find_element_by_css_selector('.login-wrapper .error')

            email.send_keys(guy)
            password.send_keys(config.PASSWORD)

            driver.find_element_by_css_selector('button.main-button.login').click()
            switch_tab(driver)

            if error.is_displayed() and error.text or captcha_requested(driver):
                if 'invalid' in error.text:
                    return
            else:
                wait(driver, EC.url_changes(config.URL))
                log('logged in with {}'.format(guy))
                return True

        except Exception as e:
            check_for_alert(driver)
            log(e, guy=guy, type='error')


def logout(driver):
    try:
        driver.get(config.LOGOUT_URL)
        switch_tab(driver)
    except:
        check_for_alert(driver)

def number(value):
    return int(''.join(s for s in value if s.isdigit()).lstrip('0') or '0')


def surf(params):
    n, start, end = map(int, params.split(':'))
    time.sleep(7 * n)

    driver = setup_driver()

    for n in cycle(range(start, end)):
        guy = make_a_guy(n)
        if login(driver, guy):

            shots = 3
            while shots:
                shots -= 1

                try:
                    roll_btn = wait(driver, EC.presence_of_element_located(
                        (By.CSS_SELECTOR, '.roll-wrapper button')))

                    if roll_btn.is_displayed():
                        roll_btn.click()
                        switch_tab(driver)

                        if captcha_requested(driver):
                            driver.refresh()
                            continue

                        num = number(driver.find_element_by_class_name('lucky-numbers').text)
                        result = wait(driver, EC.visibility_of_element_located(
                            (By.CSS_SELECTOR, '.result')))

                        log('lucky number {} brings {} to {}'.format(
                            num, result.text[-10:], guy))

                        if 9985 < num < 10001:
                            log('!!!!!!!!!!!!!!! {}'.format(num, guy))

                        break

                except Exception as e:
                    check_for_alert(driver)
                    log(e, guy=guy, type='error')
                    driver.refresh()

            logout(driver)
