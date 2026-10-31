import logging
import re
import time
from typing import List, Optional

from src.crawlers.base import BaseCrawler
from src.crawlers.utils import clean_name, load_nutrition_csv, match_by_name, nutrition_from_row
from src.models.burger import BurgerItem

logger = logging.getLogger(__name__)

BASE_URL = "https://www.momstouch.co.kr"
LIST_URL = f"{BASE_URL}/menu/new.php"
BURGER_CATEGORY = "CG0005"
MAX_PAGES = 20
GO_VIEW_RE = re.compile(r"go_view\('(\d+)'\)")

# 영양성분표는 전 메뉴 공통 이미지 한 장이라 사람이 판독·검수한 CSV를 사용
# 사이트 이미지가 바뀌면 경고 로그를 남기므로, 새 표를 판독해 CSV와 아래 두 값을 갱신
NUTRITION_CSV = "momstouch_nutrition.csv"
NUTRITION_IMAGE_PATH = "/upload_file/delv_guide/1793066787-WGNKI.jpg"
NUTRITION_ISSUED = "2026.10.22"


class MomsTouchCrawler(BaseCrawler):
    """맘스터치 공식 사이트(정적 HTML) 크롤러.

    가격은 사이트에 노출되지 않아 수집하지 않습니다. 영양성분은 공통 이미지 한 장으로만 공개되어
    사람이 판독한 CSV(NUTRITION_CSV)를 메뉴명으로 매칭합니다.
    """

    brand_name = "맘스터치"
    brand_slug = "momstouch"
    request_delay = 0.3

    def crawl(self) -> List[BurgerItem]:
        items = []
        seen = set()
        nutrition_table = load_nutrition_csv(NUTRITION_CSV)
        for page in range(1, MAX_PAGES + 1):
            soup = self.fetch_soup(LIST_URL, params={"s_sect1": BURGER_CATEGORY, "pageNo": page})
            links = soup.select(".menu-list ul li a")
            if not links:
                break

            for link in links:
                match = GO_VIEW_RE.search(link.get("href", ""))
                if not match or match.group(1) in seen:
                    continue
                idx = match.group(1)
                seen.add(idx)

                h3 = link.select_one("h3")
                en_span = h3.select_one("span")
                name_en = en_span.get_text(strip=True) if en_span else None
                if en_span:
                    en_span.extract()
                detail_url = f"{BASE_URL}/menu/view.php?idx={idx}"

                description = next(
                    (p.get_text(" ", strip=True) for p in link.select("p") if "sub-text" not in p.get("class", [])),
                    None,
                ) or self._fetch_description(detail_url)

                name = clean_name(h3.get_text())
                items.append(
                    BurgerItem(
                        brand=self.brand_name,
                        brand_slug=self.brand_slug,
                        name=name,
                        name_en=name_en or None,
                        source_id=idx,
                        description=description,
                        detail_url=detail_url,
                        nutrition=nutrition_from_row(
                            match_by_name(name, *nutrition_table),
                            f"단품 기준 (맘스터치 영양성분표 {NUTRITION_ISSUED})",
                        ),
                    )
                )
            time.sleep(self.request_delay)

        if items:
            self._check_nutrition_image(items[0].detail_url)
        missing = [item.name for item in items if item.nutrition.calories_kcal is None]
        if missing:
            logger.info("[%s] 영양성분표에 없는 메뉴 %d건: %s", self.brand_name, len(missing), ", ".join(missing))
        logger.info("[%s] 버거 %d건 수집", self.brand_name, len(items))
        return items

    def _check_nutrition_image(self, detail_url: str) -> None:
        """상세 페이지의 영양성분 이미지가 판독한 이미지와 다르면 경고 (CSV 갱신 필요)"""
        time.sleep(self.request_delay)
        try:
            img = self.fetch_soup(detail_url).select_one("#modal-nutrition img")
        except Exception as exc:
            logger.warning("[%s] 영양성분 이미지 확인 실패 %s: %s", self.brand_name, detail_url, exc)
            return
        src = img.get("src") if img else "(이미지 없음)"
        self.warn_if_nutrition_source_changed(NUTRITION_IMAGE_PATH, src, NUTRITION_CSV)

    def _fetch_description(self, detail_url: str) -> Optional[str]:
        time.sleep(self.request_delay)
        try:
            node = self.fetch_soup(detail_url).select_one(".menu-view-detail p.description")
        except Exception as exc:
            logger.warning("[%s] 상세 조회 실패 %s: %s", self.brand_name, detail_url, exc)
            return None
        return node.get_text(" ", strip=True) if node else None
