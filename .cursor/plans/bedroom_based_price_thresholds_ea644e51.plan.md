---
name: bedroom based price thresholds
overview: "Make the \"cheap unit\" price alert bedroom-aware: 1-bedroom (and studio) units alert when rent is under $3,000, while 2-bedroom (incl. \"with Den\") and 3-bedroom units alert only when rent is between $2,950 and $4,000."
todos:
  - id: parser-threshold
    content: Update find_bmr_plans in scraper/parser.py to compute bedroom-aware thresholds (1BR<3000, 2BR+ 2950-4000 exclusive) and store bedrooms/price.
    status: completed
  - id: classify-label
    content: Update classify in scraper/parser.py to emit a threshold-accurate deal label including bedroom count.
    status: completed
  - id: notifier-copy
    content: Update send_bmr_alert body wording in scraper/notifier.py to describe the two price thresholds.
    status: completed
isProject: false
---

# Bedroom-based price thresholds

## Goal
Replace the flat `price <= 3000` rule with bedroom-aware thresholds, using the reliable API `bedrooms` field:
- 1BR (and studio, `bedrooms <= 1`): alert when `price < 3000`
- 2BR+/3BR (`bedrooms >= 2`, includes "Plan 2C with Den"): alert when `2950 < price < 4000` (both ends exclusive)

BMR and Income Limit matches are unchanged and still always alert.

## Why the `bedrooms` field
The API data (see [scraper/data/spruce/listings_state.json](scraper/data/spruce/listings_state.json)) exposes a clean `bedrooms` value (`"1"`, `"2"`), and `"Plan 2C with Den"` already reports `bedrooms: "2"`. This avoids fragile plan-name string parsing.

## Changes

### 1. `find_bmr_plans` in [scraper/parser.py](scraper/parser.py)
Parse `bedrooms` to an int and apply the correct threshold:

```python
try:
    bedrooms = int(str(u.get("bedrooms", "0")).strip() or "0")
except (ValueError, TypeError):
    bedrooms = 0

try:
    price_str = u.get("bestRent") or u.get("rent") or "999999"
    price = float(price_str)
    if bedrooms <= 1:
        is_deal = price < 3000
    else:
        is_deal = 2950 < price < 4000
except (ValueError, TypeError):
    is_deal = False
```

Keep the existing dict shape but also store `bedrooms` (for a clearer label). The `is_cheap` key is reused as `is_deal`, and `price`/`bedrooms` are added.

### 2. `classify` in [scraper/parser.py](scraper/parser.py)
Update the price label so the email states the actual threshold that matched, e.g.:
- 1BR: `Under $3k (${price}, 1BR)`
- 2BR+: `Deal $2950-$4000 (${price}, 2BR)`

### 3. `send_bmr_alert` copy in [scraper/notifier.py](scraper/notifier.py)
Line ~108 currently says "BMR, Income Limit, or Under $3k unit". Reword to reflect the two thresholds, e.g. "BMR, Income Limit, or price-deal unit (1BR under $3k / 2-3BR $2,950-$4,000)".

## Notes / decisions
- Boundaries are strict on both ends as confirmed: 1BR `< 3000`; 2BR+ `2950 < price < 4000`.
- Studios (`bedrooms == 0`) follow the 1BR rule.
- Only affects `TRACKING_MODE == "bmr"` runs (the default), matching current behavior in [scraper/main.py](scraper/main.py).
- Sanity check against current data: 1BR unit `B-215` at $3,296 will no longer alert (was flagged before only if <=3000, so no change); all current 2BRs ($4,508-$4,873) stay above $4,000 so they won't alert — expected.
