from tests.conftest import make_token

BASE = "/api/v1/blog"


def make_blog_user(client, auth, nickname: str):
    return client.post(f"{BASE}/users/me", headers=auth, json={"nickname": nickname})


def test_로그인하지_않으면_글을_볼_수_없다(client):
    assert client.get(f"{BASE}/posts").status_code == 401


def test_블로그_닉네임이_없으면_글을_쓸_수_없다(client, auth):
    res = client.post(
        f"{BASE}/posts",
        headers=auth,
        json={"title": "첫 글", "content": "안녕하세요"},
    )
    assert res.status_code == 403


def test_글을_작성하고_목록에서_본다(client, auth):
    make_blog_user(client, auth, "수염냥")

    created = client.post(
        f"{BASE}/posts",
        headers=auth,
        json={"title": "첫 글", "content": "마법의 이야기예요."},
    )

    assert created.status_code == 201
    assert created.json()["author_nickname"] == "수염냥"
    assert created.json()["is_author"] is True
    posts = client.get(f"{BASE}/posts", headers=auth).json()
    assert len(posts) == 1
    assert posts[0]["title"] == "첫 글"


def test_다른_사람의_글도_목록에_나온다(client, auth):
    other_auth = {"Authorization": f"Bearer {make_token('writer@example.com')}"}
    make_blog_user(client, other_auth, "다른냥")
    client.post(
        f"{BASE}/posts",
        headers=other_auth,
        json={"title": "다른 사람 글", "content": "모두에게 보여요."},
    )

    posts = client.get(f"{BASE}/posts", headers=auth).json()

    assert posts[0]["author_nickname"] == "다른냥"
    assert posts[0]["is_author"] is False


def test_최신글이_먼저_나온다(client, auth):
    make_blog_user(client, auth, "수염냥")
    for title in ("먼저 쓴 글", "나중에 쓴 글"):
        client.post(
            f"{BASE}/posts",
            headers=auth,
            json={"title": title, "content": "본문"},
        )

    posts = client.get(f"{BASE}/posts", headers=auth).json()
    assert [post["title"] for post in posts] == ["나중에 쓴 글", "먼저 쓴 글"]


def test_빈_제목과_본문은_받지_않는다(client, auth):
    make_blog_user(client, auth, "수염냥")
    res = client.post(
        f"{BASE}/posts",
        headers=auth,
        json={"title": "   ", "content": "   "},
    )
    assert res.status_code == 422


def test_글_하나를_읽는다(client, auth):
    make_blog_user(client, auth, "수염냥")
    post_id = client.post(
        f"{BASE}/posts",
        headers=auth,
        json={"title": "제목", "content": "본문"},
    ).json()["id"]

    res = client.get(f"{BASE}/posts/{post_id}", headers=auth)

    assert res.status_code == 200
    assert res.json()["title"] == "제목"
    assert res.json()["view_count"] == 0


def test_글을_읽을_때마다_조회수가_올라간다(client, auth):
    make_blog_user(client, auth, "수염냥")
    post_id = client.post(
        f"{BASE}/posts",
        headers=auth,
        json={"title": "조회할 글", "content": "본문"},
    ).json()["id"]

    assert client.post(f"{BASE}/posts/{post_id}/view", headers=auth).json()["view_count"] == 1
    assert client.post(f"{BASE}/posts/{post_id}/view", headers=auth).json()["view_count"] == 2
    assert client.get(f"{BASE}/posts", headers=auth).json()[0]["view_count"] == 2


def test_내_글을_수정한다(client, auth):
    make_blog_user(client, auth, "수염냥")
    post_id = client.post(
        f"{BASE}/posts",
        headers=auth,
        json={"title": "전 제목", "content": "전 본문"},
    ).json()["id"]

    res = client.put(
        f"{BASE}/posts/{post_id}",
        headers=auth,
        json={"title": "새 제목", "content": "새 본문"},
    )

    assert res.status_code == 200
    assert res.json()["title"] == "새 제목"
    assert res.json()["content"] == "새 본문"


def test_내_글을_삭제한다(client, auth):
    make_blog_user(client, auth, "수염냥")
    post_id = client.post(
        f"{BASE}/posts",
        headers=auth,
        json={"title": "지울 글", "content": "본문"},
    ).json()["id"]

    assert client.delete(f"{BASE}/posts/{post_id}", headers=auth).status_code == 204
    assert client.get(f"{BASE}/posts/{post_id}", headers=auth).status_code == 404


def test_남의_글은_수정하거나_삭제할_수_없다(client, auth, other_auth):
    make_blog_user(client, auth, "글쓴냥")
    post_id = client.post(
        f"{BASE}/posts",
        headers=auth,
        json={"title": "내 글", "content": "본문"},
    ).json()["id"]

    update = client.put(
        f"{BASE}/posts/{post_id}",
        headers=other_auth,
        json={"title": "훔친 글", "content": "본문"},
    )
    delete = client.delete(f"{BASE}/posts/{post_id}", headers=other_auth)

    assert update.status_code == 403
    assert delete.status_code == 403
