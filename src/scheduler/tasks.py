"""
Celery タスク定義

自動投稿・メトリクス収集・分析の非同期タスク群。
"""
import asyncio
import logging
from datetime import datetime, timezone
from celery import Task
from src.scheduler.celery_app import celery_app

logger = logging.getLogger(__name__)


def run_async(coro):
    """Celeryタスク内でasyncioコルーチンを実行するヘルパー"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery_app.task(
    bind=True,
    name="src.scheduler.tasks.publish_post",
    max_retries=3,
    default_retry_delay=60,
)
def publish_post(self: Task, post_id: int) -> dict:
    """
    指定した投稿をThreadsに公開する

    Args:
        post_id: DBの投稿ID
    """
    async def _publish():
        from sqlalchemy import select
        from src.core.database import AsyncSessionLocal
        from src.models.post import Post, PostStatus
        from src.services.threads_client import ThreadsClient, ThreadsAPIError

        async with AsyncSessionLocal() as db:
            result = await db.execute(select(Post).where(Post.id == post_id))
            post = result.scalar_one_or_none()

            if not post:
                logger.error(f"Post {post_id} not found")
                return {"success": False, "error": "Post not found"}

            if post.status == PostStatus.PUBLISHED:
                logger.info(f"Post {post_id} already published")
                return {"success": True, "already_published": True}

            try:
                async with ThreadsClient() as client:
                    threads_id = await client.create_text_post(post.content)

                post.threads_post_id = threads_id
                post.status = PostStatus.PUBLISHED
                post.published_at = datetime.now(timezone.utc)
                await db.commit()

                logger.info(f"Post {post_id} published as Threads ID: {threads_id}")
                return {"success": True, "threads_post_id": threads_id}

            except ThreadsAPIError as e:
                post.status = PostStatus.FAILED
                post.error_message = str(e)
                await db.commit()

                logger.error(f"Failed to publish post {post_id}: {e}")
                raise self.retry(exc=e)

    return run_async(_publish())


@celery_app.task(
    name="src.scheduler.tasks.process_scheduled_posts",
)
def process_scheduled_posts() -> dict:
    """スケジュール済みで公開時刻を迎えた投稿を処理する"""
    async def _process():
        from sqlalchemy import select
        from src.core.database import AsyncSessionLocal
        from src.models.post import Post, PostStatus

        now = datetime.now(timezone.utc)
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(Post).where(
                    Post.status == PostStatus.SCHEDULED,
                    Post.scheduled_at <= now,
                )
            )
            due_posts = result.scalars().all()

            count = 0
            for post in due_posts:
                publish_post.delay(post.id)
                count += 1

            logger.info(f"Queued {count} scheduled posts for publishing")
            return {"queued": count}

    return run_async(_process())


@celery_app.task(
    name="src.scheduler.tasks.generate_ai_post",
)
def generate_ai_post(schedule_id: int) -> dict:
    """
    スケジュール設定からAI投稿を生成・公開する

    Args:
        schedule_id: PostSchedule ID
    """
    async def _generate():
        from sqlalchemy import select
        from src.core.database import AsyncSessionLocal
        from src.models.post import Post, PostSchedule, PostStatus, PostType
        from src.services.ai_generator import ContentGenerator
        from src.analytics.engine import AnalyticsEngine

        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(PostSchedule).where(PostSchedule.id == schedule_id)
            )
            schedule = result.scalar_one_or_none()

            if not schedule or not schedule.is_active:
                return {"success": False, "error": "Schedule not found or inactive"}

            # 分析データを取得
            analytics = AnalyticsEngine(db)
            my_stats = await analytics.get_my_performance_summary()
            competitor_data = await analytics.get_competitor_insights()

            # AI生成
            generator = ContentGenerator()
            generated = await generator.generate_optimized_post(
                topic=schedule.topic or "日常の気づきやインサイト",
                my_analytics=my_stats,
                competitor_analytics=competitor_data,
            )

            # 投稿レコード作成
            post = Post(
                content=generated["content"],
                status=PostStatus.SCHEDULED,
                post_type=PostType.AI_GENERATED,
                scheduled_at=datetime.now(timezone.utc),
                prompt_used=f"topic:{schedule.topic}",
                ai_model=generated.get("model", ""),
                topic=schedule.topic,
            )
            db.add(post)
            await db.commit()
            await db.refresh(post)

            # スケジュール更新
            schedule.last_run_at = datetime.now(timezone.utc)
            await db.commit()

            # 即時公開タスクをキュー
            publish_post.delay(post.id)

            logger.info(f"Generated and queued AI post {post.id} for schedule {schedule_id}")
            return {"success": True, "post_id": post.id, "content_preview": generated["content"][:50]}

    return run_async(_generate())


@celery_app.task(
    name="src.scheduler.tasks.collect_post_metrics",
)
def collect_post_metrics() -> dict:
    """公開済み投稿のエンゲージメント指標を収集する"""
    async def _collect():
        from sqlalchemy import select
        from datetime import timedelta
        from src.core.database import AsyncSessionLocal
        from src.models.post import Post, PostMetrics, PostStatus
        from src.services.threads_client import ThreadsClient

        cutoff = datetime.now(timezone.utc) - timedelta(days=30)
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(Post).where(
                    Post.status == PostStatus.PUBLISHED,
                    Post.threads_post_id.isnot(None),
                    Post.published_at >= cutoff,
                )
            )
            posts = result.scalars().all()

            collected = 0
            async with ThreadsClient() as client:
                for post in posts:
                    try:
                        insights = await client.get_post_insights(post.threads_post_id)
                        total_interactions = (
                            insights.get("likes", 0) +
                            insights.get("replies", 0) +
                            insights.get("reposts", 0)
                        )
                        views = insights.get("views", 1)
                        engagement_rate = total_interactions / views if views > 0 else 0

                        metrics = PostMetrics(
                            post_id=post.id,
                            likes=insights.get("likes", 0),
                            replies=insights.get("replies", 0),
                            reposts=insights.get("reposts", 0),
                            quotes=insights.get("quotes", 0),
                            views=views,
                            engagement_rate=engagement_rate,
                        )
                        db.add(metrics)
                        collected += 1
                    except Exception as e:
                        logger.warning(f"Failed to collect metrics for post {post.id}: {e}")

            await db.commit()
            logger.info(f"Collected metrics for {collected} posts")
            return {"collected": collected}

    return run_async(_collect())


@celery_app.task(
    name="src.scheduler.tasks.collect_tracked_thread_posts",
)
def collect_tracked_thread_posts() -> dict:
    """トラッキング対象スレッドの投稿を収集する"""
    async def _collect():
        from sqlalchemy import select
        from src.core.database import AsyncSessionLocal
        from src.models.post import TrackedThread, TrackedPost
        from src.services.threads_client import ThreadsClient

        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(TrackedThread).where(TrackedThread.is_active == True)
            )
            threads = result.scalars().all()

            total_collected = 0
            async with ThreadsClient() as client:
                for thread in threads:
                    try:
                        posts_data = await client.get_user_posts(
                            thread.threads_user_id, limit=25
                        )
                        posts = posts_data.get("data", [])

                        for p in posts:
                            # 既存チェック
                            existing = await db.execute(
                                select(TrackedPost).where(
                                    TrackedPost.threads_post_id == p["id"]
                                )
                            )
                            if existing.scalar_one_or_none():
                                continue

                            tracked_post = TrackedPost(
                                tracked_thread_id=thread.id,
                                threads_post_id=p["id"],
                                content=p.get("text", ""),
                                posted_at=datetime.fromisoformat(
                                    p.get("timestamp", datetime.utcnow().isoformat())
                                    .replace("Z", "+00:00")
                                ),
                                likes=p.get("likes_count", 0),
                                replies=p.get("replies_count", 0),
                            )
                            db.add(tracked_post)
                            total_collected += 1

                        thread.last_analyzed_at = datetime.now(timezone.utc)
                    except Exception as e:
                        logger.warning(
                            f"Failed to collect posts for thread {thread.username}: {e}"
                        )

            await db.commit()
            logger.info(f"Collected {total_collected} new posts from tracked threads")
            return {"collected": total_collected}

    return run_async(_collect())


@celery_app.task(
    name="src.scheduler.tasks.generate_weekly_report",
)
def generate_weekly_report() -> dict:
    """週次パフォーマンスレポートをAIで生成する"""
    async def _generate():
        from src.core.database import AsyncSessionLocal
        from src.analytics.engine import AnalyticsEngine
        from src.services.ai_generator import ContentGenerator

        async with AsyncSessionLocal() as db:
            analytics = AnalyticsEngine(db)
            weekly_stats = await analytics.get_weekly_stats()
            generator = ContentGenerator()

            report_prompt = f"""以下の週次データを元にパフォーマンスレポートを作成してください:
{weekly_stats}

レポートには以下を含めてください:
1. 今週のハイライト
2. 改善点
3. 来週の推奨アクション"""

            result = await generator.generate_post(
                topic="週次レポート",
                context=report_prompt,
                tone="analytical",
            )
            logger.info("Weekly report generated")
            return {"success": True, "report_preview": result.get("content", "")[:200]}

    return run_async(_generate())
