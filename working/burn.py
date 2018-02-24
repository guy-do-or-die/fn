import re
import ipdb
import time
import signal
import logging
import subprocess

from datetime import datetime

from selenium import webdriver
from selenium.webdriver import DesiredCapabilities
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.remote.remote_connection import LOGGER
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.proxy import Proxy, ProxyType
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By


from python_anticaptcha import AnticaptchaClient, NoCaptchaTaskProxylessTask

from stem.control import Controller
from stem import Signal

from utils import wait, element_has_attribute

import config

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
        driver = kwargs.get('driver')
        config.DEBUG and ipdb.set_trace()


def surf_url(guy):
    return config.SURF_URL.format(guy.ref_id)


def reconn():
    with Controller.from_port(port=config.TOR_PORT) as controller:
        controller.authenticate()
        controller.signal(Signal.NEWNYM)


def setup_driver(proxy=False, detached=False):
    try:
        chrome_options = Options()
        #chrome_options.add_argument('--headless')
        chrome_options.add_argument('--mute-audio')

        prefs = {'profile.managed_default_content_settings.images': 2}
        chrome_options.add_experimental_option('prefs', prefs)
        chrome_options.add_experimental_option('detach', False)

        dc = DesiredCapabilities.CHROME
        dc['loggingPrefs'] = {'browser': 'ALL'}
        dc['unexpectedAlertBehaviour'] = 'accept'

        if proxy:
            proxy = Proxy()
            proxy.proxy_type = ProxyType.MANUAL
            proxy.socks_proxy = config.PROXY
            proxy.http_proxy = config.PROXY
            proxy.ssl_proxy = config.PROXY
            proxy.add_to_capabilities(dc)

        driver = webdriver.Chrome(chrome_options=chrome_options,
                                  desired_capabilities=dc)

        max_wait = config.LOAD_TIMEOUT
        driver.set_window_size(500, 500)
        driver.set_page_load_timeout(max_wait)
        driver.set_script_timeout(max_wait)
    except Exception as e:
        config.DEBUG and ipdb.set_trace()

    if not detached:
        def handler(*args):
            if config.DEBUG:
                ipdb.set_trace()
            else:
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


def solve_captcha(driver):
    if driver.find_elements_by_class_name('g-recaptcha'):
        captcha = driver.find_element_by_class_name('g-recaptcha')
        site_key = captcha.get_attribute('data-sitekey')
        log('recaptcha found')

        if not site_key:
            site_key = driver.find_element_by_css_selector(
                '.challenge-form script').get_attribute('data-sitekey')

        task = NoCaptchaTaskProxylessTask(website_url=driver.current_url, website_key=site_key)
        job = anticpatcha_client.createTask(task)
        job.join()

        token = job.get_solution_response()

        global solved_captchas
        solved_captchas += 1

        log('recaptcha solved ({})'.format(solved_captchas))

        wait(driver, EC.presence_of_element_located((By.CSS_SELECTOR, '#g-recaptcha-response')))
        driver.execute_script('document.getElementById("g-recaptcha-response").value="{}"'.format(token))
    else:
        if (driver.find_elements_by_css_selector('.verify-me-progress[role="checkbox"]')
            and not driver.find_elements_by_css_selector('checkmark')):

            wait(driver, EC.presence_of_element_located(
                (By.CSS_SELECTOR, '.verify-me-progress[role="checkbox"]'))).click()

        wait(driver, element_has_attribute((By.NAME, 'coinhive-captcha-token'), 'value'))


def alarm(message, guy=None):
    send_message('{} {}'.format(message, guy))
    driver.execute_script('alert("HERE I AM! {}")'.format(guy))


def switch_tab(driver):
    main, trash = driver.window_handles
    driver.switch_to.window(trash)
    driver.close()
    driver.switch_to.window(main)


def reg(driver, guy):
    log('registering', guy=guy)
    driver.get(config.REG_URL)

    email = driver.find_element_by_name('email')
    password = driver.find_element_by_name('password')

    email.send_keys(guy)
    password.send_keys(config.PASSWORD)



def login(driver, guy):
    log('trying to login for', guy=guy)
    driver.get(config.LOGIN_URL)

    email = driver.find_element_by_name('email')
    password = driver.find_element_by_name('password')

    email.send_keys(guy)
    password.send_keys(config.PASSWORD)

    driver.find_element_by_css_selector('button.main-button.login').click()
    switch_tab(driver)
    time.sleep(1)

    if driver.find_elements_by_css_selector('#iframe.recaptcha.challenge'):
        solve_captcha(driver)
        alarm('CAPTCHA!!!')

    log('logged in')


def number(value):
    return int(''.join(s for s in value if s.isdigit()).lstrip('0') or '0')


def surf(arg):
    n, guy = arg.split(':')
    time.sleep(7 * int(n))

    driver = setup_driver()
    log('boosting!')

    login(driver, guy)

    while True:
        cd = 0

        if driver.find_elements_by_class_name('timeout-container'):
            cd = number(driver.find_element_by_class_name('timeout-container').text)

        if cd:
            m, s = divmod(cd, 100)
            time.sleep(60 * m + s)
            driver.refresh()
        else:
            try:
                wait(driver, EC.presence_of_element_located((By.CSS_SELECTOR, '.roll-wrapper button'))).click()

                time.sleep(5)

                print('{} brings {} NEM for {}'.format(
                    number(driver.find_element_by_class_name('lucky-numbers').text),
                    driver.find_element_by_class_name('result').text.split()[-1], guy))

                switch_tab(driver)
            except:
                driver.refresh()
                continue
