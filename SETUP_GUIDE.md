# 🍽️ Restaurant Reservation Monitor — Setup Guide
### No coding experience needed. Follow these steps in order.

---

## What This Does

This program runs quietly in the background on your Mac. At key times each day
(like 10:00 AM and midnight — when reservation windows typically open), it checks
Resy and OpenTable for the restaurants you care about. The moment a slot appears
that matches your date and preferred dining times, it texts you immediately so
you can go book it.

---

## Step 1: Install Python on Your Mac

Python is the language this program is written in. Your Mac may already have it.

1. Open the **Terminal** app on your Mac
   - Press `Command + Space`, type "Terminal", hit Enter
2. Type this and press Enter:
   ```
   python3 --version
   ```
3. If you see something like `Python 3.10.x` — great, you're done with this step!
4. If you get an error, go to **https://www.python.org/downloads/** and click
   the big yellow "Download Python" button. Install it like any normal app.

---

## Step 2: Download the Program Files

1. Download the three files from Claude:
   - `monitor.py`
   - `config.json`
   - `requirements.txt`

2. Create a folder on your Desktop called **ReservationMonitor**

3. Move all three files into that folder

---

## Step 3: Install the Program's Dependencies

Dependencies are small helper tools the program needs. You install them once.

1. Open Terminal
2. Type this exactly and press Enter:
   ```
   cd ~/Desktop/ReservationMonitor
   ```
3. Then type this and press Enter:
   ```
   pip3 install -r requirements.txt
   ```
4. You'll see some text scroll by. Wait for it to finish. That's it!

---

## Step 4: Set Up Gmail Alerts (So It Can Text You)

This uses a free Gmail account to send you alerts. The cleverest part: you can
have it "email" your phone number, which your carrier converts to a text message.

### 4a. Create (or use) a Gmail account
Any Gmail will do. You can create a free one at gmail.com if you don't want
to use your personal one.

### 4b. Turn on 2-Step Verification
1. Go to **myaccount.google.com**
2. Click "Security" on the left
3. Find "2-Step Verification" and turn it on (follow the prompts)

### 4c. Create an App Password
This is a special password just for this program — it keeps your real password safe.
1. Go to **myaccount.google.com/apppasswords**
2. Under "App name", type: `ReservationMonitor`
3. Click "Create"
4. Google will show you a 16-character password like `xxxx xxxx xxxx xxxx`
5. **Copy this — you'll need it in Step 5**

### 4d. Find your phone's email-to-text address
Your carrier gives your phone number an email address that arrives as a text:

| Carrier    | Your address                        |
|------------|-------------------------------------|
| AT&T       | 1234567890@txt.att.net              |
| Verizon    | 1234567890@vtext.com                |
| T-Mobile   | 1234567890@tmomail.net              |
| Sprint     | 1234567890@messaging.sprintpcs.com  |

Replace `1234567890` with your actual 10-digit phone number.

---

## Step 5: Edit the Config File

The config file is where you tell the program which restaurants to watch.
Open `config.json` in TextEdit (right-click the file → Open With → TextEdit).

### Fill in the email section:
```
"sender_address": "yourgmail@gmail.com",        ← the Gmail you set up
"sender_app_password": "xxxx xxxx xxxx xxxx",   ← the app password from Step 4c
"recipient_address": "5551234567@txt.att.net"   ← your phone's text address
```

### Add your restaurants:

**For a Resy restaurant, you need the `venue_id`:**
1. Go to the restaurant's page on resy.com
2. Right-click anywhere on the page → click "Inspect" (or press Option+Command+I)
3. Click the "Network" tab at the top of the panel that opens
4. Refresh the page
5. In the filter box, type `venue`
6. Click on one of the results and look for `"id":` — that number is your venue_id

**For an OpenTable restaurant, you need the `restaurant_id`:**
1. Go to the restaurant's page on opentable.com
2. Look at the URL — it will contain a number like `.../56789/...`
3. That number is your restaurant_id

### Example of a filled-in restaurant entry:
```json
{
  "name": "Lilia",
  "platform": "resy",
  "venue_id": "1505",
  "slug": "lilia",
  "city": "nyc",
  "party_size": 2,
  "book_days_in_advance": 28,
  "preferred_times": ["18:30", "19:00", "19:30", "20:00", "20:30"]
}
```

**book_days_in_advance:** How many days before your desired dinner date does the
reservation window open? Most restaurants: 14 days (2 weeks) or 28-30 days (1 month).
Check the restaurant's website or call to confirm.

---

## Step 6: Get Your Resy Auth Token

This lets the program log in as you on Resy.

1. Go to **resy.com** and log into your account in Chrome
2. Press `Option + Command + I` to open Developer Tools
3. Click the "Network" tab
4. Search for a restaurant on Resy
5. Click on any request that starts with `find` or `venue`
6. On the right side, look for "Request Headers"
7. Find the line that says `X-Resy-Auth-Token:` — that long string after the colon
   is your auth token. Copy it into config.json.

---

## Step 7: Run the Program

1. Open Terminal
2. Type:
   ```
   cd ~/Desktop/ReservationMonitor
   ```
3. Type:
   ```
   python3 monitor.py
   ```
4. You'll see messages like:
   ```
   📅 Scheduled check at 10:00 every day
   🚀 Reservation monitor is running!
   ```
5. **Leave this Terminal window open.** The program runs as long as it's open.

### To test it right now:
```
python3 monitor.py --test
```
This runs one check immediately so you can make sure alerts are working before
you wait for midnight.

---

## Step 8: Make It Run Automatically (Recommended)

By default, the monitor only runs while Terminal is open. This step makes it
run silently in the background **forever** — no Terminal window needed, and it
restarts automatically if you reboot your Mac.

This uses something built into every Mac called **launchd**. You set it up once
and never think about it again.

### How to set it up:

1. Make sure you have all 6 files in your **ReservationMonitor** folder:
   - `monitor.py`
   - `config.json`
   - `requirements.txt`
   - `com.reservationmonitor.plist`
   - `start_monitor.sh`
   - `stop_monitor.sh`

2. Open Terminal

3. Type this and press Enter (this gives the setup scripts permission to run):
   ```
   chmod +x ~/Desktop/ReservationMonitor/start_monitor.sh ~/Desktop/ReservationMonitor/stop_monitor.sh
   ```

4. Then type this and press Enter:
   ```
   bash ~/Desktop/ReservationMonitor/start_monitor.sh
   ```

5. You should see:
   ```
   ✅ Found Python at: /usr/bin/python3
   ✅ Success! The monitor is now running in the background.
   ```

6. **That's it. You can close Terminal.** The monitor is now running invisibly
   and will keep running even after you restart your Mac.

### To check it's working:
Open the file `monitor.log` in your ReservationMonitor folder using TextEdit.
It keeps a diary of every check the program runs. You should see entries like:
```
2024-03-01 10:00:01 - 🔍 Running reservation checks...
2024-03-01 10:00:03 - ✅ Check complete.
```

### To stop the monitor:
If you ever want to turn it off completely, open Terminal and type:
```
bash ~/Desktop/ReservationMonitor/stop_monitor.sh
```

### To restart it after making changes to config.json:
Any time you edit `config.json` (like adding a new restaurant), run:
```
bash ~/Desktop/ReservationMonitor/stop_monitor.sh
bash ~/Desktop/ReservationMonitor/start_monitor.sh
```

---

## Troubleshooting

**"Command not found" error:** Python isn't installed. Go back to Step 1.

**"No module named 'schedule'":** Run `pip3 install -r requirements.txt` again.

**Not getting texts:** Double-check your carrier email address from Step 4d.
Try sending a regular email to that address from your Gmail to confirm it works.

**"401 Unauthorized" from Resy:** Your auth token expired. Repeat Step 6.

**Program seems to do nothing:** Run with `--test` flag and check `monitor.log`
file in your folder — it records everything that happens.

---

## Need Help?

Just come back to Claude and paste any error message you see in the Terminal.
We can debug it together!
