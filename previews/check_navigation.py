"""Opt-in real-browser regression checks and screenshots for the isolated preview.

Requires an installed Firefox and geckodriver; never starts a scrape or delivery.
"""
import argparse
import functools
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import shutil
import threading

from selenium import webdriver
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.support.ui import Select, WebDriverWait

from previews.shreddeals import SOURCE


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def run(preview, screenshots, firefox, geckodriver):
    preview, screenshots = Path(preview).resolve(), Path(screenshots).resolve()
    if not json.loads((preview/'manifest.json').read_text()).get('development_only'):
        raise ValueError('Build an isolated preview first')
    if screenshots.is_relative_to(SOURCE):
        raise ValueError('Screenshots must be outside the checkout')
    screenshots.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(QuietHandler, directory=str(preview)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f'http://127.0.0.1:{server.server_port}/index.html'
    passed = []
    driver = None

    def browser(coarse=False):
        options = Options()
        options.binary_location = str(firefox)
        options.add_argument('-headless')
        options.page_load_strategy = 'eager'
        options.accept_insecure_certs = False
        options.enable_bidi = True
        # Emulate the correct input capability, not altered product CSS.
        options.set_preference('ui.primaryPointerCapabilities', 1 if coarse else 6)
        options.set_preference('ui.allPointerCapabilities', 1 if coarse else 6)
        return webdriver.Firefox(options=options, service=Service(str(geckodriver), log_output=str(screenshots/'browser.log')))

    def viewport(width, height):
        driver.browsing_context.set_viewport(context=driver.current_window_handle, viewport={'width': width, 'height': height})
        assert driver.execute_script('return innerWidth') == width
        assert driver.execute_script('return innerHeight') == height

    def wait_state(sport):
        WebDriverWait(driver, 15).until(lambda d: d.execute_script(
            'return shredApp.state().sport.id') == sport)

    def frame():
        WebDriverWait(driver, 20).until(lambda d: d.execute_script('return document.getElementById("skateFrame").dataset.ready === "true"'))
        driver.switch_to.frame(driver.find_element(By.ID, 'skateFrame'))
        WebDriverWait(driver, 15).until(lambda d: len(d.find_elements(By.CSS_SELECTOR, '.deal-card')) > 0)

    def visible_cards():
        return driver.execute_script('''return Array.from(document.querySelectorAll('#cardGrid .deal-card'))
            .filter(card=>!card.classList.contains('filtered-out')&&!card.classList.contains('grouped-hide')&&card.offsetParent!==null)
            .map(card=>({name:card.dataset.name,store:card.dataset.store,price:parseFloat(card.dataset.price)}))''')

    try:
        driver = browser()
        driver.set_page_load_timeout(25)
        viewport(1440, 1000)
        driver.get(base+'?store=CCS&type=deck&width=8.25&utm_source=prototype-test')
        wait_state('skate')
        frame()
        cards = visible_cards()
        assert cards and all(card['store'] == 'CCS' for card in cards)
        assert driver.execute_script('return document.getElementById("brandFacet").getBoundingClientRect().top < document.getElementById("contextSpecs").getBoundingClientRect().top')
        retailer_links = driver.execute_script('return Array.from(document.querySelectorAll("#cardGrid a[target=_blank]")).map(a=>a.href)')
        assert retailer_links and all(url.startswith('https://') for url in retailer_links)
        driver.switch_to.default_content()
        assert 'utm_source=prototype-test' in driver.current_url
        passed.append('Legacy Skate URLs, retailer links, and Brand-before-dimensions preserved')

        # Exercise the original app's controls; no duplicate implementation.
        frame()
        driver.find_element(By.ID, 'homeReset').click()
        search = driver.find_element(By.ID, 'searchInput')
        search.send_keys('baker')
        WebDriverWait(driver, 15).until(lambda d: visible_cards() and all('baker' in c['name'].lower() for c in visible_cards()))
        WebDriverWait(driver, 10).until(lambda d: 'q=baker' in d.current_url)
        Select(driver.find_element(By.ID, 'sortSelect')).select_by_value('price')
        WebDriverWait(driver, 10).until(lambda d: 'sort=price' in d.current_url)
        prices = [card['price'] for card in visible_cards()]
        assert prices == sorted(prices)
        driver.find_element(By.ID, 'navAlerts').click()
        WebDriverWait(driver, 10).until(lambda d: d.execute_script('return isAlertsOpen()'))
        driver.execute_script('closeAlerts()')
        driver.find_element(By.ID, 'homeReset').click()
        # Chart data remains available from the copied public history file.
        driver.execute_script('whenHistory(()=>{document.documentElement.dataset.previewHistoryReady="true"})')
        WebDriverWait(driver, 15).until(lambda d: d.execute_script('return document.documentElement.dataset.previewHistoryReady === "true"'))
        assert driver.execute_script('return matchMedia("(hover: hover) and (pointer: fine)").matches')
        first = driver.find_element(By.CSS_SELECTOR, '#cardGrid .deal-card:not(.filtered-out)')
        ActionChains(driver).move_to_element(first).perform()
        quick = first.find_element(By.CSS_SELECTOR, '.card-quick')
        quick.click()
        WebDriverWait(driver, 10).until(lambda d: d.execute_script('return isQuickOpen()'))
        driver.switch_to.default_content()
        driver.save_screenshot(str(screenshots/'desktop-quick-view.png'))
        driver.back()
        frame()
        WebDriverWait(driver, 10).until(lambda d: not d.execute_script('return isQuickOpen()'))
        driver.switch_to.default_content()
        passed.append('Existing search, sorting, Subscribe UI, price history, desktop Quick View and Back preserved')
        driver.find_element(By.ID, 'brandHome').click()
        driver.find_element(By.ID, 'sport-skate').send_keys(Keys.ARROW_LEFT)
        wait_state('bmx')
        assert driver.execute_script('return document.activeElement.id') == 'sport-bmx'
        assert driver.find_element(By.ID, 'sport-bmx').get_attribute('tabindex') == '0'
        assert driver.find_element(By.ID, 'sport-skate').get_attribute('tabindex') == '-1'
        assert driver.find_element(By.ID, 'skateFrame').get_attribute('hidden') is not None
        driver.find_element(By.ID, 'sport-ski').click()
        wait_state('ski')
        driver.back()
        wait_state('bmx')
        driver.forward()
        wait_state('ski')
        driver.find_element(By.ID, 'sport-ski').send_keys(Keys.END)
        wait_state('bmx')
        driver.find_element(By.ID, 'sport-bmx').send_keys(Keys.HOME)
        wait_state('skate')
        passed.append('Keyboard arrows/Home/End, focus/roving tabindex, sport-only Back/Forward restoration')
        driver.find_element(By.ID, 'sport-bmx').click()
        assert driver.find_element(By.ID, 'comingSoon').is_displayed()
        assert not driver.find_element(By.ID, 'skateFrame').is_displayed()
        assert 'no catalog yet' in driver.find_element(By.ID, 'comingSoon').text
        driver.save_screenshot(str(screenshots/'desktop-bmx.png'))
        driver.get(base)
        frame()
        driver.execute_script('document.activeElement.blur()')
        driver.switch_to.default_content()
        ActionChains(driver).move_to_element(driver.find_element(By.ID, 'brandHome')).perform()
        driver.save_screenshot(str(screenshots/'desktop-skate.png'))
        assert not driver.find_elements(By.ID, 'disciplineTabs')
        passed.append('Other sports never display Skate inventory; no discipline subdivision is rendered')
        driver.quit()
        driver = browser(coarse=True)
        driver.set_page_load_timeout(25)
        viewport(390, 844)
        driver.get(base+'?sport=mtb')
        wait_state('mtb')
        assert not driver.find_element(By.ID, 'skateFrame').is_displayed()
        assert driver.execute_script('return document.documentElement.scrollWidth <= innerWidth')
        driver.save_screenshot(str(screenshots/'mobile-mtb.png'))
        driver.find_element(By.ID, 'sport-skate').click()
        wait_state('skate')
        frame()
        assert driver.execute_script('return innerWidth') == 390
        assert driver.execute_script('return document.documentElement.scrollWidth <= innerWidth')
        assert driver.execute_script('return matchMedia("(pointer: coarse)").matches')
        driver.switch_to.default_content()
        driver.save_screenshot(str(screenshots/'mobile-skate.png'))
        viewport(390, 400)
        driver.find_element(By.ID, 'sport-mtb').click()
        driver.execute_script('document.getElementById("sportPanel").scrollTop=100')
        assert driver.execute_script('return document.querySelector(".shell-header").getBoundingClientRect().top') == 0
        assert driver.execute_script('return scrollY') == 0
        passed.append('True 390×844 mobile viewport, coarse pointer, compact navigation, persistent header at short heights, preserved responsive Skate iframe')
        result = {'status':'passed', 'checks':passed, 'browser':driver.capabilities['browserName'],
                  'version':driver.capabilities['browserVersion'], 'viewports':[[1440,1000],[390,844]],
                  'screenshots':['desktop-skate.png','desktop-bmx.png','desktop-quick-view.png','mobile-skate.png','mobile-mtb.png']}
        (screenshots/'browser-results.json').write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps(result,indent=2))
        return result
    finally:
        if driver:driver.quit()
        server.shutdown()
        server.server_close()


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--preview-dir',required=True,type=Path)
    parser.add_argument('--screenshots',required=True,type=Path)
    parser.add_argument('--firefox',type=Path,default=shutil.which('firefox'))
    parser.add_argument('--geckodriver',type=Path,default=shutil.which('geckodriver'))
    args=parser.parse_args(argv)
    if not args.firefox or not args.geckodriver:
        parser.error('Supply installed Firefox and geckodriver paths')
    run(args.preview_dir,args.screenshots,args.firefox,args.geckodriver)
    return 0


if __name__=='__main__':raise SystemExit(main())
