"""하루가 바뀌는 기준 = 한국 시간 자정 (D-15).

배포 서버도 DB도 UTC로 돌아가요. 그냥 두면
  - 파이썬 date.today() 는 한국 아침 9시 전까지 "어제"라고 하고
  - DB 의 NOW() 는 파이썬이 넣은 시각보다 9시간 이르게 찍혀요
그래서 시각을 만드는 곳은 전부 여기 하나를 거쳐 가게 했어요.
"""

from datetime import date, datetime
from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")


def today_kst() -> date:
    """오늘이 며칠인지 — 한국 시간 기준"""
    return datetime.now(KST).date()


def now_kst() -> datetime:
    """지금 몇 시인지 — 한국 시간 기준.

    DB 컬럼이 시간대 없는 DateTime 이라 tzinfo 는 떼고 넣어요.
    """
    return datetime.now(KST).replace(tzinfo=None)
