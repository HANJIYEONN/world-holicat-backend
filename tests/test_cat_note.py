"""고양이 수첩 계정 API 테스트.

pytest는 test_ 로 시작하는 함수를 자동으로 찾아서 실행해요.
각 함수는 "이렇게 하면 → 이렇게 되어야 한다" 하나씩만 확인해요.
"""

from tests.conftest import TEST_EMAIL

BASE = "/api/v1/cat-note"


# ── 로그인 없이 되는 것 ──────────────────────────────


def test_hello는_로그인_없이도_된다(client):
    res = client.get(f"{BASE}/hello")
    assert res.status_code == 200
    assert "콩이" in res.json()["message"]


def test_health는_ok를_돌려준다(client):
    assert client.get("/health").json() == {"status": "ok"}


# ── 문지기(로그인 검사)가 일하는지 ──────────────────


def test_토큰_없으면_401(client):
    """Depends(get_current_user_email)가 막아주는지 확인."""
    assert client.get(f"{BASE}/me").status_code == 401


def test_Bearer_없는_토큰은_401(client, token):
    res = client.get(f"{BASE}/me", headers={"Authorization": token})  # Bearer 빠짐
    assert res.status_code == 401


def test_엉터리_토큰은_401(client):
    res = client.get(f"{BASE}/me", headers={"Authorization": "Bearer not-a-real-token"})
    assert res.status_code == 401


# ── GET /me ────────────────────────────────────────


def test_계정_없으면_exists_false(client, auth):
    """첫 진입 화면이 이걸 보고 온보딩으로 보내요."""
    res = client.get(f"{BASE}/me", headers=auth)
    assert res.status_code == 200
    assert res.json() == {"exists": False}


# ── POST /me (계정 만들기) ─────────────────────────


def test_계정을_만들면_정보가_돌아온다(client, auth):
    res = client.post(
        f"{BASE}/me",
        headers=auth,
        json={"partner": "kongi", "note_id": "jiwoo07", "nickname": "지우"},
    )
    assert res.status_code == 201
    body = res.json()
    assert body["exists"] is True
    assert body["note_id"] == "jiwoo07"
    assert body["nickname"] == "지우"
    # 모델에 적어둔 기본값이 들어갔는지
    assert body["avatar"] == "cat"
    assert body["writing_stage"] == 1


def test_만들고_나면_exists_true로_바뀐다(client, auth):
    client.post(
        f"{BASE}/me",
        headers=auth,
        json={"partner": "kongi", "note_id": "jiwoo07", "nickname": "지우"},
    )
    assert client.get(f"{BASE}/me", headers=auth).json()["exists"] is True


def test_수첩_아이디는_소문자로_저장된다(client, auth):
    """Jiwoo07 과 jiwoo07 을 다른 사람으로 헷갈리면 안 돼요 (D-10)."""
    res = client.post(
        f"{BASE}/me",
        headers=auth,
        json={"partner": "kongi", "note_id": "JiWoo07", "nickname": "지우"},
    )
    assert res.json()["note_id"] == "jiwoo07"


def test_한_사람이_수첩을_두_개_못_만든다(client, auth):
    payload = {"partner": "kongi", "note_id": "jiwoo07", "nickname": "지우"}
    client.post(f"{BASE}/me", headers=auth, json=payload)
    res = client.post(f"{BASE}/me", headers=auth, json=payload)
    assert res.status_code == 409
    assert "이미" in res.json()["detail"]


def test_남이_쓰는_아이디는_못_쓴다(client, auth, other_auth):
    """다른 사람이 같은 note_id로 만들려 하면 409."""
    client.post(
        f"{BASE}/me",
        headers=auth,
        json={"partner": "kongi", "note_id": "jiwoo07", "nickname": "지우"},
    )
    res = client.post(
        f"{BASE}/me",
        headers=other_auth,
        json={"partner": "cheese", "note_id": "jiwoo07", "nickname": "민준"},
    )
    assert res.status_code == 409
    assert "아이디" in res.json()["detail"]


# ── 입력 검사(스키마)가 막아주는지 ──────────────────


def test_없는_짝꿍은_422(client, auth):
    """partner는 Literal 4종만 허용 (D-13)."""
    res = client.post(
        f"{BASE}/me",
        headers=auth,
        json={"partner": "멍멍이", "note_id": "jiwoo07", "nickname": "지우"},
    )
    assert res.status_code == 422


def test_짧은_아이디는_422(client, auth):
    res = client.post(
        f"{BASE}/me",
        headers=auth,
        json={"partner": "kongi", "note_id": "ab", "nickname": "지우"},
    )
    assert res.status_code == 422


def test_한글_아이디는_422(client, auth):
    """전세계 학습자가 쓰니까 영문+숫자만 (D-10)."""
    res = client.post(
        f"{BASE}/me",
        headers=auth,
        json={"partner": "kongi", "note_id": "지우07", "nickname": "지우"},
    )
    assert res.status_code == 422


# ── 남의 수첩이 보이면 안 됨 ───────────────────────


def test_내_수첩만_보인다(client, auth, other_auth):
    """다른 사람이 만든 계정이 내 GET /me 에 나오면 안 돼요."""
    client.post(
        f"{BASE}/me",
        headers=other_auth,
        json={"partner": "cheese", "note_id": "minjun22", "nickname": "민준"},
    )
    assert client.get(f"{BASE}/me", headers=auth).json() == {"exists": False}


def test_who는_내_이메일을_돌려준다(client, auth):
    assert client.get(f"{BASE}/who", headers=auth).json()["당신은"] == TEST_EMAIL
