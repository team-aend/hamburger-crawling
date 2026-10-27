import argparse
import logging
import warnings

warnings.filterwarnings("ignore", message=".*urllib3 v2 only supports OpenSSL.*")

from src.crawlers import CRAWLERS
from src.storage import DatabaseStorage, save_to_csv, save_to_json

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger("main")


def run_crawl(export_format: str, brands: list, dry_run: bool = False) -> None:
    """선택한 브랜드 크롤러를 실행하고 결과를 파일(JSON/CSV) 및 DB에 저장"""
    all_items = []
    for slug in brands:
        crawler = CRAWLERS[slug]()
        try:
            all_items.extend(crawler.crawl())
        except Exception:
            # 한 브랜드 사이트가 바뀌어도 나머지 브랜드는 계속 수집
            logger.exception("[%s] 크롤링 실패 - 건너뜁니다.", crawler.brand_name)

    if not all_items:
        logger.error("수집된 데이터가 없어 저장을 건너뜁니다.")
        return

    if export_format in ("json", "all"):
        save_to_json(all_items)
    if export_format in ("csv", "all"):
        save_to_csv(all_items)
    if export_format in ("db", "all"):
        DatabaseStorage().upsert_burgers(all_items, dry_run=dry_run)


def run_query(brand: str = None, keyword: str = None) -> None:
    """데이터베이스에 저장된 햄버거 정보를 조회하여 출력"""
    db = DatabaseStorage()
    burgers = db.get_burgers(brand=brand, keyword=keyword)

    if not burgers:
        print("조회된 햄버거 정보가 없습니다. 먼저 크롤링을 실행해주세요 (`python main.py crawl`).")
        return

    print(f"\n=== 조회된 햄버거 목록 (총 {len(burgers)}건) ===")
    for b in burgers:
        price_str = f"{b.price:,}원" if b.price else "가격 미정"
        set_str = f" / 세트 {b.set_price:,}원" if b.set_price else ""
        kcal_str = f"{b.nutrition.calories_kcal:g}kcal" if b.nutrition.calories_kcal else "-"
        protein_str = f"단백질 {b.nutrition.protein_g:g}g" if b.nutrition.protein_g else "-"
        print(f"[{b.brand}] {b.name} | {price_str}{set_str} | {kcal_str}, {protein_str}")


def main() -> None:
    parser = argparse.ArgumentParser(description="햄버거 정보 수집 및 조회 CLI")
    subparsers = parser.add_subparsers(dest="command")

    # crawl 서브커맨드
    crawl_parser = subparsers.add_parser("crawl", help="크롤링 실행 및 데이터 저장")
    crawl_parser.add_argument(
        "--export",
        choices=["all", "json", "csv", "db"],
        default="all",
        help="저장 방식 선택 (기본값: all)",
    )
    crawl_parser.add_argument(
        "--brand",
        choices=list(CRAWLERS),
        nargs="+",
        default=list(CRAWLERS),
        help="수집할 브랜드 (기본값: 전체)",
    )
    crawl_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="DB에 반영하지 않고 변경 예정 건수만 출력",
    )

    # query 서브커맨드
    query_parser = subparsers.add_parser("query", help="DB에 저장된 햄버거 정보 조회")
    query_parser.add_argument("--brand", type=str, help="브랜드명 또는 slug (예: 맥도날드, burgerking)")
    query_parser.add_argument("--keyword", type=str, help="메뉴명 검색 키워드 (예: 와퍼, 빅맥)")

    args = parser.parse_args()

    if args.command == "query":
        run_query(brand=args.brand, keyword=args.keyword)
    elif args.command == "crawl":
        run_crawl(export_format=args.export, brands=args.brand, dry_run=args.dry_run)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
