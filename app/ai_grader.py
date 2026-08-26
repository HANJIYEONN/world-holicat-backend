"""AI 맞춤법 채점 (D-01).

**AI를 부르는 곳은 여기 딱 한 군데예요.** 하루에 한 번, 5문장을 통째로
보내서 한꺼번에 채점받아요 (D-12). 문장마다 부르면 비용이 5배가 되고,
쓰는 도중에 교정이 끼어들어 흐름이 끊기거든요.

번역도 이 응답에 같이 담겨요 (D-20) — 번역 전용 API를 따로 쓰지 않아요.

⚠️ API 키가 없으면 **가짜 응답**으로 동작해요. 키 없이도 화면을 만들고
테스트할 수 있게 하려고요. 키를 넣는 순간 코드 수정 없이 진짜 AI로 바뀌어요.
"""

import os
from typing import List, Optional

from pydantic import BaseModel, Field

MODEL = "claude-opus-5"

# 짝꿍이 정하는 건 **말투와 설명의 자세함**뿐이에요 (D-16).
# 기능은 모두에게 똑같아요.
PARTNER_TONE = {
    "kongi": "초등학생 이하에게 말하듯 아주 쉽고 짧게, 반말로. 칭찬을 아끼지 마세요.",
    "cheese": "중·고등학생에게 친구처럼 쿨한 반말로. 짧고 담백하게.",
    "meokmul": "어른에게 존댓말로. 문법 규칙을 정확하고 자세하게 설명하세요.",
    "sikppang": "누구에게나 느긋한 반말로. 부담 주지 않게 부드럽게.",
}

LANGUAGE_NAME = {"ko": "한국어", "en": "영어", "ja": "일본어", "zh": "중국어"}


# ── 응답 모양 (AI가 이 구조에 맞춰서 답해요) ──────────────


class Correction(BaseModel):
    """고친 것 하나."""

    wrong_text: str = Field(description="원문에서 틀린 부분만")
    right_text: str = Field(description="올바르게 고친 부분만")
    note: str = Field(description="왜 그런지 설명 (피드백 언어로)")
    pronunciation: Optional[str] = Field(
        default=None, description="발음 표기. 한국어처럼 표기와 소리가 다를 때만"
    )


class SentenceGrade(BaseModel):
    """문장 하나의 채점 결과."""

    position: int = Field(description="몇 번째 문장인지 (1~5)")
    original_text: str = Field(description="원문 그대로")
    corrected_text: Optional[str] = Field(
        default=None, description="고친 문장 전체. 틀린 게 없으면 null"
    )
    corrections: List[Correction] = Field(default_factory=list)
    translation: str = Field(description="이 문장을 피드백 언어로 번역")


class GradingResult(BaseModel):
    """5문장 전체 채점 결과."""

    sentences: List[SentenceGrade]
    new_expressions: List[str] = Field(
        default_factory=list, description="오늘 새로 배운 표현 (고친 것 중에서)"
    )


def build_system_prompt(learning_language: str, feedback_language: str, partner: str) -> str:
    """채점 지시문을 만들어요.

    이 부분은 매번 똑같아서 프롬프트 캐싱이 잘 들어요 (비용 절감).
    """
    learning = LANGUAGE_NAME.get(learning_language, "한국어")
    feedback = LANGUAGE_NAME.get(feedback_language or learning_language, "한국어")
    tone = PARTNER_TONE.get(partner, PARTNER_TONE["kongi"])

    return f"""당신은 글쓰기 수첩 앱의 다정한 선생님이에요.

사용자는 {learning}로 하루 다섯 문장을 씁니다. 다섯 문장을 한꺼번에 받아
맞춤법·문법을 봐주세요.

## 말투
{tone}
설명은 {feedback}로 씁니다.

## 채점 규칙
1. **틀린 곳이 없으면 corrected_text 를 null 로 두고 corrections 를 비워두세요.**
   억지로 고치지 마세요. 자연스러운 문장을 "더 나은 표현"으로 바꾸는 것도 금지예요.
2. 고칠 때는 **문장 전체가 아니라 틀린 부분만** wrong_text / right_text 에 담으세요.
3. note 는 규칙을 알려주세요. "틀렸어요"가 아니라 "왜 그런지"를요.
   예: "'좋다'의 어간은 좋-이라서 ㅎ 받침을 유지해요."
4. pronunciation 은 표기와 소리가 다를 때만 채우세요. 아니면 null.
5. translation 에는 그 문장을 {feedback}로 번역해 넣으세요. 틀린 문장이면
   **고친 문장 기준**으로 번역하세요.
6. new_expressions 에는 오늘 고쳐준 것 중 기억하면 좋을 표현을 넣으세요.
   고친 게 없으면 빈 배열로 두세요.

## 중요
- 어린이가 볼 수 있어요. 부드럽고 격려하는 말투로, 겁주지 마세요.
- 아이가 쓴 내용 자체를 평가하지 마세요. 맞춤법·문법만 봐요.
- position 은 받은 순서 그대로 1부터 매기세요."""


def build_user_message(sentences: List[str]) -> str:
    lines = [f"{i}. {s}" for i, s in enumerate(sentences, start=1)]
    return "오늘 쓴 문장이에요. 채점해주세요.\n\n" + "\n".join(lines)


# ── 가짜 채점 (API 키 없을 때) ────────────────────────────

# 개발 중에 자주 쓰는 대표적인 맞춤법 실수 몇 개만 흉내내요.
FAKE_RULES = [
    ("조아요", "좋아요", "'좋다'의 어간은 좋-이라서 ㅎ 받침을 유지해요.", "[조아요]"),
    ("됬", "됐", "'되었'의 줄임은 '됐'이에요.", None),
    ("안되", "안 돼", "'안'은 띄어 쓰고, '되어'의 줄임은 '돼'예요.", None),
    ("할께", "할게", "'-ㄹ게'로 적어요. 소리는 [할께]지만 표기는 '할게'예요.", "[할께]"),
]


def fake_grade(sentences: List[str]) -> GradingResult:
    """API 키가 없을 때 쓰는 가짜 채점.

    진짜 AI를 안 부르니 **비용이 0원**이에요. 화면 만들고 테스트하는 데는
    이걸로 충분해요. 키를 넣으면 자동으로 진짜 채점으로 바뀌어요.
    """
    graded = []
    learned = []

    for position, text in enumerate(sentences, start=1):
        corrections = []
        fixed = text
        for wrong, right, note, pron in FAKE_RULES:
            if wrong in fixed:
                corrections.append(
                    Correction(wrong_text=wrong, right_text=right, note=note, pronunciation=pron)
                )
                fixed = fixed.replace(wrong, right)
                learned.append(right)

        graded.append(
            SentenceGrade(
                position=position,
                original_text=text,
                corrected_text=fixed if corrections else None,
                corrections=corrections,
                translation=f"(개발용 가짜 번역) {fixed}",
            )
        )

    return GradingResult(sentences=graded, new_expressions=learned)


# ── 진짜 채점 ────────────────────────────────────────────


def grade_sentences(
    sentences: List[str],
    learning_language: str = "ko",
    feedback_language: Optional[str] = None,
    partner: str = "kongi",
) -> GradingResult:
    """다섯 문장을 채점해요. 하루에 한 번만 불러요 (D-12).

    ANTHROPIC_API_KEY 가 없으면 가짜 채점으로 넘어가요.
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return fake_grade(sentences)

    import anthropic  # 키가 있을 때만 불러와요

    client = anthropic.Anthropic(api_key=api_key)

    response = client.messages.parse(
        model=MODEL,
        max_tokens=16000,
        system=build_system_prompt(learning_language, feedback_language, partner),
        messages=[{"role": "user", "content": build_user_message(sentences)}],
        output_format=GradingResult,
    )
    return response.parsed_output


def accuracy_percent(result: GradingResult) -> int:
    """정확도 = 교정이 없는 문장 수 ÷ 전체 문장 수 (D-11).

    단어 기준이 아니라 **문장 기준**이에요. 언어마다 단어를 세는 방법이
    달라서 4개국어에서 기준을 맞추기 어렵거든요.
    """
    if not result.sentences:
        return 0
    clean = sum(1 for s in result.sentences if not s.corrections)
    return round(clean / len(result.sentences) * 100)
