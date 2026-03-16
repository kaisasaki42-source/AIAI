"""
AIAI - FastAPI メインアプリ

自動投稿ツールのREST APIサーバー。
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.core.database import init_db
from src.api.routers import posts, schedules, analytics, tracked_threads


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(
    title="AIAI - Auto Posting & Analytics",
    description="Meta Threads 自動投稿・分析ツール (Powered by Claude AI)",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(posts.router, prefix="/api/posts", tags=["投稿管理"])
app.include_router(schedules.router, prefix="/api/schedules", tags=["スケジュール"])
app.include_router(analytics.router, prefix="/api/analytics", tags=["分析"])
app.include_router(tracked_threads.router, prefix="/api/tracked-threads", tags=["スレッド追跡"])


@app.get("/health")
async def health():
    return {"status": "ok", "service": "AIAI"}
