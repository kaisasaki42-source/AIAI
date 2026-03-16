"""分析 API ルーター"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from src.core.database import get_db
from src.analytics.engine import AnalyticsEngine

router = APIRouter()


@router.get("/summary")
async def get_analytics_summary(
    days: int = 30,
    db: AsyncSession = Depends(get_db),
):
    """直近N日間のパフォーマンスサマリー"""
    engine = AnalyticsEngine(db)
    return await engine.get_my_performance_summary(days=days)


@router.get("/trend")
async def get_engagement_trend(
    days: int = 14,
    db: AsyncSession = Depends(get_db),
):
    """エンゲージメントトレンド（日別）"""
    engine = AnalyticsEngine(db)
    data = await engine.get_engagement_trend(days=days)
    return {"data": data}


@router.get("/weekly-report")
async def get_weekly_report(db: AsyncSession = Depends(get_db)):
    """今週vs先週の比較レポート"""
    engine = AnalyticsEngine(db)
    return await engine.get_weekly_stats()


@router.get("/topic/{topic}")
async def get_topic_analytics(topic: str, db: AsyncSession = Depends(get_db)):
    """トピック別パフォーマンス分析"""
    engine = AnalyticsEngine(db)
    posts = await engine.get_posts_by_topic(topic)
    return {"topic": topic, "posts": posts, "count": len(posts)}
