"""오늘의 글감 (WRITE-02).

"오늘 뭐 쓰지?" 하고 막힐 때 도와주는 질문이에요. 30개를 돌려가며 써요.

## 왜 날짜로 고르나
무작위로 고르면 새로고침할 때마다 글감이 바뀌어요. 쓰는 도중에 질문이
바뀌면 당황스러우니까, **날짜가 같으면 항상 같은 글감**이 나오게 했어요.

## 언어
앱이 4개국어를 지원해서(한·영·일·중) 글감도 언어별로 있어요.
사용자가 **설명받을 언어**로 보여줘요 — 글감은 "무엇을 쓸지" 알려주는
안내라서, 배우는 언어가 아니라 알아듣는 언어로 나와야 해요.
"""

from datetime import date
from typing import Optional

# 30개 × 4개국어.
# 고르는 기준: 어린이가 바로 떠올릴 수 있는 **구체적인 하루의 조각**.
# "오늘 어땠어?" 같은 막연한 질문은 오히려 쓰기 어려워서 뺐어요.
PROMPTS: list[dict[str, str]] = [
    {
        "ko": "오늘 누구랑 놀았는지 써 볼까?",
        "en": "Who did you play with today?",
        "ja": "今日は誰と遊んだ？",
        "zh": "今天和谁一起玩了？",
    },
    {
        "ko": "오늘 먹은 것 중에 제일 맛있었던 건?",
        "en": "What was the tastiest thing you ate today?",
        "ja": "今日食べた中で一番おいしかったものは？",
        "zh": "今天吃的东西里最好吃的是什么？",
    },
    {
        "ko": "오늘 하늘은 어떤 색이었어?",
        "en": "What color was the sky today?",
        "ja": "今日の空は何色だった？",
        "zh": "今天的天空是什么颜色？",
    },
    {
        "ko": "오늘 웃었던 일이 있었어?",
        "en": "Did something make you laugh today?",
        "ja": "今日笑ったことはあった？",
        "zh": "今天有什么让你笑了吗？",
    },
    {
        "ko": "지금 입고 있는 옷을 그려보듯 써 볼까?",
        "en": "Describe what you're wearing right now.",
        "ja": "今着ている服を描くように書いてみよう。",
        "zh": "描述一下你现在穿的衣服。",
    },
    {
        "ko": "오늘 가장 오래 있었던 곳은 어디야?",
        "en": "Where did you spend the most time today?",
        "ja": "今日いちばん長くいた場所はどこ？",
        "zh": "今天待得最久的地方是哪里？",
    },
    {
        "ko": "요즘 좋아하는 노래가 있어?",
        "en": "Is there a song you like these days?",
        "ja": "最近好きな歌はある？",
        "zh": "最近有喜欢的歌吗？",
    },
    {
        "ko": "오늘 만난 사람 중에 기억나는 사람은?",
        "en": "Who do you remember meeting today?",
        "ja": "今日会った人で覚えている人は？",
        "zh": "今天遇到的人中记得谁？",
    },
    {
        "ko": "창밖에 무엇이 보여?",
        "en": "What can you see out the window?",
        "ja": "窓の外に何が見える？",
        "zh": "窗外能看到什么？",
    },
    {
        "ko": "오늘 새로 알게 된 것이 있어?",
        "en": "Did you learn something new today?",
        "ja": "今日新しく知ったことはある？",
        "zh": "今天学到了什么新东西吗？",
    },
    {
        "ko": "좋아하는 동물에 대해 써 볼까?",
        "en": "Write about an animal you like.",
        "ja": "好きな動物について書いてみよう。",
        "zh": "写一写你喜欢的动物。",
    },
    {
        "ko": "오늘 조금 힘들었던 일이 있었어?",
        "en": "Was there anything a little hard today?",
        "ja": "今日ちょっと大変だったことはあった？",
        "zh": "今天有什么有点辛苦的事吗？",
    },
    {
        "ko": "내일 하고 싶은 일은 뭐야?",
        "en": "What do you want to do tomorrow?",
        "ja": "明日やりたいことは何？",
        "zh": "明天想做什么？",
    },
    {
        "ko": "가장 좋아하는 색에 대해 써 볼까?",
        "en": "Write about your favorite color.",
        "ja": "いちばん好きな色について書いてみよう。",
        "zh": "写一写你最喜欢的颜色。",
    },
    {
        "ko": "오늘 아침에 제일 먼저 한 일은?",
        "en": "What was the first thing you did this morning?",
        "ja": "今朝いちばん最初にしたことは？",
        "zh": "今天早上第一件事做了什么？",
    },
    {
        "ko": "요즘 자주 가는 곳이 있어?",
        "en": "Is there a place you go often these days?",
        "ja": "最近よく行く場所はある？",
        "zh": "最近常去的地方是哪里？",
    },
    {
        "ko": "가족 중 한 명에 대해 써 볼까?",
        "en": "Write about someone in your family.",
        "ja": "家族の誰かについて書いてみよう。",
        "zh": "写一写你的一位家人。",
    },
    {
        "ko": "오늘 들은 소리 중에 기억나는 게 있어?",
        "en": "What sound do you remember hearing today?",
        "ja": "今日聞いた音で覚えているものは？",
        "zh": "今天听到的声音里记得哪个？",
    },
    {
        "ko": "좋아하는 음식을 만드는 방법을 써 볼까?",
        "en": "Write how to make a food you like.",
        "ja": "好きな食べ物の作り方を書いてみよう。",
        "zh": "写一写你喜欢的食物怎么做。",
    },
    {
        "ko": "오늘 기분을 날씨로 말하면 어때?",
        "en": "If today's mood were weather, what would it be?",
        "ja": "今日の気分を天気で言うと？",
        "zh": "如果今天的心情是天气，会是什么？",
    },
    {
        "ko": "가지고 싶은 것이 있어?",
        "en": "Is there something you want?",
        "ja": "ほしいものはある？",
        "zh": "有想要的东西吗？",
    },
    {
        "ko": "오늘 도와준 사람이 있어?",
        "en": "Did someone help you today?",
        "ja": "今日助けてくれた人はいる？",
        "zh": "今天有人帮助你吗？",
    },
    {
        "ko": "좋아하는 계절과 그 이유를 써 볼까?",
        "en": "Write about your favorite season and why.",
        "ja": "好きな季節とその理由を書いてみよう。",
        "zh": "写一写你喜欢的季节和原因。",
    },
    {
        "ko": "오늘 본 것 중 가장 예뻤던 건?",
        "en": "What was the prettiest thing you saw today?",
        "ja": "今日見た中でいちばんきれいだったものは？",
        "zh": "今天看到的最美的东西是什么？",
    },
    {
        "ko": "잘 하는 것에 대해 자랑해 볼까?",
        "en": "Brag about something you're good at.",
        "ja": "得意なことを自慢してみよう。",
        "zh": "夸一夸你擅长的事。",
    },
    {
        "ko": "오늘 걸어간 길을 떠올려 써 볼까?",
        "en": "Write about a road you walked today.",
        "ja": "今日歩いた道を思い出して書いてみよう。",
        "zh": "写一写你今天走过的路。",
    },
    {
        "ko": "친구에게 하고 싶은 말이 있어?",
        "en": "Is there something you want to tell a friend?",
        "ja": "友だちに言いたいことはある？",
        "zh": "有想对朋友说的话吗？",
    },
    {
        "ko": "요즘 읽거나 본 이야기가 있어?",
        "en": "Have you read or watched a story lately?",
        "ja": "最近読んだり見たりした話はある？",
        "zh": "最近读过或看过什么故事吗？",
    },
    {
        "ko": "오늘 하루를 색깔 하나로 칠한다면?",
        "en": "If you painted today in one color, which?",
        "ja": "今日一日を一色で塗るなら？",
        "zh": "如果用一种颜色涂今天，是哪种？",
    },
    {
        "ko": "잠들기 전에 하는 일이 있어?",
        "en": "Is there something you do before falling asleep?",
        "ja": "寝る前にすることはある？",
        "zh": "睡前会做什么吗？",
    },
]

FALLBACK_LANGUAGE = "ko"


def prompt_for(day: date, language: Optional[str] = None) -> str:
    """그 날짜의 글감을 돌려줘요.

    같은 날이면 몇 번을 물어도 같은 글감이 나와요 — 쓰는 중에 질문이
    바뀌면 당황스러우니까요. 30개라서 한 달에 한 바퀴 돌아요.
    """
    index = day.toordinal() % len(PROMPTS)
    entry = PROMPTS[index]
    return entry.get(language or FALLBACK_LANGUAGE) or entry[FALLBACK_LANGUAGE]
