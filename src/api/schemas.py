"""Pydantic スキーマ定義"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field
from src.models.post import PostStatus, PostType


# ─── 投稿 ───────────────────────────────────────

class PostCreate(BaseModel):
    content: str = Field(..., max_length=500)
    topic: Optional[str] = None
    scheduled_at: Optional[datetime] = None


class PostGenerateRequest(BaseModel):
    topic: str = Field(..., description="投稿のテーマ")
    tone: str = Field("informative", description="トーン: informative/casual/inspiring")
    publish_immediately: bool = Field(False, description="生成後すぐに公開するか")
    scheduled_at: Optional[datetime] = Field(None, description="スケジュール公開日時")


class PostResponse(BaseModel):
    id: int
    content: str
    status: PostStatus
    post_type: PostType
    threads_post_id: Optional[str]
    threads_permalink: Optional[str]
    scheduled_at: Optional[datetime]
    published_at: Optional[datetime]
    topic: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


# ─── スケジュール ─────────────────────────────────

class ScheduleCreate(BaseModel):
    name: str
    cron_expression: str = Field(..., description="Cron式 例: '0 9 * * *'")
    topic: Optional[str] = None
    use_ai_generation: bool = True


class ScheduleResponse(BaseModel):
    id: int
    name: str
    cron_expression: str
    topic: Optional[str]
    is_active: bool
    use_ai_generation: bool
    last_run_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


# ─── トラッキング ─────────────────────────────────

class TrackedThreadCreate(BaseModel):
    username: str = Field(..., description="ThreadsのユーザーID or ユーザー名")
    track_reason: Optional[str] = Field(None, description="追跡理由（例: 競合他社、参考アカウント）")


class TrackedThreadResponse(BaseModel):
    id: int
    threads_user_id: str
    username: str
    display_name: Optional[str]
    is_active: bool
    track_reason: Optional[str]
    last_analyzed_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


# ─── 分析 ─────────────────────────────────────────

class AnalyticsSummaryResponse(BaseModel):
    period_days: int
    total_posts: int
    avg_likes: float
    avg_replies: float
    avg_views: float
    avg_engagement_rate: float
    max_likes: int
    top_posts: list[dict]


class TrendResponse(BaseModel):
    data: list[dict]


class WeeklyReportResponse(BaseModel):
    this_week: dict
    last_week: dict
    changes: dict
