"""오늘의 글감 테스트."""

from datetime import date

import pytest

from app.writing_prompts import PROMPTS, prompt_for

LANGUAGES = ("ko", "en", "ja", "zh")


# ── 글감 데이터 ──────────────────────────────────────


def test_글감이_30개다():
    assert len(PROMPTS) == 30


@pytest.mark.parametrize("language", LANGUAGES)
def test_모든_글감이_네_언어를_갖고_있다(language):
    """한 언어만 빠져도 그 언어 사용자에겐 글감이 안 나와요."""
    missing = [i for i, p in enumerate(PROMPTS) if not p.get(language, "").strip()]
    assert missing == [], f"{language} 번역이 빠진 글감: {missing}"


def test_글감이_전부_다르다():
    """같은 질문이 두 번 들어있으면 한 달에 두 번 나와요."""
    korean = [p["ko"] for p in PROMPTS]
    assert len(set(korean)) == len(korean)


# ── 날짜별 고르기 ────────────────────────────────────


def test_같은_날이면_항상_같은_글감():
    """쓰는 도중에 새로고침해도 질문이 안 바뀌어야 해요."""
    day = date(2026, 8, 26)
    assert len({prompt_for(day) for _ in range(10)}) == 1


def test_날이_바뀌면_글감도_바뀐다():
    a = prompt_for(date(2026, 8, 26))
    b = prompt_for(date(2026, 8, 27))
    assert a != b


def test_30일_동안_모든_글감이_한_번씩_나온다():
    """한 달이면 한 바퀴 — 같은 걸 자주 만나지 않아요."""
    seen = {prompt_for(date.fromordinal(date(2026, 8, 1).toordinal() + i)) for i in range(30)}
    assert len(seen) == 30


# ── 언어 ─────────────────────────────────────────────


@pytest.mark.parametrize("language", LANGUAGES)
def test_요청한_언어로_나온다(language):
    day = date(2026, 8, 26)
    expected = next(p for p in PROMPTS if p["ko"] == prompt_for(day, "ko"))
    assert prompt_for(day, language) == expected[language]


def test_모르는_언어는_한국어로_준다():
    day = date(2026, 8, 26)
    assert prompt_for(day, "fr") == prompt_for(day, "ko")


def test_언어를_안_주면_한국어로_준다():
    day = date(2026, 8, 26)
    assert prompt_for(day) == prompt_for(day, "ko")
