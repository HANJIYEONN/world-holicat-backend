"""고양이 수첩 5장 — 단어장 API 테스트.

여기 모은 개수가 내 단계를 정하니까(D-23), 단계가 GET /me 와 GET /stats
양쪽에서 **같은 값**으로 나오는지도 같이 확인해요.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import engine
from app.models import CatUser, CatVocabItem
from app.routers.cat_note import stage_of
from tests.conftest import TEST_EMAIL

BASE = "/api/v1/cat-note"

FIVE = [
    "오늘의 하늘은 푸르다",
    "고양이가 조아요",
    "아침에 우유를 마셨다",
    "학교에서 그림을 그렸다",
    "밤에는 별이 보인다",
]


def register(client, headers, note_id="jiwoo07", nickname="지우"):
    return client.post(
        f"{BASE}/me",
        headers=headers,
        json={"partner": "kongi", "note_id": note_id, "nickname": nickname},
    )


def finish_today(client, headers):
    for position, text in enumerate(FIVE, start=1):
        client.put(
            f"{BASE}/entries/today/sentences/{position}", headers=headers, json={"text": text}
        )
    return client.post(f"{BASE}/entries/today/complete", headers=headers)


def first_correction_id(complete_response):
    """채점 결과에서 교정 번호 하나 꺼내기."""
    for sentence in complete_response.json()["sentences"]:
        if sentence["corrections"]:
            return sentence["corrections"][0]["correction_id"]
    raise AssertionError("교정이 하나도 없어요")


def stuff_vocab(count, email=TEST_EMAIL):
    """단계 계산을 확인하려고 표현을 잔뜩 넣어둬요."""
    with Session(engine) as db:
        user = db.scalar(select(CatUser).where(CatUser.user_email == email))
        for n in range(count):
            db.add(CatVocabItem(cat_user_id=user.id, expression=f"표현{n}"))
        db.commit()


# ── 문지기 ────────────────────────────────────────────


def test_토큰_없으면_401(client):
    assert client.get(f"{BASE}/vocab").status_code == 401
    assert client.post(f"{BASE}/vocab", json={"correction_id": 1}).status_code == 401
    assert client.delete(f"{BASE}/vocab/1").status_code == 401


def test_수첩을_안_만들었으면_404(client, auth):
    assert client.get(f"{BASE}/vocab", headers=auth).status_code == 404


# ── 담기 · 목록 · 빼기 ────────────────────────────────


def test_처음엔_단어장이_비어있다(client, auth):
    register(client, auth)
    assert client.get(f"{BASE}/vocab", headers=auth).json() == {"vocab": []}


def test_교정을_단어장에_담는다(client, auth):
    register(client, auth)
    correction_id = first_correction_id(finish_today(client, auth))

    res = client.post(f"{BASE}/vocab", headers=auth, json={"correction_id": correction_id})
    assert res.status_code == 201
    body = res.json()
    assert body["expression"] == "좋아요"  # 틀린 "조아요" 가 아니라 고친 쪽
    assert "좋다" in body["meaning"]
    assert body["correction_id"] == correction_id

    vocab = client.get(f"{BASE}/vocab", headers=auth).json()["vocab"]
    assert len(vocab) == 1
    assert vocab[0]["expression"] == "좋아요"


def test_같은_교정을_두_번_담으면_409(client, auth):
    register(client, auth)
    correction_id = first_correction_id(finish_today(client, auth))
    client.post(f"{BASE}/vocab", headers=auth, json={"correction_id": correction_id})

    res = client.post(f"{BASE}/vocab", headers=auth, json={"correction_id": correction_id})
    assert res.status_code == 409


def test_남의_교정은_못_담는다(client, auth, other_auth):
    """친구 글에서 배운 표현이라도 내 단어장에 몰래 넣을 순 없어요."""
    register(client, auth, "jiwoo07")
    register(client, other_auth, "minjun22", nickname="민준")
    correction_id = first_correction_id(finish_today(client, other_auth))

    res = client.post(f"{BASE}/vocab", headers=auth, json={"correction_id": correction_id})
    assert res.status_code == 403


def test_없는_교정은_404(client, auth):
    register(client, auth)
    res = client.post(f"{BASE}/vocab", headers=auth, json={"correction_id": 9999})
    assert res.status_code == 404


def test_단어장에서_뺄_수_있다(client, auth):
    register(client, auth)
    correction_id = first_correction_id(finish_today(client, auth))
    vocab_id = client.post(
        f"{BASE}/vocab", headers=auth, json={"correction_id": correction_id}
    ).json()["vocab_id"]

    assert client.delete(f"{BASE}/vocab/{vocab_id}", headers=auth).status_code == 204
    assert client.get(f"{BASE}/vocab", headers=auth).json()["vocab"] == []


def test_남의_단어장은_못_지운다(client, auth, other_auth):
    register(client, auth, "jiwoo07")
    register(client, other_auth, "minjun22")
    correction_id = first_correction_id(finish_today(client, other_auth))
    vocab_id = client.post(
        f"{BASE}/vocab", headers=other_auth, json={"correction_id": correction_id}
    ).json()["vocab_id"]

    assert client.delete(f"{BASE}/vocab/{vocab_id}", headers=auth).status_code == 404


def test_최근에_담은_것이_먼저_나온다(client, auth):
    register(client, auth)
    stuff_vocab(3)
    vocab = client.get(f"{BASE}/vocab", headers=auth).json()["vocab"]
    assert [item["expression"] for item in vocab] == ["표현2", "표현1", "표현0"]


# ── 단계가 두 곳에서 같은지 ───────────────────────────


def test_단어장이_차면_통계에_반영된다(client, auth):
    register(client, auth)
    correction_id = first_correction_id(finish_today(client, auth))
    client.post(f"{BASE}/vocab", headers=auth, json={"correction_id": correction_id})

    assert client.get(f"{BASE}/stats", headers=auth).json()["vocab_count"] == 1


def test_내_정보와_통계가_같은_단계를_말한다(client, auth):
    """저장된 값을 쓰면 두 화면이 다른 단계를 말할 수 있어요 (D-23)."""
    register(client, auth)
    stuff_vocab(124)

    me = client.get(f"{BASE}/me", headers=auth).json()
    stats = client.get(f"{BASE}/stats", headers=auth).json()

    assert stats["vocab_count"] == 124
    assert stats["level"] == "중급 1"
    assert stats["expressions_to_next_level"] == 26
    assert me["writing_stage"] == 3  # "중급 1" 은 세 번째 단계


def test_처음_만든_수첩은_1단계(client, auth):
    body = register(client, auth).json()
    assert body["writing_stage"] == 1


def test_단계_번호는_1부터_6까지(client, auth):
    assert stage_of(0) == 1
    assert stage_of(49) == 1
    assert stage_of(50) == 2
    assert stage_of(124) == 3
    assert stage_of(250) == 6
    assert stage_of(99999) == 6  # 더 올라가지 않아요
