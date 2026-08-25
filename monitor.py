#!/usr/bin/env python3
"""
Restaurant Reservation Monitor
Checks Resy and OpenTable for available reservations and sends you a text alert.
"""

import json
import time
import requests
import smtplib
import schedule
import logging
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# Load your configuration
with open("config.json", "r") as f:
    CONFIG = json.load(f)

# Set up logging so you can see what's happening
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(message)s",
    handlers=[
        logging.FileHandler("monitor.log"),
        logging.StreamHandler()
    ]
)
log = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# NOTIFICATION: Send yourself an email/text
# ─────────────────────────────────────────────

def send_alert(restaurant_name, platform, date, time_slot, party_size, booking_url):
    """Send an email alert which arrives as a text via carrier gateway."""

    subject = "RESERVATION AVAILABLE: " + restaurant_name + " on " + date + "!"
    body = (
        "A reservation just opened up!\n\n"
        "Restaurant: " + restaurant_name + "\n"
        "Platform:   " + platform + "\n"
        "Date:       " + date + "\n"
        "Time:       " + time_slot + "\n"
        "Party size: " + str(party_size) + "\n\n"
        "Book it now: " + booking_url + "\n\n"
        "Hurry - these go fast!"
    )

    try:
        msg = MIMEMultipart()
        msg["From"] = CONFIG["email"]["sender_address"]
        msg["To"] = CONFIG["email"]["recipient_address"]
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(
                CONFIG["email"]["sender_address"],
                CONFIG["email"]["sender_app_password"]
            )
            server.sendmail(
                CONFIG["email"]["sender_address"],
                CONFIG["email"]["recipient_address"],
                msg.as_string()
            )
        log.info("Alert sent for " + restaurant_name + " on " + date + " at " + time_slot)
    except Exception as e:
        log.error("Failed to send alert: " + str(e))


# ─────────────────────────────────────────────
# RESY CHECKER
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
    options.add_argument("user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=options
    )
    driver.set_page_load_timeout(30)
    driver.set_script_timeout(30)
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    return driver


def check_resy(restaurant):
    """Check Resy by visiting the restaurant page and reading available slots."""

    target_date = get_target_date(restaurant)
    venue_id = restaurant["venue_id"]
    party_size = restaurant["party_size"]
    name = restaurant["name"]
    city = restaurant.get("city", "nyc")
    slug = restaurant.get("slug", "")

    driver = None
    try:
        driver = get_browser()

        # Visit the restaurant page directly
        venue_url = "https://resy.com/cities/" + city + "/" + slug + "?date=" + target_date + "&seats=" + str(party_size)
        log.info("Visiting: " + venue_url)
        driver.get(venue_url)

        # Wait up to 15 seconds for reservation slots to appear on the page
        try:
            WebDriverWait(driver, 15).until(
                lambda d: any(x in d.page_source for x in ["button--time", "ReservationButton", "time-slot", "reservation-button", "5:00 PM", "6:00 PM", "7:00 PM", "8:00 PM"])
            )
            log.info("Slots detected on page, reading...")
        except Exception:
            log.info("Timed out waiting for slots -- reading page anyway")

        time.sleep(2)  # Extra buffer for full render
        page_source = driver.page_source

        # Check if page loaded properly
        if "resy" not in page_source.lower():
            log.warning("Resy page did not load properly for " + name)
            return

        # Try to find time slot buttons on the page
        slots_found = []
        try:
            # Try multiple possible CSS selectors for time buttons
            selectors = [
                "button.button--time",
                "[class*='ReservationButton']",
                "[class*='time-slot']",
                "[class*='TimeSlot']",
                "button[data-type='time']",
                "[class*='reservation-button']",
                "[data-test*='slot']",
            ]
            for selector in selectors:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                for el in elements:
                    text = el.text.strip()
                    if text and ":" in text and ("PM" in text or "AM" in text):
                        slots_found.append(text)
                if slots_found:
                    break
        except Exception:
            pass

        # Also try looking for time patterns in the page source
        if not slots_found:
            import re
            times = re.findall(r'([1-9]|1[0-2]):[0-5][0-9]\s*(?:AM|PM)', page_source)
            slots_found = list(set(times))

        if not slots_found:
            page_text = driver.find_element(By.TAG_NAME, "body").text.lower()
            if "no online availability" in page_text or "no reservations" in page_text:
                log.info("No availability yet for " + name + " on " + target_date + " -- will keep checking.")
            elif "join waitlist" in page_text:
                log.info("Only waitlist available for " + name + " on " + target_date)
            else:
                log.info("No slots found for " + name + " on " + target_date)
            return

        # Clean up slot text — extract just the time portion (e.g. "7:00 PM" from "7:00 PM\nDining Room")
        cleaned_slots = []
        for slot in slots_found:
            first_line = slot.split("\n")[0].strip()
            if ":" in first_line and ("PM" in first_line or "AM" in first_line):
                if first_line not in cleaned_slots:
                    cleaned_slots.append(first_line)

        log.info("Available slots for " + name + " on " + target_date + ": " + str(cleaned_slots))

        for time_display in cleaned_slots:
            if is_time_desired(time_display, restaurant.get("preferred_times", [])):
                log.info("Match found: " + time_display + " -- sending alert!")
                send_alert(name, "Resy", target_date, time_display, party_size, venue_url)

    except Exception as e:
        log.error("Error checking Resy for " + name + ": " + str(e))
    finally:
        if driver:
            driver.quit()


def check_opentable(restaurant):
    """Check OpenTable for available reservation slots."""

    target_date = get_target_date(restaurant)
    preferred_times = restaurant.get("preferred_times", ["19:00"])

    params = {
        "restaurant_id": restaurant["restaurant_id"],
        "date": target_date,
        "covers": restaurant["party_size"],
        "time": preferred_times[0],
    }

    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
        "Accept": "application/json",
        "Referer": "https://www.opentable.com/"
    }

    try:
        response = requests.get(
            "https://www.opentable.com/dapi/fe/gql",
            params=params,
            headers=headers,
            timeout=10
        )

        data = response.json()
        timeslots = data.get("data", {}).get("availability", {}).get("timeslots", [])

        for slot in timeslots:
            time_display = slot.get("time", "")
            if is_time_desired(time_display, preferred_times):
                restaurant_id = restaurant["restaurant_id"]
                booking_url = "https://www.opentable.com/restaurant/profile/" + str(restaurant_id) + "/reserve"
                send_alert(
                    restaurant["name"],
                    "OpenTable",
                    target_date,
                    time_display,
                    restaurant["party_size"],
                    booking_url
                )

    except requests.exceptions.RequestException as e:
        log.error("Network error checking OpenTable for " + restaurant["name"] + ": " + str(e))
    except Exception as e:
        log.error("Error checking OpenTable for " + restaurant["name"] + ": " + str(e))


# ─────────────────────────────────────────────
# HELPER FUNCTIONS
# ─────────────────────────────────────────────

def get_target_date(restaurant):
    """Return the specific date to check, or calculate from days_in_advance."""
    specific_date = restaurant.get("target_date", "").strip()
    if specific_date:
        try:
            datetime.strptime(specific_date, "%Y-%m-%d")
            return specific_date
        except ValueError:
            log.warning("Invalid target_date for " + restaurant["name"] + " -- falling back to days_in_advance")
    days_ahead = restaurant.get("book_days_in_advance", 14)
    target = datetime.now() + timedelta(days=days_ahead)
    return target.strftime("%Y-%m-%d")


def is_past_date(restaurant):
    """Return True if the target date has already passed."""
    date_str = get_target_date(restaurant)
    target = datetime.strptime(date_str, "%Y-%m-%d")
    if target.date() < datetime.now().date():
        log.info("Skipping " + restaurant["name"] + " -- target date " + date_str + " has already passed.")
        return True
    return False


def is_time_desired(time_str, preferred_times):
    """Check if an available slot is within your preferred dining times."""
    if not preferred_times:
        return True
    try:
        slot_hour = int(time_str.split(":")[0]) % 24
        for pref in preferred_times:
            pref_hour = int(pref.split(":")[0]) % 24
            if abs(slot_hour - pref_hour) <= 1:
                return True
    except Exception:
        return True
    return False


def run_checks():
    """Run all restaurant checks."""
    log.info("Running reservation checks...")

    for restaurant in CONFIG.get("restaurants", []):
        if is_past_date(restaurant):
            continue

        platform = restaurant.get("platform", "").lower()

        if platform == "resy":
            check_resy(restaurant)
        elif platform == "opentable":
            check_opentable(restaurant)
        else:
            log.warning("Unknown platform for " + restaurant["name"] + " -- skipping")

        time.sleep(2)

    log.info("Check complete.")


# ─────────────────────────────────────────────
# SCHEDULER
# ─────────────────────────────────────────────

def start_scheduler():
    """Schedule checks to run at the times reservation windows typically open."""

    check_times = CONFIG.get("check_times", ["09:55", "10:00", "10:05", "23:55", "00:00", "00:05"])

    for t in check_times:
        schedule.every().day.at(t).do(run_checks)
        log.info("Scheduled check at " + t + " every day")

    log.info("Reservation monitor is running! Press Ctrl+C to stop.")

    while True:
        schedule.run_pending()
        time.sleep(30)


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        log.info("Running test check now...")
        run_checks()
    else:
        start_scheduler()
