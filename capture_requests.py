"""Open a visible Chrome browser to capture API requests from the Konsentas form.

Instructions:
1. Run this script: python capture_requests.py
2. The browser opens https://stuttgart.konsentas.de/form/7/?signup_new=1
3. Make your selections and click "Weiter"
4. The script captures all XHR/fetch requests and responses
5. Press Ctrl+C in the terminal when done — captured data is saved to captured_requests.json
"""

from __future__ import annotations

import json
import time

from selenium import webdriver
from selenium.webdriver.chrome.service import Service

FORM_URL = "https://stuttgart.konsentas.de/form/7/?signup_new=1"
OUTPUT_FILE = "captured_requests.json"


def make_driver() -> webdriver.Chrome:
    """Create a visible Chrome instance with network logging enabled."""
    options = webdriver.ChromeOptions()
    options.set_capability("goog:loggingPrefs", {"performance": "ALL"})
    options.add_argument("--auto-open-devtools-for-tabs")
    options.add_argument("--window-size=1400,900")
    return webdriver.Chrome(options=options)


def extract_network_events(driver: webdriver.Chrome) -> list[dict]:
    """Pull performance log entries related to network requests/responses."""
    logs = driver.get_log("performance")
    events = []
    for entry in logs:
        try:
            msg = json.loads(entry["message"])["message"]
            method = msg.get("method", "")
            if method in (
                "Network.requestWillBeSent",
                "Network.responseReceived",
                "Network.loadingFinished",
            ):
                events.append(msg)
        except (json.JSONDecodeError, KeyError):
            continue
    return events


def get_response_body(driver: webdriver.Chrome, request_id: str) -> str | None:
    """Attempt to get response body for a given request ID."""
    try:
        result = driver.execute_cdp_cmd("Network.getResponseBody", {"requestId": request_id})
        return result.get("body")
    except Exception:
        return None


def main() -> None:
    driver = make_driver()
    driver.get(FORM_URL)

    print(f"Browser opened: {FORM_URL}")
    print("Interact with the form, make your selections, and click 'Weiter'.")
    print("Press Ctrl+C when you're done to save captured requests.\n")

    all_requests: dict[str, dict] = {}

    try:
        while True:
            events = extract_network_events(driver)
            for event in events:
                method = event["method"]
                params = event.get("params", {})

                if method == "Network.requestWillBeSent":
                    req = params.get("request", {})
                    request_id = params.get("requestId", "")
                    url = req.get("url", "")
                    if "/api/" in url or "konsentas" in url:
                        all_requests[request_id] = {
                            "url": url,
                            "method": req.get("method", "GET"),
                            "headers": req.get("headers", {}),
                            "postData": req.get("postData"),
                            "timestamp": params.get("timestamp"),
                        }

                elif method == "Network.responseReceived":
                    request_id = params.get("requestId", "")
                    if request_id in all_requests:
                        resp = params.get("response", {})
                        all_requests[request_id]["response_status"] = resp.get("status")
                        all_requests[request_id]["response_headers"] = resp.get("headers", {})

                elif method == "Network.loadingFinished":
                    request_id = params.get("requestId", "")
                    if request_id in all_requests:
                        body = get_response_body(driver, request_id)
                        if body:
                            try:
                                all_requests[request_id]["response_body"] = json.loads(body)
                            except json.JSONDecodeError:
                                all_requests[request_id]["response_body"] = body

            time.sleep(0.5)

    except KeyboardInterrupt:
        print(f"\n\nCapturing complete. {len(all_requests)} API requests recorded.")

    finally:
        captured = list(all_requests.values())
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(captured, f, indent=2, ensure_ascii=False)
        print(f"Saved to {OUTPUT_FILE}")

        for i, req in enumerate(captured, 1):
            print(f"\n--- Request {i} ---")
            print(f"  {req['method']} {req['url']}")
            if req.get("postData"):
                print(f"  Body: {req['postData'][:200]}")
            if req.get("response_status"):
                print(f"  Response: HTTP {req['response_status']}")

        driver.quit()


if __name__ == "__main__":
    main()
