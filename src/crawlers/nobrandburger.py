import logging
import re
from typing import List, Optional, Tuple

from src.crawlers.base import BaseCrawler
from src.crawlers.utils import clean_name, load_nutrition_csv, match_by_name, nutrition_from_row
from src.models.burger import BurgerItem

logger = logging.getLogger(__name__)

BASE_URL = "https://www.shinsegaefood.com"
MENU_URL = f"{BASE_URL}/nobrandburger/"
BURGER_GROUP_TITLE = "버거"
BR_RE = re.compile(r"<br\s*/?>|</br>", re.I)

# 영양성분표는 원산지·알레르기 표와 합쳐진 팝업 이미지 한 장이라 사람이 판독·검수한 CSV를 사용
# 팝업의 이미지 주소(?v= 버전 포함)가 바뀌면 경고 로그를 남기므로, 새 표를 판독해 CSV와 아래 값을 갱신
NUTRITION_CSV = "nobrandburger_nutrition.csv"
NUTRITION_POPUP_URL = f"{BASE_URL}/popup/nobrandburger_02.html"
NUTRITION_IMAGE_PATH = "/images/pop/nobrandburger_foodinfo.png?v=261030"
NUTRITION_ISSUED = "2026.10.30"


class NoBrandBurgerCrawler(BaseCrawler):
    """노브랜드 버거(신세계푸드 브랜드 페이지, 정적 HTML) 크롤러.

    가격은 사이트에 노출되지 않습니다.
    """

    brand_name = "노브랜드버거"
    brand_slug = "nobrandburger"

    def crawl(self) -> List[BurgerItem]:
        soup = self.fetch_soup(MENU_URL)
        group = next(
            (
                g
                for g in soup.select(".menu_group")
                if g.select_one(".menu_group_title")
                and g.select_one(".menu_group_title").get_text(strip=True) == BURGER_GROUP_TITLE
            ),
            None,
        )
        if group is None:
            raise ValueError("버거 메뉴 그룹을 찾지 못했습니다 (사이트 구조 변경)")

        nutrition_table = load_nutrition_csv(NUTRITION_CSV)
        items = []
        for button in group.select(".menu_anch"):
            name, name_en = self._split_name(button.get("data-name", ""))
            items.append(
                BurgerItem(
                    brand=self.brand_name,
                    brand_slug=self.brand_slug,
                    name=name,
                    name_en=name_en,
                    description=clean_name(BR_RE.sub(" ", button.get("data-story", ""))) or None,
                    detail_url=MENU_URL,
                    nutrition=nutrition_from_row(
                        match_by_name(name, *nutrition_table), f"단품 기준 (노브랜드버거 영양성분 {NUTRITION_ISSUED})"
                    ),
                )
            )

        self._check_nutrition_image()
        logger.info("[%s] 버거 %d건 수집", self.brand_name, len(items))
        return items

    def _check_nutrition_image(self) -> None:
        try:
            img = self.fetch_soup(NUTRITION_POPUP_URL).select_one("img")
        except Exception as exc:
            logger.warning("[%s] 영양성분 이미지 확인 실패 %s: %s", self.brand_name, NUTRITION_POPUP_URL, exc)
            return
        src = img.get("src") if img else "(이미지 없음)"
        self.warn_if_nutrition_source_changed(NUTRITION_IMAGE_PATH, src, NUTRITION_CSV)

    @staticmethod
    def _split_name(data_name: str) -> Tuple[str, Optional[str]]:
        """'진짜 비빔밥 버거</br> Real Bibimbap Burger' → ('진짜 비빔밥 버거', 'Real Bibimbap Burger')"""
        parts = [clean_name(part) for part in BR_RE.split(data_name)]
        parts = [part for part in parts if part]
        return parts[0], (" ".join(parts[1:]) or None)
