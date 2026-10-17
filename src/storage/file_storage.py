import csv
import json
import logging
from pathlib import Path
from typing import List, Union

from src.config import DATA_DIR
from src.models.burger import BurgerItem

logger = logging.getLogger(__name__)


def save_to_json(
    items: List[BurgerItem], filename: Union[str, Path] = DATA_DIR / "hamburgers.json"
) -> Path:
    """BurgerItem 리스트를 JSON 파일로 저장"""
    filepath = Path(filename)
    filepath.parent.mkdir(parents=True, exist_ok=True)

    payload = [item.model_dump(mode="json") for item in items]
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    logger.info("JSON 저장 완료 (%d건): %s", len(items), filepath)
    return filepath


def save_to_csv(
    items: List[BurgerItem], filename: Union[str, Path] = DATA_DIR / "hamburgers.csv"
) -> Path:
    """BurgerItem 리스트를 평탄화(flatten)하여 CSV 파일로 저장"""
    filepath = Path(filename)
    filepath.parent.mkdir(parents=True, exist_ok=True)

    if not items:
        logger.warning("저장할 데이터가 없어 CSV 생성을 건너뜁니다.")
        return filepath

    rows = [item.to_flat_dict() for item in items]
    fieldnames = list(rows[0].keys())

    with open(filepath, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            row["crawled_at"] = row["crawled_at"].isoformat()
            writer.writerow(row)

    logger.info("CSV 저장 완료 (%d건): %s", len(items), filepath)
    return filepath
