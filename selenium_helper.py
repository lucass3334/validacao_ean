from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


def get_chrome_driver():
    """Creates a headless Chrome driver with standard options."""
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-setuid-sandbox")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

    driver_path = "/usr/local/bin/chromedriver"
    driver = webdriver.Chrome(service=Service(driver_path), options=options)
    driver.set_page_load_timeout(20)
    return driver


def fetch_page_html(url: str, wait_selector: str = None, wait_timeout: int = 10) -> str | None:
    """Fetches a page using Selenium and returns its HTML. Optionally waits for a CSS selector."""
    driver = None
    try:
        driver = get_chrome_driver()
        driver.get(url)

        if wait_selector:
            try:
                WebDriverWait(driver, wait_timeout).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, wait_selector))
                )
            except Exception:
                pass  # Proceed with whatever loaded

        html = driver.page_source
        return html
    except Exception:
        return None
    finally:
        if driver:
            try:
                driver.quit()
            except Exception:
                pass
