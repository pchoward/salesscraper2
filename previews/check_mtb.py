"""Opt-in desktop/mobile checks for saved MTB pages; never starts a scraper."""
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
from selenium.webdriver.support.ui import Select,WebDriverWait
from previews.check_navigation import QuietHandler


def run(site,shots,firefox,geckodriver):
    site,shots=Path(site).resolve(),Path(shots).resolve()
    manifest=json.loads((site/'review-manifest.json').read_text())
    shots.mkdir(parents=True,exist_ok=True)
    server=ThreadingHTTPServer(('127.0.0.1',0),functools.partial(QuietHandler,directory=str(site)))
    threading.Thread(target=server.serve_forever,daemon=True).start()
    base=f'http://127.0.0.1:{server.server_port}/'
    driver=None;checks=[]
    def browser(coarse=False):
        options=Options();options.binary_location=str(firefox);options.add_argument('-headless');options.enable_bidi=True
        options.set_preference('ui.primaryPointerCapabilities',1 if coarse else 6)
        options.set_preference('ui.allPointerCapabilities',1 if coarse else 6)
        return webdriver.Firefox(options=options,service=Service(str(geckodriver),log_output=str(shots/'browser.log')))
    def viewport(w,h):driver.browsing_context.set_viewport(context=driver.current_window_handle,viewport={'width':w,'height':h})
    def cards():return driver.execute_script('''return Array.from(document.querySelectorAll('#cardGrid .deal-card'))
        .filter(c=>!c.classList.contains('filtered-out')&&!c.classList.contains('grouped-hide')&&c.offsetParent!==null)
        .map(c=>({name:c.dataset.name,part:c.dataset.part,price:parseFloat(c.dataset.price)}))''')
    def choose(key,value):Select(driver.find_element(By.ID,'tech-'+key)).select_by_value(value)
    def show_specs():
        button=driver.find_element(By.CSS_SELECTOR,'#productSpecs>.section-toggle')
        if button.get_attribute('aria-expanded')!='true':button.click()
    try:
        driver=browser();viewport(1440,1000)
        driver.get(base+'mtb/sale_items_chart.html')
        WebDriverWait(driver,15).until(lambda d:cards())
        show_specs()
        driver.save_screenshot(str(shots/'desktop-mtb.png'))
        assert driver.execute_script('return document.documentElement.scrollWidth<=innerWidth')
        if manifest['synthetic']:
            assert len(cards())==12
            choose('wheel_size','29');WebDriverWait(driver,10).until(lambda d:'mtb_wheel=29' in d.current_url)
            assert sum(c['part']=='Tires' for c in cards())==2
            assert any(c['part']=='Protection' for c in cards()), 'unrelated categories remain visible'
            tire=driver.find_element(By.CSS_SELECTOR,'.deal-card[data-part="Tires"]:not(.filtered-out)')
            assert '$55.00' in tire.find_element(By.CSS_SELECTOR,'.now-price').text
            assert '$90.00' in tire.find_element(By.CSS_SELECTOR,'.avg-price').text
            choose('tire_width','2.4');WebDriverWait(driver,10).until(lambda d:sum(c['part']=='Tires' for c in cards())==0)
            choose('tire_width','2.5');WebDriverWait(driver,10).until(lambda d:sum(c['part']=='Tires' for c in cards())==2)
            driver.back();WebDriverWait(driver,10).until(lambda d:sum(c['part']=='Tires' for c in cards())==0)
            driver.forward();WebDriverWait(driver,10).until(lambda d:sum(c['part']=='Tires' for c in cards())==2)
            checks.append('Exact wheel/width same-variant filtering, variant price and compare-at, URL Back/Forward')
        else:
            selects=driver.find_elements(By.CSS_SELECTOR,'#contextSpecs select')
            if selects and len(Select(selects[0]).options)>1:
                Select(selects[0]).select_by_index(1)
                WebDriverWait(driver,10).until(lambda d:'mtb_' in d.current_url)
                assert cards()
            checks.append('Real saved catalog loads with available technical filters')
        driver.find_element(By.ID,'clearAll').click()
        WebDriverWait(driver,10).until(lambda d:'mtb_' not in d.current_url)
        Select(driver.find_element(By.ID,'sortSelect')).select_by_value('price')
        WebDriverWait(driver,10).until(lambda d:'sort=price' in d.current_url)
        assert [c['price'] for c in cards()]==sorted(c['price'] for c in cards())
        first=driver.find_element(By.CSS_SELECTOR,'.deal-card:not(.filtered-out)')
        ActionChains(driver).move_to_element(first).perform();first.find_element(By.CSS_SELECTOR,'.card-quick').click()
        WebDriverWait(driver,10).until(lambda d:d.execute_script('return isQuickOpen()'))
        driver.save_screenshot(str(shots/'desktop-quickview.png'))
        driver.back();WebDriverWait(driver,10).until(lambda d:not d.execute_script('return isQuickOpen()'))
        links=driver.find_elements(By.CSS_SELECTOR,'.card-store-link')
        assert links and all(l.get_attribute('target')=='_blank' for l in links)
        assert not driver.execute_script('return Boolean(window.SKATEDEALS_ALERTS)')
        checks.append('Clear all, original sort/Quick View/Back/new-tab retailer links, no live alerts config')
        driver.quit();driver=browser(True);viewport(390,844)
        driver.get(base+'mtb/sale_items_chart.html');WebDriverWait(driver,15).until(lambda d:cards())
        assert driver.execute_script('return innerWidth')==390
        assert driver.execute_script('return document.documentElement.scrollWidth<=innerWidth')
        driver.save_screenshot(str(shots/'mobile-mtb.png'))
        driver.find_element(By.ID,'filtersOpen').click();show_specs()
        driver.save_screenshot(str(shots/'mobile-filters.png'))
        if manifest['synthetic']:
            choose('wheel_size','29')
            WebDriverWait(driver,10).until(lambda d:'mtb_wheel=29' in d.current_url)
        driver.find_element(By.ID,'filtersClose').click()
        assert cards()
        checks.append('True 390x844 mobile layout, original drawer, technical filter and preserved results')
        result={'status':'passed','synthetic':manifest['synthetic'],'checks':checks,'viewports':[[1440,1000],[390,844]]}
        (shots/'browser-results.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
    finally:
        if driver:driver.quit()
        server.shutdown();server.server_close()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('site','screenshots','firefox','geckodriver'):p.add_argument('--'+key,required=True,type=Path)
    a=p.parse_args();run(a.site,a.screenshots,a.firefox,a.geckodriver)


if __name__=='__main__':main()
