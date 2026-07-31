import logging
from typing import Dict, Any, List
from app.graph.state import TestPilotState
from playwright.async_api import async_playwright

logger = logging.getLogger("graph-page-inspection")

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

    try:
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
                            .map(input => {
                                const type = input.tagName.toLowerCase() === 'select' ? 'select' : input.tagName.toLowerCase() === 'textarea' ? 'textarea' : input.type;
                                return {
                                    type,
                                    name: input.name || undefined,
                                    id: input.id || undefined,
                                    placeholder: getAttr(input, 'placeholder'),
                                    dataTestId: getAttr(input, 'data-testid'),
                                    ariaLabel: getAttr(input, 'aria-label'),
                                    label: document.querySelector(`label[for="${input.id}"]`)?.innerText.trim() || getAttr(input, 'aria-label') || undefined
                                };
                            });

                        // Forms
                        const forms = Array.from(document.querySelectorAll('form'))
                            .filter(isVisible)
                            .map(form => ({
                                id: form.id || undefined,
                                action: getAttr(form, 'action'),
                                inputsCount: form.querySelectorAll('input, select, textarea').length
                            }));

                        // Tables
                        const tables = Array.from(document.querySelectorAll('table'))
                            .filter(isVisible)
                            .map(table => ({
                                id: table.id || undefined,
                                rowsCount: table.querySelectorAll('tr').length,
                                headers: Array.from(table.querySelectorAll('th')).map(th => th.innerText.trim()).filter(Boolean)
                            }));

                        // Cards
                        const cards = Array.from(document.querySelectorAll('.card, [class*="card" i], article, .product-item'))
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
                        "authentication_required": auth_required
                    })

                    logger.info(f"[Node: page_inspection] Discovered page type '{page_type}' for route '{route}'")

                except Exception as route_err:
                    logger.error(f"[Node: page_inspection] Failed route inspection for {route}: {route_err}")

            await browser.close()
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
                "authentication_required": False
            })

    return {
        "page_inspections": inspections,
        "status": "planning",
        "messages": [{"role": "assistant", "content": f"Inspected {len(inspections)} routes and extracted element selectors."}]
    }
