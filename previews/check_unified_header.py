"""Opt-in Firefox acceptance checks for the native unified-header preview."""
import argparse
import functools
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import threading

from selenium import webdriver
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.support.ui import Select, WebDriverWait

from previews.check_navigation import QuietHandler
from previews.shreddeals import SOURCE


def run(preview, screenshots, firefox, geckodriver):
    preview, screenshots = Path(preview).resolve(), Path(screenshots).resolve()
    manifest = json.loads((preview / 'manifest.json').read_text())
    if not manifest.get('development_only') or not manifest.get('native_pages'):
        raise ValueError('Build the native isolated preview first')
    if screenshots.is_relative_to(SOURCE):
        raise ValueError('Screenshots must be outside checkout')
    screenshots.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(QuietHandler, directory=str(preview)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f'http://127.0.0.1:{server.server_port}/'
    passed = []
    driver = None

    def launch(coarse=False):
        options = Options()
        options.binary_location = str(firefox)
        options.add_argument('-headless')
        options.enable_bidi = True
        options.set_preference('ui.primaryPointerCapabilities', 1 if coarse else 6)
        options.set_preference('ui.allPointerCapabilities', 1 if coarse else 6)
        return webdriver.Firefox(options=options, service=Service(str(geckodriver), log_output=str(screenshots / 'browser.log')))

    def viewport(width, height):
        driver.browsing_context.set_viewport(context=driver.current_window_handle, viewport={'width': width, 'height': height})
        assert driver.execute_script('return innerWidth') == width

    def ready(sport='skate'):
        WebDriverWait(driver, 15).until(lambda d: d.execute_script(
            'return document.querySelector(".shred-sport[aria-current=page]")?.dataset.sport') == sport)

    def cards():
        return driver.execute_script('''return Array.from(document.querySelectorAll('#cardGrid .deal-card'))
            .filter(c=>!c.classList.contains('filtered-out')&&!c.classList.contains('grouped-hide')&&c.offsetParent!==null)
            .map(c=>({name:c.dataset.name,store:c.dataset.store,price:parseFloat(c.dataset.price)}))''')

    def sport(name):
        driver.find_element(By.CSS_SELECTOR, f'.shred-sport[data-sport={name}]').click()
        ready(name)

    def clean_layout():
        assert driver.execute_script('return document.querySelectorAll("header").length') == 1
        assert not driver.find_elements(By.TAG_NAME, 'iframe')
        assert driver.execute_script('return document.documentElement.scrollWidth <= innerWidth')
        # Every header control fits horizontally, without overlapping its siblings.
        assert driver.execute_script('''const selectors=['.brand','.shred-sports','.topnav-links','#filtersOpen'];
        const rects=selectors.map(s=>document.querySelector('.shred-header '+s)).filter(n=>n&&n.getClientRects().length).map(n=>n.getBoundingClientRect());
        return rects.every(r=>r.left>=0&&r.right<=innerWidth+1)&&rects.every((r,i)=>rects.slice(i+1).every(b=>r.right<=b.left+1||b.right<=r.left+1||r.bottom<=b.top+1||b.bottom<=r.top+1));''')

    try:
        driver = launch()
        viewport(1440, 1000)
        driver.get(base + '?store=CCS&type=deck&width=8.25&utm_source=header-test')
        ready()
        WebDriverWait(driver, 15).until(lambda d: cards())
        assert all(c['store'] == 'CCS' for c in cards())
        assert driver.execute_script('return document.getElementById("brandFacet").getBoundingClientRect().top < document.getElementById("contextSpecs").getBoundingClientRect().top')
        assert driver.execute_script('return document.getElementById("lastScan").dateTime')
        legacy = driver.current_url
        clean_layout()
        sport('bmx')
        assert not driver.find_elements(By.CSS_SELECTOR, '.deal-card')
        assert driver.find_element(By.CSS_SELECTOR, '.shred-empty').is_displayed()
        assert driver.find_element(By.CSS_SELECTOR, '.topnav-links button:last-child').get_attribute('disabled')
        driver.save_screenshot(str(screenshots / 'desktop-bmx.png'))
        driver.back()
        ready()
        assert driver.current_url == legacy, (driver.current_url, legacy)
        driver.forward()
        ready('bmx')
        sport('skate')
        assert driver.current_url == legacy, (driver.current_url, legacy)
        passed.append('Native sport page links, exact Skate query restoration, Back/Forward, honest non-Skate placeholders')

        first_link = driver.find_element(By.CSS_SELECTOR, '.shred-sport')
        first_link.send_keys(Keys.HOME)
        first_link.send_keys(Keys.END)
        assert driver.switch_to.active_element.get_attribute('data-sport') == 'bmx'
        driver.switch_to.active_element.send_keys(Keys.ARROW_RIGHT)
        assert driver.switch_to.active_element.get_attribute('data-sport') == 'skate'
        assert driver.current_url == legacy, (driver.current_url, legacy)
        passed.append('Native link keyboard semantics, Arrow/Home/End focus without destructive selection')

        driver.find_element(By.ID, 'homeReset').click()
        search = driver.find_element(By.ID, 'searchInput')
        search.send_keys('baker')
        WebDriverWait(driver, 15).until(lambda d: cards() and all('baker' in c['name'].lower() for c in cards()))
        WebDriverWait(driver, 10).until(lambda d: 'q=baker' in d.current_url)
        Select(driver.find_element(By.ID, 'sortSelect')).select_by_value('price')
        WebDriverWait(driver, 10).until(lambda d: 'sort=price' in d.current_url)
        assert [c['price'] for c in cards()] == sorted(c['price'] for c in cards())
        selected = driver.current_url
        driver.find_element(By.ID, 'navInsights').click()
        assert driver.find_element(By.ID, 'statsPanel').is_displayed()
        assert 'q=baker' in driver.current_url
        driver.find_element(By.ID, 'navDeals').click()
        driver.find_element(By.ID, 'navTrack').click()
        assert driver.find_element(By.ID, 'navTrack').get_attribute('aria-pressed') == 'true'
        driver.find_element(By.ID, 'navDeals').click()
        assert 'q=baker' in driver.current_url
        driver.find_element(By.ID, 'navAlerts').click()
        WebDriverWait(driver, 10).until(lambda d: d.execute_script('return isAlertsOpen()'))
        assert 'coming soon' in driver.find_element(By.ID, 'alertsRoot').text.lower()
        driver.execute_script('closeAlerts()')
        assert 'q=baker' in driver.current_url
        driver.find_element(By.CSS_SELECTOR, '.shred-sport[aria-current=page]').click()
        assert 'q=baker' in driver.current_url
        passed.append('Original search/sort, Deals/Track/Insights/Subscribe listeners and panel/filter retention')

        driver.find_element(By.ID, 'homeReset').click()
        driver.execute_script('whenHistory(()=>{document.documentElement.dataset.headerHistory="ready"})')
        WebDriverWait(driver, 15).until(lambda d: d.execute_script('return document.documentElement.dataset.headerHistory') == 'ready')
        links = driver.execute_script('return Array.from(document.querySelectorAll("#cardGrid a[target=_blank]")).map(a=>a.href)')
        assert links and all(link.startswith('https://') for link in links)
        first = driver.find_element(By.CSS_SELECTOR, '#cardGrid .deal-card:not(.filtered-out)')
        ActionChains(driver).move_to_element(first).perform()
        first.find_element(By.CSS_SELECTOR, '.card-quick').click()
        WebDriverWait(driver, 10).until(lambda d: d.execute_script('return isQuickOpen()'))
        driver.save_screenshot(str(screenshots / 'desktop-quickview.png'))
        driver.back()
        WebDriverWait(driver, 10).until(lambda d: not d.execute_script('return isQuickOpen()'))
        clean_layout()
        driver.save_screenshot(str(screenshots / 'desktop-skate.png'))
        passed.append('Retailer-first links, original history loading and Quick View with Back')
        for width in (1100, 900, 801):
            viewport(width, 900)
            clean_layout()
        driver.quit()
        driver = launch(coarse=True)
        viewport(390, 844)
        driver.get(base)
        ready()
        clean_layout()
        driver.save_screenshot(str(screenshots / 'mobile-skate.png'))
        driver.find_element(By.ID, 'filtersOpen').click()
        assert driver.find_element(By.CSS_SELECTOR, '.sidebar').is_displayed()
        driver.find_element(By.ID, 'filtersClose').click()
        sport('ski')
        clean_layout()
        driver.save_screenshot(str(screenshots / 'mobile-ski.png'))
        sport('mtb')
        assert not driver.find_elements(By.CSS_SELECTOR, '.deal-card')
        sport('skate')
        for width in (320, 360, 768):
            viewport(width, 844)
            clean_layout()
        viewport(390, 400)
        driver.execute_script('window.scrollTo(0,600)')
        assert abs(driver.find_element(By.CSS_SELECTOR, '.shred-header').rect['y'] - driver.execute_script('return scrollY')) < 2
        passed.append('390×844 mobile, 320/360/768px and intermediate desktop layout, filters drawer, sticky short viewport')
        result = {'status': 'passed', 'checks': passed, 'browser': driver.capabilities['browserName'],
                  'viewports': [[1440, 1000], [390, 844]], 'native_pages': True}
        (screenshots / 'browser-results.json').write_text(json.dumps(result, indent=2) + '\n')
        print(json.dumps(result, indent=2))
    finally:
        if driver:
            driver.quit()
        server.shutdown()
        server.server_close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--preview-dir', type=Path, required=True)
    parser.add_argument('--screenshots', type=Path, required=True)
    parser.add_argument('--firefox', type=Path, required=True)
    parser.add_argument('--geckodriver', type=Path, required=True)
    args = parser.parse_args()
    run(args.preview_dir, args.screenshots, args.firefox, args.geckodriver)


if __name__ == '__main__':
    main()
