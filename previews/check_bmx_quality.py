"""Local Firefox acceptance/screenshots for the saved BMX quality preview."""
import argparse
import functools
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import threading

from selenium import webdriver
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.support.ui import Select, WebDriverWait

from previews.check_navigation import QuietHandler
from previews.shreddeals import SOURCE


def run(preview, shots, firefox, geckodriver):
    preview, shots = Path(preview).resolve(), Path(shots).resolve()
    if shots.is_relative_to(SOURCE):
        raise ValueError('Screenshots must be outside the checkout')
    audit=json.loads((preview/'quality-audit.json').read_text())
    if audit['scan_timestamp'] != '2026-11-01T18:52:07+00:00':
        raise ValueError('Build the saved quality preview first')
    shots.mkdir(parents=True,exist_ok=True)
    server=ThreadingHTTPServer(('127.0.0.1',0),functools.partial(QuietHandler,directory=str(preview/'site')))
    threading.Thread(target=server.serve_forever,daemon=True).start()
    base=f'http://127.0.0.1:{server.server_port}/'
    driver=None
    passed=[]

    def browser(coarse=False):
        options=Options()
        options.binary_location=str(firefox)
        options.add_argument('-headless')
        options.enable_bidi=True
        options.set_preference('ui.primaryPointerCapabilities',1 if coarse else 6)
        options.set_preference('ui.allPointerCapabilities',1 if coarse else 6)
        return webdriver.Firefox(options=options,service=Service(str(geckodriver),log_output=str(shots/'browser.log')))

    def viewport(width,height):
        driver.browsing_context.set_viewport(context=driver.current_window_handle,viewport={'width':width,'height':height})
        assert driver.execute_script('return innerWidth')==width

    def visible():
        return driver.execute_script('''return Array.from(document.querySelectorAll('#cardGrid .deal-card'))
        .filter(c=>!c.classList.contains('filtered-out')&&!c.classList.contains('grouped-hide')&&c.offsetParent!==null)
        .map(c=>({name:c.dataset.name,price:parseFloat(c.dataset.price)}))''')

    def expand_all():
        WebDriverWait(driver,15).until(lambda d:visible())
        for _ in range(6):
            count=len(visible())
            if count==63:return
            driver.find_element(By.ID,'showMoreCards').click()
            WebDriverWait(driver,10).until(lambda d:len(visible())>count)
        assert len(visible())==63, len(visible())

    try:
        driver=browser()
        viewport(1440,1000)
        driver.get(base+'bmx/sale_items_chart.html')
        expand_all()
        names={c['name'] for c in visible()}
        assert not names & {item['name'] for item in audit['excluded']}
        assert driver.find_element(By.ID,'lastScan').get_attribute('datetime')==audit['scan_timestamp']
        assert driver.execute_script('return document.documentElement.scrollWidth<=innerWidth')
        links=driver.execute_script('return Array.from(document.querySelectorAll("#cardGrid a[target=_blank]")).map(a=>a.href)')
        assert links and all('www.albes.com/products/' in link for link in links)
        driver.execute_script('scrollResultsToTop()')
        WebDriverWait(driver,15).until(lambda d:d.execute_script(
            'return Array.from(document.querySelectorAll("#cardGrid .deal-card:first-child img")).every(i=>i.complete)'))
        driver.save_screenshot(str(shots/'desktop-bmx.png'))
        passed.append('63 real distinct listings, nine exclusions absent, original scan time and retailer-first links preserved')
        driver.find_element(By.ID,'searchInput').send_keys('freecoaster')
        WebDriverWait(driver,10).until(lambda d:visible() and all('freecoaster' in c['name'].lower() for c in visible()))
        Select(driver.find_element(By.ID,'sortSelect')).select_by_value('price')
        WebDriverWait(driver,10).until(lambda d:'sort=price' in d.current_url)
        prices=[c['price'] for c in visible()]
        assert prices==sorted(prices)
        driver.find_element(By.ID,'navInsights').click()
        assert driver.find_element(By.ID,'statsPanel').is_displayed()
        driver.find_element(By.ID,'navDeals').click()
        assert 'q=freecoaster' in driver.current_url
        driver.find_element(By.ID,'navAlerts').click()
        WebDriverWait(driver,10).until(lambda d:d.execute_script('return isAlertsOpen()'))
        assert 'coming soon' in driver.find_element(By.ID,'alertsRoot').text.lower()
        driver.execute_script('closeAlerts()')
        driver.find_element(By.ID,'homeReset').click()
        driver.execute_script('whenHistory(()=>{document.documentElement.dataset.qualityHistory="ready"})')
        WebDriverWait(driver,15).until(lambda d:d.execute_script('return document.documentElement.dataset.qualityHistory')=='ready')
        card=driver.find_element(By.CSS_SELECTOR,'#cardGrid .deal-card:not(.filtered-out)')
        ActionChains(driver).move_to_element(card).perform()
        card.find_element(By.CSS_SELECTOR,'.card-quick').click()
        WebDriverWait(driver,10).until(lambda d:d.execute_script('return isQuickOpen()'))
        driver.save_screenshot(str(shots/'desktop-quickview.png'))
        driver.back()
        WebDriverWait(driver,10).until(lambda d:not d.execute_script('return isQuickOpen()'))
        passed.append('Original search, sort, Insights/Deals, offline Subscribe, history, Quick View and Back work')
        driver.get(base+'index.html?sport=bmx')
        WebDriverWait(driver,15).until(lambda d:d.execute_script('return document.getElementById("skateFrame").dataset.ready')=='true')
        driver.find_element(By.ID,'sport-skate').click()
        WebDriverWait(driver,15).until(lambda d:d.execute_script('return shredApp.state().sport.id')=='skate')
        driver.switch_to.frame(driver.find_element(By.ID,'skateFrame'))
        WebDriverWait(driver,15).until(lambda d:d.find_elements(By.CSS_SELECTOR,'.deal-card'))
        assert 'Albe' not in driver.find_element(By.ID,'cardGrid').text
        passed.append('Existing Skate catalog stays separate from BMX through the unchanged shell')
        driver.quit()
        driver=browser(coarse=True)
        viewport(390,844)
        driver.get(base+'bmx/sale_items_chart.html')
        expand_all()
        assert driver.execute_script('return document.documentElement.scrollWidth<=innerWidth')
        driver.execute_script('scrollResultsToTop()')
        WebDriverWait(driver,15).until(lambda d:d.execute_script(
            'return Array.from(document.querySelectorAll("#cardGrid .deal-card:first-child img")).every(i=>i.complete)'))
        driver.save_screenshot(str(shots/'mobile-bmx.png'))
        driver.find_element(By.ID,'filtersOpen').click()
        assert driver.find_element(By.CSS_SELECTOR,'.sidebar').is_displayed()
        driver.find_element(By.ID,'filtersClose').click()
        driver.find_element(By.ID,'searchInput').send_keys('freecoaster')
        WebDriverWait(driver,10).until(lambda d:visible() and all('freecoaster' in c['name'].lower() for c in visible()))
        passed.append('True 390x844 mobile layout, search and Filters drawer work without horizontal overflow')
        result={'status':'passed','checks':passed,'viewports':[[1440,1000],[390,844]],'browser':'firefox'}
        (shots/'browser-results.json').write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps(result,indent=2))
    finally:
        if driver:driver.quit()
        server.shutdown()
        server.server_close()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--preview-dir',type=Path,required=True)
    parser.add_argument('--screenshots',type=Path,required=True)
    parser.add_argument('--firefox',type=Path,required=True)
    parser.add_argument('--geckodriver',type=Path,required=True)
    args=parser.parse_args()
    run(args.preview_dir,args.screenshots,args.firefox,args.geckodriver)


if __name__=='__main__':main()
