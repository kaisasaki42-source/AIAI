"""
分析エンジン

自分の投稿パフォーマンスと他スレッドの分析を行う。
AIによるインサイト生成もここで統合する。
"""
from datetime import datetime, timezone, timedelta
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from src.models.post import Post, PostMetrics, TrackedThread, TrackedPost, PostStatus


class AnalyticsEngine:
    """投稿分析エンジン"""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ──────────────────────────────────────────────
    # 自分の投稿分析
    # ──────────────────────────────────────────────

    async def get_my_performance_summary(self, days: int = 30) -> dict:
        """直近N日間のパフォーマンスサマリーを取得"""
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        # 投稿数
        post_count_result = await self.db.execute(
            select(func.count(Post.id)).where(
                Post.status == PostStatus.PUBLISHED,
                Post.published_at >= cutoff,
            )
        )
        total_posts = post_count_result.scalar() or 0

        # エンゲージメント集計
        metrics_result = await self.db.execute(
            select(
                func.avg(PostMetrics.likes).label("avg_likes"),
                func.avg(PostMetrics.replies).label("avg_replies"),
                func.avg(PostMetrics.reposts).label("avg_reposts"),
                func.avg(PostMetrics.views).label("avg_views"),
                func.avg(PostMetrics.engagement_rate).label("avg_engagement_rate"),
                func.max(PostMetrics.likes).label("max_likes"),
            ).join(Post).where(Post.published_at >= cutoff)
        )
        metrics = metrics_result.first()

        # 高エンゲージメント投稿のパターン
        top_posts_result = await self.db.execute(
            select(Post, PostMetrics)
            .join(PostMetrics)
            .where(Post.published_at >= cutoff)
            .order_by(desc(PostMetrics.engagement_rate))
            .limit(5)
        )
        top_posts = top_posts_result.all()

        top_patterns = []
        for post, m in top_posts:
            top_patterns.append({
                "content": post.content[:100],
                "topic": post.topic,
                "likes": m.likes,
                "engagement_rate": m.engagement_rate,
            })

        return {
            "period_days": days,
            "total_posts": total_posts,
            "avg_likes": float(metrics.avg_likes or 0),
            "avg_replies": float(metrics.avg_replies or 0),
            "avg_reposts": float(metrics.avg_reposts or 0),
            "avg_views": float(metrics.avg_views or 0),
            "avg_engagement_rate": float(metrics.avg_engagement_rate or 0),
            "max_likes": int(metrics.max_likes or 0),
            "top_posts": top_patterns,
            "top_post_patterns": self._extract_patterns(top_posts),
        }

    def _extract_patterns(self, top_posts: list) -> str:
        """上位投稿からパターンを抽出"""
        if not top_posts:
            return "データ不足"
        topics = [p.Post.topic for p, _ in top_posts if p.Post.topic]
        if topics:
            return f"高エンゲージメントトピック: {', '.join(set(topics))}"
        return "多様なトピックで均一なパフォーマンス"

    async def get_posts_by_topic(self, topic: str) -> list[dict]:
        """トピック別の投稿パフォーマンスを取得"""
        result = await self.db.execute(
            select(Post, PostMetrics)
            .join(PostMetrics, isouter=True)
            .where(
                Post.topic.ilike(f"%{topic}%"),
                Post.status == PostStatus.PUBLISHED,
            )
            .order_by(desc(Post.published_at))
            .limit(20)
        )
        rows = result.all()
        return [
            {
                "post_id": post.id,
                "content": post.content[:150],
                "published_at": post.published_at.isoformat() if post.published_at else None,
                "likes": metrics.likes if metrics else 0,
                "replies": metrics.replies if metrics else 0,
                "engagement_rate": metrics.engagement_rate if metrics else 0,
            }
            for post, metrics in rows
        ]

    async def get_engagement_trend(self, days: int = 14) -> list[dict]:
        """日別エンゲージメントトレンドを取得"""
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        result = await self.db.execute(
            select(
                func.date(PostMetrics.collected_at).label("date"),
                func.avg(PostMetrics.engagement_rate).label("avg_engagement"),
                func.sum(PostMetrics.likes).label("total_likes"),
                func.count(PostMetrics.id).label("post_count"),
            )
            .join(Post)
            .where(PostMetrics.collected_at >= cutoff)
            .group_by(func.date(PostMetrics.collected_at))
            .order_by(func.date(PostMetrics.collected_at))
        )
        rows = result.all()
        return [
            {
                "date": str(row.date),
                "avg_engagement_rate": float(row.avg_engagement or 0),
                "total_likes": int(row.total_likes or 0),
                "post_count": int(row.post_count or 0),
            }
            for row in rows
        ]

    async def get_weekly_stats(self) -> dict:
        """今週vs先週の比較統計"""
        now = datetime.now(timezone.utc)
        this_week_start = now - timedelta(days=7)
        last_week_start = now - timedelta(days=14)

        async def _get_period_stats(start, end):
            result = await self.db.execute(
                select(
                    func.count(Post.id).label("posts"),
                    func.avg(PostMetrics.likes).label("avg_likes"),
                    func.avg(PostMetrics.engagement_rate).label("avg_engagement"),
                )
                .join(PostMetrics, isouter=True)
                .where(
                    Post.published_at >= start,
                    Post.published_at < end,
                    Post.status == PostStatus.PUBLISHED,
                )
            )
            row = result.first()
            return {
                "posts": int(row.posts or 0),
                "avg_likes": float(row.avg_likes or 0),
                "avg_engagement": float(row.avg_engagement or 0),
            }

        this_week = await _get_period_stats(this_week_start, now)
        last_week = await _get_period_stats(last_week_start, this_week_start)

        def change_pct(current, previous):
            if previous == 0:
                return 0
            return ((current - previous) / previous) * 100

        return {
            "this_week": this_week,
            "last_week": last_week,
            "changes": {
                "posts_change_pct": change_pct(this_week["posts"], last_week["posts"]),
                "likes_change_pct": change_pct(this_week["avg_likes"], last_week["avg_likes"]),
                "engagement_change_pct": change_pct(
                    this_week["avg_engagement"], last_week["avg_engagement"]
                ),
            },
        }

    # ──────────────────────────────────────────────
    # 他スレッド分析
    # ──────────────────────────────────────────────

    async def get_competitor_insights(self, limit: int = 3) -> list[dict]:
        """トラッキング中の上位スレッドのインサイトを取得"""
        result = await self.db.execute(
            select(TrackedThread).where(TrackedThread.is_active == True).limit(limit)
        )
        threads = result.scalars().all()

        insights = []
        for thread in threads:
            posts_result = await self.db.execute(
                select(TrackedPost)
                .where(TrackedPost.tracked_thread_id == thread.id)
                .order_by(desc(TrackedPost.likes))
                .limit(10)
            )
            posts = posts_result.scalars().all()

            if not posts:
                continue

            avg_likes = sum(p.likes for p in posts) / len(posts)
            top_post = posts[0] if posts else None

            insights.append({
                "username": thread.username,
                "avg_likes": avg_likes,
                "top_post_content": top_post.content[:100] if top_post else "",
                "pattern": thread.track_reason or "分析対象",
                "post_count": len(posts),
            })

        return insights

    async def get_tracked_thread_analysis(self, thread_id: int) -> dict:
        """特定の追跡スレッドの詳細分析"""
        thread_result = await self.db.execute(
            select(TrackedThread).where(TrackedThread.id == thread_id)
        )
        thread = thread_result.scalar_one_or_none()
        if not thread:
            return {"error": "Thread not found"}

        posts_result = await self.db.execute(
            select(TrackedPost)
            .where(TrackedPost.tracked_thread_id == thread_id)
            .order_by(desc(TrackedPost.posted_at))
            .limit(50)
        )
        posts = posts_result.scalars().all()

        if not posts:
            return {"username": thread.username, "posts": [], "summary": "投稿データなし"}

        posts_for_ai = [
            {
                "content": p.content,
                "likes": p.likes,
                "replies": p.replies,
                "posted_at": p.posted_at.isoformat(),
            }
            for p in posts
        ]

        # AIによる分析
        from src.services.ai_generator import ContentGenerator
        generator = ContentGenerator()
        ai_analysis = await generator.analyze_competitor_posts(posts_for_ai)

        return {
            "username": thread.username,
            "display_name": thread.display_name,
            "total_posts_analyzed": len(posts),
            "avg_likes": sum(p.likes for p in posts) / len(posts),
            "avg_replies": sum(p.replies for p in posts) / len(posts),
            "ai_analysis": ai_analysis,
            "last_analyzed_at": thread.last_analyzed_at.isoformat() if thread.last_analyzed_at else None,
        }
