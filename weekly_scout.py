#!/usr/bin/env python3
"""
Weekly Restaurant Scout
Scrapes Eater DC for new/notable restaurants, checks Thu–Sun 5–9 PM availability
on Resy for the next 8 weeks, and emails a report every Monday morning.
"""

import json
import re
import time
import smtplib
import logging
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

with open("config.json", "r") as f:
    CONFIG = json.load(f)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(message)s",
    handlers=[
        logging.FileHandler("scout.log"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger(__name__)

PARTY_SIZE = 2
CITY = "washington-dc"
RESY_API_KEY = CONFIG["resy"]["api_key"]
RESY_AUTH_TOKEN = CONFIG["resy"]["auth_token"]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
}


# ─────────────────────────────────────────────
# DATE HELPERS
# ─────────────────────────────────────────────

def get_thu_sun_dates(weeks=8):
    """Return all Thursday–Sunday dates for the next N weeks."""
    dates = []
    today = datetime.now().date()
    for i in range(weeks * 7):
        d = today + timedelta(days=i)
        if d.weekday() in (3, 4, 5, 6):  # Thu=3 Fri=4 Sat=5 Sun=6
            dates.append(d.strftime("%Y-%m-%d"))
    return dates


def is_evening_slot(time_str):
    """Return True if slot is between 5:00 PM and 9:00 PM inclusive."""
    try:
        if "PM" not in time_str:
            return False
        hour = int(time_str.split(":")[0])
        return 5 <= hour <= 9
    except Exception:
        return False


# ─────────────────────────────────────────────
# RESTAURANT DISCOVERY (Eater DC)
# ─────────────────────────────────────────────

EATER_SOURCES = [
    ("New Opening",  "https://dc.eater.com/maps/best-new-restaurants-heatmap-dc"),
    ("Essential DC", "https://dc.eater.com/maps/dc-best-restaurants-38"),
]


def get_eater_names():
    """
    Fetch Eater DC map pages and return a set of restaurant names.
    Used to tag Resy-discovered venues as 'New Opening' or 'Essential DC'.
    """
    tagged = {}  # name -> label
    for label, url in EATER_SOURCES:
        try:
            resp = requests.get(url, headers=HEADERS, timeout=20)
            if resp.status_code != 200:
                continue
            soup = BeautifulSoup(resp.text, "html.parser")
            names = []
            for script in soup.find_all("script", type="application/ld+json"):
                try:
                    data = json.loads(script.string or "")
                    if data.get("@type") == "ItemList":
                        for item in data.get("itemListElement", []):
                            n = item.get("item", {}).get("name", "").strip()
                            if n:
                                names.append(n)
                        break
                except Exception:
                    pass
            if not names:
                names = [t.get_text(" ", strip=True) for t in soup.select("h2") if 3 <= len(t.get_text()) <= 60]
            for n in names:
                if n not in tagged:
                    tagged[n] = label
        except Exception as e:
            log.warning(f"Eater DC scrape error ({url}): {e}")
    log.info(f"Eater DC: tagged {len(tagged)} restaurants")
    return tagged


def discover_resy_dc_venues(driver):
    """
    Load Resy's DC explore page and extract all featured venue slugs + names.
    Returns list of {"name", "slug", "city"} dicts — all guaranteed bookable on Resy.
    """
    log.info("Loading Resy DC explore page...")
    driver.get("https://resy.com/cities/washington-dc")
    time.sleep(5)

    # Scroll to load more venue cards
    for _ in range(5):
        driver.execute_script("window.scrollBy(0, 900)")
        time.sleep(1.5)

    # Build a slug → name map from all venue links on the page
    slug_to_name = {}
    for link in driver.find_elements(By.TAG_NAME, "a"):
        href = link.get_attribute("href") or ""
        match = re.search(r"/cities/washington-dc/venues/([a-z0-9\-]+)", href)
        if not match:
            continue
        slug = match.group(1)
        if slug in slug_to_name:
            continue

        # Try several sources for the restaurant name
        name = (
            link.text.strip()
            or link.get_attribute("aria-label") or ""
        ).strip()

        # If the link itself has no text, check child elements
        if not name:
            try:
                child = link.find_element(By.CSS_SELECTOR, "[class*='name'], [class*='title'], h2, h3, span")
                name = child.text.strip()
            except Exception:
                pass

        # Last resort: derive a readable name from the slug
        if not name:
            name = slug.replace("-", " ").title()

        if name:
            slug_to_name[slug] = name

    log.info(f"Found {len(slug_to_name)} venues on Resy DC explore page")
    return [{"name": name, "slug": slug, "city": CITY} for slug, name in slug_to_name.items()]


# ─────────────────────────────────────────────
# RESY VENUE LOOKUP
# ─────────────────────────────────────────────

def tag_with_eater(venues, eater_names):
    """
    Add a 'source' tag to each venue if it appears in the Eater DC lists.
    Matching is fuzzy: checks if any Eater name is a substring of the Resy name or vice versa.
    """
    for venue in venues:
        resy_name_lower = venue["name"].lower()
        for eater_name, label in eater_names.items():
            eater_lower = eater_name.lower()
            # Match if names share 4+ consecutive chars or one contains the other
            if eater_lower in resy_name_lower or resy_name_lower in eater_lower:
                venue["source"] = label
                break
        if "source" not in venue:
            venue["source"] = "Resy DC"
    return venues


# ─────────────────────────────────────────────
# BROWSER
# ─────────────────────────────────────────────

def get_browser():
    """Launch a hidden Chrome browser."""
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    options.add_argument(f"user-agent={HEADERS['User-Agent']}")
    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=options,
    )
    driver.set_page_load_timeout(30)
    driver.set_script_timeout(30)
    driver.execute_script(
        "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    )
    return driver


# ─────────────────────────────────────────────
# AVAILABILITY CHECK
# ─────────────────────────────────────────────

def fetch_slots_for_date(driver, venue, date):
    """
    Visit one Resy venue/date page and return a sorted list of
    available Thu–Sun evening time slots (5–9 PM).
    Reuses the passed driver; caller is responsible for open/close.
    """
    slug = venue["slug"]
    city = venue.get("city", CITY)
    url = f"https://resy.com/cities/{city}/venues/{slug}?date={date}&seats={PARTY_SIZE}"
    try:
        driver.get(url)
        try:
            WebDriverWait(driver, 12).until(
                lambda d: any(
                    kw in d.page_source
                    for kw in [
                        "button--time", "5:00 PM", "6:00 PM",
                        "7:00 PM", "8:00 PM", "9:00 PM", "No availability",
                    ]
                )
            )
        except Exception:
            pass
        time.sleep(1)

        slots = []
        for selector in [
            "button.button--time",
            "[class*='ReservationButton']",
            "[class*='time-slot']",
            "[class*='TimeSlot']",
        ]:
            elements = driver.find_elements(By.CSS_SELECTOR, selector)
            for el in elements:
                text = el.text.strip().split("\n")[0]
                if ":" in text and ("PM" in text or "AM" in text):
                    slots.append(text)
            if slots:
                break

        return sorted(
            set(s for s in slots if is_evening_slot(s)),
            key=lambda s: (int(s.split(":")[0]), s)
        )

    except Exception as e:
        log.error(f"Error fetching slots for {venue['name']} on {date}: {e}")
        return []


def check_venue_availability(venue, dates):
    """
    Check a venue across all target dates using a single browser session.
    Returns {date_str: [time_slots]} for dates that have 5–9 PM availability.
    """
    results = {}
    driver = get_browser()
    try:
        for date in dates:
            slots = fetch_slots_for_date(driver, venue, date)
            if slots:
                results[date] = slots
            time.sleep(0.6)
    finally:
        driver.quit()
    return results


# ─────────────────────────────────────────────
# WATCHLIST QUICK-CHECK LINKS (OpenTable / Tock)
# ─────────────────────────────────────────────

def make_booking_url(entry, date_str, time_str="19:00"):
    """Build a pre-filled booking URL for a watchlist restaurant on a specific date."""
    platform = entry.get("platform", "").lower()
    slug = entry.get("slug", "")
    covers = entry.get("party_size", 2)
    dt = f"{date_str}T{time_str}"  # e.g. 2026-05-22T19:00

    if platform == "opentable":
        return (
            f"https://www.opentable.com/r/{slug}"
            f"?covers={covers}&datetime={dt}"
        )
    elif platform == "tock":
        hour_min = time_str.replace(":", "")  # "1900"
        return (
            f"https://www.exploretock.com/{slug}"
            f"?date={date_str}&size={covers}&time={hour_min}"
        )
    return ""


def build_watchlist_html(watchlist, dates):
    """
    Build the 'Quick Check' HTML section for OpenTable / Tock watchlist restaurants.
    Groups dates into weeks (Mon–Sun). Each restaurant gets a compact calendar row.
    """
    if not watchlist:
        return ""

    # Group Thu–Sun dates into calendar weeks
    weeks = {}
    for date_str in dates:
        d = datetime.strptime(date_str, "%Y-%m-%d")
        # Week key = Monday of that week
        monday = (d - timedelta(days=d.weekday())).strftime("%Y-%m-%d")
        weeks.setdefault(monday, []).append(date_str)

    week_keys = sorted(weeks.keys())

    ot_entries  = [e for e in watchlist if e.get("platform") == "opentable"]
    tock_entries = [e for e in watchlist if e.get("platform") == "tock"]

    html = """
<hr style="margin: 40px 0 28px; border-color: #ddd;"/>
<h1 style="color:#1a6b3c; font-size:20px; margin-bottom:4px;">
  &#128279; Quick Check — OpenTable &amp; Tock
</h1>
<p style="color:#666; font-size:13px; margin-bottom:20px;">
  These restaurants can't be auto-checked, but one click goes straight to the booking page for that evening.
  Links open pre-filled for party of 2 at 7 PM — adjust on the page as needed.
</p>
"""

    for section_label, entries, platform_color in [
        ("OpenTable", ot_entries, "#da3743"),
        ("Tock",      tock_entries, "#1a6b3c"),
    ]:
        if not entries:
            continue

        html += f"""
<h2 style="color:{platform_color}; font-size:16px; margin-top:28px; margin-bottom:10px;
           border-bottom: 2px solid #eee; padding-bottom:6px;">
  {section_label}
</h2>
<table style="border-collapse:collapse; width:100%; font-size:12px; margin-bottom:16px;">
<tr style="background:#f7f7f7;">
  <th style="padding:6px 8px; text-align:left; border-bottom:1px solid #ddd; min-width:160px;">Restaurant</th>
"""
        # Column headers: one per week, showing the Thu date
        for wk in week_keys:
            thu = weeks[wk][0]  # first date in the week group (always Thursday)
            d = datetime.strptime(thu, "%Y-%m-%d")
            html += f'<th style="padding:6px 4px; text-align:center; border-bottom:1px solid #ddd; white-space:nowrap;">{d.strftime("%-m/%-d")}<br/><span style="font-weight:normal;color:#888;">wk</span></th>\n'

        html += "</tr>\n"

        for entry in entries:
            name = entry["name"]
            note = entry.get("note", "")
            html += f'<tr><td style="padding:6px 8px; border-bottom:1px solid #f2f2f2; vertical-align:top;">'
            html += f'<b>{name}</b>'
            if note:
                html += f'<br/><span style="color:#999;font-size:11px;">{note}</span>'
            html += '</td>\n'

            for wk in week_keys:
                html += '<td style="padding:4px 4px; border-bottom:1px solid #f2f2f2; text-align:center; vertical-align:middle;">'
                day_links = []
                for date_str in weeks[wk]:
                    d = datetime.strptime(date_str, "%Y-%m-%d")
                    day_abbr = d.strftime("%a")  # "Thu", "Fri", etc.
                    url = make_booking_url(entry, date_str)
                    if url:
                        day_links.append(
                            f'<a href="{url}" style="display:inline-block;margin:1px;padding:2px 5px;'
                            f'background:{platform_color};color:#fff;border-radius:3px;'
                            f'text-decoration:none;font-size:10px;">{day_abbr}</a>'
                        )
                html += " ".join(day_links)
                html += "</td>\n"

            html += "</tr>\n"

        html += "</table>\n"

    html += """
<p style="font-size:11px; color:#aaa; margin-top:8px;">
  To add or remove restaurants from this section, edit the "watchlist" in config.json
  and restart the scout with <code>bash start_scout.sh</code>.
</p>
"""
    return html


# ─────────────────────────────────────────────
# REPORT
# ─────────────────────────────────────────────

def build_html_report(resy_findings, watchlist, dates):
    """
    resy_findings: list of venue dicts with 'availability' (from Resy)
    watchlist: list of OT/Tock entries from config.json
    dates: all Thu–Sun date strings for the 8-week window
    """
    today_str = datetime.now().strftime("%B %d, %Y")
    week_range = datetime.now().strftime("%b %d") + " – " + (
        datetime.now() + timedelta(weeks=8)
    ).strftime("%b %d, %Y")

    html = f"""
<html>
<head>
<meta charset="utf-8"/>
<style>
  body {{ font-family: Georgia, serif; max-width: 680px; margin: 0 auto; color: #222; padding: 16px; }}
  h1 {{ color: #9b2335; font-size: 22px; margin-bottom: 4px; }}
  .subtitle {{ color: #666; font-size: 13px; margin-bottom: 24px; }}
  h2 {{ color: #2c3e50; font-size: 17px; margin-top: 28px; margin-bottom: 2px;
        border-bottom: 2px solid #f0e6e6; padding-bottom: 5px; }}
  .source-tag {{ font-size: 11px; color: #9b2335; font-weight: normal;
                 background: #fdf0f0; border-radius: 3px; padding: 2px 6px;
                 margin-left: 6px; vertical-align: middle; }}
  .book-link {{ font-size: 13px; color: #9b2335; text-decoration: none; }}
  table.avail {{ border-collapse: collapse; width: 100%; margin-top: 8px; font-size: 13px; }}
  table.avail th {{ background: #f9f9f9; padding: 5px 10px; text-align: left;
        color: #555; font-weight: normal; border-bottom: 1px solid #ddd; }}
  table.avail td {{ padding: 6px 10px; border-bottom: 1px solid #f2f2f2; }}
  td.day {{ font-weight: bold; white-space: nowrap; color: #333; }}
  td.slots {{ color: #2c3e50; }}
  .none {{ color: #aaa; font-style: italic; font-size: 13px; padding: 8px 0; }}
  hr {{ border: none; border-top: 1px solid #eee; margin: 32px 0 0; }}
  .footer {{ font-size: 11px; color: #bbb; padding-top: 8px; }}
</style>
</head>
<body>
<h1>&#127869;&#65039; Weekly DC Restaurant Scout</h1>
<div class="subtitle">
  <b>{today_str}</b> &nbsp;·&nbsp; Thu–Sun evenings 5–9 PM &nbsp;·&nbsp; {week_range}
</div>

<h2 style="color:#9b2335; border-color:#9b2335;">Resy — Available This Week</h2>
<p style="font-size:12px;color:#888;margin-top:0;">
  Slots confirmed open right now. Book directly from the links below.
</p>
"""

    shown = 0
    for item in resy_findings:
        avail = item.get("availability", {})
        if not avail:
            continue
        shown += 1
        name = item["name"]
        source = item.get("source", "")
        slug = item.get("slug", "")
        resy_url = f"https://resy.com/cities/{CITY}/venues/{slug}"

        html += f'<h2>{name} <span class="source-tag">{source}</span></h2>\n'
        html += f'<p><a class="book-link" href="{resy_url}">Book on Resy &rarr;</a></p>\n'
        html += '<table class="avail"><tr><th>Date</th><th>Open times (5–9 PM)</th></tr>\n'

        for date_str in sorted(avail.keys()):
            d = datetime.strptime(date_str, "%Y-%m-%d")
            day_label = d.strftime("%A, %b %-d")
            slots_str = " &nbsp;&middot;&nbsp; ".join(avail[date_str])
            html += f'<tr><td class="day">{day_label}</td><td class="slots">{slots_str}</td></tr>\n'

        html += "</table>\n"

    if shown == 0:
        html += '<p class="none">No Thu–Sun evening slots found on Resy this week.</p>'

    # Watchlist section (OpenTable + Tock quick-check links)
    html += build_watchlist_html(watchlist, dates)

    html += f"""
<hr/>
<div class="footer">
  Generated by your Reservation Monitor &nbsp;&middot;&nbsp; {today_str}
</div>
</body>
</html>
"""
    return html


def send_report(resy_findings, watchlist, dates):
    """Send the HTML report email."""
    today_str = datetime.now().strftime("%B %d, %Y")
    subject = f"DC Restaurant Scout — Thu–Sun openings — {today_str}"
    html_body = build_html_report(resy_findings, watchlist, dates)

    try:
        msg = MIMEMultipart("alternative")
        msg["From"] = CONFIG["email"]["sender_address"]
        msg["To"] = CONFIG["email"]["recipient_address"]
        msg["Subject"] = subject
        msg.attach(MIMEText(html_body, "html"))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(
                CONFIG["email"]["sender_address"],
                CONFIG["email"]["sender_app_password"],
            )
            server.sendmail(
                CONFIG["email"]["sender_address"],
                CONFIG["email"]["recipient_address"],
                msg.as_string(),
            )

        count = sum(1 for f in resy_findings if f.get("availability"))
        log.info(f"Report sent — {count} Resy restaurants with availability + {len(watchlist)} watchlist entries")
    except Exception as e:
        log.error(f"Failed to send report: {e}")


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def run_scout():
    log.info("=== Weekly Restaurant Scout starting ===")

    dates = get_thu_sun_dates(weeks=8)
    log.info(f"Target: {len(dates)} Thu–Sun dates over 8 weeks")

    driver = get_browser()
    findings = []
    try:
        # Step 1: Get Eater DC tags (new openings / essential) — fast, no browser needed
        eater_names = get_eater_names()

        # Step 2: Discover Resy DC venues from Resy's own explore page
        # (all results are guaranteed bookable on Resy — no slug-guessing needed)
        all_venues = discover_resy_dc_venues(driver)

        # Tag each venue with its Eater source label, then sort:
        # New Openings first, then Essential DC, then the rest
        all_venues = tag_with_eater(all_venues, eater_names)
        priority = {"New Opening": 0, "Essential DC": 1, "Resy DC": 2}
        all_venues.sort(key=lambda v: priority.get(v.get("source", ""), 2))

        # Cap at 25 to keep Monday runtime reasonable (~40 min)
        venues = all_venues[:25]
        log.info(f"Checking {len(venues)} venues (of {len(all_venues)} discovered)")
        for v in venues:
            log.info(f"  [{v['source']}] {v['name']}")

        # Step 3: Check Thu–Sun 5–9 PM availability for each venue
        for venue in venues:
            log.info(f"Checking availability: {venue['name']}...")
            avail = {}
            for date in dates:
                slots = fetch_slots_for_date(driver, venue, date)
                if slots:
                    avail[date] = slots
                time.sleep(0.5)

            venue["availability"] = avail
            findings.append(venue)
            count = len(avail)
            log.info(f"  → {count} date{'s' if count != 1 else ''} with 5–9 PM openings")
            time.sleep(1)

    finally:
        driver.quit()

    # Step 4: Load watchlist (OT + Tock — quick-check links, no automated checking)
    watchlist = CONFIG.get("watchlist", [])
    log.info(f"Watchlist: {len(watchlist)} OpenTable/Tock restaurants for quick-check links")

    # Step 5: Send report
    restaurants_with_avail = [f for f in findings if f.get("availability")]
    log.info(
        f"=== Scout complete: {len(restaurants_with_avail)}/{len(findings)} Resy restaurants "
        f"have Thu–Sun availability; {len(watchlist)} watchlist entries ==="
    )
    send_report(findings, watchlist, dates)


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        log.info("Running scout test now...")
    run_scout()
