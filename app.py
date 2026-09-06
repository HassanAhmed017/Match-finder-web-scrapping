import io
from pathlib import Path
from datetime import datetime

import pandas as pd
import requests
from bs4 import BeautifulSoup
from flask import Flask, redirect, render_template, request, send_file, url_for

APP_DIR = Path(__file__).resolve().parent
app = Flask(
    __name__,
    template_folder=APP_DIR,
    static_folder=APP_DIR,
    static_url_path="/static",
)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# Holds the most recent successful scrape so the CSV download doesn't
# need to hit the site again.
_last_result = {"date_str": None, "rows": None}


class ScrapeError(Exception):
    """Raised for anything that stops us from returning match data."""


def parse_date(date_str: str) -> datetime:
    """
    Accepts the date from the HTML5 date picker (YYYY-MM-DD), and as a
    fallback also accepts mm/dd/yyyy typed by hand. Anything else raises
    a clear, actionable error instead of crashing.
    """
    date_str = (date_str or "").strip()
    for fmt in ("%Y-%m-%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    raise ScrapeError(
        f"Couldn't read the date '{date_str}'. Pick it from the calendar, "
        "or type it as mm/dd/yyyy."
    )


def scrape_matches(date_obj: datetime):
    """Fetches and parses yallakora's matches-center page for one date."""
    url = (
        "https://www.yallakora.com/matches-center"
        f"?date={date_obj.month}/{date_obj.day}/{date_obj.year}"
    )

    try:
        res = requests.get(url, headers=HEADERS, timeout=15)
    except requests.RequestException as exc:
        raise ScrapeError(
            f"Couldn't reach yallakora.com ({exc.__class__.__name__}). "
            "Check the connection and try again."
        ) from exc

    if res.status_code != 200:
        raise ScrapeError(f"yallakora.com returned status {res.status_code}.")

    soup = BeautifulSoup(res.text, "lxml")
    match_cards = soup.find_all("div", class_="matchCard")
    if not match_cards:
        return []

    championships = {}
    for card in match_cards:
        h2 = card.find("h2")
        if not h2:
            continue
        championship_name = h2.text.strip()

        matches = []
        for item in card.find_all("div", class_="liItem"):
            top_data = item.find("div", class_="topData")
            teams_data = item.find("div", class_="teamsData")
            if not teams_data:
                continue

            team_a_div = teams_data.find("div", class_="teamA")
            team_a = (
                team_a_div.find("p").text.strip()
                if team_a_div and team_a_div.find("p")
                else None
            )

            team_b_div = teams_data.find("div", class_="teamB")
            team_b = (
                team_b_div.find("p").text.strip()
                if team_b_div and team_b_div.find("p")
                else None
            )

            result_div = teams_data.find("div", class_="MResult")
            score = (
                [s.text.strip() for s in result_div.find_all("span", class_="score")]
                if result_div
                else []
            )
            time_span = result_div.find("span", class_="time") if result_div else None
            time_text = time_span.text.strip() if time_span else None

            round_text = None
            status = None
            if top_data:
                date_div = top_data.find("div", class_="date")
                round_text = date_div.text.strip() if date_div else None
                status_div = top_data.find("div", class_="matchStatus")
                status_span = status_div.find("span") if status_div else None
                status = status_span.text.strip() if status_span else None

            matches.append(
                {
                    "team_a": team_a,
                    "team_b": team_b,
                    "score": score,
                    "time": time_text,
                    "round": round_text,
                    "status": status,
                }
            )

        championships.setdefault(championship_name, []).extend(matches)

    rows = []
    for champ_name, match_list in championships.items():
        for m in match_list:
            score = m["score"] or []
            if len(score) >= 2 and score[0].strip() and score[1].strip():
                score_display = f"{score[0].strip()} - {score[1].strip()}"
            else:
                score_display = "_ - _"

            rows.append(
                {
                    "championship": champ_name,
                    "team_a": m["team_a"],
                    "team_b": m["team_b"],
                    "score": score_display,
                    "time": m["time"],
                    "round": m["round"],
                    "status": m["status"],
                }
            )

    return rows


def group_by_championship(rows):
    grouped = {}
    for r in rows:
        grouped.setdefault(r["championship"], []).append(r)
    return grouped


@app.route("/", methods=["GET"])
def index():

    #grouped none tells the interface to not show any matches yet
    return render_template("index.html", grouped=None, date_str="", error=None)


@app.route("/scrape", methods=["POST"])
def scrape():
    date_str = request.form.get("date", "")
    try:
        date_obj = parse_date(date_str)
        rows = scrape_matches(date_obj)
    except ScrapeError as exc:
        return render_template(
            "index.html", grouped=None, date_str=date_str, error=str(exc)
        )

    _last_result["date_str"] = date_obj.strftime("%Y-%m-%d")
    _last_result["rows"] = rows


    return render_template(
        "index.html",
        grouped=group_by_championship(rows),
        date_str=date_obj.strftime("%Y-%m-%d"),
        display_date=date_obj.strftime("%A, %d %B %Y"),
        error=None,
        searched=True,
    )


@app.route("/download")
def download():
    if not _last_result["rows"]:
        return redirect(url_for("index"))

    df = pd.DataFrame(_last_result["rows"])
    buf = io.BytesIO()
    df.to_csv(buf, index=False, encoding="utf-8-sig")
    buf.seek(0)

    filename = f"matches_{_last_result['date_str']}.csv"
    return send_file(
        buf, mimetype="text/csv", as_attachment=True, download_name=filename
    )


if __name__ == "__main__":
    app.run(debug=False)
