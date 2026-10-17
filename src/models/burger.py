from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field
from sqlalchemy import Column, DateTime, Float, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class NutritionInfo(BaseModel):
    """햄버거 영양성분 데이터 스키마"""

    weight_g: Optional[float] = Field(None, description="중량(g)")
    calories_kcal: Optional[float] = Field(None, description="열량(kcal)")
    protein_g: Optional[float] = Field(None, description="단백질(g)")
    saturated_fat_g: Optional[float] = Field(None, description="포화지방(g)")
    sodium_mg: Optional[float] = Field(None, description="나트륨(mg)")
    sugars_g: Optional[float] = Field(None, description="당류(g)")
    caffeine_mg: Optional[float] = Field(None, description="카페인(mg)")


class BurgerItem(BaseModel):
    """크롤링된 햄버거 정보 통합 모델 (Pydantic)"""

    brand: str = Field(..., description="브랜드명 (예: 맥도날드, 버거킹, 롯데리아)")
    name: str = Field(..., description="메뉴명 (한국어)")
    name_en: Optional[str] = Field(None, description="메뉴명 (영어)")
    category: str = Field(default="버거", description="카테고리 (버거, 세트, 사이드 등)")
    price: Optional[int] = Field(None, description="단품 가격(원)")
    set_price: Optional[int] = Field(None, description="세트 가격(원)")
    description: Optional[str] = Field(None, description="메뉴 설명")
    image_url: Optional[str] = Field(None, description="메뉴 이미지 URL")
    detail_url: Optional[str] = Field(None, description="상세 페이지 URL")
    allergens: Optional[str] = Field(None, description="알레르기 유발물질 정보")
    origin_info: Optional[str] = Field(None, description="원산지 정보")
    nutrition: NutritionInfo = Field(default_factory=NutritionInfo, description="영양성분")
    crawled_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="수집 일시(UTC)",
    )

    def to_flat_dict(self) -> dict:
        """CSV 및 DB 저장을 위해 중첩된 영양성분 필드를 평탄화한 딕셔너리 반환"""
        data = self.model_dump(exclude={"nutrition"})
        nutrition_data = self.nutrition.model_dump()
        return {**data, **nutrition_data}


class BurgerORM(Base):
    """데이터베이스 저장용 SQLAlchemy ORM 모델 (SQLite / MySQL / PostgreSQL 호환)"""

    __tablename__ = "burgers"
    __table_args__ = (
        UniqueConstraint("brand", "name", name="uq_burger_brand_name"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    brand = Column(String(50), nullable=False, index=True)
    name = Column(String(150), nullable=False, index=True)
    name_en = Column(String(150), nullable=True)
    category = Column(String(50), nullable=False, default="버거")
    price = Column(Integer, nullable=True)
    set_price = Column(Integer, nullable=True)
    description = Column(Text, nullable=True)
    image_url = Column(String(500), nullable=True)
    detail_url = Column(String(500), nullable=True)
    allergens = Column(Text, nullable=True)
    origin_info = Column(Text, nullable=True)

    # 영양성분 컬럼
    weight_g = Column(Float, nullable=True)
    calories_kcal = Column(Float, nullable=True)
    protein_g = Column(Float, nullable=True)
    saturated_fat_g = Column(Float, nullable=True)
    sodium_mg = Column(Float, nullable=True)
    sugars_g = Column(Float, nullable=True)
    caffeine_mg = Column(Float, nullable=True)

    crawled_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
