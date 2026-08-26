"""AI 채점 테스트.

진짜 AI를 부르지 않아요 — 테스트마다 돈이 나가면 안 되니까요.
가짜 채점은 그대로 쓰고, 진짜 경로는 mock 으로 확인해요.
"""

from unittest.mock import Mock, patch

import pytest

from app.ai_grader import (
    Correction,
    GradingResult,
    SentenceGrade,
    accuracy_percent,
    build_system_prompt,
    fake_grade,
    grade_sentences,
)

다섯문장 = [
    "오늘의 하늘은 푸르다",
    "고양이가 조아요",
    "아침에 우유를 마셨다",
    "학교에서 그림을 그렸다",
    "저녁에 산책을 했다",
]


# ── 정확도 계산 (D-11) ───────────────────────────────


def 문장(pos, corrections=0):
    return SentenceGrade(
        position=pos,
        original_text="x",
        corrections=[
            Correction(wrong_text="a", right_text="b", note="n") for _ in range(corrections)
        ],
        translation="t",
    )


@pytest.mark.parametrize(
    "교정있는문장수, 기대정확도",
    [(0, 100), (1, 80), (2, 60), (5, 0)],
)
def test_정확도는_문장_기준이다(교정있는문장수, 기대정확도):
    """단어가 아니라 문장 단위로 세요 (D-11).

    5문장 중 교정 없는 문장이 4개면 80%.
    """
    sentences = [문장(i, corrections=1 if i <= 교정있는문장수 else 0) for i in range(1, 6)]
    assert accuracy_percent(GradingResult(sentences=sentences)) == 기대정확도


def test_한_문장에_교정이_여러개여도_한_번만_센다():
    """문장 기준이니까 교정 개수는 상관없어요."""
    result = GradingResult(sentences=[문장(1, corrections=3)] + [문장(i) for i in range(2, 6)])
    assert accuracy_percent(result) == 80


def test_문장이_없으면_0():
    assert accuracy_percent(GradingResult(sentences=[])) == 0


# ── 가짜 채점 (API 키 없을 때) ───────────────────────


def test_키가_없으면_가짜_채점을_쓴다(monkeypatch):
    """키 없이도 개발할 수 있어야 해요. 그리고 돈이 안 나가야 해요."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    result = grade_sentences(다섯문장)

    assert len(result.sentences) == 5
    assert accuracy_percent(result) == 80  # '조아요' 하나만 잡혀요


def test_가짜_채점도_틀린_것만_고친다():
    result = fake_grade(다섯문장)

    맞은문장 = [s for s in result.sentences if not s.corrections]
    틀린문장 = [s for s in result.sentences if s.corrections]

    assert len(틀린문장) == 1
    assert 틀린문장[0].original_text == "고양이가 조아요"
    assert 틀린문장[0].corrected_text == "고양이가 좋아요"
    # 맞은 문장은 corrected_text 가 없어야 해요 (억지로 고치지 않기)
    assert all(s.corrected_text is None for s in 맞은문장)


def test_가짜_채점도_번역과_배운_표현을_준다():
    result = fake_grade(다섯문장)
    assert all(s.translation for s in result.sentences)
    assert "좋아요" in result.new_expressions


def test_틀린_게_없으면_배운_표현도_없다():
    result = fake_grade(["오늘은 맑았다", "밥을 먹었다"])
    assert result.new_expressions == []
    assert accuracy_percent(result) == 100


# ── 채점 지시문 ──────────────────────────────────────


def test_짝꿍마다_말투가_다르다():
    """짝꿍은 말투만 정해요 (D-16). 기능은 모두 같아요."""
    콩이 = build_system_prompt("ko", "ko", "kongi")
    먹물이 = build_system_prompt("ko", "ko", "meokmul")

    assert "반말" in 콩이
    assert "존댓말" in 먹물이
    assert 콩이 != 먹물이


def test_배우는_언어와_설명_언어를_따로_넣는다():
    """한국어를 배우면서 설명은 영어로 받을 수 있어요."""
    prompt = build_system_prompt("ko", "en", "meokmul")
    assert "한국어" in prompt  # 배우는 언어
    assert "영어" in prompt  # 설명 언어


def test_억지로_고치지_말라는_지시가_있다():
    """어린이용이라 멀쩡한 문장을 고치면 혼란스러워요."""
    prompt = build_system_prompt("ko", "ko", "kongi")
    assert "억지로 고치지" in prompt


# ── 진짜 채점 경로 (mock) ────────────────────────────


def test_키가_있으면_AI를_부른다(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-key")

    가짜응답 = Mock()
    가짜응답.parsed_output = GradingResult(sentences=[문장(1)], new_expressions=[])
    가짜클라이언트 = Mock()
    가짜클라이언트.messages.parse.return_value = 가짜응답

    with patch("anthropic.Anthropic", return_value=가짜클라이언트):
        result = grade_sentences(다섯문장, partner="meokmul")

    assert len(result.sentences) == 1
    호출 = 가짜클라이언트.messages.parse.call_args.kwargs
    assert 호출["model"] == "claude-opus-5"
    assert 호출["output_format"] is GradingResult  # 응답 모양 고정
    assert "존댓말" in 호출["system"]  # 짝꿍 말투 반영
    assert "고양이가 조아요" in 호출["messages"][0]["content"]  # 문장 전달


def test_AI를_한_번만_부른다(monkeypatch):
    """문장마다 부르면 비용이 5배가 돼요 (D-12)."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-key")

    가짜응답 = Mock()
    가짜응답.parsed_output = GradingResult(sentences=[])
    가짜클라이언트 = Mock()
    가짜클라이언트.messages.parse.return_value = 가짜응답

    with patch("anthropic.Anthropic", return_value=가짜클라이언트):
        grade_sentences(다섯문장)

    assert 가짜클라이언트.messages.parse.call_count == 1
