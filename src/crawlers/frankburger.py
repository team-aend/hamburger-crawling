import logging
import re
from typing import List, Optional
from urllib.parse import urljoin

from src.crawlers.base import BaseCrawler
from src.crawlers.utils import clean_name, load_nutrition_csv, match_by_name, nutrition_from_row
from src.models.burger import BurgerItem

logger = logging.getLogger(__name__)

BASE_URL = "https://frankburger.co.kr"
MENU_URL = f"{BASE_URL}/html/menu_1.html"
BG_URL_RE = re.compile(r"url\(['\"]?([^'\")]+)")

# 영양성분표는 원산지·알레르기 표와 합쳐진 이미지 한 장이라 사람이 판독·검수한 CSV를 사용
# 이미지가 갱신되면(Last-Modified 변경) 경고 로그를 남기므로, 새 표를 판독해 CSV와 아래 값을 갱신
NUTRITION_CSV = "frankburger_nutrition.csv"
NUTRITION_IMAGE_URL = f"{BASE_URL}/img/page/2022_menu/01/ingredient.jpg?2"
NUTRITION_LAST_MODIFIED = "Fri, 24 Jul 2026 01:16:44 GMT"


class FrankBurgerCrawler(BaseCrawler):
    """프랭크버거 공식 사이트(정적 HTML) 크롤러.

    메뉴명은 영양성분표·기존 DB 표기와 맞추려고 공백을 뺍니다 (예: 'K 불고기 버거' → 'K불고기버거').
    가격은 사이트에 노출되지 않습니다.
    """

    brand_name = "프랭크버거"
    brand_slug = "frankburger"

    def crawl(self) -> List[BurgerItem]:
        soup = self.fetch_soup(MENU_URL)
        nutrition_table = load_nutrition_csv(NUTRITION_CSV)

        items = []
        for card in soup.select("div.set .set_cont"):
            name = re.sub(r"\s+", "", clean_name(card.select_one(".menu_ko").get_text()))
            description = card.select_one(".stext")
            items.append(
                BurgerItem(
                    brand=self.brand_name,
                    brand_slug=self.brand_slug,
                    name=name,
                    description=description.get_text(" ", strip=True) if description else None,
                    image_url=self._image_url(card.select_one(".img_area")),
                    detail_url=MENU_URL,
                    nutrition=nutrition_from_row(
                        match_by_name(name, *nutrition_table), "단품 기준 (프랭크버거 영양성분표)"
                    ),
                )
            )

        self.warn_if_nutrition_source_changed(
            NUTRITION_LAST_MODIFIED, self.last_modified(NUTRITION_IMAGE_URL), NUTRITION_CSV
        )
        logger.info("[%s] 버거 %d건 수집", self.brand_name, len(items))
        return items

    @staticmethod
    def _image_url(node) -> Optional[str]:
        match = BG_URL_RE.search(node.get("style", "")) if node else None
        return urljoin(MENU_URL, match.group(1)) if match else None
