"""
Celery アプリケーション設定

自動投稿・分析収集のタスクキューと定期実行を管理する。
"""
from celery import Celery
from celery.schedules import crontab
from src.core.config import settings

celery_app = Celery(
    "aiai",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["src.scheduler.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Tokyo",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)

# 定期タスク設定
celery_app.conf.beat_schedule = {
    # 毎時間: 公開済み投稿のメトリクスを収集
    "collect-post-metrics-hourly": {
        "task": "src.scheduler.tasks.collect_post_metrics",
        "schedule": crontab(minute=0),  # 毎時0分
    },
    # 1日2回: トラッキング対象スレッドの投稿を収集
    "collect-tracked-threads-twice-daily": {
        "task": "src.scheduler.tasks.collect_tracked_thread_posts",
        "schedule": crontab(hour="9,21", minute=0),  # 9時・21時
    },
    # 毎日深夜: スケジュール済み投稿を実行
    "process-scheduled-posts": {
        "task": "src.scheduler.tasks.process_scheduled_posts",
        "schedule": crontab(minute="*/5"),  # 5分毎にチェック
    },
    # 毎週月曜: 週次分析レポート生成
    "weekly-analytics-report": {
        "task": "src.scheduler.tasks.generate_weekly_report",
        "schedule": crontab(hour=8, minute=0, day_of_week=1),  # 月曜8時
    },
}
