import logging
import re
import time
from typing import List

from src.crawlers.base import BaseCrawler
from src.crawlers.utils import build_name_tables, clean_name, match_by_name, parse_number, parse_price
from src.models.burger import BurgerItem, NutritionInfo

logger = logging.getLogger(__name__)

BASE_URL = "https://www.lotteeatz.com"
BRAND_PAGE_URL = f"{BASE_URL}/brand/ria"
NUTRITION_URL = f"{BASE_URL}/upload/etc/ria/items.html"


class LotteriaCrawler(BaseCrawler):
    """롯데리아(롯데잇츠) 크롤러.

    브랜드 페이지의 '버거' 섹션(전국 공통 단품가) + 상품 소개 페이지(설명) + 영양성분표 HTML.
    세트 가격은 매장별 주문 페이지에만 있어 수집하지 않습니다.
    """

    brand_name = "롯데리아"
    brand_slug = "lotteria"
    request_delay = 0.3

    def crawl(self) -> List[BurgerItem]:
        soup = self.fetch_soup(BRAND_PAGE_URL)
        title = soup.find("h2", class_="mn-section-title", string=re.compile(r"^\s*버거\s*$"))
        if title is None:
            raise RuntimeError("롯데리아 브랜드 페이지에서 '버거' 섹션을 찾지 못했습니다.")
        grid = title.find_next("ul", class_="mn-grid")

        nutrition_tables = build_name_tables(self._fetch_nutrition_rows(), lambda r: r["name"])

        items = []
        for card in grid.select("div.mn-card"):
            body = card.select_one(".mn-card-body")
            name = clean_name(body.select_one(".mn-card-name").get_text())
            if name.endswith("팩"):  # 한우연인팩 등 묶음 상품 제외
                continue
            product_id = body.get("id")
            detail_url = f"{BASE_URL}/products/introductions/{product_id}?rccode=brnd_main&brandCode=RIA"
            badge = body.select_one(".mn-badge")
            price = body.select_one(".mn-card-price")

            row = match_by_name(name, *nutrition_tables)
            if row is None:
                logger.warning("[%s] 영양성분 매칭 실패: %s", self.brand_name, name)

            items.append(
                BurgerItem(
                    brand=self.brand_name,
                    brand_slug=self.brand_slug,
                    name=name,
                    source_id=product_id,
                    price=parse_price(price.get_text()) if price else None,
                    description=self._fetch_description(detail_url),
                    # 리사이즈 파라미터(/dims/...)를 떼고 원본 이미지 사용
                    detail_url=detail_url,
                    is_limited=bool(badge) and "한정" in badge.get_text(),
                    nutrition=row["nutrition"] if row else NutritionInfo(),
                )
            )

        logger.info("[%s] 버거 %d건 수집", self.brand_name, len(items))
        return items

    def _fetch_description(self, detail_url: str):
        time.sleep(self.request_delay)
        try:
            node = self.fetch_soup(detail_url).select_one(".prod-detail-header p.btext")
        except Exception as exc:
            logger.warning("[%s] 상세 조회 실패 %s: %s", self.brand_name, detail_url, exc)
            return None
        return node.get_text(" ", strip=True) if node else None

    def _fetch_nutrition_rows(self) -> List[dict]:
        """영양성분표의 '버거메뉴' 구간 파싱

        열: 제품명, 알레르기, 중량(g), 열량(kcal), 단백질(g), 나트륨(mg), 당류(g), 포화지방(g), 카페인, 원산지
        """
        soup = self.fetch_soup(NUTRITION_URL)
        header = soup.find("th", string=re.compile("버거메뉴"))
        if header is None:
            logger.warning("[%s] 영양성분표에서 버거메뉴 구간을 찾지 못했습니다.", self.brand_name)
            return []

        row_count = int(header.get("rowspan", 1))
        rows = []
        tr = header.find_parent("tr")
        for _ in range(row_count):
            if tr is None:
                break
            cells = [td.get_text(" ", strip=True) for td in tr.find_all("td")]
            if len(cells) >= 8:
                rows.append(
                    {
                        "name": cells[0],
                        "nutrition": NutritionInfo(
                            serving_size_g=parse_number(cells[2]),
                            calories_kcal=parse_number(cells[3]),
                            protein_g=parse_number(cells[4]),
                            sodium_mg=parse_number(cells[5]),
                            sugar_g=parse_number(cells[6]),
                            saturated_fat_g=parse_number(cells[7]),
                            basis_note="단품 기준 (롯데리아 영양성분표)",
                        ),
                    }
                )
            tr = tr.find_next_sibling("tr")
        return rows
