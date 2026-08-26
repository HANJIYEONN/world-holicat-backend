"""구글 로그인 테스트.

진짜 구글에 연결하지 않아요. 구글이 이렇게 답한 척(mock)하고
우리 코드가 제대로 판단하는지만 봐요.
"""

from unittest.mock import Mock, patch

from tests.conftest import TEST_EMAIL

URL = "/api/v1/auth/google"
CLIENT_ID = "test-client-id"  # conftest.py 가 넣어둔 값


def 구글응답(status_code=200, body=None):
    m = Mock()
    m.status_code = status_code
    m.json.return_value = body or {}
    return m


# ── 무엇을 보냈는지에 따른 처리 ──────────────────────


def test_아무것도_안_보내면_400(client):
    assert client.post(URL, json={}).status_code == 400


# ── 🛡️ 보안: 남의 앱 토큰 막기 ──────────────────────


def test_다른_앱_토큰이면_401(client):
    """제일 중요한 검사.

    공격자가 자기 앱에서 발급받은 남의 액세스 토큰을 우리한테 보내면,
    aud 검사가 없을 때 그 사람으로 로그인돼버려요. 그걸 막는지 확인해요.
    """
    남의앱 = 구글응답(200, {"aud": "someone-elses-app.apps.googleusercontent.com",
                          "email": "victim@example.com"})

    with patch("app.routers.auth.http.get", return_value=남의앱):
        res = client.post(URL, json={"access_token": "훔친토큰"})

    assert res.status_code == 401
    assert "다른 앱" in res.json()["detail"]


def test_구글이_토큰을_거부하면_401(client):
    with patch("app.routers.auth.http.get", return_value=구글응답(400)):
        res = client.post(URL, json={"access_token": "엉터리"})
    assert res.status_code == 401


def test_이메일을_못_가져오면_401(client):
    """aud 는 맞지만 이메일 권한이 없는 토큰."""
    with patch("app.routers.auth.http.get", return_value=구글응답(200, {"aud": CLIENT_ID})):
        res = client.post(URL, json={"access_token": "이메일없는토큰"})
    assert res.status_code == 401


# ── 정상 로그인 ──────────────────────────────────────


def test_우리앱_토큰이면_로그인된다(client):
    tokeninfo = 구글응답(200, {"aud": CLIENT_ID, "email": TEST_EMAIL})
    userinfo = 구글응답(200, {"email": TEST_EMAIL, "name": "지연", "picture": "https://x/y.png"})

    with patch("app.routers.auth.http.get", side_effect=[tokeninfo, userinfo]):
        res = client.post(URL, json={"access_token": "정상토큰"})

    assert res.status_code == 200
    body = res.json()
    assert body["token_type"] == "bearer"
    assert body["user"]["email"] == TEST_EMAIL
    assert body["user"]["name"] == "지연"


def test_발급된_JWT로_다른_API를_쓸_수_있다(client):
    """로그인 결과가 실제로 문지기를 통과하는지 — 끝까지 이어지는지 확인."""
    tokeninfo = 구글응답(200, {"aud": CLIENT_ID, "email": TEST_EMAIL})
    userinfo = 구글응답(200, {"email": TEST_EMAIL, "name": "지연"})

    with patch("app.routers.auth.http.get", side_effect=[tokeninfo, userinfo]):
        our_token = client.post(URL, json={"access_token": "정상토큰"}).json()["access_token"]

    res = client.get(
        "/api/v1/cat-note/who", headers={"Authorization": f"Bearer {our_token}"}
    )
    assert res.status_code == 200
    assert res.json()["당신은"] == TEST_EMAIL


def test_이름을_못_가져와도_로그인은_된다(client):
    """프로필 조회가 실패해도 이메일만 있으면 들어갈 수 있어야 해요."""
    tokeninfo = 구글응답(200, {"aud": CLIENT_ID, "email": TEST_EMAIL})

    with patch("app.routers.auth.http.get", side_effect=[tokeninfo, 구글응답(500)]):
        res = client.post(URL, json={"access_token": "정상토큰"})

    assert res.status_code == 200
    assert res.json()["user"]["email"] == TEST_EMAIL
    assert res.json()["user"]["name"] is None


def test_구글에_연결이_안_되면_503(client):
    import requests as real_requests

    with patch("app.routers.auth.http.get", side_effect=real_requests.RequestException("끊김")):
        res = client.post(URL, json={"access_token": "정상토큰"})

    assert res.status_code == 503


# ── 기존 ID 토큰 방식도 그대로 ───────────────────────


def test_ID토큰_방식도_계속_동작한다(client):
    """프론트 배포 중에 옛 화면을 열어둔 사람이 로그인해도 안 깨지게."""
    with patch("app.routers.auth.id_token.verify_oauth2_token",
               return_value={"email": TEST_EMAIL, "name": "지연", "picture": None}):
        res = client.post(URL, json={"token": "구글ID토큰"})

    assert res.status_code == 200
    assert res.json()["user"]["email"] == TEST_EMAIL


def test_엉터리_ID토큰은_401(client):
    with patch("app.routers.auth.id_token.verify_oauth2_token",
               side_effect=ValueError("Invalid token")):
        res = client.post(URL, json={"token": "엉터리"})
    assert res.status_code == 401
