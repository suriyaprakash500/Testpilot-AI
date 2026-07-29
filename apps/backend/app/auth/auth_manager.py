import os
import uuid
import logging
from datetime import datetime, timedelta
from playwright.async_api import async_playwright
from app.models import AuthSession
from app.config import settings
from app.auth.credential_store import credential_store
from app.auth.session_cache import auth_session_cache

logger = logging.getLogger("auth-manager")

class AuthManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(AuthManager, cls).__new__(cls)
        return cls._instance

    async def get_or_authenticate_session(
        self,
        project_id: str,
        website_url: str,
        strategy: str = "form"
    ) -> AuthSession:
        logger.info(f"AuthManager acquiring session for project={project_id}")

        # 1. Check AuthSessionCache
        session = auth_session_cache.get(project_id)
        if session:
            logger.info("Reusing valid cached AuthSession")
            return session

        # 2. Fetch Credentials from CredentialStore
        credentials = await credential_store.get_credential(project_id)

        # 3. Perform Playwright Authentication & Save StorageState
        storage_dir = os.path.join(settings.artifacts_dir, "auth")
        os.makedirs(storage_dir, exist_ok=True)
        storage_state_path = os.path.join(storage_dir, f"{project_id}-storage-state.json")

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(website_url, wait_until="domcontentloaded", timeout=10000)

            # Fill credentials if login form present
            email_field = page.locator('input[type="email"], input[name="email"]')
            password_field = page.locator('input[type="password"]')

            if await email_field.count() > 0 and await password_field.count() > 0 and credentials:
                await email_field.fill(credentials.get("username", ""))
                await password_field.fill(credentials.get("password", ""))
                await page.click('button[type="submit"], button:has-text("Sign In"), button:has-text("Log In")')
                await page.wait_for_load_state("domcontentloaded")

            # Save storage state
            await page.context.storage_state(path=storage_state_path)
            await browser.close()

        session = AuthSession(
            id=str(uuid.uuid4()),
            project_id=project_id,
            strategy=strategy,
            storage_state_path=storage_state_path,
            expires_at=datetime.utcnow() + timedelta(hours=24)
        )

        # 4. Fail-Fast Post-Authentication Verification
        is_valid = await self.verify_session_post_auth(session, website_url)
        if not is_valid:
            auth_session_cache.invalidate(project_id)
            logger.error("Post-authentication verification failed. Aborting run.")
            raise RuntimeError("Authentication failed. Please verify the test credentials or login flow.")

        auth_session_cache.set(session)
        return session

    async def verify_session_post_auth(self, session: AuthSession, website_url: str) -> bool:
        logger.info(f"Running Fail-Fast Post-Auth Verification probe for project={session.project_id}")

        if not session.storage_state_path:
            return True

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(storage_state=session.storage_state_path)
            page = await context.new_page()

            await page.goto(website_url, wait_until="domcontentloaded", timeout=10000)
            current_url = page.url.lower()

            is_login_page = any(path in current_url for path in ["/login", "/auth", "/signin"])
            password_count = await page.locator('input[type="password"]').count()

            await browser.close()

            if is_login_page or password_count > 0:
                logger.warning(f"Verification probe detected page is still on login screen: {current_url}")
                return False

            logger.info("Post-authentication verification probe passed")
            return True

auth_manager = AuthManager()
