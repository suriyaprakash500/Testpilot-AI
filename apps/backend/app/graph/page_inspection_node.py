import logging
from typing import Dict, Any, List
from app.graph.state import TestPilotState
from playwright.async_api import async_playwright
from app.graph.playwright_runner import run_playwright

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
                                text: h.innerText.trim()
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
                                ariaLabel: getAttr(inp, 'aria-label')
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

                        const bodyText = document.body.innerText || "";

                        return {
                            title: document.title,
                            headings,
                            buttons,
                            inputs,
                            forms,
                            tables,
                            cards,
                            links,
                            interactive_elements: interactive,
                            bodyText: bodyText.slice(0, 800)
                        };
                    }""")

                    # Classify page type
                    page_type = classify_page_type(route, dom_data)

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
                        "title": dom_data.get("title", ""),
                        "headings": dom_data.get("headings", []),
                        "buttons": dom_data.get("buttons", []),
                        "forms": dom_data.get("forms", []),
                        "tables": dom_data.get("tables", []),
                        "cards": dom_data.get("cards", []),
                        "links": dom_data.get("links", []),
                        "interactive_elements": dom_data.get("interactive_elements", []),
                        "inputs": dom_data.get("inputs", []),
                        "authentication_required": auth_required,
                        "accessibility_tree": accessibility_tree,
                    })

                    logger.info(f"[Node: page_inspection] Discovered page type '{page_type}' for route '{route}'")

                except Exception as route_err:
                    logger.error(f"[Node: page_inspection] Failed route inspection for {route}: {route_err}")

            await browser.close()

    try:
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
                "headings": [],
                "buttons": [],
                "forms": [],
                "tables": [],
                "cards": [],
                "links": [],
                "interactive_elements": [],
                "inputs": [],
                "authentication_required": False,
                "accessibility_tree": "",
            })

    return {
        "page_inspections": inspections,
        "status": "planning",
        "messages": [{"role": "assistant", "content": f"Inspected {len(inspections)} routes and extracted element selectors."}]
    }
