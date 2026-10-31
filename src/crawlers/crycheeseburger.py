import logging
import re
from typing import List, Optional

from src.crawlers.base import BaseCrawler
from src.crawlers.utils import clean_name, name_key, parse_price
from src.models.burger import BurgerItem

logger = logging.getLogger(__name__)

BASE_URL = "https://www.crycheeseburger.com"
MENU_URL = f"{BASE_URL}/menu"


class CryCheeseBurgerCrawler(BaseCrawler):
    """크라이치즈버거 공식 사이트(Next.js 정적 렌더링) 크롤러.

    '버거' 섹션을 단품으로, '버거세트' 섹션의 '{버거명} 세트' 가격을 세트가로 씁니다.
    영양성분은 사이트에서 제공하지 않습니다.
    """

    brand_name = "크라이치즈버거"
    brand_slug = "crycheeseburger"

    def crawl(self) -> List[BurgerItem]:
        soup = self.fetch_soup(MENU_URL)
        burgers = soup.select("section#burger article")
        if not burgers:
            raise ValueError("버거 섹션을 찾지 못했습니다 (사이트 구조 변경)")

        set_prices = {}
        for card in soup.select("section#set article"):
            set_name = re.sub(r"\s*세트$", "", clean_name(card.select_one("h3").get_text()))
            set_prices[name_key(set_name)] = self._price(card)

        items = []
        for card in burgers:
            name = clean_name(card.select_one("h3").get_text())
            items.append(
                BurgerItem(
                    brand=self.brand_name,
                    brand_slug=self.brand_slug,
                    name=name,
                    description=self._description(card),
                    price=self._price(card),
                    set_price=set_prices.get(name_key(name)),
                    detail_url=MENU_URL,
                )
            )

        logger.info("[%s] 버거 %d건 수집", self.brand_name, len(items))
        return items

    @staticmethod
    def _price(card) -> Optional[int]:
        texts = [p.get_text(strip=True) for p in card.select("p")]
        return next((parse_price(t) for t in texts if t.endswith("원")), None)

    @staticmethod
    def _description(card) -> Optional[str]:
        """소개 문구(없으면 구성)를 설명으로 사용"""
        intro = card.select_one("p.line-clamp-2")
        texts = [intro.get_text(" ", strip=True)] if intro else []
        texts += [p.get_text(" ", strip=True) for p in card.select("p") if not p.get_text(strip=True).endswith("원")]
        return next((text for text in texts if text), None)
