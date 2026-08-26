"""고양이 수첩 3장 — 기록 보기(달력·통계) API 테스트.

지난 날짜 기록은 API로는 못 만들어요(오늘 것만 쓸 수 있으니까).
그래서 DB에 직접 넣어두고 조회만 확인해요.
"""

from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import engine
from app.models import CatEntry, CatUser
from app.routers.cat_note import level_of
from tests.conftest import TEST_EMAIL

BASE = "/api/v1/cat-note"

FIVE = [
    "오늘의 하늘은 푸르다",
    "고양이가 조아요",
    "아침에 우유를 마셨다",
    "학교에서 그림을 그렸다",
    "밤에는 별이 보인다",
]


def make_account(client, auth, note_id="jiwoo07"):
    client.post(
        f"{BASE}/me",
        headers=auth,
        json={"partner": "kongi", "note_id": note_id, "nickname": "지우"},
    )


def finish_today(client, auth):
    """오늘 5문장 쓰고 제출까지."""
    for position, text in enumerate(FIVE, start=1):
        client.put(
            f"{BASE}/entries/today/sentences/{position}", headers=auth, json={"text": text}
        )
    return client.post(f"{BASE}/entries/today/complete", headers=auth)


def add_entry(day, accuracy=100, complete=True, email=TEST_EMAIL):
    """지난 날짜 수첩을 DB에 직접 하나 넣어요."""
    with Session(engine) as db:
        user = db.scalar(select(CatUser).where(CatUser.user_email == email))
        db.add(
            CatEntry(
                cat_user_id=user.id,
                entry_date=day,
                is_complete=complete,
                accuracy=accuracy if complete else None,
            )
        )
        db.commit()


# ── 문지기 ────────────────────────────────────────────


def test_토큰_없으면_전부_401(client):
    assert client.get(f"{BASE}/entries?year=2026&month=7").status_code == 401
    assert client.get(f"{BASE}/entries/2026-07-20").status_code == 401
    assert client.get(f"{BASE}/stats").status_code == 401


def test_수첩을_안_만들었으면_404(client, auth):
    assert client.get(f"{BASE}/entries?year=2026&month=7", headers=auth).status_code == 404
    assert client.get(f"{BASE}/stats", headers=auth).status_code == 404


# ── 3-1 월별 기록 ─────────────────────────────────────


def test_아무것도_안_쓴_달은_비어있다(client, auth):
    make_account(client, auth)
    body = client.get(f"{BASE}/entries?year=2026&month=7", headers=auth).json()
    assert body == {"days": [], "total_stamps_this_month": 0}


def test_그_달에_쓴_날들이_날짜순으로_나온다(client, auth):
    make_account(client, auth)
    add_entry(date(2026, 7, 20), accuracy=80)
    add_entry(date(2026, 7, 2), accuracy=100)

    body = client.get(f"{BASE}/entries?year=2026&month=7", headers=auth).json()
    assert body["days"] == [
        {"date": "2026-07-02", "is_complete": True, "accuracy": 100},
        {"date": "2026-07-20", "is_complete": True, "accuracy": 80},
    ]
    assert body["total_stamps_this_month"] == 2


def test_발도장은_다_쓴_날만_센다(client, auth):
    make_account(client, auth)
    add_entry(date(2026, 7, 1), complete=True)
    add_entry(date(2026, 7, 2), complete=False)

    body = client.get(f"{BASE}/entries?year=2026&month=7", headers=auth).json()
    assert len(body["days"]) == 2  # 쓰다 만 날도 달력엔 보여요
    assert body["total_stamps_this_month"] == 1  # 발도장은 하나


def test_옆_달_기록은_안_섞인다(client, auth):
    """7월 31일과 8월 1일이 헷갈리면 안 돼요."""
    make_account(client, auth)
    for day in [date(2026, 6, 30), date(2026, 7, 1), date(2026, 7, 31), date(2026, 8, 1)]:
        add_entry(day)

    days = client.get(f"{BASE}/entries?year=2026&month=7", headers=auth).json()["days"]
    assert [d["date"] for d in days] == ["2026-07-01", "2026-07-31"]


def test_12월도_제대로_끊긴다(client, auth):
    """12월 다음은 다음 해 1월 — 여기서 자주 틀려요."""
    make_account(client, auth)
    add_entry(date(2026, 12, 31))
    add_entry(date(2027, 1, 1))

    days = client.get(f"{BASE}/entries?year=2026&month=12", headers=auth).json()["days"]
    assert [d["date"] for d in days] == ["2026-12-31"]


def test_이상한_달은_422(client, auth):
    make_account(client, auth)
    for month in [0, 13, 99]:
        res = client.get(f"{BASE}/entries?year=2026&month={month}", headers=auth)
        assert res.status_code == 422, month


def test_년_월을_안_주면_422(client, auth):
    make_account(client, auth)
    assert client.get(f"{BASE}/entries", headers=auth).status_code == 422


def test_남의_기록은_안_보인다(client, auth, other_auth):
    make_account(client, auth, note_id="jiwoo07")
    make_account(client, other_auth, note_id="minsu01")
    add_entry(date(2026, 7, 5), email="other@example.com")

    body = client.get(f"{BASE}/entries?year=2026&month=7", headers=auth).json()
    assert body["days"] == []


# ── 3-2 특정 날짜 상세 ────────────────────────────────


def test_안_쓴_날은_404(client, auth):
    make_account(client, auth)
    res = client.get(f"{BASE}/entries/2026-07-20", headers=auth)
    assert res.status_code == 404
    assert "없어요" in res.json()["detail"]


def test_날짜가_아니면_422(client, auth):
    make_account(client, auth)
    assert client.get(f"{BASE}/entries/어제", headers=auth).status_code == 422


def test_지난_날짜를_펼치면_교정까지_나온다(client, auth):
    make_account(client, auth)
    finish_today(client, auth)

    today = date.today().isoformat()
    body = client.get(f"{BASE}/entries/{today}", headers=auth).json()
    assert body["entry_date"] == today
    assert body["is_complete"] is True
    assert body["accuracy"] == 80
    assert body["sentences"][1]["corrected_text"] == "고양이가 좋아요"
    assert body["sentences"][1]["translation"]
    assert body["new_expressions"] == ["좋아요"]


def test_오늘_주소는_날짜로_안_읽힌다(client, auth):
    """/entries/today 가 /entries/{날짜} 에 먹히면 안 돼요 (주소 등록 순서)."""
    make_account(client, auth)
    res = client.get(f"{BASE}/entries/today", headers=auth)
    assert res.status_code == 200
    assert "sentences" in res.json()


def test_남의_수첩은_못_펼친다(client, auth, other_auth):
    make_account(client, auth, note_id="jiwoo07")
    make_account(client, other_auth, note_id="minsu01")
    finish_today(client, other_auth)

    today = date.today().isoformat()
    assert client.get(f"{BASE}/entries/{today}", headers=auth).status_code == 404


# ── 3-3 통계 ──────────────────────────────────────────


def test_처음_시작한_사람의_통계(client, auth):
    make_account(client, auth)
    body = client.get(f"{BASE}/stats", headers=auth).json()
    assert body["streak_days"] == 0
    assert body["total_stamps"] == 0
    assert body["praises_received"] == 0
    # 아직 쓴 게 없으면 "정확도 0%" 대신 없음으로 — 못했다는 뜻으로 보이면 안 되니까요
    assert body["weekly_accuracy"] is None
    assert body["weekly_accuracy_diff"] is None
    assert body["vocab_count"] == 0
    assert body["level"] == "초급 1"
    assert body["expressions_to_next_level"] == 50


def test_오늘_다_쓰면_통계가_올라간다(client, auth):
    make_account(client, auth)
    finish_today(client, auth)

    body = client.get(f"{BASE}/stats", headers=auth).json()
    assert body["streak_days"] == 1
    assert body["total_stamps"] == 1
    assert body["weekly_accuracy"] == 80
    assert body["weekly_accuracy_diff"] is None  # 지난주엔 쓴 게 없어서 비교 불가


def test_연속_기록은_끊기면_멈춘다(client, auth):
    make_account(client, auth)
    today = date.today()
    add_entry(today)
    add_entry(today - timedelta(days=1))
    # 이틀 전은 건너뜀 → 연속은 2일에서 멈춰야 해요
    add_entry(today - timedelta(days=3))

    body = client.get(f"{BASE}/stats", headers=auth).json()
    assert body["streak_days"] == 2
    assert body["total_stamps"] == 3


def test_이번주와_지난주_정확도를_비교한다(client, auth):
    make_account(client, auth)
    today = date.today()
    add_entry(today, accuracy=90)  # 이번 주
    add_entry(today - timedelta(days=10), accuracy=70)  # 지난 주

    body = client.get(f"{BASE}/stats", headers=auth).json()
    assert body["weekly_accuracy"] == 90
    assert body["weekly_accuracy_diff"] == 20


def test_주간_정확도는_평균이다(client, auth):
    make_account(client, auth)
    today = date.today()
    add_entry(today, accuracy=100)
    add_entry(today - timedelta(days=2), accuracy=80)

    assert client.get(f"{BASE}/stats", headers=auth).json()["weekly_accuracy"] == 90


# ── 단계(레벨) 계산 ───────────────────────────────────


def test_단계는_표현_50개마다_올라간다():
    assert level_of(0) == ("초급 1", 50)
    assert level_of(49) == ("초급 1", 1)
    assert level_of(50) == ("초급 2", 50)
    # 명세서 예시 그대로 — 124개면 "중급 1", 다음까지 26개
    assert level_of(124) == ("중급 1", 26)


def test_마지막_단계에서는_더_안_올라간다():
    assert level_of(250) == ("고급 2", 0)
    assert level_of(9999) == ("고급 2", 0)
