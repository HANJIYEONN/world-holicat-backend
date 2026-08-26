"""고양이 수첩 2장 — 쓰기 API 테스트.

키가 없을 때 도는 가짜 채점(fake_grade)을 기준으로 확인해요.
conftest 의 no_real_ai 픽스처가 진짜 AI 를 못 부르게 막아둡니다 (💸).
"""

BASE = "/api/v1/cat-note"

# 가짜 채점 규칙에 걸리는 문장은 이 하나뿐 — "조아요" → "좋아요"
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


def write_all(client, auth, texts=FIVE):
    for position, text in enumerate(texts, start=1):
        client.put(
            f"{BASE}/entries/today/sentences/{position}",
            headers=auth,
            json={"text": text},
        )


# ── 문지기 ────────────────────────────────────────────


def test_토큰_없으면_전부_401(client):
    assert client.get(f"{BASE}/entries/today").status_code == 401
    assert client.put(f"{BASE}/entries/today/sentences/1", json={"text": "안녕"}).status_code == 401
    assert client.post(f"{BASE}/entries/today/complete").status_code == 401


def test_수첩을_안_만들었으면_404(client, auth):
    """로그인은 했지만 아직 계정을 안 만든 사람."""
    res = client.get(f"{BASE}/entries/today", headers=auth)
    assert res.status_code == 404
    assert "없어요" in res.json()["detail"]


# ── 2-1 오늘 수첩 가져오기 ────────────────────────────


def test_처음_열면_빈_수첩이_생긴다(client, auth):
    make_account(client, auth)
    body = client.get(f"{BASE}/entries/today", headers=auth).json()
    assert body["is_complete"] is False
    assert body["accuracy"] is None
    assert body["sentences"] == []
    assert isinstance(body["entry_id"], int)


def test_두_번_열어도_수첩은_하나다(client, auth):
    """열 때마다 새로 만들면 하루에 수첩이 여러 개 생겨버려요."""
    make_account(client, auth)
    first = client.get(f"{BASE}/entries/today", headers=auth).json()["entry_id"]
    second = client.get(f"{BASE}/entries/today", headers=auth).json()["entry_id"]
    assert first == second


def test_남의_문장은_안_보인다(client, auth, other_auth):
    make_account(client, auth, note_id="jiwoo07")
    make_account(client, other_auth, note_id="minsu01")
    write_all(client, other_auth)

    body = client.get(f"{BASE}/entries/today", headers=auth).json()
    assert body["sentences"] == []


# ── 2-2 문장 저장 ─────────────────────────────────────


def test_문장을_저장하면_다시_읽힌다(client, auth):
    make_account(client, auth)
    res = client.put(
        f"{BASE}/entries/today/sentences/4",
        headers=auth,
        json={"text": "학교에서 그림을 그렸다"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["position"] == 4
    assert body["text"] == "학교에서 그림을 그렸다"
    assert "saved_at" in body

    sentences = client.get(f"{BASE}/entries/today", headers=auth).json()["sentences"]
    assert sentences == [{"position": 4, "text": "학교에서 그림을 그렸다"}]


def test_같은_자리에_다시_쓰면_덮어쓴다(client, auth):
    """고쳐 쓸 때마다 문장이 쌓이면 안 돼요."""
    make_account(client, auth)
    for text in ["처음 쓴 글", "고쳐 쓴 글"]:
        client.put(f"{BASE}/entries/today/sentences/1", headers=auth, json={"text": text})

    sentences = client.get(f"{BASE}/entries/today", headers=auth).json()["sentences"]
    assert len(sentences) == 1
    assert sentences[0]["text"] == "고쳐 쓴 글"


def test_문장은_번호_순서대로_나온다(client, auth):
    make_account(client, auth)
    for position in [3, 1, 2]:
        client.put(
            f"{BASE}/entries/today/sentences/{position}",
            headers=auth,
            json={"text": f"{position}번 문장"},
        )
    sentences = client.get(f"{BASE}/entries/today", headers=auth).json()["sentences"]
    assert [s["position"] for s in sentences] == [1, 2, 3]


def test_1에서_5번_밖은_422(client, auth):
    make_account(client, auth)
    for position in [0, 6, 99]:
        res = client.put(
            f"{BASE}/entries/today/sentences/{position}", headers=auth, json={"text": "안녕"}
        )
        assert res.status_code == 422, position


def test_빈_문장은_422(client, auth):
    make_account(client, auth)
    for text in ["", "   "]:
        res = client.put(
            f"{BASE}/entries/today/sentences/1", headers=auth, json={"text": text}
        )
        assert res.status_code == 422, repr(text)


def test_앞뒤_공백은_잘린다(client, auth):
    make_account(client, auth)
    res = client.put(
        f"{BASE}/entries/today/sentences/1", headers=auth, json={"text": "  안녕하세요  "}
    )
    assert res.json()["text"] == "안녕하세요"


def test_너무_긴_문장은_422(client, auth):
    make_account(client, auth)
    res = client.put(
        f"{BASE}/entries/today/sentences/1", headers=auth, json={"text": "가" * 201}
    )
    assert res.status_code == 422


# ── 2-3 다 썼어요 (채점) ──────────────────────────────


def test_다_안_쓰면_400에_몇_개_썼는지_알려준다(client, auth):
    make_account(client, auth)
    write_all(client, auth, FIVE[:3])
    res = client.post(f"{BASE}/entries/today/complete", headers=auth)
    assert res.status_code == 400
    assert res.json()["detail"] == "아직 다 못 썼어요 (3/5)"


def test_다_쓰면_채점된다(client, auth):
    make_account(client, auth)
    write_all(client, auth)
    res = client.post(f"{BASE}/entries/today/complete", headers=auth)
    assert res.status_code == 200

    body = res.json()
    assert body["is_complete"] is True
    # 5문장 중 "고양이가 조아요" 하나만 틀렸으니 4/5 = 80% (D-11, 문장 기준)
    assert body["accuracy"] == 80
    assert len(body["sentences"]) == 5

    맞은_문장 = body["sentences"][0]
    assert 맞은_문장["corrected_text"] is None
    assert 맞은_문장["corrections"] == []

    틀린_문장 = body["sentences"][1]
    assert 틀린_문장["corrected_text"] == "고양이가 좋아요"
    correction = 틀린_문장["corrections"][0]
    assert correction["wrong_text"] == "조아요"
    assert correction["right_text"] == "좋아요"
    assert correction["pronunciation"] == "[조아요]"


def test_채점_결과에_번역이_함께_온다(client, auth):
    """번역 전용 API 는 안 만들어요 — 채점 응답에 같이 담겨요 (D-20)."""
    make_account(client, auth)
    write_all(client, auth)
    body = client.post(f"{BASE}/entries/today/complete", headers=auth).json()
    assert all(s["translation"] for s in body["sentences"])


def test_새로_배운_표현이_온다(client, auth):
    make_account(client, auth)
    write_all(client, auth)
    body = client.post(f"{BASE}/entries/today/complete", headers=auth).json()
    assert body["new_expressions"] == ["좋아요"]


def test_다_내면_발도장과_연속기록이_1이_된다(client, auth):
    make_account(client, auth)
    write_all(client, auth)
    body = client.post(f"{BASE}/entries/today/complete", headers=auth).json()
    assert body["streak_days"] == 1
    assert body["total_stamps"] == 1


def test_다_낸_뒤엔_문장을_못_고친다(client, auth):
    make_account(client, auth)
    write_all(client, auth)
    client.post(f"{BASE}/entries/today/complete", headers=auth)

    res = client.put(
        f"{BASE}/entries/today/sentences/1", headers=auth, json={"text": "몰래 고치기"}
    )
    assert res.status_code == 400
    assert "이미" in res.json()["detail"]


def test_두_번_내도_결과가_똑같다(client, auth):
    """💸 다시 부를 때마다 채점하면 같은 글에 돈을 두 번 내요."""
    make_account(client, auth)
    write_all(client, auth)
    first = client.post(f"{BASE}/entries/today/complete", headers=auth).json()
    second = client.post(f"{BASE}/entries/today/complete", headers=auth).json()
    assert first == second
    # 교정이 두 배로 쌓이지 않았는지도 확인
    assert len(second["sentences"][1]["corrections"]) == 1


def test_채점_뒤엔_오늘_수첩에도_정확도가_보인다(client, auth):
    make_account(client, auth)
    write_all(client, auth)
    client.post(f"{BASE}/entries/today/complete", headers=auth)

    body = client.get(f"{BASE}/entries/today", headers=auth).json()
    assert body["is_complete"] is True
    assert body["accuracy"] == 80


def test_쓰는_중에는_교정이_안_보인다(client, auth):
    """D-12 — 다 쓰기 전엔 틀린 그대로 남아있어야 해요."""
    make_account(client, auth)
    write_all(client, auth, FIVE[:2])

    sentences = client.get(f"{BASE}/entries/today", headers=auth).json()["sentences"]
    assert sentences[1]["text"] == "고양이가 조아요"
    assert "corrected_text" not in sentences[1]
