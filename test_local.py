import json
import re

from scraper.parser import parse_listings

with open('sprucewebsite/Spruce _ Prometheus.html', 'r') as f:
    html = f.read()

# Since we're parsing HTML directly (not through Playwright), we have to simulate
# Playwright's inner_text() which strips tags but preserves newlines.
start = html.find('id="pricingAndFloorPlanBox"')
end = html.find('id="nearbyPlacesBox"', start)
if end == -1: end = start + 200000

chunk = html[start:end]
# A rough approximation of inner_text
text = re.sub('<[^>]+>', '\n', chunk)

units = parse_listings(text)
print(f"Found {len(units)} units")

for uid, data in units.items():
    print(f"Unit {uid}: {data['plan']}")
