"""Anti-detection utilities for Playwright browsers."""

import random

from fake_useragent import UserAgent

_ua = UserAgent(browsers=["chrome", "edge"])

VIEWPORT_SIZES = [
    {"width": 1920, "height": 1080},
    {"width": 1366, "height": 768},
    {"width": 1536, "height": 864},
    {"width": 1440, "height": 900},
    {"width": 1280, "height": 720},
]


def random_ua() -> str:
    return _ua.random


def random_viewport() -> dict[str, int]:
    return random.choice(VIEWPORT_SIZES)


async def apply_stealth(page) -> None:
    """Apply stealth patches to a Playwright page to avoid detection."""
    await page.add_init_script("""
        // Override navigator.webdriver
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });

        // Override chrome runtime
        window.chrome = { runtime: {} };

        // Override permissions query
        const originalQuery = window.navigator.permissions.query;
        window.navigator.permissions.query = (parameters) =>
            parameters.name === 'notifications'
                ? Promise.resolve({ state: Notification.permission })
                : originalQuery(parameters);

        // Override plugins length
        Object.defineProperty(navigator, 'plugins', {
            get: () => [1, 2, 3, 4, 5],
        });

        // Override languages
        Object.defineProperty(navigator, 'languages', {
            get: () => ['en-US', 'en'],
        });
    """)
