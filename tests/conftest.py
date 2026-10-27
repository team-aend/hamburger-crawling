import json
from pathlib import Path

import pytest
from bs4 import BeautifulSoup

FIXTURE_DIR = Path(__file__).parent / "fixtures"


def pytest_addoption(parser):
    parser.addoption("--live", action="store_true", help="실제 브랜드 사이트에 접속하는 스모크 테스트 실행")


def pytest_collection_modifyitems(config, items):
    if config.getoption("--live"):
        return
    skip_live = pytest.mark.skip(reason="실사이트 테스트는 --live 옵션으로 실행")
    for item in items:
        if "live" in item.keywords:
            item.add_marker(skip_live)


def load_text(relative_path: str) -> str:
    return (FIXTURE_DIR / relative_path).read_text(encoding="utf-8")


def load_json(relative_path: str) -> dict:
    return json.loads(load_text(relative_path))


def load_soup(relative_path: str) -> BeautifulSoup:
    return BeautifulSoup(load_text(relative_path), "lxml")


@pytest.fixture(autouse=True)
def no_sleep(request, monkeypatch):
    """크롤러의 요청 간 대기(time.sleep)를 없애 테스트를 빠르게 (실사이트 테스트는 대기 유지)"""
    if "live" not in request.keywords:
        monkeypatch.setattr("time.sleep", lambda _seconds: None)
