# Spruce Apartments — BMR Listing Tracker

Automatically checks the [Spruce Apartments Sunnyvale](https://prometheusapartments.com/ca/sunnyvale-apartments/spruce) listing page every hour and sends an email alert the moment a BMR (Below Market Rate) or Income Limit unit becomes available.

---

## How it works

1. **GitHub Actions** triggers the script on a schedule — every hour, 24/7, for free
2. A headless Chrome browser (Playwright) opens the listing page and waits for the JavaScript to fully render the floor plans
3. The script scans the rendered text for any plan containing **`BMR`** or **`Income Limit`**
4. Because Spruce only shows units that are currently available, any match means a unit just opened up
5. If a match is found → you get an email with the plan name, price, and details
6. If nothing is found → the job exits silently, no email sent

```
Every hour
    └── GitHub Actions runner starts
        └── Playwright opens Spruce listing page
            └── Waits for floor plans to load (JS-rendered)
                ├── No BMR / Income Limit found → exit silently
                └── Found → send Gmail alert to saifeemustafaq@gmail.com
```

---

## Project structure

```
.github/
  workflows/
    check-listings.yml   # Scheduled GitHub Actions workflow (runs every hour)
scraper/
  check.py               # Python script: scrape + detect + email
  requirements.txt       # Python dependencies (just playwright)
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

## Schedule

The job runs at the top of every hour (`0 * * * *`). GitHub Actions may delay it by a few minutes under heavy load, but it will run.

To change the frequency, edit `.github/workflows/check-listings.yml` and update the cron expression:

| Cron | Frequency |
|------|-----------|
| `0 * * * *` | Every hour (default) |
| `0 */2 * * *` | Every 2 hours |
| `0 9,17 * * *` | 9am and 5pm only |

---

## Cost

**Free.** GitHub Actions gives every account 2,000 free minutes/month for private repos (unlimited for public). Each run takes roughly 1–2 minutes, so 24 runs/day × 30 days × 2 min = ~1,440 minutes/month — within the free tier.
