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
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.proxy import Proxy, ProxyType
from selenium.webdriver.common.by import By

from selenium.common.exceptions import NoAlertPresentException

from python_anticaptcha import AnticaptchaClient, NoCaptchaTaskProxylessTask

from stem.control import Controller
from stem import Signal

from utils import log as base_log, wait, pers

import config


SPECIAL_GUYS = cycle(config.GUYS)

anticpatcha_client = AnticaptchaClient(config.API_KEY)
solved_captchas = 0
errors_count = 0
cmd = 'surf'
proc = 0
n = 0


def log(*args, **kwargs):
    global errors_count, cmd, n, proc
    kwargs['proc'] = proc

    base_log(*args, **kwargs)

    if kwargs.get('type') == 'error':
        if errors_count == 0:
            pers('{}_{}'.format(proc, cmd), n)

        errors_count += 1

        log('errors count: {}'.format(errors_count))


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
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-logging')

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
        driver.set_window_size(1000, 1000)
        driver.set_page_load_timeout(max_wait)
        driver.set_script_timeout(max_wait)

        setattr(driver, 'proxy', proxy)
    except Exception as e:
        log(e, type='error')

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


def check_for_alert(driver):
    try:
        driver and driver.switch_to_alert().dismiss()
    except NoAlertPresentException:
        pass
    except Exception as e:
        log(e, type='error')


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


def guys(proc, cmd, start, end):
    try:
        key = '{}_{}'.format(proc, cmd)
        val = pers(key)

        offset = int(val or '0')

        if proc > 0:
            offset -= start
        else:
            offset += len(config.GUYS) if val else 0

        gload = list(range(start, end))
        gload = list(gload[offset:] + gload[:offset])

        return cycle(gload) if cmd == 'surf' else gload

    except Exception as e:
        log(e, type='error')
    finally:
        pers('-' + key)


def login(driver, guy):
    shots = 3
    while shots:
        log('trying to login ({} shots left) for {}'.format(shots, guy))
        shots -= 1

        try:
            driver.get(config.LOGIN_URL)

            session = pers(guy, raw=True)

            if session:
                log('restoring session for {}'.format(guy))
                c = driver.get_cookie('coinmaster_session')
                driver.delete_cookie('coinmaster_session')
                c['value'] = session
                driver.add_cookie(c)
                driver.refresh()
            else:
                if driver.current_url == config.URL:
                    logout(driver)

                email = driver.find_element_by_css_selector('.login-wrapper .email')
                password = driver.find_element_by_css_selector('.login-wrapper .password')

                email.send_keys(guy)
                password.send_keys(config.PASSWORD)

                driver.find_element_by_css_selector('button.main-button.login').click()
                switch_tab(driver)
                time.sleep(2)

            if driver.current_url == config.URL:
                balance = driver.find_element_by_class_name('navbar-coins').text

                log('logged in with {}, balance: {}'.format(guy, number(balance, True)))

                pers(guy, driver.get_cookie('coinmaster_session')['value'])

                if driver.find_elements_by_class_name('timeout-container'):
                    min, sec = divmod(number(driver.find_element_by_class_name('timeout-container').text), 100)
                    log('countdown: {0:02d}:{0:02d}'.format(min, sec))

                    if 0 < min < 10 and cmd == 'surf':
                        log('waiting for the time...')
                        time.sleep(60 * min + sec)

                return True

            if captcha_requested(driver):
                log('captcha :(')
                continue

            if session:
                log('session for {} is no longer valid'.format(guy))
                pers('-' + guy)

            if driver.find_elements_by_css_selector('.login-wrapper .error'):
                error = driver.find_element_by_css_selector('.login-wrapper .error')

                if error.is_displayed() and error.text:
                    log('{} {}'.format(error.text, guy))

                    if 'invalid' in error.text:
                        return

        except Exception as e:
            check_for_alert(driver)

            log(e, guy=guy, type='error')


def reg(start, end=None):
    global errors_count, cmd, n

    cmd = 'reg'

    not_registered = set()
    login_driver = setup_driver()

    for n in pers('not_registered') or guys(0, cmd, start, end or start + 1):
        if errors_count > config.ERRORS_MAX_COUNT:
            sys.exit(0)

        guy = make_a_guy(n)

        if login(login_driver, guy):
            log('already registered', guy=guy)
            logout(login_driver)
            continue
        else:
            registered = False
            log('registering', guy=guy)
            shots = 5
            while shots:
                shots -= 1

                try:
                    driver = None; # reconn()
                    driver = setup_driver(proxy=True)

                    driver.get(config.REG_URL)
                    reg_btn = wait(driver, EC.presence_of_element_located(
                        (By.CLASS_NAME, 'register-link')))

                    if not (reg_btn and reg_btn.is_displayed()):
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
                            time.sleep(5)  # maybe check url instead of waiting???

                            if driver.find_elements_by_css_selector('.register-wrapper .error'):
                                error = driver.find_element_by_css_selector('.register-wrapper .error')
                                if error and error.is_displayed() and error.text:
                                    log(error.text, guy=guy)
                                    if 'taken' in error.text:
                                        break

                                    continue

                            log('registered', guy=guy)

                            registered = True
                            errors_count = 0
                            break

                except Exception as e:
                    check_for_alert(driver)
                    log(e, guy=guy, type='error')
                finally:
                    if registered:
                        not_registered.discard(n)
                    else:
                        not_registered.add(n)

                    pers('not_registered', list(not_registered))
                    driver and driver.close()

    not_registered and log('not registered: {}'.format(list(not_registered)))


def logout(driver):
    driver.delete_all_cookies()
    '''
    try:
        driver.get(config.LOGOUT_URL)
        switch_tab(driver)
    except Exception as e:
        log(e, type='error')
        check_for_alert(driver)
    '''


def number(value, float_=False):
    text = ''.join(s for s in value if s.isdigit() or s == '.').lstrip('0') or '0'

    if float_:
        return float(text)

    return int(text)


def surf(params):
    global errors_count, cmd, n, proc

    cmd = 'surf'

    proc, start, end = map(int, params.split(':'))
    time.sleep(7 * n)

    driver = setup_driver()

    for n in guys(proc, cmd, start, end):
        if errors_count > config.ERRORS_MAX_COUNT:
            sys.exit(0)

        guy = make_a_guy(n)

        if login(driver, guy):
            shots = 3
            while shots:
                shots -= 1

                try:
                    roll_btn = wait(driver, EC.presence_of_element_located(
                        (By.CSS_SELECTOR, '.roll-wrapper button')))

                    if roll_btn and roll_btn.is_displayed():
                        roll_btn.click()
                        switch_tab(driver)

                        if captcha_requested(driver):
                            driver.refresh()
                            continue

                        num_text = driver.find_element_by_class_name('lucky-numbers').text
                        num = number(num_text)

                        result = wait(driver, EC.visibility_of_element_located(
                            (By.CSS_SELECTOR, '.result')))

                        errors_count = 0
                        log('lucky number {} brings {} to {}'.format(
                            num, result.text[-10:], guy))

                        if 9985 < num < 10001 and num_text[0] in ('0', '1'):
                            log('BINGO! {}'.format(num, guy))

                        break

                except Exception as e:
                    check_for_alert(driver)
                    log(e, guy=guy, type='error')
                    log('errors count: {}'.format(errors_count), guy=guy)
                    driver.refresh()

            logout(driver)
