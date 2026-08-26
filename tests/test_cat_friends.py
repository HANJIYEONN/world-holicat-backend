"""고양이 수첩 4장 — 친구 API 테스트.

사람이 여러 명 나오는 테스트라, 누가 누구인지 헷갈리지 않게
지우 · 민준 · 하준 이름을 고정해서 써요.
"""

from tests.conftest import make_token

BASE = "/api/v1/cat-note"

FIVE = [
    "오늘의 하늘은 푸르다",
    "고양이가 조아요",
    "아침에 우유를 마셨다",
    "학교에서 그림을 그렸다",
    "밤에는 별이 보인다",
]


def headers_for(email):
    return {"Authorization": f"Bearer {make_token(email)}"}


def register(client, headers, note_id, nickname="지우"):
    return client.post(
        f"{BASE}/me",
        headers=headers,
        json={"partner": "kongi", "note_id": note_id, "nickname": nickname},
    )


def become_friends(client, asker, accepter, accepter_note_id):
    """asker 가 신청하고 accepter 가 수락 → 친구 성립."""
    res = client.post(f"{BASE}/friends", headers=asker, json={"note_id": accepter_note_id})
    friendship_id = res.json()["friendship_id"]
    client.post(f"{BASE}/friends/{friendship_id}/accept", headers=accepter)
    return friendship_id


def write_sentences(client, headers, texts):
    for position, text in enumerate(texts, start=1):
        client.put(
            f"{BASE}/entries/today/sentences/{position}", headers=headers, json={"text": text}
        )


def finish_today(client, headers):
    write_sentences(client, headers, FIVE)
    return client.post(f"{BASE}/entries/today/complete", headers=headers)


# ── 문지기 ────────────────────────────────────────────


def test_토큰_없으면_전부_401(client):
    assert client.get(f"{BASE}/users/search?note_id=minjun22").status_code == 401
    assert client.get(f"{BASE}/friends").status_code == 401
    assert client.get(f"{BASE}/friends/feed").status_code == 401
    assert client.post(f"{BASE}/friends", json={"note_id": "minjun22"}).status_code == 401
    assert client.post(f"{BASE}/entries/1/praises").status_code == 401
    assert client.get(f"{BASE}/entries/1/comments").status_code == 401


# ── 4-1 아이디로 찾기 ─────────────────────────────────


def test_없는_아이디는_found_false(client, auth):
    register(client, auth, "jiwoo07")
    assert client.get(f"{BASE}/users/search?note_id=nobody99", headers=auth).json() == {
        "found": False
    }


def test_있는_아이디를_찾으면_카드가_온다(client, auth, other_auth):
    register(client, auth, "jiwoo07")
    register(client, other_auth, "minjun22", nickname="민준")

    body = client.get(f"{BASE}/users/search?note_id=minjun22", headers=auth).json()
    assert body == {"found": True, "note_id": "minjun22", "nickname": "민준", "avatar": "cat"}


def test_대문자로_찾아도_찾아진다(client, auth, other_auth):
    """아이디는 소문자로 저장되니까 (D-10) 찾을 때도 맞춰줘야 해요."""
    register(client, auth, "jiwoo07")
    register(client, other_auth, "minjun22", nickname="민준")
    assert client.get(f"{BASE}/users/search?note_id=MinJun22", headers=auth).json()["found"]


def test_이메일_같은_건_안_나온다(client, auth, other_auth):
    """친구 검색으로 남의 이메일이 새어나가면 안 돼요."""
    register(client, auth, "jiwoo07")
    register(client, other_auth, "minjun22", nickname="민준")
    body = client.get(f"{BASE}/users/search?note_id=minjun22", headers=auth).json()
    assert set(body) == {"found", "note_id", "nickname", "avatar"}


# ── 4-3 신청 · 4-4 수락 ───────────────────────────────


def test_친구_신청하고_수락하면_친구가_된다(client, auth, other_auth):
    register(client, auth, "jiwoo07")
    register(client, other_auth, "minjun22", nickname="민준")

    res = client.post(f"{BASE}/friends", headers=auth, json={"note_id": "minjun22"})
    assert res.status_code == 201
    friendship_id = res.json()["friendship_id"]

    # 받은 사람 목록에 신청이 보여요
    waiting = client.get(f"{BASE}/friends", headers=other_auth).json()["pending_received"]
    assert waiting == [
        {"friendship_id": friendship_id, "note_id": "jiwoo07", "nickname": "지우", "avatar": "cat"}
    ]

    accepted = client.post(f"{BASE}/friends/{friendship_id}/accept", headers=other_auth)
    assert accepted.status_code == 200

    # 이제 양쪽 모두의 친구 목록에 있어요
    mine = client.get(f"{BASE}/friends", headers=auth).json()["friends"]
    theirs = client.get(f"{BASE}/friends", headers=other_auth).json()["friends"]
    assert mine[0]["note_id"] == "minjun22"
    assert theirs[0]["note_id"] == "jiwoo07"


def test_처음엔_친구가_없고_상한을_알려준다(client, auth):
    register(client, auth, "jiwoo07")
    body = client.get(f"{BASE}/friends", headers=auth).json()
    assert body == {"friends": [], "pending_received": [], "max_friends": 10}


def test_없는_아이디에는_신청_못_한다(client, auth):
    register(client, auth, "jiwoo07")
    res = client.post(f"{BASE}/friends", headers=auth, json={"note_id": "nobody99"})
    assert res.status_code == 404


def test_나에게는_신청_못_한다(client, auth):
    register(client, auth, "jiwoo07")
    res = client.post(f"{BASE}/friends", headers=auth, json={"note_id": "jiwoo07"})
    assert res.status_code == 400


def test_두_번_신청하면_409(client, auth, other_auth):
    register(client, auth, "jiwoo07")
    register(client, other_auth, "minjun22")
    client.post(f"{BASE}/friends", headers=auth, json={"note_id": "minjun22"})
    res = client.post(f"{BASE}/friends", headers=auth, json={"note_id": "minjun22"})
    assert res.status_code == 409


def test_반대쪽에서_신청해도_409(client, auth, other_auth):
    """지우가 민준에게 신청했는데, 민준이 다시 지우에게 신청하면 안 돼요."""
    register(client, auth, "jiwoo07")
    register(client, other_auth, "minjun22")
    client.post(f"{BASE}/friends", headers=auth, json={"note_id": "minjun22"})
    res = client.post(f"{BASE}/friends", headers=other_auth, json={"note_id": "jiwoo07"})
    assert res.status_code == 409


def test_신청한_사람은_수락_못_한다(client, auth, other_auth):
    """내가 신청해놓고 내가 수락하면 상대 뜻과 상관없이 친구가 돼요."""
    register(client, auth, "jiwoo07")
    register(client, other_auth, "minjun22")
    friendship_id = client.post(
        f"{BASE}/friends", headers=auth, json={"note_id": "minjun22"}
    ).json()["friendship_id"]

    assert client.post(f"{BASE}/friends/{friendship_id}/accept", headers=auth).status_code == 404


def test_이미_친구면_수락_409(client, auth, other_auth):
    register(client, auth, "jiwoo07")
    register(client, other_auth, "minjun22")
    friendship_id = become_friends(client, auth, other_auth, "minjun22")
    res = client.post(f"{BASE}/friends/{friendship_id}/accept", headers=other_auth)
    assert res.status_code == 409


def test_친구는_열_명까지(client, auth):
    """D-22 — 열한 번째부터는 막혀요."""
    register(client, auth, "jiwoo07")
    for n in range(10):
        friend = headers_for(f"friend{n}@example.com")
        register(client, friend, f"friend{n:02d}x", nickname=f"친구{n}")
        become_friends(client, auth, friend, f"friend{n:02d}x")

    assert len(client.get(f"{BASE}/friends", headers=auth).json()["friends"]) == 10

    eleventh = headers_for("eleventh@example.com")
    register(client, eleventh, "eleventh1", nickname="열한번")
    res = client.post(f"{BASE}/friends", headers=auth, json={"note_id": "eleventh1"})
    assert res.status_code == 409
    assert res.json()["detail"] == "친구는 10명까지 사귈 수 있어요"


def test_상대가_가득_차도_막힌다(client, auth, other_auth):
    register(client, auth, "jiwoo07")
    register(client, other_auth, "minjun22", nickname="민준")
    for n in range(10):
        friend = headers_for(f"friend{n}@example.com")
        register(client, friend, f"friend{n:02d}x", nickname=f"친구{n}")
        become_friends(client, other_auth, friend, f"friend{n:02d}x")

    res = client.post(f"{BASE}/friends", headers=auth, json={"note_id": "minjun22"})
    assert res.status_code == 409


def test_수락하는_순간_자리가_없으면_막힌다(client, auth, other_auth):
    """신청할 땐 자리가 있었는데 그 사이에 다 찬 경우 (D-22)."""
    register(client, auth, "jiwoo07")
    register(client, other_auth, "minjun22", nickname="민준")
    friendship_id = client.post(
        f"{BASE}/friends", headers=auth, json={"note_id": "minjun22"}
    ).json()["friendship_id"]

    # 수락하기 전에 지우가 다른 친구 10명을 채워버려요
    for n in range(10):
        friend = headers_for(f"friend{n}@example.com")
        register(client, friend, f"friend{n:02d}x", nickname=f"친구{n}")
        become_friends(client, auth, friend, f"friend{n:02d}x")

    res = client.post(f"{BASE}/friends/{friendship_id}/accept", headers=other_auth)
    assert res.status_code == 409


# ── 4-5 거절 · 삭제 ───────────────────────────────────


def test_받은_사람이_거절할_수_있다(client, auth, other_auth):
    register(client, auth, "jiwoo07")
    register(client, other_auth, "minjun22")
    friendship_id = client.post(
        f"{BASE}/friends", headers=auth, json={"note_id": "minjun22"}
    ).json()["friendship_id"]

    assert client.delete(f"{BASE}/friends/{friendship_id}", headers=other_auth).status_code == 204
    assert client.get(f"{BASE}/friends", headers=other_auth).json()["pending_received"] == []


def test_신청한_사람이_취소할_수_있다(client, auth, other_auth):
    register(client, auth, "jiwoo07")
    register(client, other_auth, "minjun22")
    friendship_id = client.post(
        f"{BASE}/friends", headers=auth, json={"note_id": "minjun22"}
    ).json()["friendship_id"]

    assert client.delete(f"{BASE}/friends/{friendship_id}", headers=auth).status_code == 204


def test_친구를_끊으면_목록에서_사라진다(client, auth, other_auth):
    register(client, auth, "jiwoo07")
    register(client, other_auth, "minjun22")
    friendship_id = become_friends(client, auth, other_auth, "minjun22")

    client.delete(f"{BASE}/friends/{friendship_id}", headers=auth)
    assert client.get(f"{BASE}/friends", headers=auth).json()["friends"] == []
    assert client.get(f"{BASE}/friends", headers=other_auth).json()["friends"] == []


def test_남의_친구_관계는_못_지운다(client, auth, other_auth):
    register(client, auth, "jiwoo07")
    register(client, other_auth, "minjun22")
    hajun = headers_for("hajun@example.com")
    register(client, hajun, "hajun9x", nickname="하준")
    friendship_id = become_friends(client, other_auth, hajun, "hajun9x")

    assert client.delete(f"{BASE}/friends/{friendship_id}", headers=auth).status_code == 404


# ── 4-6 친구 피드 ─────────────────────────────────────


def test_친구가_없으면_피드도_비어있다(client, auth):
    register(client, auth, "jiwoo07")
    assert client.get(f"{BASE}/friends/feed", headers=auth).json() == {"feed": []}


def test_쓰는_중인_친구가_보인다(client, auth, other_auth):
    register(client, auth, "jiwoo07")
    register(client, other_auth, "minjun22", nickname="민준")
    become_friends(client, auth, other_auth, "minjun22")
    write_sentences(client, other_auth, FIVE[:2])

    card = client.get(f"{BASE}/friends/feed", headers=auth).json()["feed"][0]
    assert card["note_id"] == "minjun22"
    assert card["status"] == "writing"
    assert card["progress"] == "2/5"
    assert card["praise_count"] == 0
    assert card["i_praised"] is False
    assert card["written_at"]


def test_다_쓴_친구는_complete로_보인다(client, auth, other_auth):
    register(client, auth, "jiwoo07")
    register(client, other_auth, "minjun22", nickname="민준")
    become_friends(client, auth, other_auth, "minjun22")
    finish_today(client, other_auth)

    card = client.get(f"{BASE}/friends/feed", headers=auth).json()["feed"][0]
    assert card["status"] == "complete"
    assert card["progress"] == "5/5"


def test_피드에는_고친_글이_아니라_쓴_글이_나온다(client, auth, other_auth):
    """친구가 뭘 썼는지 보는 자리예요. 교정본을 보여주면 창피할 수 있어요."""
    register(client, auth, "jiwoo07")
    register(client, other_auth, "minjun22", nickname="민준")
    become_friends(client, auth, other_auth, "minjun22")
    finish_today(client, other_auth)

    card = client.get(f"{BASE}/friends/feed", headers=auth).json()["feed"][0]
    assert card["sentences"][1] == "고양이가 조아요"  # 고친 "좋아요" 가 아니라


def test_친구_아닌_사람은_피드에_안_나온다(client, auth, other_auth):
    register(client, auth, "jiwoo07")
    register(client, other_auth, "minjun22")
    finish_today(client, other_auth)  # 친구가 아닌 상태

    assert client.get(f"{BASE}/friends/feed", headers=auth).json()["feed"] == []


# ── 4-7 칭찬도장 ──────────────────────────────────────


def test_친구_수첩에_칭찬도장을_준다(client, auth, other_auth):
    register(client, auth, "jiwoo07")
    register(client, other_auth, "minjun22", nickname="민준")
    become_friends(client, auth, other_auth, "minjun22")
    entry_id = finish_today(client, other_auth).json()["entry_id"]

    res = client.post(f"{BASE}/entries/{entry_id}/praises", headers=auth)
    assert res.status_code == 201
    assert res.json() == {"praise_count": 1}

    card = client.get(f"{BASE}/friends/feed", headers=auth).json()["feed"][0]
    assert card["praise_count"] == 1
    assert card["i_praised"] is True


def test_같은_수첩에_두_번은_못_준다(client, auth, other_auth):
    register(client, auth, "jiwoo07")
    register(client, other_auth, "minjun22")
    become_friends(client, auth, other_auth, "minjun22")
    entry_id = finish_today(client, other_auth).json()["entry_id"]

    client.post(f"{BASE}/entries/{entry_id}/praises", headers=auth)
    assert client.post(f"{BASE}/entries/{entry_id}/praises", headers=auth).status_code == 409


def test_내_수첩에는_못_준다(client, auth):
    register(client, auth, "jiwoo07")
    entry_id = finish_today(client, auth).json()["entry_id"]
    assert client.post(f"{BASE}/entries/{entry_id}/praises", headers=auth).status_code == 403


def test_친구_아닌_사람_수첩에는_못_준다(client, auth, other_auth):
    register(client, auth, "jiwoo07")
    register(client, other_auth, "minjun22")
    entry_id = finish_today(client, other_auth).json()["entry_id"]
    assert client.post(f"{BASE}/entries/{entry_id}/praises", headers=auth).status_code == 403


def test_없는_수첩에는_404(client, auth):
    register(client, auth, "jiwoo07")
    assert client.post(f"{BASE}/entries/9999/praises", headers=auth).status_code == 404


def test_받은_칭찬은_통계에_쌓인다(client, auth, other_auth):
    register(client, auth, "jiwoo07")
    register(client, other_auth, "minjun22")
    become_friends(client, auth, other_auth, "minjun22")
    entry_id = finish_today(client, other_auth).json()["entry_id"]
    client.post(f"{BASE}/entries/{entry_id}/praises", headers=auth)

    assert client.get(f"{BASE}/stats", headers=other_auth).json()["praises_received"] == 1


# ── 4-8 · 4-9 댓글 ────────────────────────────────────


def test_친구_수첩에_댓글을_쓴다(client, auth, other_auth):
    register(client, auth, "jiwoo07")
    register(client, other_auth, "minjun22", nickname="민준")
    become_friends(client, auth, other_auth, "minjun22")
    entry_id = finish_today(client, other_auth).json()["entry_id"]

    res = client.post(
        f"{BASE}/entries/{entry_id}/comments", headers=auth, json={"content": "잘 썼다!"}
    )
    assert res.status_code == 201
    assert res.json()["content"] == "잘 썼다!"
    assert res.json()["nickname"] == "지우"

    comments = client.get(f"{BASE}/entries/{entry_id}/comments", headers=auth).json()["comments"]
    assert len(comments) == 1
    assert comments[0]["note_id"] == "jiwoo07"


def test_내_수첩에_달린_댓글은_내가_볼_수_있다(client, auth, other_auth):
    """내 글에 달린 칭찬을 못 보면 댓글이 무슨 소용이겠어요."""
    register(client, auth, "jiwoo07")
    register(client, other_auth, "minjun22")
    become_friends(client, auth, other_auth, "minjun22")
    entry_id = finish_today(client, other_auth).json()["entry_id"]
    client.post(f"{BASE}/entries/{entry_id}/comments", headers=auth, json={"content": "잘 썼다!"})

    comments = client.get(f"{BASE}/entries/{entry_id}/comments", headers=other_auth).json()
    assert comments["comments"][0]["content"] == "잘 썼다!"


def test_친구_아닌_사람_수첩엔_댓글_못_쓴다(client, auth, other_auth):
    register(client, auth, "jiwoo07")
    register(client, other_auth, "minjun22")
    entry_id = finish_today(client, other_auth).json()["entry_id"]

    assert client.get(f"{BASE}/entries/{entry_id}/comments", headers=auth).status_code == 403
    res = client.post(f"{BASE}/entries/{entry_id}/comments", headers=auth, json={"content": "안녕"})
    assert res.status_code == 403


def test_빈_댓글과_너무_긴_댓글은_422(client, auth, other_auth):
    register(client, auth, "jiwoo07")
    register(client, other_auth, "minjun22")
    become_friends(client, auth, other_auth, "minjun22")
    entry_id = finish_today(client, other_auth).json()["entry_id"]

    for content in ["", "   ", "가" * 201]:
        res = client.post(
            f"{BASE}/entries/{entry_id}/comments", headers=auth, json={"content": content}
        )
        assert res.status_code == 422, repr(content[:10])
