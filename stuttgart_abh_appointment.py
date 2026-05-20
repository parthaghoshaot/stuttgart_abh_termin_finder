"""Local appointment checker for the Stuttgart immigration office form."""
import time
from typing import Optional

from selenium import webdriver
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

URL = "https://stuttgart.konsentas.de/form/7/?signup_new=1"
SEARCH_TERM = "Übertragung"
#SEARCH_TERM = "abholen"
POLL_MINUTES = 0.5  # alle X Minuten erneut prüfen

# ---------------- helpers ----------------

def log(msg: str):
    """Print a timestamped log message to the console."""
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}")

def type_search(driver, wait):
    """Enter the configured search term into the page search input."""
    search = wait.until(EC.presence_of_element_located((
        By.CSS_SELECTOR, "input[type='search'], input[placeholder*='Suche'], input[aria-label*='Suche']"
    )))
    search.clear()
    search.send_keys(SEARCH_TERM)
    time.sleep(0.3)

def keyboard_select_flow(driver):
    """
    Select the '1 Person' option using keyboard navigation.
    This works both for abholen and ubertragung services, as they are the first option in the dropdown.
    Sequence: 7x TAB, ARROW_DOWN, 1x TAB, ENTER.
    """
    ac = ActionChains(driver)
    for _ in range(7):
        ac.send_keys(Keys.TAB).pause(0.12)
    ac.send_keys(Keys.ARROW_DOWN).pause(0.15)
    for _ in range(1):
        ac.send_keys(Keys.TAB).pause(0.12)
    ac.send_keys(Keys.ENTER)
    ac.perform()
    log("Selection completed via keyboard flow.")


def click_weiter(driver, max_clicks: int = 10, retry_callback=None):
    """Click the 'Weiter' button until it disappears or max_clicks is reached."""
    idx = 1
    while idx <= max_clicks:
        try:
            time.sleep(5) # Important to wait for the next page to load after each click, otherwise we might click too fast and miss the button's state change.
            btn = driver.find_element(By.XPATH, "//button[normalize-space(text())='Weiter']")
            if btn.is_displayed() and btn.is_enabled():
                btn.click()
                log(f"Clicked 'Weiter' ({idx}).")
                idx += 1
            else:
                log("'Weiter' button is not visible/enabled; stopping click loop.")
                return
        except NoSuchElementException:
            log("'Weiter' button not found; stopping click loop.")
            return

    log(f"Too many 'Weiter' clicks ({max_clicks}); restarting the flow to recover.")
    if retry_callback:
        retry_callback()

def page_has_no_appointments(wait) -> bool:
    """
    Return True if a visible "No appointments available" message is found.
    Checks text-based locators first, then common error-box CSS selectors.
    """
    selectors = [
        # 1) Exact text
        (By.XPATH, "//*[contains(normalize-space(.), 'Keine verfügbaren Termine')]"),
        (By.XPATH, "//*[contains(normalize-space(.), 'Keine verf\u00FCgbaren Termine')]"),  # mit ü, falls nötig
        # 2) Bootstrap failure
        (By.CSS_SELECTOR, ".alert.alert-danger, .alert-danger, .message.error, .alert--danger")
    ]

    for by, sel in selectors:
        try:
            el = wait.until(EC.visibility_of_element_located((by, sel)))
            txt = el.text.strip().lower()
            if "keine verfügbaren termine" in txt or "keine verf" in txt:
                return True
        except TimeoutException:
            continue
    return False

def perform_full_check(driver, timeout: int = 20) -> bool:
    """
    Run one full availability check flow.
    Returns False when "No appointments available" is found, otherwise True.
    """
    wait = WebDriverWait(driver, timeout)
    
    def retry():
        """Restart the check flow from the initial page state."""
        log("Restarting perform_full_check...")
        driver.get(URL) 
        perform_full_check(driver, timeout)

    driver.get(URL)
    log("Page loaded.")
    
    type_search(driver, wait)
    keyboard_select_flow(driver)
    click_weiter(driver, max_clicks=10, retry_callback=retry)

    no_slots = page_has_no_appointments(wait)
    if no_slots:
        log("No appointments available; retrying later.")
        return False
    log("No red 'no appointments' message found; appointments may be available.")
    return True

# --------------- Driver Setup ----------------

def get_driver() -> Optional[webdriver.Chrome]:
    """Create and return a local Chrome WebDriver."""
    opts = webdriver.ChromeOptions()
    opts.add_argument("--disable-notifications")
    opts.add_argument("--start-maximized")
    try:
        driver = webdriver.Chrome(options=opts)
        log("WebDriver connection established successfully.")
        return driver
    except WebDriverException as e:
        log("ERROR: Failed to establish a WebDriver connection.")
        log("On macOS, use Selenium Manager by running 'pip install -U selenium' and keep Chrome updated.")
        log(f"Details: {e}")
        return None
    except Exception as e:
        log(f"Unexpected error during WebDriver initialization: {e}")
        return None

# --------------- monitor loop ----------------

def run_monitor(driver: webdriver.Chrome, interval_minutes: float) -> None:
    """Poll appointment availability in a loop until a possible slot is detected."""
    try:
        while True:
            log("Checking for available appointments...")
            try:
                available = perform_full_check(driver, timeout=45)
            except Exception as e:
                log(f"Error during check cycle: {e}")
                log("Resetting state and retrying.")
                time.sleep(5)
                continue

            if available:
                log("Appointments may be available. Continue in the browser and book now.")
                break
            else:
                log(f"No appointments. Next check in {interval_minutes} minute(s)...")
                time.sleep(interval_minutes * 60)
    finally:
        log("Monitoring loop ended.")

# --------------- main ----------------

def main():
    """Parse CLI arguments, initialize the driver, and start monitoring."""
    driver = get_driver()

    if driver:
        try:
            run_monitor(driver, interval_minutes=POLL_MINUTES)
            print("\nThe script found a possible appointment.")
            print("Please complete the booking in the connected browser window.")
            print("Press Ctrl+C to exit the program.")
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nProgram stopped by user.")
        finally:
            print("Script execution finished.")

if __name__ == "__main__":
    main()