from playwright.sync_api import sync_playwright

def scrape_page(target_url):
    """
    Fetches the page content using Playwright.
    Targets the pricing section specifically if found, otherwise grabs the body text.
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--no-sandbox", "--disable-dev-shm-usage"])
        page = browser.new_page(user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ))
        page.goto(target_url, wait_until="domcontentloaded", timeout=60000)

        try:
            page.wait_for_selector("#pricingAndFloorPlanBox", timeout=15000)
        except Exception:
            pass

        page.wait_for_timeout(4000)

        # The floor plans are hidden inside accordions. Let's find all the
        # buttons in the pricing section that expand the accordions and click them.
        try:
            pricing_box = page.locator("#pricingAndFloorPlanBox")
            
            # Find all closed accordions - they could be buttons OR divs acting as buttons.
            # Look for anything with aria-expanded="false" inside an accordion item
            buttons = pricing_box.locator('[aria-expanded="false"]')
            count = buttons.count()
            
            for i in range(count):
                btn = buttons.nth(i)
                try:
                    btn.click(timeout=2000)
                    page.wait_for_timeout(300) # Let animation play
                except Exception:
                    pass
        except Exception as e:
            print(f"Warning: Failed to expand accordions: {e}")

        page.wait_for_timeout(1000)

        # Prefer just the pricing section to reduce noise from unrelated page areas
        try:
            content = page.locator("#pricingAndFloorPlanBox").inner_text(timeout=5000)
        except Exception:
            content = page.inner_text("body")

        browser.close()
        return content
