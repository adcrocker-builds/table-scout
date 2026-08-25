# Table Scout

A pair of Python scripts that hunt restaurant reservations across Resy, OpenTable, and Tock — built with Claude, iterated through real use.

**Monitor** watches specific restaurants and emails you the moment a slot opens on your target date. **Scout** runs every Monday morning, discovers new and notable restaurants, checks Thursday–Sunday evening availability for the next 8 weeks on Resy, and emails a formatted report. OpenTable and Tock are included via a one-click deep-link watchlist (both platforms block automation — contributions welcome).

> **Current state:** Resy automation is fully working. OpenTable and Tock support is a watchlist workaround — the goal is full automation as the platforms evolve or contributors find new approaches.

---

## What it does

### `monitor.py` — Targeted reservation watcher
- Watches a list of specific restaurants on Resy
- Checks at configurable times (e.g. right when books open at 10 AM, and at midnight)
- Sends an email alert the moment a slot opens on your target date and preferred times
- Runs continuously in the background via macOS launchd

### `weekly_scout.py` — Monday morning discovery report
- Scrapes Eater DC for new openings and essential restaurant lists
- Discovers all DC venues directly from Resy's explore page (guarantees valid slugs)
- Checks Thursday–Sunday 5–9 PM availability for the next 8 weeks on the top 25 venues
- Prioritizes "New Opening" and "Essential DC" venues over general Resy listings
- Generates a second section with one-click booking deep links for OpenTable and Tock restaurants (which block automation)
- Emails a formatted HTML report every Monday at 7 AM

---

## Prerequisites

- Python 3.9+
- Google Chrome (for Selenium)
- A Gmail account with [App Passwords](https://support.google.com/accounts/answer/185833) enabled
- A Resy account (free) — you'll need your API key and auth token

---

## Setup

### 1. Clone the repo

```bash
git clone https://github.com/YOUR_USERNAME/table-scout.git
cd table-scout
```

### 2. Install dependencies

```bash
pip3 install -r requirements.txt
```

### 3. Configure

Copy the example config and fill in your credentials:

```bash
cp config.example.json config.json
```

Edit `config.json`:

| Field | Where to find it |
|---|---|
| `email.sender_address` | Your Gmail address |
| `email.sender_app_password` | [Generate here](https://myaccount.google.com/apppasswords) — requires 2FA enabled |
| `email.recipient_address` | Where to send reports (can be same address) |
| `resy.api_key` | Open resy.com, open DevTools → Network, make any request, look for `Authorization: ResyAPI api_key="..."` header |
| `resy.auth_token` | Same network tab — look for `X-Resy-Auth-Token` header |

### 4. Add restaurants to watch

In `config.json`, fill in the `restaurants` array for the monitor and the `watchlist` array for OpenTable/Tock venues. See `config.example.json` for the format and field explanations.

---

## Running

### Test the weekly scout
```bash
python3 weekly_scout.py --test
```
Runs immediately and sends a report to your email — good for verifying your setup.

### Test the monitor
```bash
python3 monitor.py
```
Runs one check cycle and prints results.

### Schedule the weekly scout (Monday 7 AM)
```bash
bash start_scout.sh
```

### Schedule the monitor (runs continuously)
```bash
bash start_monitor.sh
```

### Stop either
```bash
bash stop_scout.sh
bash stop_monitor.sh
```

---

## Adapting for other cities

The weekly scout targets Washington DC by default. To point it at another city:

1. Find your city's Resy explore URL: `resy.com/cities/{city-slug}`
2. Update the `city` variable in `weekly_scout.py`
3. Replace the Eater DC URLs in `get_eater_names()` with your city's Eater feed

---

## How the Resy slug extraction works

Resy's API returns HTML (it's a single-page app), so the scout drives a headless Chrome browser to Resy's explore page, scrolls to load all results, and extracts venue slugs directly from `<a>` tags. This guarantees every venue in the report is actually bookable on Resy — no guessing or slug verification needed.

---

## OpenTable & Tock

Both platforms block automated access. The scout handles this with a pre-configured watchlist: you add restaurants manually to `config.json`, and the weekly report generates a calendar grid with one-click deep links — one button per restaurant per week, pre-filled with your party size and date.

---

## Files

| File | Purpose |
|---|---|
| `monitor.py` | Targeted watcher for specific restaurants |
| `weekly_scout.py` | Monday discovery + availability report |
| `config.json` | Your credentials and restaurant lists (gitignored) |
| `config.example.json` | Template — copy this to get started |
| `start_scout.sh` / `stop_scout.sh` | Schedule/unschedule the weekly scout |
| `start_monitor.sh` / `stop_monitor.sh` | Start/stop the continuous monitor |
| `com.weekscout.plist` | macOS launchd config for the scout |
| `requirements.txt` | Python dependencies |

---

## Known limitations

This started as a personal tool and grew through real use, so it has rough edges:

- OpenTable and Tock block automation, so they run through a manual watchlist with one-click deep links rather than full monitoring
- The weekly email's Resy links sometimes point to the wrong page or error out — the availability check is reliable, the deep-linking is not fully hardened
- Built and tested on macOS with launchd; other platforms need a different scheduler

I built this to learn and improve my AI fluency, not as an actively maintained project — so I may not respond to issues or PRs. That said, it's MIT licensed, so fork it freely and take it wherever you want.

---

## Built with

Python · Selenium · BeautifulSoup4 · Gmail SMTP · macOS launchd

Built iteratively with [Claude](https://claude.ai) — the monitor started as a simple script and grew into the two-script system here through real use and problem-solving.

---

## License

MIT — use it, fork it, adapt it.
