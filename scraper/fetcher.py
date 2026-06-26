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
            # We explicitly execute Javascript in the browser to forcefully open
            # every single accordion, bypassing Playwright's visibility checks.
            # This ensures we never miss a plan due to a weird CSS trick or slow animation.
            page.evaluate('''() => {
                // Click any button in the pricing box that is currently closed
                const box = document.querySelector("#pricingAndFloorPlanBox");
                if (box) {
                    const buttons = box.querySelectorAll('button[aria-expanded="false"]');
                    buttons.forEach(btn => btn.click());
                    
                    // Also try the specific class if it wasn't caught by aria-expanded
                    const classButtons = box.querySelectorAll('.accordionItemButton');
                    classButtons.forEach(btn => {
                        if (btn.getAttribute('aria-expanded') !== 'true') {
                            btn.click();
                        }
                    });
                }
            }''')
            page.wait_for_timeout(1000) # Give it a full second to render all changes
        except Exception as e:
            print(f"Warning: Failed to expand accordions via JS: {e}")

        page.wait_for_timeout(1000)

        # Prefer just the pricing section to reduce noise from unrelated page areas
        try:
            # We explicitly tell Playwright to extract the innerText, but we also 
            # execute a small Javascript script in the browser to ensure the DOM 
            # returns text for elements even if they are technically hidden/collapsed 
            # by CSS (in case our click logic above failed on a weird element).
            content = page.evaluate('''() => {
                const box = document.querySelector("#pricingAndFloorPlanBox");
                return box ? box.innerText : document.body.innerText;
            }''')
            
            # Fallback if Javascript returned None
            if not content:
                content = page.locator("#pricingAndFloorPlanBox").inner_text(timeout=5000)
        except Exception:
            content = page.inner_text("body")

        browser.close()
        return content
