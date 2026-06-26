from playwright.sync_api import sync_playwright


def scrape_page(target_url):
    """
    Fetches the page content using Playwright.
    Because the Prometheus site uses mutually exclusive accordions (opening one
    closes another), clicking them one-by-one never exposes all plans at once.
    Instead, we directly manipulate the DOM via JavaScript to remove the CSS
    height restriction on every collapsed accordion container, making all plan
    content readable in a single innerText pass — no clicking required.
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

        # The accordions are mutually exclusive — clicking one closes another.
        # Instead, we inject JS to forcibly reveal every collapsed container by
        # overriding the inline height style that the React component uses to hide them.
        try:
            revealed = page.evaluate('''() => {
                const box = document.querySelector("#pricingAndFloorPlanBox");
                if (!box) return 0;

                // Every collapsed accordion content div has style="height: 0px"
                // Overriding to "auto" makes all content visible simultaneously.
                const containers = box.querySelectorAll(".accordionContentContainer");
                containers.forEach(el => {
                    el.style.height = "auto";
                    el.style.overflow = "visible";
                });
                return containers.length;
            }''')
            print(f"Revealed {revealed} accordion containers")
        except Exception as e:
            print(f"Warning: Failed to reveal accordion containers: {e}")

        # Small wait to let any deferred rendering settle
        page.wait_for_timeout(500)

        # Read the full text of the pricing section now that all plans are visible
        try:
            content = page.evaluate('''() => {
                const box = document.querySelector("#pricingAndFloorPlanBox");
                return box ? box.innerText : document.body.innerText;
            }''')

            if not content:
                content = page.locator("#pricingAndFloorPlanBox").inner_text(timeout=5000)
        except Exception:
            content = page.inner_text("body")

        browser.close()
        return content
