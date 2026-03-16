"""他スレッド追跡・分析 API ルーター"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.core.database import get_db
from src.models.post import TrackedThread
from src.api.schemas import TrackedThreadCreate, TrackedThreadResponse
from src.analytics.engine import AnalyticsEngine
from src.services.threads_client import ThreadsClient, ThreadsAPIError
from src.scheduler.tasks import collect_tracked_thread_posts

router = APIRouter()


@router.get("/", response_model=list[TrackedThreadResponse])
async def list_tracked_threads(db: AsyncSession = Depends(get_db)):
    """追跡中のスレッド一覧"""
    result = await db.execute(select(TrackedThread).order_by(TrackedThread.created_at.desc()))
    return result.scalars().all()


@router.post("/", response_model=TrackedThreadResponse, status_code=201)
async def add_tracked_thread(
    data: TrackedThreadCreate,
    db: AsyncSession = Depends(get_db),
):
    """
    追跡するスレッドアカウントを追加する。
    Threads APIでユーザー情報を取得して登録する。
    """
    try:
        async with ThreadsClient() as client:
            user_info = await client.get_user_by_username(data.username)
    except ThreadsAPIError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Threadsユーザーの取得に失敗しました: {e}",
        )

    # 重複チェック
    existing = await db.execute(
        select(TrackedThread).where(TrackedThread.threads_user_id == user_info["id"])
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="既に追跡中のアカウントです")

    thread = TrackedThread(
        threads_user_id=user_info["id"],
        username=user_info.get("username", data.username),
        display_name=user_info.get("name"),
        track_reason=data.track_reason,
    )
    db.add(thread)
    await db.commit()
    await db.refresh(thread)

    # 即時にデータ収集を開始
    collect_tracked_thread_posts.delay()

    return thread


@router.get("/{thread_id}/analysis")
async def get_thread_analysis(thread_id: int, db: AsyncSession = Depends(get_db)):
    """
    追跡スレッドの詳細AI分析レポートを取得する。
    高エンゲージメント投稿のパターンや戦略をAIが分析。
    """
    engine = AnalyticsEngine(db)
    return await engine.get_tracked_thread_analysis(thread_id)


@router.post("/{thread_id}/refresh")
async def refresh_thread_data(thread_id: int, db: AsyncSession = Depends(get_db)):
    """指定スレッドのデータを今すぐ更新する"""
    result = await db.execute(select(TrackedThread).where(TrackedThread.id == thread_id))
    thread = result.scalar_one_or_none()
    if not thread:
        raise HTTPException(status_code=404, detail="スレッドが見つかりません")

    task = collect_tracked_thread_posts.delay()
    return {"message": "データ収集タスクをキューに追加しました", "task_id": task.id}


@router.delete("/{thread_id}", status_code=204)
async def remove_tracked_thread(thread_id: int, db: AsyncSession = Depends(get_db)):
    """追跡スレッドを削除する"""
    result = await db.execute(select(TrackedThread).where(TrackedThread.id == thread_id))
    thread = result.scalar_one_or_none()
    if not thread:
        raise HTTPException(status_code=404, detail="スレッドが見つかりません")
    await db.delete(thread)
    await db.commit()
