import logging
import re
import time
from typing import List, Optional

from src.crawlers.base import BaseCrawler
from src.crawlers.utils import clean_name
from src.models.burger import BurgerItem

logger = logging.getLogger(__name__)

BASE_URL = "https://www.momstouch.co.kr"
LIST_URL = f"{BASE_URL}/menu/new.php"
BURGER_CATEGORY = "CG0005"
MAX_PAGES = 20
GO_VIEW_RE = re.compile(r"go_view\('(\d+)'\)")
BG_URL_RE = re.compile(r"url\(['\"]?([^'\")]+)")


class MomsTouchCrawler(BaseCrawler):
    """맘스터치 공식 사이트(정적 HTML) 크롤러.

    가격은 사이트에 노출되지 않고, 영양성분은 이미지 한 장으로만 공개되어 수집하지 않습니다.
    """

    brand_name = "맘스터치"
    brand_slug = "momstouch"
    request_delay = 0.3

    def crawl(self) -> List[BurgerItem]:
        items = []
        seen = set()
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

                items.append(
                    BurgerItem(
                        brand=self.brand_name,
                        brand_slug=self.brand_slug,
                        name=clean_name(h3.get_text()),
                        name_en=name_en or None,
                        source_id=idx,
                        description=description,
                        image_url=self._image_url(link.select_one("figure span[style]")),
                        detail_url=detail_url,
                    )
                )
            time.sleep(self.request_delay)

        logger.info("[%s] 버거 %d건 수집", self.brand_name, len(items))
        return items

    @staticmethod
    def _image_url(node) -> Optional[str]:
        match = BG_URL_RE.search(node.get("style", "")) if node else None
        if not match:
            return None
        path = match.group(1)
        return path if path.startswith("http") else f"{BASE_URL}{path}"

    def _fetch_description(self, detail_url: str) -> Optional[str]:
        time.sleep(self.request_delay)
        try:
            node = self.fetch_soup(detail_url).select_one(".menu-view-detail p.description")
        except Exception as exc:
            logger.warning("[%s] 상세 조회 실패 %s: %s", self.brand_name, detail_url, exc)
            return None
        return node.get_text(" ", strip=True) if node else None
