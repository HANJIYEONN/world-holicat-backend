"""고양이 수첩 3장 — 기록 보기(달력·통계) API 테스트.

지난 날짜 기록은 API로는 못 만들어요(오늘 것만 쓸 수 있으니까).
그래서 DB에 직접 넣어두고 조회만 확인해요.
"""

from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import engine
from app.models import CatEntry, CatSentence, CatUser
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


def add_entry(day, accuracy=100, complete=True, email=TEST_EMAIL, sentences=1):
    """지난 날짜 수첩을 DB에 직접 하나 넣어요.

    문장도 같이 넣어요. 문장이 하나도 없으면 "앱을 열어만 본 날"이라
    달력에 안 나오거든요.
    """
    with Session(engine) as db:
        user = db.scalar(select(CatUser).where(CatUser.user_email == email))
        entry = CatEntry(
            cat_user_id=user.id,
            entry_date=day,
            is_complete=complete,
            accuracy=accuracy if complete else None,
        )
        db.add(entry)
        db.flush()  # entry.id 를 받아오려고요
        for position in range(1, sentences + 1):
            db.add(
                CatSentence(
                    entry_id=entry.id, position=position, original_text=f"{position}번 문장"
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


def test_열어만_본_날은_달력에_안_나온다(client, auth):
    """GET /entries/today 는 빈 수첩을 만들어둬요.

    그 빈 수첩까지 달력에 그리면, 앱을 열기만 한 날이
    "쓰다 만 날"처럼 보여요.
    """
    make_account(client, auth)
    today = date.today()

    client.get(f"{BASE}/entries/today", headers=auth)  # 열어만 봄

    body = client.get(
        f"{BASE}/entries?year={today.year}&month={today.month}", headers=auth
    ).json()
    assert body["days"] == []

    # 한 글자라도 쓰면 그때부터 보여요
    client.put(f"{BASE}/entries/today/sentences/1", headers=auth, json={"text": "한 줄 썼어요"})
    body = client.get(
        f"{BASE}/entries?year={today.year}&month={today.month}", headers=auth
    ).json()
    assert [day["date"] for day in body["days"]] == [today.isoformat()]


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


# ── 하루가 바뀌는 기준 (D-15) ─────────────────────────


def test_하루는_한국_시간_자정에_바뀐다():
    """배포 서버는 UTC라서, 그냥 date.today() 를 쓰면
    한국 아침 9시 전까지 서버는 아직 "어제"라고 생각해요.
    학교 가기 전에 쓴 글이 어제 수첩에 들어가면 안 돼요.

    (한국은 서머타임이 없어서 UTC+9 로 고정이에요.)
    """
    from datetime import timezone

    from app.routers.cat_note import today_kst

    한국_지금 = datetime.now(timezone.utc) + timedelta(hours=9)
    assert today_kst() == 한국_지금.date()


def test_저장할_시각에는_시간대가_안_붙는다():
    """DB 컬럼이 시간대 없는 DateTime 이라, tzinfo 가 붙어 있으면
    저장할 때 문제가 생겨요."""
    from app.routers.cat_note import now_kst

    assert now_kst().tzinfo is None


def test_DB가_찍는_시각도_한국_시간이다(client, auth):
    """created_at 을 DB(server_default=NOW())에 맡기면 UTC로 찍혀요.

    그러면 파이썬이 넣는 completed_at 과 **9시간**이 어긋나서,
    친구 피드의 "몇 분 전"이 9시간 틀리게 나와요.
    """
    from sqlalchemy import select
    from sqlalchemy.orm import Session

    from app.korea_time import now_kst
    from app.models import CatEntry

    make_account(client, auth)
    client.put(f"{BASE}/entries/today/sentences/1", headers=auth, json={"text": "한 줄"})

    with Session(engine) as db:
        entry = db.scalar(select(CatEntry))
        차이 = abs((now_kst() - entry.created_at).total_seconds())

    assert 차이 < 120, "created_at 이 한국 시간이 아니에요"


def test_오늘_안_써도_어제까지_연속은_살아있다(client, auth):
    """아침에 들어왔을 때 "연속 0일" 이라고 하면
    어제까지 쌓아온 게 끊긴 것처럼 보여요. 오늘이 끝날 때까지는 기다려줘요."""
    make_account(client, auth)
    today = date.today()
    add_entry(today - timedelta(days=1))
    add_entry(today - timedelta(days=2))
    # 오늘은 아직 안 썼어요

    assert client.get(f"{BASE}/stats", headers=auth).json()["streak_days"] == 2


def test_어제도_안_썼으면_연속이_끊긴다(client, auth):
    """봐주는 건 오늘 하루까지예요."""
    make_account(client, auth)
    today = date.today()
    add_entry(today - timedelta(days=2))
    add_entry(today - timedelta(days=3))

    assert client.get(f"{BASE}/stats", headers=auth).json()["streak_days"] == 0


def test_오늘_쓰면_연속에_오늘이_들어간다(client, auth):
    make_account(client, auth)
    today = date.today()
    add_entry(today)
    add_entry(today - timedelta(days=1))

    assert client.get(f"{BASE}/stats", headers=auth).json()["streak_days"] == 2
