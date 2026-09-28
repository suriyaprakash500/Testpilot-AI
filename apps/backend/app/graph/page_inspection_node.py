import logging
import re
from typing import Dict, Any, List
from app.graph.state import TestPilotState
from playwright.async_api import async_playwright
from app.graph.playwright_runner import run_playwright, target_slot

# --- SPA post-navigation stabilization (Fix 1) ---
# ``domcontentloaded`` fires before a SPA's client-side router renders the final
# view, so an in-app 404 page can be mis-captured as an "unknown" page (and thus
# treated as a valid route). We wait (bounded) for network idle — which lets the
# router settle when the app does go idle — then a short fixed settle for
# frameworks that keep long-lived connections / polling and therefore never
# reach networkidle. Both waits are bounded; stabilization never aborts a scan.
NETWORKIDLE_TIMEOUT_MS = 2500
SETTLE_TIMEOUT_MS = 400


def _is_not_found_page(title: str, body_text: str) -> bool:
    """Heuristically detects the app's own "404 / not found" page.

    SPAs frequently return HTTP 200 while rendering an in-app 404 view, so a
    successful response status is not sufficient evidence that a route is a
    real, usable page. Routes that render a not-found view must NOT be treated
    as verified navigation targets (otherwise the planner grounds tests on
    routes that only lead to a 404 page).
    """
    title_l = (title or "").lower()
    body_l = (body_text or "").lower()
    if "404" in title_l or "not found" in title_l:
        return True
    if re.search(r"(error\s*404|404\s*error|page\s*not\s*found|does\s*not\s*exist)", body_l):
        return True
    return False

logger = logging.getLogger("graph-page-inspection")


def _format_accessibility_tree(node: Dict[str, Any], depth: int = 0) -> str:
    """Converts Playwright AOM snapshot into a flat indented text format.

    Produces a semantic, simplified view of the page suitable for LLM
    consumption, limiting the model's ability to hallucinate invalid selectors.
    """
    indent = "  " * depth
    role = node.get("role", "")
    name = node.get("name", "")
    value = node.get("value", "")

    parts = [role]
    if name:
        parts.append(f'"{name}"')
    if value:
        parts.append(f'value="{value}"')

    line = f"{indent}{' '.join(parts)}"
    lines = [line]

    for child in node.get("children", []):
        lines.append(_format_accessibility_tree(child, depth + 1))

    return "\n".join(lines)

def classify_page_type(route: str, metadata: Dict[str, Any]) -> str:
    """Classifies a page type based on route and extracted metadata."""
    route_lower = route.lower()
    title_lower = metadata.get("title", "").lower()
    body_lower = metadata.get("bodyText", "").lower()
    inputs = metadata.get("inputs", [])
    forms = metadata.get("forms", [])
    tables = metadata.get("tables", [])
    cards = metadata.get("cards", [])

    # Check for authentication pages
    if any(k in route_lower or k in title_lower for k in ["login", "signin", "signup", "register", "auth"]) or any(i.get("type") == "password" for i in inputs):
        return "authentication_page"

    # Contact page
    if any(k in route_lower or k in title_lower for k in ["contact", "support", "help", "feedback"]):
        return "contact_page"

    # Settings / Profile page
    if any(k in route_lower or k in title_lower for k in ["settings", "profile", "account", "preference"]):
        return "settings_page"

    # Dashboard
    if any(k in route_lower or k in title_lower for k in ["dashboard", "admin", "console", "overview"]):
        return "dashboard"

    # Documentation / Blog
    if any(k in route_lower or k in title_lower for k in ["docs", "documentation", "guide", "wiki"]):
        return "documentation"
    if any(k in route_lower or k in title_lower for k in ["blog", "news", "post"]):
        return "blog"

    # Product detail
    if any(k in route_lower for k in ["/product/", "/item/", "/shop/product/"]) or (len(cards) == 0 and "add to cart" in body_lower):
        return "product_detail"

    # Product listing
    if any(k in route_lower or k in title_lower for k in ["products", "shop", "store", "catalog", "pricing"]) or len(cards) > 2:
        return "product_listing"

    # CRUD table
    if len(tables) > 0 or "table" in body_lower:
        return "crud_table"

    # Form page
    if len(forms) > 0 or any(i.get("type") in ["text", "email", "textarea"] for i in inputs):
        return "form_page"

    # Landing page (root)
    if route == "/" or route_lower in ["/home", "/index"]:
        return "landing_page"

        return "unknown"


async def _stabilize_page(page) -> None:
    """Bounded post-navigation stabilization before capturing the final DOM.

    A SPA's in-app 404 view is rendered client-side, so the DOM captured
    immediately after ``domcontentloaded`` can still be the pre-hydration shell.
    We first wait (bounded) for network idle, then apply a short fixed settle for
    apps that never reach networkidle (long-lived sockets / polling). Both waits
    are bounded and swallow errors: stabilization must never abort an inspection.
    """
    try:
        await page.wait_for_load_state("networkidle", timeout=NETWORKIDLE_TIMEOUT_MS)
    except Exception:
        # Not an error: SPAs frequently never reach networkidle. The bounded
        # settle below provides the framework-render window instead.
        pass
    try:
        await page.wait_for_timeout(SETTLE_TIMEOUT_MS)
    except Exception:
        pass


async def page_inspection_node(state: TestPilotState) -> Dict[str, Any]:
    """Agent Node: Launches Playwright, scans target pages, and extracts structured metadata."""
    run_id = state["run_id"]
    website_url = state["website_url"]
    repo_info = state.get("repo_analysis", {})
    routes = repo_info.get("routes", ["/"])

    logger.info(f"[Node: page_inspection] Inspecting {len(routes)} routes for run {run_id}")
    inspections: List[Dict[str, Any]] = []

    async def _run_inspection():
        """Inner async function that runs inside a ProactorEventLoop thread."""
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()
            page = await context.new_page()

            for route in routes:
                target_url = f"{website_url.rstrip('/')}{route}" if route != "/" else website_url
                logger.info(f"[Node: page_inspection] Inspecting route {route} at {target_url}")

                try:
                    # Navigate with timeout
                    response = await page.goto(target_url, wait_until="domcontentloaded", timeout=12000)

                    if not response or response.status >= 400:
                        logger.warning(f"[Node: page_inspection] Failed route {route}: Status {response.status if response else 'No Response'}")
                        continue

                    # Wait (bounded) for the client-side router to finish
                    # rendering BEFORE sampling the DOM, so an in-app 404 view is
                    # classified correctly instead of as an "unknown" page.
                    await _stabilize_page(page)

                    # Execute script inside page context to get structured elements
                    dom_data = await page.evaluate("""() => {
                        const getAttr = (el, name) => el.getAttribute(name) || undefined;
                        const isVisible = (el) => {
                            const rect = el.getBoundingClientRect();
                            return rect.width > 0 && rect.height > 0 && window.getComputedStyle(el).display !== 'none' && window.getComputedStyle(el).visibility !== 'hidden';
                        };

                        // Headings
                        const headings = Array.from(document.querySelectorAll('h1, h2, h3, h4, h5, h6'))
                            .filter(isVisible)
                            .map(h => ({
                                tag: h.tagName.toLowerCase(),
                                text: h.innerText.trim(),
                                dataTestId: getAttr(h, 'data-testid')
                            })).filter(h => h.text);

                        // Buttons
                        const buttons = Array.from(document.querySelectorAll('button, a[role="button"], input[type="submit"], input[type="button"]'))
                            .filter(isVisible)
                            .map(btn => ({
                                text: btn.innerText?.trim() || btn.value?.trim() || getAttr(btn, 'aria-label') || getAttr(btn, 'title'),
                                id: btn.id || undefined,
                                role: getAttr(btn, 'role') || 'button',
                                dataTestId: getAttr(btn, 'data-testid'),
                                ariaLabel: getAttr(btn, 'aria-label')
                            })).filter(btn => btn.text);

                        // Inputs
                        const inputs = Array.from(document.querySelectorAll('input, select, textarea'))
                            .filter(isVisible)
                            .map(inp => ({
                                type: inp.type || 'text',
                                name: getAttr(inp, 'name'),
                                placeholder: getAttr(inp, 'placeholder'),
                                label: inp.labels?.[0]?.innerText?.trim(),
                                required: inp.required,
                                id: inp.id || undefined,
                                ariaLabel: getAttr(inp, 'aria-label'),
                                dataTestId: getAttr(inp, 'data-testid')
                            }));

                        // Forms
                        const forms = Array.from(document.querySelectorAll('form')).map(f => ({
                            action: getAttr(f, 'action'),
                            method: getAttr(f, 'method') || 'GET',
                            fields: Array.from(f.querySelectorAll('input, select, textarea')).map(inp => ({
                                type: inp.type || 'text',
                                name: getAttr(inp, 'name'),
                                placeholder: getAttr(inp, 'placeholder')
                            }))
                        }));

                        // Tables
                        const tables = Array.from(document.querySelectorAll('table')).map(t => ({
                            rows: t.rows?.length || 0,
                            headers: Array.from(t.querySelectorAll('th')).map(th => th.innerText.trim())
                        }));

                        // Cards
                        const cards = Array.from(document.querySelectorAll('[class*="card" i], article, .card'))
                            .filter(isVisible)
                            .map(card => ({
                            title: card.querySelector('h1, h2, h3, h4, h5, h6, .card-title, [class*="title" i]')?.innerText.trim(),
                            text: card.innerText.trim().slice(0, 100)
                        })).filter(c => c.title);

                        // Links
                        const links = Array.from(document.querySelectorAll('a')).map(link => ({
                            text: link.innerText.trim(),
                            href: getAttr(link, 'href')
                        })).filter(link => link.text && link.href && !link.href.startsWith('javascript:'));

                        // Interactive elements (anything with click listeners or cursor pointer styles)
                        const interactive = Array.from(document.querySelectorAll('[onclick], [role="tab"], [role="checkbox"], [role="radio"]')).map(el => ({
                            tag: el.tagName.toLowerCase(),
                            text: el.innerText?.trim().slice(0, 50),
                            role: getAttr(el, 'role')
                        }));

                        // Elements carrying an explicit data-testid (stable locators)
                        const elementsWithTestId = Array.from(document.querySelectorAll('[data-testid]'))
                            .filter(isVisible)
                            .map(el => ({
                                testId: getAttr(el, 'data-testid'),
                                tag: el.tagName.toLowerCase(),
                                role: getAttr(el, 'role') || undefined,
                                text: (el.innerText || '').trim().slice(0, 100)
                            })).filter(e => e.testId);

                                                const bodyText = document.body.innerText || "";

                        // Images with alt text. Alt text is an ACCESSIBILITY
                        // NAME (like an aria-label), NOT visible text: it must
                        // never be turned into a getByText(...) assertion.
                        const images = Array.from(document.querySelectorAll('img'))
                            .filter(isVisible)
                            .map(img => ({
                                alt: getAttr(img, 'alt'),
                                src: getAttr(img, 'src')
                            })).filter(img => img.alt);

                        return {
                            title: document.title || "",
                            headings,
                            buttons,
                            inputs,
                            forms,
                            tables,
                            cards,
                            links,
                            interactive_elements: interactive,
                            elements_with_testid: elementsWithTestId,
                            images,
                            bodyText: bodyText.slice(0, 800)
                        };
                    }""")

                    # Classify page type (in-app 404 views are NOT usable routes)
                    body_text = dom_data.get("bodyText", "")
                    title_text = dom_data.get("title", "")
                    is_not_found = _is_not_found_page(title_text, body_text)

                    page_type = classify_page_type(route, dom_data)
                    if is_not_found:
                        page_type = "not_found"

                    # Extract Accessibility Tree (AOM) for semantic page structure.
                    # Used by test_repair_node instead of raw HTML to reduce
                    # hallucinated selectors during LLM-powered repairs.
                    accessibility_tree = ""
                    try:
                        if hasattr(page.locator("body"), "aria_snapshot"):
                            accessibility_tree = await page.locator("body").aria_snapshot()
                        elif hasattr(page, "accessibility") and page.accessibility is not None:
                            aom_snapshot = await page.accessibility.snapshot()
                            if aom_snapshot:
                                accessibility_tree = _format_accessibility_tree(aom_snapshot)
                    except Exception as aom_err:
                        logger.warning(f"[Node: page_inspection] AOM extraction failed for {route}: {aom_err}")

                    # Check if auth required (redirected to login or page has password fields and route is not login)
                    current_url = page.url
                    auth_required = False
                    if "login" in current_url.lower() and "login" not in route.lower():
                        auth_required = True

                    inspections.append({
                        "route": route,
                        "page_type": page_type,
                        "title": title_text,
                        "status_code": response.status if response else None,
                        "is_not_found": is_not_found,
                        "headings": dom_data.get("headings", []),
                        "buttons": dom_data.get("buttons", []),
                        "forms": dom_data.get("forms", []),
                        "tables": dom_data.get("tables", []),
                        "cards": dom_data.get("cards", []),
                        "links": dom_data.get("links", []),
                        "interactive_elements": dom_data.get("interactive_elements", []),
                                                "inputs": dom_data.get("inputs", []),
                        "elements_with_testid": dom_data.get("elements_with_testid", []),
                        "images": dom_data.get("images", []),
                        "authentication_required": auth_required,
                        "accessibility_tree": accessibility_tree,
                    })

                    logger.info(f"[Node: page_inspection] Discovered page type '{page_type}' for route '{route}'")

                except Exception as route_err:
                    logger.error(f"[Node: page_inspection] Failed route inspection for {route}: {route_err}")

            await browser.close()

    try:
        async with target_slot(website_url):
            await run_playwright(_run_inspection)
    except Exception as e:
        logger.error(f"[Node: page_inspection] Playwright inspection failed: {e}")

    # Fallback default inspections if all failed to scan
    if not inspections:
        for route in routes:
            inspections.append({
                "route": route,
                "page_type": "landing_page" if route == "/" else "unknown",
                "title": f"Route {route}",
                "status_code": None,
                "is_not_found": False,
                "headings": [],
                "buttons": [],
                "forms": [],
                "tables": [],
                "cards": [],
                "links": [],
                                "interactive_elements": [],
                "inputs": [],
                "elements_with_testid": [],
                "images": [],
                "authentication_required": False,
                "accessibility_tree": "",
            })

    return {
        "page_inspections": inspections,
        "status": "planning",
        "messages": [{"role": "assistant", "content": f"Inspected {len(inspections)} routes and extracted element selectors."}]
    }
