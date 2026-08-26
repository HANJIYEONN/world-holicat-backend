"""테스트 공통 준비물.

⚠️ 제일 중요한 것: 앱을 불러오기 **전에** DATABASE_URL을 테스트용 SQLite로 바꿔요.
   안 그러면 테스트가 운영 DB(TiDB)에 붙어서 테이블을 만들어버려요.
"""

import os
import pathlib

# ── 앱 import보다 먼저! 순서가 바뀌면 운영 DB에 붙어요 ──
TEST_DB = pathlib.Path(__file__).parent / "test.db"
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB}"
os.environ.setdefault("GOOGLE_CLIENT_ID", "test-client-id")
os.environ.setdefault("JWT_SECRET", "test-secret-for-pytest-at-least-32-bytes-long")

import datetime  # noqa: E402

import jwt  # noqa: E402
import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.database import Base, engine  # noqa: E402
from app.main import app  # noqa: E402

TEST_EMAIL = "tester@example.com"


@pytest.fixture(autouse=True)
def no_real_ai(monkeypatch):
    """💸 테스트가 진짜 AI를 부르지 못하게 막아요.

    누나 컴퓨터에 ANTHROPIC_API_KEY 가 설정돼 있으면, 아무 생각 없이
    grade_sentences() 를 부르는 테스트가 **진짜 돈을 씁니다.**
    기본적으로 키를 지워두고, AI 경로를 테스트하는 곳만 직접 넣게 해요.
    """
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)


@pytest.fixture(autouse=True)
def fresh_db():
    """테스트 하나가 끝날 때마다 DB를 싹 비워요.

    앞 테스트가 만든 데이터가 다음 테스트에 영향을 주면
    "혼자 돌리면 되는데 같이 돌리면 실패"하는 골치 아픈 상황이 생기거든요.
    """
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client():
    """가짜 브라우저. 서버를 진짜로 켜지 않고도 요청을 보낼 수 있어요."""
    return TestClient(app)


def make_token(email: str) -> str:
    """그 사람으로 로그인한 척하는 진짜 JWT를 만들어요.

    문지기(get_current_user_email)가 실제로 검증하는 바로 그 토큰이에요.
    비밀키를 여기 한 곳에만 둬서, 나중에 바꿔도 테스트를 안 고쳐도 돼요.
    """
    payload = {
        "sub": email,
        "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=1),
    }
    return jwt.encode(payload, os.environ["JWT_SECRET"], algorithm="HS256")


@pytest.fixture
def token():
    """기본 테스트 사용자의 토큰."""
    return make_token(TEST_EMAIL)


@pytest.fixture
def other_auth():
    """다른 사람으로 로그인한 명찰 (남의 데이터가 안 보이는지 확인용)."""
    return {"Authorization": f"Bearer {make_token('other@example.com')}"}


@pytest.fixture
def auth(token):
    """요청에 붙일 로그인 명찰."""
    return {"Authorization": f"Bearer {token}"}
