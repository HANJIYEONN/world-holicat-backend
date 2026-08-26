"""테스트가 운영 DB를 건드리지 않는지 확인하는 안전장치.

2026-08-16에 실수로 운영 TiDB에 테이블을 만든 적이 있어요.
conftest.py가 DATABASE_URL을 SQLite로 바꾸는데, 누군가 그 순서를
잘못 건드리면 조용히 운영 DB에 붙어버려요. 이 테스트가 그걸 막아요.
"""

from app.database import engine


def test_테스트는_SQLite를_쓴다():
    assert engine.dialect.name == "sqlite", (
        f"테스트가 {engine.dialect.name} 에 붙었어요! "
        "conftest.py에서 DATABASE_URL을 앱 import보다 먼저 바꿔야 해요."
    )


def test_운영_DB에는_절대_안_붙는다():
    host = (engine.url.host or "").lower()
    assert "tidbcloud" not in host, "🚨 테스트가 운영 DB(TiDB)에 붙었어요! 즉시 중단하세요."
    assert host in ("", "localhost", "127.0.0.1"), f"예상 못 한 DB 주소: {host}"


def test_테스트는_진짜_AI를_부르지_않는다():
    """💸 돈이 나가는 실수를 막는 안전장치.

    conftest 의 no_real_ai 픽스처가 키를 지워둬요. 이게 깨지면
    테스트를 돌릴 때마다 요금이 나갈 수 있어요.
    """
    import os

    assert os.getenv("ANTHROPIC_API_KEY") is None, (
        "테스트 중에 ANTHROPIC_API_KEY 가 살아있어요! "
        "conftest.py 의 no_real_ai 픽스처를 확인하세요."
    )
