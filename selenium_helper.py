from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
def get_chrome_driver():
    """Creates a headless Chrome driver. ChromeDriver version matched in Dockerfile."""
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-setuid-sandbox")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

    driver = webdriver.Chrome(service=Service("/usr/local/bin/chromedriver"), options=options)
    driver.set_page_load_timeout(30)
    return driver


def fetch_page_html(url: str, wait_selector: str = None, wait_timeout: int = 10) -> str | None:
    """Fetches a page using Selenium and returns its HTML. Optionally waits for a CSS selector."""
    import logging
    logger = logging.getLogger("selenium_helper")

    driver = None
    try:
        logger.info(f"[SELENIUM] Starting Chrome for: {url[:80]}")
        driver = get_chrome_driver()
        logger.info(f"[SELENIUM] Chrome started, navigating...")
        driver.get(url)
        logger.info(f"[SELENIUM] Page loaded, title: {driver.title[:60] if driver.title else 'none'}")

        if wait_selector:
            try:
                WebDriverWait(driver, wait_timeout).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, wait_selector))
                )
                logger.info(f"[SELENIUM] Wait selector found: {wait_selector}")
            except Exception:
                logger.info(f"[SELENIUM] Wait selector timeout: {wait_selector}")

        html = driver.page_source
        img_count = html.count('<img')
        logger.info(f"[SELENIUM] HTML length: {len(html)}, img tags: {img_count}")
        return html
    except Exception as e:
        logger.error(f"[SELENIUM] ERROR: {type(e).__name__}: {str(e)[:150]}")
        return None
    finally:
        if driver:
            try:
                driver.quit()
            except Exception:
                pass
