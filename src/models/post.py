from datetime import datetime
from enum import Enum
from sqlalchemy import String, Text, Integer, DateTime, Float, Boolean, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.core.database import Base


class PostStatus(str, Enum):
    DRAFT = "draft"
    SCHEDULED = "scheduled"
    PUBLISHED = "published"
    FAILED = "failed"


class PostType(str, Enum):
    AI_GENERATED = "ai_generated"
    MANUAL = "manual"
    TEMPLATE = "template"


class Post(Base):
    """自動投稿管理テーブル"""
    __tablename__ = "posts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[PostStatus] = mapped_column(String(20), default=PostStatus.DRAFT)
    post_type: Mapped[PostType] = mapped_column(String(20), default=PostType.AI_GENERATED)

    # Threads連携
    threads_post_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    threads_permalink: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # スケジュール
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # AI生成メタ情報
    prompt_used: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_model: Mapped[str | None] = mapped_column(String(50), nullable=True)
    topic: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # エラー情報
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # リレーション
    metrics: Mapped[list["PostMetrics"]] = relationship("PostMetrics", back_populates="post")


class PostMetrics(Base):
    """投稿エンゲージメント指標テーブル"""
    __tablename__ = "post_metrics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    post_id: Mapped[int] = mapped_column(Integer, ForeignKey("posts.id"), nullable=False)

    likes: Mapped[int] = mapped_column(Integer, default=0)
    replies: Mapped[int] = mapped_column(Integer, default=0)
    reposts: Mapped[int] = mapped_column(Integer, default=0)
    quotes: Mapped[int] = mapped_column(Integer, default=0)
    views: Mapped[int] = mapped_column(Integer, default=0)

    engagement_rate: Mapped[float] = mapped_column(Float, default=0.0)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    post: Mapped["Post"] = relationship("Post", back_populates="metrics")


class TrackedThread(Base):
    """分析対象の他スレッド管理テーブル"""
    __tablename__ = "tracked_threads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    threads_user_id: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    username: Mapped[str] = mapped_column(String(100), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    track_reason: Mapped[str | None] = mapped_column(String(200), nullable=True)

    last_analyzed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    posts: Mapped[list["TrackedPost"]] = relationship("TrackedPost", back_populates="tracked_thread")


class TrackedPost(Base):
    """分析対象スレッドの投稿データテーブル"""
    __tablename__ = "tracked_posts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tracked_thread_id: Mapped[int] = mapped_column(Integer, ForeignKey("tracked_threads.id"), nullable=False)
    threads_post_id: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    posted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    likes: Mapped[int] = mapped_column(Integer, default=0)
    replies: Mapped[int] = mapped_column(Integer, default=0)
    reposts: Mapped[int] = mapped_column(Integer, default=0)
    quotes: Mapped[int] = mapped_column(Integer, default=0)
    views: Mapped[int] = mapped_column(Integer, default=0)

    # Claude分析結果
    ai_analysis: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    analyzed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    tracked_thread: Mapped["TrackedThread"] = relationship("TrackedThread", back_populates="posts")


class PostTemplate(Base):
    """投稿テンプレートテーブル"""
    __tablename__ = "post_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    template: Mapped[str] = mapped_column(Text, nullable=False)
    topic: Mapped[str | None] = mapped_column(String(200), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    use_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class PostSchedule(Base):
    """投稿スケジュール設定テーブル"""
    __tablename__ = "post_schedules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    cron_expression: Mapped[str] = mapped_column(String(100), nullable=False)
    topic: Mapped[str | None] = mapped_column(String(200), nullable=True)
    template_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("post_templates.id"), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    use_ai_generation: Mapped[bool] = mapped_column(Boolean, default=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
