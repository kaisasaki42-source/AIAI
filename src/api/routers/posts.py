"""投稿管理 API ルーター"""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.core.database import get_db
from src.models.post import Post, PostStatus, PostType
from src.api.schemas import PostCreate, PostGenerateRequest, PostResponse
from src.services.ai_generator import ContentGenerator
from src.scheduler.tasks import publish_post

router = APIRouter()


@router.get("/", response_model=list[PostResponse])
async def list_posts(
    status: PostStatus = None,
    limit: int = 20,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    """投稿一覧を取得"""
    query = select(Post).order_by(Post.created_at.desc()).limit(limit).offset(offset)
    if status:
        query = query.where(Post.status == status)
    result = await db.execute(query)
    return result.scalars().all()


@router.post("/", response_model=PostResponse, status_code=201)
async def create_post(
    data: PostCreate,
    db: AsyncSession = Depends(get_db),
):
    """手動で投稿を作成する（スケジュールまたは即時）"""
    status = PostStatus.SCHEDULED if data.scheduled_at else PostStatus.DRAFT
    post = Post(
        content=data.content,
        topic=data.topic,
        status=status,
        post_type=PostType.MANUAL,
        scheduled_at=data.scheduled_at,
    )
    db.add(post)
    await db.commit()
    await db.refresh(post)
    return post


@router.post("/generate", status_code=201)
async def generate_and_post(
    data: PostGenerateRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Claude AIで投稿コンテンツを生成し、即時公開またはスケジュール登録する
    """
    generator = ContentGenerator()
    generated = await generator.generate_post(
        topic=data.topic,
        tone=data.tone,
    )

    if not generated.get("content"):
        raise HTTPException(status_code=500, detail="コンテンツ生成に失敗しました")

    status = PostStatus.DRAFT
    scheduled_at = None

    if data.publish_immediately:
        status = PostStatus.SCHEDULED
        scheduled_at = datetime.now(timezone.utc)
    elif data.scheduled_at:
        status = PostStatus.SCHEDULED
        scheduled_at = data.scheduled_at

    post = Post(
        content=generated["content"],
        topic=data.topic,
        status=status,
        post_type=PostType.AI_GENERATED,
        scheduled_at=scheduled_at,
        prompt_used=f"topic:{data.topic}, tone:{data.tone}",
        ai_model=generated.get("model", ""),
    )
    db.add(post)
    await db.commit()
    await db.refresh(post)

    if data.publish_immediately:
        publish_post.delay(post.id)

    return {
        "post": PostResponse.model_validate(post),
        "generated": generated,
        "queued_for_publish": data.publish_immediately,
    }


@router.post("/{post_id}/publish")
async def publish_now(post_id: int, db: AsyncSession = Depends(get_db)):
    """指定投稿を即時公開キューに入れる"""
    result = await db.execute(select(Post).where(Post.id == post_id))
    post = result.scalar_one_or_none()
    if not post:
        raise HTTPException(status_code=404, detail="投稿が見つかりません")
    if post.status == PostStatus.PUBLISHED:
        raise HTTPException(status_code=400, detail="既に公開済みです")

    post.status = PostStatus.SCHEDULED
    post.scheduled_at = datetime.now(timezone.utc)
    await db.commit()

    publish_post.delay(post.id)
    return {"message": "公開キューに追加しました", "post_id": post_id}


@router.delete("/{post_id}", status_code=204)
async def delete_post(post_id: int, db: AsyncSession = Depends(get_db)):
    """投稿を削除する（未公開のみ）"""
    result = await db.execute(select(Post).where(Post.id == post_id))
    post = result.scalar_one_or_none()
    if not post:
        raise HTTPException(status_code=404, detail="投稿が見つかりません")
    if post.status == PostStatus.PUBLISHED:
        raise HTTPException(status_code=400, detail="公開済み投稿は削除できません")
    await db.delete(post)
    await db.commit()
