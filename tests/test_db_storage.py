"""메모리 SQLite로 버거픽 DB 저장 규칙(상품·변형·가격 이력·영양성분)을 검증"""

import pytest
from sqlalchemy import func, select

from src.models import (
    BrandORM,
    BurgerItem,
    CategoryORM,
    NutritionInfo,
    NutritionORM,
    ProductORM,
    ProductPriceORM,
    ProductVariantORM,
)
from src.storage.db_storage import DatabaseStorage


@pytest.fixture
def db():
    return DatabaseStorage("sqlite://")


def make_item(**overrides) -> BurgerItem:
    data = dict(
        brand="버거킹",
        brand_slug="burgerking",
        name="와퍼",
        price=7400,
        set_price=9600,
        description="불에 직접 구운 순 쇠고기 패티",
        image_url="https://example.com/whopper.png",
        nutrition=NutritionInfo(serving_size_g=286, calories_kcal=706, protein_g=30, sodium_mg=1098),
    )
    data.update(overrides)
    return BurgerItem(**data)


def count(db, model) -> int:
    with db.SessionLocal() as session:
        return session.scalar(select(func.count()).select_from(model))


def prices(db):
    """(variant_type, price, 현재가 여부) 목록"""
    with db.SessionLocal() as session:
        rows = session.execute(
            select(ProductVariantORM.variant_type, ProductPriceORM.price, ProductPriceORM.ended_at)
            .join(ProductVariantORM, ProductPriceORM.product_variant_id == ProductVariantORM.id)
            .order_by(ProductPriceORM.id)
        ).all()
    return [(variant_type, price, ended_at is None) for variant_type, price, ended_at in rows]


def test_first_save_creates_all_rows(db):
    stats = db.upsert_burgers([make_item()])

    assert stats["product_created"] == 1
    assert count(db, CategoryORM) == 1
    assert count(db, BrandORM) == 1
    assert prices(db) == [("SINGLE", 7400, True), ("SET", 9600, True)]

    with db.SessionLocal() as session:
        variants = session.scalars(select(ProductVariantORM).order_by(ProductVariantORM.id)).all()
        assert [(v.variant_type, v.name, v.is_default) for v in variants] == [
            ("SINGLE", "단품", True),
            ("SET", "세트", False),
        ]
        nutrition = session.scalar(select(NutritionORM))
        assert nutrition.product_variant_id == variants[0].id  # 영양성분은 단품 기준
        assert float(nutrition.calories_kcal) == 706


def test_saving_same_data_twice_does_not_add_price_history(db):
    db.upsert_burgers([make_item()])
    stats = db.upsert_burgers([make_item()])

    assert stats["product_created"] == 0
    assert stats["price_created"] == 0 and stats["price_changed"] == 0
    assert count(db, ProductORM) == 1
    assert count(db, ProductVariantORM) == 2
    assert count(db, ProductPriceORM) == 2


def test_price_change_closes_old_row_and_adds_new_one(db):
    db.upsert_burgers([make_item()])
    stats = db.upsert_burgers([make_item(price=7600)])

    assert stats["price_changed"] == 1
    assert prices(db) == [("SINGLE", 7400, False), ("SET", 9600, True), ("SINGLE", 7600, True)]
    assert db.get_burgers()[0].price == 7600


def test_dry_run_rolls_back_everything(db):
    stats = db.upsert_burgers([make_item()], dry_run=True)

    assert stats["product_created"] == 1  # 변경 예정 건수는 계산됨
    assert count(db, ProductORM) == 0
    assert count(db, BrandORM) == 0
    assert count(db, ProductPriceORM) == 0


def test_existing_product_matched_by_name_keeps_own_image(db):
    """운영 DB에 이미 있는 상품(다른 slug, 자체 이미지 경로)을 이름으로 찾아 갱신"""
    with db.SessionLocal() as session:
        category = CategoryORM(name="버거", slug="burger")
        brand = BrandORM(name="버거킹", slug="burgerking")
        session.add_all([category, brand])
        session.flush()
        session.add(
            ProductORM(
                brand_id=brand.id,
                category_id=category.id,
                name="와퍼",
                slug="whopper",
                image_url="/images/burgers/whopper.png",
            )
        )
        session.commit()

    stats = db.upsert_burgers([make_item()])

    assert stats["product_updated"] == 1 and stats["product_created"] == 0
    with db.SessionLocal() as session:
        product = session.scalar(select(ProductORM))
        assert product.slug == "whopper"
        assert product.image_url == "/images/burgers/whopper.png"
        assert product.description == "불에 직접 구운 순 쇠고기 패티"


def test_missing_set_price_and_nutrition_are_skipped(db):
    db.upsert_burgers([make_item(set_price=None, nutrition=NutritionInfo())])

    assert prices(db) == [("SINGLE", 7400, True)]
    assert count(db, ProductVariantORM) == 1
    assert count(db, NutritionORM) == 0  # calories_kcal이 NOT NULL이라 영양성분 없으면 저장 안 함


def test_get_burgers_filters_by_brand_and_keyword(db):
    db.upsert_burgers(
        [
            make_item(),
            make_item(name="치즈와퍼", price=8000, set_price=10200),
            make_item(brand="롯데리아", brand_slug="lotteria", name="한우불고기버거", price=9200, set_price=None),
        ]
    )

    assert {b.name for b in db.get_burgers(brand="burgerking")} == {"와퍼", "치즈와퍼"}
    assert {b.name for b in db.get_burgers(brand="롯데리아")} == {"한우불고기버거"}
    cheese = db.get_burgers(keyword="치즈")
    assert [(b.name, b.price, b.set_price) for b in cheese] == [("치즈와퍼", 8000, 10200)]
    assert cheese[0].nutrition.calories_kcal == 706
