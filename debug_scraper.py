from playwright.sync_api import sync_playwright

target_url = "https://prometheusapartments.com/ca/sunnyvale-apartments/spruce"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto(target_url, wait_until="networkidle")
    
    page.wait_for_timeout(4000)
    
    pricing_box = page.locator("#pricingAndFloorPlanBox")
    print("Pricing box text initially:")
    print(pricing_box.inner_text()[:500])
    
    # Try to find the accordion buttons
    buttons = pricing_box.locator('h2 button, div[role="button"]')
    print(f"Found {buttons.count()} buttons")
    
    for i in range(buttons.count()):
        btn = buttons.nth(i)
        try:
            print(f"Clicking button: {btn.inner_text().strip()}")
            btn.click(timeout=2000)
            page.wait_for_timeout(500)
        except Exception as e:
            print(f"Could not click: {e}")
            
    print("\n--- After clicking ---")
    full_text = pricing_box.inner_text()
    print("Length of text:", len(full_text))
    import re
    plans = set(re.findall(r'Plan [A-Z0-9]+', full_text))
    print("Found plans:", plans)
    
    browser.close()
