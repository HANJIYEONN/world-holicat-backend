BASE = "/api/v1/blog/users"


def test_로그인하지_않으면_블로그_닉네임을_볼_수_없다(client):
    assert client.get(f"{BASE}/me").status_code == 401


def test_처음에는_블로그_닉네임이_없다(client, auth):
    assert client.get(f"{BASE}/me", headers=auth).json() == {"exists": False}


def test_블로그_닉네임을_처음_한_번_저장한다(client, auth):
    res = client.post(f"{BASE}/me", headers=auth, json={"nickname": "홀리캣"})

    assert res.status_code == 201
    assert res.json() == {"exists": True, "nickname": "홀리캣"}
    assert client.get(f"{BASE}/me", headers=auth).json() == res.json()


def test_닉네임의_앞뒤_공백은_없애서_저장한다(client, auth):
    res = client.post(f"{BASE}/me", headers=auth, json={"nickname": "  홀리캣  "})
    assert res.json()["nickname"] == "홀리캣"


def test_빈_닉네임은_받지_않는다(client, auth):
    assert client.post(f"{BASE}/me", headers=auth, json={"nickname": "   "}).status_code == 422


def test_닉네임은_20자까지다(client, auth):
    assert (
        client.post(f"{BASE}/me", headers=auth, json={"nickname": "가" * 21}).status_code
        == 422
    )


def test_한번_정한_블로그_닉네임은_바꿀_수_없다(client, auth):
    client.post(f"{BASE}/me", headers=auth, json={"nickname": "처음이름"})

    res = client.post(f"{BASE}/me", headers=auth, json={"nickname": "바꾼이름"})

    assert res.status_code == 409
    assert "바꿀 수 없" in res.json()["detail"]
    assert client.get(f"{BASE}/me", headers=auth).json()["nickname"] == "처음이름"


def test_사람마다_자기_블로그_닉네임을_본다(client, auth, other_auth):
    client.post(f"{BASE}/me", headers=auth, json={"nickname": "첫째"})
    client.post(f"{BASE}/me", headers=other_auth, json={"nickname": "둘째"})

    assert client.get(f"{BASE}/me", headers=auth).json()["nickname"] == "첫째"
    assert client.get(f"{BASE}/me", headers=other_auth).json()["nickname"] == "둘째"
