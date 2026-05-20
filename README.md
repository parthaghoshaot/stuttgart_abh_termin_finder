# Immigration Appointment Checker

This project monitors the Stuttgart immigration office booking form for available appointments.
The code launches your browser and keeps on checking for appointment in the stuttgart abh. Once it finds one, it stops there, and you can book it for your purpose.


## Setup

Create and activate a virtual environment in the project folder:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install the dependency:

```bash
python -m pip install -U selenium
```


## Run

```bash
python stuttgart_abh_appointment.py
```

## Search Term

Update the `SEARCH_TERM` line in [stuttgart_abh_appointment.py](stuttgart_abh_appointment.py) based on the appointment type you want:

```python
#SEARCH_TERM = "abholen"
SEARCH_TERM = "Übertragung"
```

If you want the other appointment type, just swap which line is active and keep the other one commented.

## Notes

- Keep Google Chrome updated.
- Selenium Manager will resolve the browser driver automatically when using Selenium 4.6+.
- The browser window stays open if an appointment appears so you can continue manually from there onwards.
