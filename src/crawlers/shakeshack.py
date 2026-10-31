import logging
import re
from typing import List, Optional

from src.crawlers.base import BaseCrawler
from src.crawlers.utils import clean_name
from src.models.burger import BurgerItem

logger = logging.getLogger(__name__)

# 공식 사이트가 https(443)를 열어두지 않아 http로 접속
BASE_URL = "http://www.shakeshack.kr"
MENU_URL = f"{BASE_URL}/sub/menu.jsp"
BURGER_SECTIONS = ("menu_burger", "menu_chicken")
# 'W 10,9' = 10,900원 (천 단위 뒤 한 자리만 표기)
PRICE_RE = re.compile(r"W\s*(\d+),(\d)")


def parse_won(text: str) -> Optional[int]:
    """'Single W 9,2' → 9200"""
    match = PRICE_RE.search(text or "")
    return int(match.group(1)) * 1000 + int(match.group(2)) * 100 if match else None


class ShakeShackCrawler(BaseCrawler):
    """쉐이크쉑 코리아 공식 사이트(정적 HTML) 크롤러.

    버거·치킨 탭에서 버거만 수집합니다 (치킨 바이트 제외). 가격이 여러 개면 첫 번째
    (Single / 닭가슴살)를 단품가로 씁니다. 세트 메뉴와 영양성분은 사이트에서 제공하지 않습니다.
    """

    brand_name = "쉐이크쉑"
    brand_slug = "shakeshack"

    def crawl(self) -> List[BurgerItem]:
        soup = self.fetch_soup(MENU_URL)

        items = []
        for section_id in BURGER_SECTIONS:
            section = soup.find(id=section_id)
            if section is None:
                raise ValueError(f"{section_id} 섹션을 찾지 못했습니다 (사이트 구조 변경)")
            for card in section.select("li"):
                titles = card.select(".menu-wrap h3")
                if len(titles) < 2:
                    continue
                name = clean_name(titles[1].get_text())
                description = card.select_one(".menu-wrap p.body-normal-kr")
                description = description.get_text(" ", strip=True) if description else ""
                if "버거" not in description and "버거" not in name:
                    continue

                prices = card.select(".menu-wrap p")
                items.append(
                    BurgerItem(
                        brand=self.brand_name,
                        brand_slug=self.brand_slug,
                        name=name,
                        name_en=clean_name(titles[0].find(string=True, recursive=False) or "") or None,
                        description=description or None,
                        price=parse_won(prices[-1].get_text(" ", strip=True)) if prices else None,
                        detail_url=f"{MENU_URL}#tab1",
                        is_limited="한정" in description,
                    )
                )

        logger.info("[%s] 버거 %d건 수집", self.brand_name, len(items))
        return items
