"""
R1 - Enhanced Browser Controller
Provides Playwright-based autonomous web interaction.
"""
import asyncio
import logging
from typing import Dict, List, Optional, Any
from playwright.async_api import async_playwright, Browser, BrowserContext, Page

logger = logging.getLogger("R1:browser")

class BrowserController:
    _instance = None

    def __init__(self, headless: bool = True):
        self.headless = headless
        self.playwright = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self._initialized = False

    @classmethod
    async def get(cls, headless: bool = True):
        if cls._instance is None:
            cls._instance = cls(headless=headless)
        return cls._instance

    async def initialize(self):
        if self._initialized:
            return

        try:
            self.playwright = await async_playwright().start()
            self.browser = await self.playwright.chromium.launch(headless=self.headless)
            self.context = await self.browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            )
            self.page = await self.context.new_page()
            self._initialized = True
            logger.info("Browser initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize browser: {e}")
            raise

    async def navigate(self, url: str):
        if not self._initialized:
            await self.initialize()

        try:
            response = await self.page.goto(url, wait_until="networkidle")
            return type('BrowserResult', (), {
                'success': True,
                'content': await self.page.content(),
                'error': None
            })
        except Exception as e:
            return type('BrowserResult', (), {
                'success': False,
                'content': None,
                'error': str(e)
            })

    async def search_google(self, query: str):
        if not self._initialized:
            await self.initialize()

        try:
            await self.page.goto(f"https://www.google.com/search?q={query}")
            await self.page.wait_for_selector("h3")

            results = await self.page.evaluate("""() => {
                const items = [];
                document.querySelectorAll('h3').forEach(el => {
                    const link = el.closest('a');
                    if (link) {
                        items.push({
                            title: el.innerText,
                            url: link.href
                        });
                    }
                });
                return items;
            }""")

            return type('BrowserResult', (), {
                'success': True,
                'data': results,
                'content': await self.page.content(),
                'error': None
            })
        except Exception as e:
            return type('BrowserResult', (), {
                'success': False,
                'data': [],
                'content': None,
                'error': str(e)
            })

    async def click(self, selector: str):
        if not self._initialized:
            await self.initialize()
        try:
            await self.page.click(selector)
            await self.page.wait_for_timeout(1000)
            return type('BrowserResult', (), {
                'success': True,
                'content': await self.page.content(),
                'error': None
            })
        except Exception as e:
            return type('BrowserResult', (), {
                'success': False,
                'content': None,
                'error': str(e)
            })

    async def fill(self, selector: str, value: str):
        if not self._initialized:
            await self.initialize()
        try:
            await self.page.fill(selector, value)
            return type('BrowserResult', (), {
                'success': True,
                'content': await self.page.content(),
                'error': None
            })
        except Exception as e:
            return type('BrowserResult', (), {
                'success': False,
                'content': None,
                'error': str(e)
            })

    async def get_text(self, selector: str):
        if not self._initialized:
            await self.initialize()
        try:
            content = await self.page.inner_text(selector)
            return type('BrowserResult', (), {
                'success': True,
                'content': content,
                'error': None
            })
        except Exception as e:
            return type('BrowserResult', (), {
                'success': False,
                'content': None,
                'error': str(e)
            })

    async def screenshot(self):
        if not self._initialized:
            await self.initialize()
        try:
            data = await self.page.screenshot()
            return type('BrowserResult', (), {
                'success': True,
                'data': data,
                'content': "Screenshot taken",
                'error': None
            })
        except Exception as e:
            return type('BrowserResult', (), {
                'success': False,
                'data': None,
                'content': None,
                'error': str(e)
            })

    async def close(self):
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
        self._initialized = False
