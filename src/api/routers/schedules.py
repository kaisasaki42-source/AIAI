"""スケジュール管理 API ルーター"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.core.database import get_db
from src.models.post import PostSchedule
from src.api.schemas import ScheduleCreate, ScheduleResponse
from src.scheduler.tasks import generate_ai_post

router = APIRouter()


@router.get("/", response_model=list[ScheduleResponse])
async def list_schedules(db: AsyncSession = Depends(get_db)):
    """スケジュール一覧を取得"""
    result = await db.execute(
        select(PostSchedule).order_by(PostSchedule.created_at.desc())
    )
    return result.scalars().all()


@router.post("/", response_model=ScheduleResponse, status_code=201)
async def create_schedule(data: ScheduleCreate, db: AsyncSession = Depends(get_db)):
    """
    定期投稿スケジュールを作成する

    cron_expression 例:
    - "0 9 * * *"  → 毎日9時
    - "0 9,18 * * *" → 毎日9時・18時
    - "0 9 * * 1-5" → 平日9時
    """
    schedule = PostSchedule(
        name=data.name,
        cron_expression=data.cron_expression,
        topic=data.topic,
        use_ai_generation=data.use_ai_generation,
    )
    db.add(schedule)
    await db.commit()
    await db.refresh(schedule)
    return schedule


@router.patch("/{schedule_id}/toggle", response_model=ScheduleResponse)
async def toggle_schedule(schedule_id: int, db: AsyncSession = Depends(get_db)):
    """スケジュールの有効/無効を切り替える"""
    result = await db.execute(
        select(PostSchedule).where(PostSchedule.id == schedule_id)
    )
    schedule = result.scalar_one_or_none()
    if not schedule:
        raise HTTPException(status_code=404, detail="スケジュールが見つかりません")
    schedule.is_active = not schedule.is_active
    await db.commit()
    await db.refresh(schedule)
    return schedule


@router.post("/{schedule_id}/run-now")
async def run_schedule_now(schedule_id: int, db: AsyncSession = Depends(get_db)):
    """スケジュールを今すぐ手動実行する"""
    result = await db.execute(
        select(PostSchedule).where(PostSchedule.id == schedule_id)
    )
    schedule = result.scalar_one_or_none()
    if not schedule:
        raise HTTPException(status_code=404, detail="スケジュールが見つかりません")

    task = generate_ai_post.delay(schedule_id)
    return {"message": "投稿生成タスクをキューに追加しました", "task_id": task.id}


@router.delete("/{schedule_id}", status_code=204)
async def delete_schedule(schedule_id: int, db: AsyncSession = Depends(get_db)):
    """スケジュールを削除する"""
    result = await db.execute(
        select(PostSchedule).where(PostSchedule.id == schedule_id)
    )
    schedule = result.scalar_one_or_none()
    if not schedule:
        raise HTTPException(status_code=404, detail="スケジュールが見つかりません")
    await db.delete(schedule)
    await db.commit()
