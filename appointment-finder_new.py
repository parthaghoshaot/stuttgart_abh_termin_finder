"""Poll Stuttgart ABH appointment API and notify when a slot is available.

Flow:
1. GET /api/getOtaStartUp/ → obtain JWT
2. POST /api/postOtaNextStep/ → select service (opt-12_15: Übertrag)
3. POST /api/postOtaNextStep/ → confirm review (op_id from step 2 response)
4. GET /api/brick_ota_termin_getFirstAvailableTimeslot/ → check availability

When data.termin is not null, a slot exists → notify and open browser for booking.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
import threading

import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

BASE_URL = "https://stuttgart.konsentas.de"
STARTUP_URL = f"{BASE_URL}/api/getOtaStartUp/"
NEXT_STEP_URL = f"{BASE_URL}/api/postOtaNextStep/"
TIMESLOT_URL = f"{BASE_URL}/api/brick_ota_termin_getFirstAvailableTimeslot/"
FORM_URL = f"{BASE_URL}/form/7/?signup_new=1"

SERVICE_OPTION = "opt-12_15"
POLL_SECONDS = 10


def log(message: str) -> None:
    """Print a timestamped log message."""
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {message}")


BOOKING_CAPTURE_FILE = "booking_requests.json"


def notify(title: str, message: str) -> None:
    """Send a macOS notification and play an alert sound."""
    subprocess.run(
        ["osascript", "-e", f'display notification "{message}" with title "{title}" sound name "Glass"'],
        check=False,
    )
    subprocess.run(["afplay", "/System/Library/Sounds/Glass.aiff"], check=False)


def open_booking_browser(token: str) -> None:
    """Open a visible Chrome with the JWT pre-loaded and capture all API traffic."""
    options = Options()
    options.set_capability("goog:loggingPrefs", {"performance": "ALL"})
    options.add_argument("--window-size=1400,900")

    driver = webdriver.Chrome(options=options)
    driver.get(FORM_URL)

    # Inject the JWT into localStorage so the session is authenticated
    driver.execute_script(f"localStorage.setItem('ota_jwt', '{token}');")
    driver.refresh()

    # Navigate through the flow to reach the appointment step
    driver.execute_script(f"""
        localStorage.setItem('ota_jwt', '{token}');
    """)

    log("Browser opened. Complete your booking — all requests will be captured.")
    log(f"Requests will be saved to {BOOKING_CAPTURE_FILE} when you close the browser.")

    # Capture network events in background
    captured: dict[str, dict] = {}

    def capture_loop():
        while True:
            try:
                logs = driver.get_log("performance")
            except Exception:
                break
            for entry in logs:
                try:
                    msg = json.loads(entry["message"])["message"]
                    method = msg.get("method", "")
                    params = msg.get("params", {})

                    if method == "Network.requestWillBeSent":
                        req = params.get("request", {})
                        request_id = params.get("requestId", "")
                        url = req.get("url", "")
                        if "/api/" in url:
                            captured[request_id] = {
                                "url": url,
                                "method": req.get("method", "GET"),
                                "headers": req.get("headers", {}),
                                "postData": req.get("postData"),
                            }

                    elif method == "Network.responseReceived":
                        request_id = params.get("requestId", "")
                        if request_id in captured:
                            resp = params.get("response", {})
                            captured[request_id]["response_status"] = resp.get("status")
                            captured[request_id]["response_headers"] = resp.get("headers", {})

                    elif method == "Network.loadingFinished":
                        request_id = params.get("requestId", "")
                        if request_id in captured:
                            try:
                                body = driver.execute_cdp_cmd(
                                    "Network.getResponseBody", {"requestId": request_id}
                                )
                                raw = body.get("body", "")
                                try:
                                    captured[request_id]["response_body"] = json.loads(raw)
                                except json.JSONDecodeError:
                                    captured[request_id]["response_body"] = raw
                            except Exception:
                                pass

                except (json.JSONDecodeError, KeyError):
                    continue
            time.sleep(0.5)

    capture_thread = threading.Thread(target=capture_loop, daemon=True)
    capture_thread.start()

    # Wait for user to finish booking (browser window close)
    try:
        while True:
            try:
                _ = driver.window_handles
            except Exception:
                break
            time.sleep(1)
    except KeyboardInterrupt:
        pass

    # Save captured requests
    results = list(captured.values())
    with open(BOOKING_CAPTURE_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    log(f"Saved {len(results)} API requests to {BOOKING_CAPTURE_FILE}")
    for i, req in enumerate(results, 1):
        log(f"  {i}. {req['method']} {req['url']}")

    try:
        driver.quit()
    except Exception:
        pass


def common_headers(token: str | None = None) -> dict[str, str]:
    """Build common request headers."""
    headers = {
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Referer": FORM_URL,
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/148.0.0.0 Safari/537.36"
        ),
        "X-Requested-With": "XMLHttpRequest",
        "sec-ch-ua": '"Chromium";v="148", "Google Chrome";v="148", "Not/A)Brand";v="99"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"macOS"',
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def get_jwt() -> str:
    """Step 1: Call getOtaStartUp to obtain a fresh JWT token."""
    params = {
        "signupform_id": "7",
        "userauth": "",
        "queryParameter[signup_new]": "1",
        "r": "",
    }
    resp = requests.get(STARTUP_URL, params=params, headers=common_headers(), timeout=15)
    resp.raise_for_status()
    data = resp.json()
    log(f"[Step 1] getOtaStartUp → HTTP {resp.status_code} | code={data.get('code')} | jwt={data['data']['ota_jwt'][:40]}...")
    token = data["data"]["ota_jwt"]
    return token


def select_service(token: str) -> str:
    """Step 2: POST process selection. Returns the next op_id."""
    form_data = {
        "formdata[processes][0]": SERVICE_OPTION,
        "op_id": "id2",
        "navigation": "1",
    }
    resp = requests.post(NEXT_STEP_URL, data=form_data, headers=common_headers(token), timeout=15)
    resp.raise_for_status()
    data = resp.json()
    log(f"[Step 2] postOtaNextStep (select service) → HTTP {resp.status_code} | code={data.get('code')} | next_op_id={data['data']['op_id']} | op_type={data['data'].get('op_type')}")
    return data["data"]["op_id"]


def confirm_review(token: str, op_id: str) -> None:
    """Step 3: POST review confirmation."""
    form_data = {
        "0": "",
        "formdata[0]": "",
        "op_id": op_id,
        "navigation": "1",
    }
    resp = requests.post(NEXT_STEP_URL, data=form_data, headers=common_headers(token), timeout=15)
    resp.raise_for_status()
    data = resp.json()
    log(f"[Step 3] postOtaNextStep (confirm review) → HTTP {resp.status_code} | code={data.get('code')} | next_op_id={data['data']['op_id']} | op_type={data['data'].get('op_type')}")


def check_timeslot(token: str) -> dict | None:
    """Step 4: GET first available timeslot. Returns termin dict or None."""
    resp = requests.get(TIMESLOT_URL, headers=common_headers(token), timeout=15)
    resp.raise_for_status()
    data = resp.json()
    termin = data["data"]["termin"]
    log(f"[Step 4] getFirstAvailableTimeslot → HTTP {resp.status_code} | code={data.get('code')} | msg={data.get('msg')} | termin={termin}")
    return termin


def poll_once() -> bool:
    """Run the full flow once. Returns True if a slot was found."""
    token = get_jwt()
    review_op_id = select_service(token)
    confirm_review(token, review_op_id)
    termin = check_timeslot(token)

    if termin is not None:
        log(f"APPOINTMENT AVAILABLE: {json.dumps(termin, ensure_ascii=False, indent=2)}")
        notify("ABH Termin gefunden!", f"Termin verfügbar: {json.dumps(termin, ensure_ascii=False)[:100]}")
        open_booking_browser(token)
        return True

    log("No appointment available.")
    return False


def main() -> None:
    """Poll in a loop until an appointment is found."""
    log(f"Starting appointment monitor (polling every {POLL_SECONDS}s)...")
    log(f"Service: {SERVICE_OPTION}")

    while True:
        try:
            found = poll_once()
            if found:
                log("Continuing to monitor...")
        except requests.RequestException as exc:
            log(f"Network error: {exc}")
        except (KeyError, TypeError) as exc:
            log(f"Unexpected API response: {exc}")

        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("Stopped by user.")
        sys.exit(0)
