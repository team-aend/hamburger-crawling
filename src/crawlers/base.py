from abc import ABC, abstractmethod
from contextlib import contextmanager
import logging
from typing import Generator, List, Optional

from bs4 import BeautifulSoup
from playwright.sync_api import BrowserContext, Page, sync_playwright
import requests

from src.config import HEADLESS, REQUEST_TIMEOUT, USER_AGENT
from src.models.burger import BurgerItem

logger = logging.getLogger(__name__)


class BaseCrawler(ABC):
    """정적(requests/BS4) 및 동적(Playwright) 크롤링을 모두 지원하는 기본 추상 클래스"""

    brand_name: str = "Unknown"
    brand_slug: str = "unknown"

    def __init__(self, headless: bool = HEADLESS, timeout: int = REQUEST_TIMEOUT):
        self.headless = headless
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})

    def fetch_soup(
        self, url: str, params: Optional[dict] = None, encoding: Optional[str] = "utf-8"
    ) -> BeautifulSoup:
        """정적 웹페이지 요청 후 BeautifulSoup 객체 반환"""
        logger.info("[%s] GET %s", self.brand_name, url)
        response = self.session.get(url, params=params, timeout=self.timeout)
        response.raise_for_status()
        if encoding:
            response.encoding = encoding
        return BeautifulSoup(response.text, "lxml")

    def fetch_json(self, url: str, params: Optional[dict] = None) -> dict:
        """JSON API GET 요청"""
        logger.info("[%s] GET %s", self.brand_name, url)
        response = self.session.get(url, params=params, timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    @contextmanager
    def playwright_page(self) -> Generator[Page, None, None]:
        """동적 렌더링이 필요한 페이지를 위한 Playwright Page 컨텍스트 매니저"""
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=self.headless)
            context: BrowserContext = browser.new_context(user_agent=USER_AGENT)
            page: Page = context.new_page()
            page.set_default_timeout(self.timeout * 1000)
            try:
                yield page
            finally:
                context.close()
                browser.close()

    @abstractmethod
    def crawl(self) -> List[BurgerItem]:
        """브랜드별 햄버거 메뉴 및 영양성분을 크롤링하여 BurgerItem 리스트로 반환"""
        raise NotImplementedError
