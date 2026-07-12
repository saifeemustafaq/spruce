# Prometheus Apartments — BMR Listing Tracker

Automatically checks Prometheus apartment listings every hour and sends an email alert the moment a BMR (Below Market Rate), Income Limit, or under-$3k unit becomes available.

Currently tracked properties:
- [Spruce Apartments Sunnyvale](https://prometheusapartments.com/ca/sunnyvale-apartments/spruce)
- [Kensington Place Sunnyvale](https://prometheusapartments.com/ca/sunnyvale-apartments/kensington-place)

Each property is tracked independently, with its own state and history files under `scraper/data/<property>/`.

---

## How it works

1. **GitHub Actions** triggers the script on a schedule — every hour, 24/7, for free
2. For each tracked property, the script calls Prometheus's internal JSON API (`.../<property_id>/available-units`) directly — no browser needed
3. It parses the returned units and looks for any plan containing **`BMR`** / **`Income Limit`**, or any unit priced under $3,000
4. Because the API only returns units that are currently available, any match means a unit just opened up
5. If a match is found → you get an email with the plan name, price, and details
6. Every run also records added/removed/price/date changes into that property's `listings_history.md`

```
Every hour
    └── GitHub Actions runner starts
        └── For each property in config.PROPERTIES:
            └── Call available-units JSON API
                ├── Record any changes into scraper/data/<property>/listings_history.md
                ├── No BMR / deal found → no BMR alert
                └── Found → send Gmail alert to saifeemustafaq@gmail.com
```

---

## Adding a new property

1. Open the property's listing page in Chrome, open DevTools → Network, filter for `available-units`, and reload. The number in that request URL is the property ID.
2. Add an entry to `PROPERTIES` in [scraper/config.py](scraper/config.py) with its `key`, `name`, `property_id`, and `page_url`.
3. That's it — the scraper will create `scraper/data/<key>/` files automatically on the next run.

---

## Project structure

```
.github/
  workflows/
    check-listings.yml   # Scheduled GitHub Actions workflow (runs every hour)
scraper/
  config.py              # Property registry (PROPERTIES) + settings
  fetcher.py             # Calls the Prometheus JSON API
  parser.py              # Normalizes API units + detects BMR/deals
  tracker.py             # Diffs against saved state, writes history
  notifier.py            # Sends property-aware Gmail alerts
  main.py                # Loops over all properties
  check.py               # Entry point (python scraper/check.py)
  data/
    <property>/
      listings_state.json    # Last-seen units for this property
      listings_history.md    # Human-readable change log
      snapshot.json          # Raw API snapshot (changes mode only)
```

---

## Action items (you must do these)

### 1. Generate a Gmail App Password

You need a special app password — your regular Gmail password won't work.

1. Go to [myaccount.google.com](https://myaccount.google.com) → **Security**
2. Make sure **2-Step Verification** is turned ON
3. Search for **"App passwords"** in the search bar
4. Select app: **Mail** → Generate
5. Google gives you a **16-character password** — copy it, you'll need it in the next step

### 2. Add the App Password as a GitHub Secret

This keeps your password encrypted and out of the code.

1. Go to `github.com/saifeemustafaq/spruce`
2. Click **Settings** → **Secrets and variables** → **Actions**
3. Click **New repository secret**
4. Set:
   - **Name:** `GMAIL_APP_PASSWORD`
   - **Value:** the 16-character password from Step 1
5. Click **Add secret**

### 3. Merge this branch to main

The GitHub Actions workflow only runs automatically from the **default branch** (main).

1. Go to `github.com/saifeemustafaq/spruce`
2. Open a pull request from `claude/apartment-listing-tracker-aq5p6m` → `main`
3. Merge it

### 4. Test it manually

Once merged, trigger a manual run to confirm everything works:

1. Go to `github.com/saifeemustafaq/spruce` → **Actions**
2. Click **Check BMR Listings** in the left sidebar
3. Click **Run workflow** → **Run workflow**
4. Watch the logs — you should see either:
   - `No BMR or Income Limit listings found. No alert sent.` ← working correctly, nothing available yet
   - `FOUND [BMR + Income Limit]: Plan ...` + email in your inbox ← a unit is available!

---

## What the email looks like

**Subject:**
```
BMR Alert — 2 units available at Spruce Apartments Sunnyvale!
```

**Body:**
```
2 BMR / Income Limit units just appeared at Spruce!

  [BMR + Income Limit] Plan 1D-BMR (Income Limit)
  $2,618
  1 Bed
  1 Bath
  676 Sq Ft

  [BMR + Income Limit] Plan 2B-BMR (Income Limit)
  $3,131
  2 Beds
  2 Baths
  936 Sq Ft

Apply now:
https://prometheusapartments.com/ca/sunnyvale-apartments/spruce
```

---

## Tracking modes

The scraper has two modes you can toggle without touching any code.

### `bmr` mode (default)
Silent unless a BMR / Income Limit unit appears. You only hear from it when something is actually available.

### `changes` mode
Emails you whenever **anything** on the listing page changes — new content, removed content, price updates, anything. The email shows exactly what was added (`+`) and removed (`-`) so you can cross-check it against the real website. Use this to verify the scraper is reading the page correctly.

**Example change detection email:**
```
Subject: Spruce — Page changed (+3 / -1 lines)

ADDED (3 lines):
  + Plan 1D-BMR (Income Limit)
  + $2,618
  + 1 Bed

REMOVED (1 line):
  - Loading...
```

### How to toggle

1. Go to `github.com/saifeemustafaq/spruce` → **Settings** → **Variables** → **Actions**
2. Create (or edit) a variable named `TRACKING_MODE`
3. Set value to `bmr` or `changes`
4. The next hourly run picks it up automatically

**Recommended workflow:**
1. Set `TRACKING_MODE = changes` and run manually
2. The first run emails you: *"Baseline saved"* — confirming it loaded the page
3. Wait for a page change (or manually verify against the site)
4. Once satisfied the detection works, set `TRACKING_MODE = bmr`

## Schedule

Runs at the top of every hour. GitHub Actions may delay it by a few minutes under heavy load.

---

## Cost

**Free.** GitHub Actions gives every account 2,000 free minutes/month for private repos (unlimited for public). Each run takes roughly 1–2 minutes, so 24 runs/day × 30 days × 2 min = ~1,440 minutes/month — within the free tier.
