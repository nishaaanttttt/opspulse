# OpsPulse

A weekly operations reporting tool that cleans task exports, calculates delivery KPIs, and creates a one-page PDF. All included data is synthetic.

## Live demo

[Open OpsPulse](https://opspulse-o146.onrender.com). The free Render service may take 50 seconds or more to wake after inactivity.

## Project files

- [Full README, setup instructions, and KPI definitions](opspulse/README.md)
- [Flask application](opspulse/app.py)
- [Sample task data](opspulse/data/sample_tasks.csv)
- [Pinned dependencies](opspulse/requirements.txt)

## Run locally

```bash
cd opspulse
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Open `http://127.0.0.1:5000` in a browser.
