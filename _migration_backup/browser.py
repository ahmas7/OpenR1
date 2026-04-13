"""
R1 - Browser Automation
Web browsing, forms, data extraction using Playwright
"""
import asyncio
import base64
from typing import Dict, Any, Optional, List
from dataclasses import dataclass


@dataclass
class BrowserResult:
    success: bool
    content: str = ""
    data: Any = None
    error: Optional[str] = None


class Browser:
    def __init__(self, headless: bool = True):
        self.headless = headless
        self.browser = None
        self.page = None
    
    async def start(self) -> BrowserResult:
        try:
            from playwright.async_api import async_playwright
            pw = await async_playwright().start()
            self.browser = await pw.chromium.launch(headless=self.headless)
            self.page = await self.browser.new_page()
            return BrowserResult(success=True, content="Browser started")
        except Exception as e:
            return BrowserResult(success=False, error=str(e))
    
    async def stop(self):
        if self.browser:
            await self.browser.close()
    
    async def navigate(self, url: str) -> BrowserResult:
        try:
            await self.page.goto(url, wait_until="domcontentloaded")
            title = await self.page.title()
            return BrowserResult(success=True, content=f"Loaded: {title}")
        except Exception as e:
            return BrowserResult(success=False, error=str(e))
    
    async def click(self, selector: str) -> BrowserResult:
        try:
            await self.page.click(selector)
            return BrowserResult(success=True, content=f"Clicked: {selector}")
        except Exception as e:
            return BrowserResult(success=False, error=str(e))
    
    async def fill(self, selector: str, value: str) -> BrowserResult:
        try:
            await self.page.fill(selector, value)
            return BrowserResult(success=True, content=f"Filled: {selector}")
        except Exception as e:
            return BrowserResult(success=False, error=str(e))
    
    async def type_text(self, selector: str, text: str, delay: int = 50) -> BrowserResult:
        try:
            await self.page.type(selector, text, delay=delay)
            return BrowserResult(success=True, content=f"Typed in: {selector}")
        except Exception as e:
            return BrowserResult(success=False, error=str(e))
    
    async def get_text(self, selector: str) -> BrowserResult:
        try:
            text = await self.page.text_content(selector)
            return BrowserResult(success=True, content=text or "")
        except Exception as e:
            return BrowserResult(success=False, error=str(e))
    
    async def get_all(self, selector: str) -> BrowserResult:
        try:
            elements = await self.page.query_selector_all(selector)
            texts = [await el.text_content() for el in elements]
            return BrowserResult(success=True, content="\n".join(texts), data=texts)
        except Exception as e:
            return BrowserResult(success=False, error=str(e))
    
    async def screenshot(self, path: Optional[str] = None) -> BrowserResult:
        try:
            if path:
                await self.page.screenshot(path=path, full_page=True)
                return BrowserResult(success=True, content=f"Saved: {path}")
            else:
                img = await self.page.screenshot(full_page=True)
                return BrowserResult(success=True, content="Screenshot captured", data=base64.b64encode(img).decode())
        except Exception as e:
            return BrowserResult(success=False, error=str(e))
    
    async def execute(self, script: str) -> BrowserResult:
        try:
            result = await self.page.evaluate(script)
            return BrowserResult(success=True, content=str(result))
        except Exception as e:
            return BrowserResult(success=False, error=str(e))
    
    async def get_links(self) -> BrowserResult:
        try:
            links = await self.page.evaluate("""
                Array.from(document.querySelectorAll('a')).map(a => ({
                    text: a.textContent.trim().slice(0, 50),
                    href: a.href
                })).filter(l => l.href)
            """)
            return BrowserResult(success=True, content=str(links[:10]), data=links)
        except Exception as e:
            return BrowserResult(success=False, error=str(e))
    
    async def search_google(self, query: str) -> BrowserResult:
        await self.navigate(f"https://www.google.com/search?q={query}")
        await asyncio.sleep(2)
        return await self.get_all("div.g")
    
    async def fill_form(self, fields: Dict[str, str]) -> BrowserResult:
        for selector, value in fields.items():
            result = await self.fill(selector, value)
            if not result.success:
                return result
        return BrowserResult(success=True, content="Form filled")
    
    async def __aenter__(self):
        await self.start()
        return self
    
    async def __aexit__(self, *args):
        await self.stop()


class BrowserController:
    """Singleton browser instance"""
    _instance: Optional[Browser] = None
    
    @classmethod
    async def get(cls, headless: bool = True) -> Browser:
        if cls._instance is None:
            cls._instance = Browser(headless)
            await cls._instance.start()
        return cls._instance
    
    @classmethod
    async def close(cls):
        if cls._instance:
            await cls._instance.stop()
            cls._instance = None
