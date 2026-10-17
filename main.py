import argparse
import logging
import warnings

warnings.filterwarnings("ignore", message=".*urllib3 v2 only supports OpenSSL.*")

from src.crawlers import SampleBurgerCrawler
from src.storage import DatabaseStorage, save_to_csv, save_to_json

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger("main")


def run_crawl(export_format: str) -> None:
    """등록된 크롤러들을 실행하고 결과를 파일(JSON/CSV) 및 DB에 저장"""
    crawlers = [
        SampleBurgerCrawler(),
        # 추후 브랜드별 크롤러를 이곳에 추가하세요 (예: McDonaldsCrawler(), BurgerKingCrawler())
    ]

    all_items = []
    for crawler in crawlers:
        items = crawler.crawl()
        all_items.extend(items)

    if export_format in ("json", "all"):
        save_to_json(all_items)
    if export_format in ("csv", "all"):
        save_to_csv(all_items)
    if export_format in ("db", "all"):
        db = DatabaseStorage()
        db.upsert_burgers(all_items)


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
        kcal_str = f"{b.nutrition.calories_kcal}kcal" if b.nutrition.calories_kcal else "-"
        protein_str = f"단백질 {b.nutrition.protein_g}g" if b.nutrition.protein_g else "-"
        print(f"[{b.brand}] {b.name} ({b.name_en or '-'}) | {price_str} | {kcal_str}, {protein_str}")


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

    # query 서브커맨드
    query_parser = subparsers.add_parser("query", help="DB에 저장된 햄버거 정보 조회")
    query_parser.add_argument("--brand", type=str, help="브랜드명 필터 (예: 맥도날드, 버거킹)")
    query_parser.add_argument("--keyword", type=str, help="메뉴명 검색 키워드 (예: 와퍼, 빅맥)")

    args = parser.parse_args()

    if args.command == "query":
        run_query(brand=args.brand, keyword=args.keyword)
    else:
        run_crawl(export_format=getattr(args, "export", "all"))
        run_query()


if __name__ == "__main__":
    main()
