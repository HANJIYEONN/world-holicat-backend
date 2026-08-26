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


# ── GET /note-id/check (아이디 쓸 수 있나 확인) ────────


def 계정만들기(client, auth, note_id: str, partner: str = "kongi"):
    """테스트용: 그 아이디로 계정을 하나 만들어둬요."""
    return client.post(
        f"{BASE}/me",
        headers=auth,
        json={"partner": partner, "note_id": note_id, "nickname": "지우"},
    )


def test_아이디_검사도_로그인이_필요하다(client):
    assert client.get(f"{BASE}/note-id/check", params={"value": "jiwoo07"}).status_code == 401


def test_안_쓰는_아이디는_쓸_수_있다(client, auth):
    res = client.get(f"{BASE}/note-id/check", headers=auth, params={"value": "jiwoo07"})
    assert res.status_code == 200
    assert res.json() == {"available": True, "reason": None, "suggestions": []}


def test_이미_있는_아이디는_duplicate(client, auth, other_auth):
    계정만들기(client, other_auth, "jiwoo07")

    res = client.get(f"{BASE}/note-id/check", headers=auth, params={"value": "jiwoo07"})

    body = res.json()
    assert body["available"] is False
    assert body["reason"] == "duplicate"
    assert len(body["suggestions"]) > 0  # 대안을 줘야 해요


def test_짧으면_too_short(client, auth):
    res = client.get(f"{BASE}/note-id/check", headers=auth, params={"value": "abc"})
    assert res.json()["reason"] == "too_short"


def test_비어있으면_too_short(client, auth):
    res = client.get(f"{BASE}/note-id/check", headers=auth, params={"value": ""})
    assert res.json()["reason"] == "too_short"


def test_길면_too_long(client, auth):
    res = client.get(f"{BASE}/note-id/check", headers=auth, params={"value": "a" * 16})
    assert res.json()["reason"] == "too_long"


def test_한글은_invalid_char(client, auth):
    """전세계 학습자가 쓰니까 영문·숫자만 (D-10)."""
    res = client.get(f"{BASE}/note-id/check", headers=auth, params={"value": "지우07"})
    assert res.json()["reason"] == "invalid_char"


def test_특수문자는_invalid_char(client, auth):
    res = client.get(f"{BASE}/note-id/check", headers=auth, params={"value": "ji-woo07"})
    assert res.json()["reason"] == "invalid_char"


def test_짧고_한글이면_글자_문제를_먼저_알려준다(client, auth):
    """"지우"는 짧기도 하고 한글이기도 한데, 더 도움 되는 쪽을 알려줘요."""
    res = client.get(f"{BASE}/note-id/check", headers=auth, params={"value": "지우"})
    assert res.json()["reason"] == "invalid_char"


def test_대문자로_물어도_소문자로_판단한다(client, auth, other_auth):
    """jiwoo07을 이미 쓰고 있으면 JiWoo07도 못 써요 (D-10)."""
    계정만들기(client, other_auth, "jiwoo07")

    res = client.get(f"{BASE}/note-id/check", headers=auth, params={"value": "JiWoo07"})

    assert res.json()["reason"] == "duplicate"


def test_앞뒤_공백은_무시한다(client, auth):
    res = client.get(f"{BASE}/note-id/check", headers=auth, params={"value": "  jiwoo07  "})
    assert res.json()["available"] is True


# ── 추천 아이디 ──────────────────────────────────────


def test_추천은_최대_3개(client, auth, other_auth):
    계정만들기(client, other_auth, "jiwoo07")

    suggestions = client.get(
        f"{BASE}/note-id/check", headers=auth, params={"value": "jiwoo07"}
    ).json()["suggestions"]

    assert len(suggestions) <= 3


def test_추천은_전부_규칙에_맞는다(client, auth, other_auth):
    """추천해놓고 정작 못 쓰면 곤란하니까요."""
    계정만들기(client, other_auth, "jiwoo07")

    suggestions = client.get(
        f"{BASE}/note-id/check", headers=auth, params={"value": "jiwoo07"}
    ).json()["suggestions"]

    for s in suggestions:
        assert 4 <= len(s) <= 15, f"길이 규칙 위반: {s}"
        assert s.isalnum(), f"영문·숫자가 아님: {s}"


def test_추천에_이미_쓰는_아이디는_안_들어간다(client, auth, other_auth):
    """jiwoo1 이 이미 있으면 그건 추천하면 안 돼요."""
    계정만들기(client, other_auth, "jiwoo1")

    suggestions = client.get(
        f"{BASE}/note-id/check", headers=auth, params={"value": "jiwoo07"}
    ).json()["suggestions"]

    assert "jiwoo1" not in suggestions


def test_추천은_실제로_쓸_수_있다(client, auth, other_auth):
    """추천받은 걸 그대로 검사하면 available이어야 해요."""
    계정만들기(client, other_auth, "jiwoo07")

    suggestions = client.get(
        f"{BASE}/note-id/check", headers=auth, params={"value": "jiwoo07"}
    ).json()["suggestions"]

    for s in suggestions:
        res = client.get(f"{BASE}/note-id/check", headers=auth, params={"value": s})
        assert res.json()["available"] is True, f"추천했는데 못 쓰는 아이디: {s}"


# ── PATCH /me (내 정보 수정) ────────────────────────


def test_수정도_로그인이_필요하다(client):
    assert client.patch(f"{BASE}/me", json={"nickname": "지우"}).status_code == 401


def test_수첩이_없으면_404(client, auth):
    assert client.patch(f"{BASE}/me", headers=auth, json={"nickname": "지우"}).status_code == 404


def test_별명만_바꾼다(client, auth):
    계정만들기(client, auth, "jiwoo07")

    res = client.patch(f"{BASE}/me", headers=auth, json={"nickname": "지우니"})

    assert res.status_code == 200
    assert res.json()["nickname"] == "지우니"


def test_안_보낸_항목은_그대로_둔다(client, auth):
    """PATCH 의 핵심 — 보낸 것만 바꿔요."""
    계정만들기(client, auth, "jiwoo07")
    client.patch(f"{BASE}/me", headers=auth, json={"bio": "그림 좋아해요"})

    # 별명만 바꿔도 소개는 살아있어야 해요
    body = client.patch(f"{BASE}/me", headers=auth, json={"nickname": "지우니"}).json()

    assert body["nickname"] == "지우니"
    assert body["bio"] == "그림 좋아해요"  # 안 보냈으니 그대로
    assert body["note_id"] == "jiwoo07"


def test_짝꿍을_바꿀_수_있다(client, auth):
    """D-17 — 말투만 정하는 거라 바꿔도 괜찮아요."""
    계정만들기(client, auth, "jiwoo07", partner="kongi")

    res = client.patch(f"{BASE}/me", headers=auth, json={"partner": "meokmul"})

    assert res.json()["partner"] == "meokmul"


def test_여러_개를_한_번에_바꾼다(client, auth):
    계정만들기(client, auth, "jiwoo07")

    res = client.patch(
        f"{BASE}/me",
        headers=auth,
        json={"nickname": "지우니", "avatar": "dino", "daily_reminder": True},
    )

    body = res.json()
    assert body["nickname"] == "지우니"
    assert body["avatar"] == "dino"
    assert body["daily_reminder"] is True


def test_소개를_지울_수_있다(client, auth):
    """null 을 보내면 비우기 — 안 보내는 것과는 달라요."""
    계정만들기(client, auth, "jiwoo07")
    client.patch(f"{BASE}/me", headers=auth, json={"bio": "그림 좋아해요"})

    body = client.patch(f"{BASE}/me", headers=auth, json={"bio": None}).json()

    assert body["bio"] is None


def test_빈_요청은_아무것도_안_바꾼다(client, auth):
    계정만들기(client, auth, "jiwoo07")

    res = client.patch(f"{BASE}/me", headers=auth, json={})

    assert res.status_code == 200
    assert res.json()["note_id"] == "jiwoo07"


# ── 못 바꾸는 것 ─────────────────────────────────────


def test_수첩_아이디는_못_바꾼다(client, auth):
    """바꾸면 친구가 나를 못 찾게 돼요 (D-10).

    조용히 무시하지 않고 422 로 알려줘요 — 프론트가 잘못 보낸 걸 바로 알게요.
    """
    계정만들기(client, auth, "jiwoo07")

    res = client.patch(f"{BASE}/me", headers=auth, json={"note_id": "newid123"})

    assert res.status_code == 422
    # 진짜로 안 바뀌었는지도 확인
    assert client.get(f"{BASE}/me", headers=auth).json()["note_id"] == "jiwoo07"


def test_오타난_항목도_422(client, auth):
    계정만들기(client, auth, "jiwoo07")
    res = client.patch(f"{BASE}/me", headers=auth, json={"nickname_typo": "지우"})
    assert res.status_code == 422


def test_수정할_때_없는_짝꿍은_422(client, auth):
    계정만들기(client, auth, "jiwoo07")
    assert client.patch(f"{BASE}/me", headers=auth, json={"partner": "멍멍이"}).status_code == 422


def test_없는_아바타는_422(client, auth):
    계정만들기(client, auth, "jiwoo07")
    assert client.patch(f"{BASE}/me", headers=auth, json={"avatar": "용"}).status_code == 422


def test_너무_긴_별명은_422(client, auth):
    계정만들기(client, auth, "jiwoo07")
    assert client.patch(f"{BASE}/me", headers=auth, json={"nickname": "가" * 11}).status_code == 422
