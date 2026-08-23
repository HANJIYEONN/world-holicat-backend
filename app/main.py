import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .database import Base, engine
from .routers import auth, cat_note, entries, favorites

app = FastAPI(title="두통 기록 차트 API")

# 로컬 개발 주소 + 배포된 Vercel 주소(FRONTEND_URL 환경변수)를 함께 허용해요
allowed_origins = ["http://localhost:3000"]
if frontend_url := os.getenv("FRONTEND_URL"):
    allowed_origins.append(frontend_url)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(entries.router)

app.include_router(auth.router)

app.include_router(favorites.router)

app.include_router(cat_note.router)


@app.on_event("startup")
def on_startup() -> None:
    Base.metadata.create_all(bind=engine)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
