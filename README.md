# Immigration Appointment Checker

This project monitors the Stuttgart immigration office booking system for available appointments.

## Setup

Create and activate a virtual environment in the project folder:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install dependencies:

```bash
python -m pip install -U requests selenium
```

## Run (New Appointment Finder)

```bash
python3 appointment-finder_new.py
```

What happens when you run it:

- The script polls the ABH API every 10 seconds from your terminal.
- It prints timestamped status logs for every check.
- It only opens a Chrome window after an appointment is found.
- When an appointment is found, it also sends a macOS notification + sound.

Stop the script with `Ctrl+C`.

## Why this is better

- Terminal-first monitoring: lower noise and less resource usage than keeping a browser session open all the time.
- Faster feedback loop: you can see each poll result directly in logs.
- Action only when needed: browser opens only when a slot is available, so you can jump straight into booking.
- Better automation flow: API polling is more robust for long-running checks than UI-only polling.

## Legacy Script (Optional)

If you want to use the older browser-first script:

```bash
python stuttgart_abh_appointment.py
```

## Search Term (Legacy Script)

Update the `SEARCH_TERM` line in [stuttgart_abh_appointment.py](stuttgart_abh_appointment.py) based on the appointment type you want:

```python
#SEARCH_TERM = "abholen"
SEARCH_TERM = "Übertragung"
```

If you want the other appointment type, just swap which line is active and keep the other one commented.

## Notes

- Keep Google Chrome updated.
- Selenium Manager will resolve the browser driver automatically when using Selenium 4.6+.
- The new finder keeps running in terminal and opens the browser only when an appointment is available.
