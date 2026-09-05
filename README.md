# MatchDay

A small local web interface for the yallakora.com scraper.

## Run it

```bash
pip install -r requirements.txt
python app.py
```

Then open **http://127.0.0.1:5000** in your browser.

## Using it

1. Pick a date with the calendar field (no more manual `mm/dd/yyyy` typing —
   the browser's date picker handles the format for you, and the backend
   also still accepts `mm/dd/yyyy` if typed directly).
2. Click **Get matches**. Fixtures are grouped by championship, with score,
   status/time, and round shown for each match.
3. Click **Download CSV** to save the same data as a `.csv` file
   (this re-uses the last search — no need to scrape twice).

## Notes

- If yallakora.com is unreachable or changes its page structure, the app
  shows a plain-language error instead of crashing.
- If there simply aren't any matches on the chosen date, that's shown
  explicitly rather than looking like a failure.
