import datetime
import os
from typing import Optional

import jwt
import requests as http
from fastapi import APIRouter, Header, HTTPException, status
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

# ⚠️ 실제 서비스 시에는 .env 같은 환경 변수 파일로 관리하시는 것이 안전합니다!
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
JWT_SECRET = os.getenv(
    "JWT_SECRET", "default-fallback-secret-key"
)  # 없을 때를 대비한 기본값 설정 가능
JWT_ALGORITHM = "HS256"

if not GOOGLE_CLIENT_ID:
    raise RuntimeError(
        "환경 변수에 GOOGLE_CLIENT_ID가 설정되지 않았습니다. .env 파일을 확인해주세요, 누나!"
    )


class TokenRequest(BaseModel):
    """로그인 요청. 둘 중 하나만 오면 돼요.

    token        : 구글 ID 토큰 — 구글이 그려주는 기본 버튼이 주는 것 (기존 방식)
    access_token : 구글 액세스 토큰 — 커스텀 버튼(useGoogleLogin)이 주는 것

    둘 다 지원하는 이유: 프론트를 배포하는 동안 잠깐 두 버전이 섞여 돌아요.
    옛 화면을 열어둔 사람이 로그인해도 안 깨지게 하려고요.
    """

    token: Optional[str] = None
    access_token: Optional[str] = None


def create_access_token(data: dict, expires_delta: datetime.timedelta = None):
    """우리 서비스 전용 JWT 토큰 생성"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.datetime.utcnow() + expires_delta
    else:
        expire = datetime.datetime.utcnow() + datetime.timedelta(days=7)  # 7일 유효
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)


def get_current_user_email(authorization: str = Header(None)) -> str:
    """요청 헤더의 JWT를 검증하고 사용자 이메일을 돌려주는 '문지기' 함수.

    다른 API에서 Depends(get_current_user_email)로 붙이면
    로그인한 사람만 통과할 수 있어요.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="로그인이 필요해요")
    token = authorization.split(" ", 1)[1]
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=401, detail="로그인이 만료됐어요. 다시 로그인해주세요"
        )
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="유효하지 않은 토큰이에요")
    return payload["sub"]


GOOGLE_TOKENINFO_URL = "https://oauth2.googleapis.com/tokeninfo"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"


def google_user_from_access_token(access_token: str) -> dict:
    """구글 액세스 토큰을 확인하고 사용자 정보를 돌려줘요.

    🛡️ 제일 중요한 건 **aud 검사**예요.
    액세스 토큰은 "누가 발급받았는지"가 토큰 안에 안 적혀 있어요. 그래서
    확인 없이 쓰면, 공격자가 **자기 앱에서 발급받은 남의 토큰**을 우리한테
    보내서 그 사람으로 로그인할 수 있어요 (혼동된 대리자 문제).

    구글의 tokeninfo 가 알려주는 aud(이 토큰을 발급받은 앱)가 우리 앱인지
    반드시 확인해야 해요.
    """
    try:
        res = http.get(
            GOOGLE_TOKENINFO_URL, params={"access_token": access_token}, timeout=10
        )
    except http.RequestException as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"구글에 연결하지 못했어요: {e!s}",
        ) from e

    if res.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="유효하지 않은 구글 토큰이에요",
        )

    info = res.json()

    # 🛡️ 우리 앱이 발급받은 토큰이 맞나? — 이 검사를 빼면 안 돼요
    if info.get("aud") != GOOGLE_CLIENT_ID:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="다른 앱에서 발급된 토큰이에요",
        )

    # 이름·프로필 사진은 tokeninfo 에 없어서 따로 물어봐요
    profile = {}
    try:
        pres = http.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=10,
        )
        if pres.status_code == 200:
            profile = pres.json()
    except http.RequestException:
        pass  # 이름·사진은 없어도 로그인은 되게 해요

    email = info.get("email") or profile.get("email")
    if not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="구글 계정에서 이메일을 가져오지 못했어요",
        )

    return {
        "email": email,
        "name": profile.get("name"),
        "picture": profile.get("picture"),
    }


@router.post("/google")
async def google_login(payload: TokenRequest):
    """구글 로그인 → 우리 서비스 JWT 발급.

    ID 토큰(기본 버튼)과 액세스 토큰(커스텀 버튼) 둘 다 받아요.
    """
    if payload.access_token:
        # 커스텀 버튼(useGoogleLogin)이 주는 액세스 토큰
        user = google_user_from_access_token(payload.access_token)
    elif payload.token:
        # 구글 기본 버튼이 주는 ID 토큰 (기존 방식)
        try:
            id_info = id_token.verify_oauth2_token(
                payload.token, google_requests.Request(), GOOGLE_CLIENT_ID
            )
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"유효하지 않은 구글 토큰입니다: {e!s}",
            ) from e
        user = {
            "email": id_info.get("email"),
            "name": id_info.get("name"),
            "picture": id_info.get("picture"),
        }
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="token 또는 access_token 이 필요해요",
        )

    # 우리 서비스 전용 JWT 발급 (7일)
    our_token = create_access_token(data={"sub": user["email"], "name": user["name"]})

    return {
        "access_token": our_token,
        "token_type": "bearer",
        "user": user,
    }
