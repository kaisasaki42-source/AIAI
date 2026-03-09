"""
投稿スケジューラーモジュール
- AIコンテンツ自動生成 + 投稿
- 手動入力済みコンテンツのスケジュール投稿
"""
import os
import json
import logging
from datetime import datetime
from pathlib import Path

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from src.poster import post_tweet
from src.generator import generate_post

logger = logging.getLogger(__name__)

QUEUE_FILE = Path("posts_queue.json")
SENT_FILE = Path("posts_sent.json")


# ── キューファイル操作 ─────────────────────────────────────

def load_queue() -> list[dict]:
    """posts_queue.json から未送信の投稿リストを読み込む"""
    if not QUEUE_FILE.exists():
        return []
    with open(QUEUE_FILE, encoding="utf-8") as f:
        return json.load(f)


def save_queue(posts: list[dict]) -> None:
    with open(QUEUE_FILE, "w", encoding="utf-8") as f:
        json.dump(posts, f, ensure_ascii=False, indent=2)


def record_sent(post: dict, result: dict) -> None:
    """送信済み投稿を posts_sent.json に記録する"""
    sent = []
    if SENT_FILE.exists():
        with open(SENT_FILE, encoding="utf-8") as f:
            sent = json.load(f)
    sent.append({**post, "sent_at": datetime.now().isoformat(), "result": result})
    with open(SENT_FILE, "w", encoding="utf-8") as f:
        json.dump(sent, f, ensure_ascii=False, indent=2)


# ── ジョブ関数 ────────────────────────────────────────────

def job_post_from_queue(dry_run: bool = False) -> None:
    """
    キュー先頭の投稿をXに投稿する。
    キューが空の場合は AI でコンテンツを自動生成する。
    """
    dry_run = dry_run or os.getenv("DRY_RUN", "false").lower() == "true"
    posts = load_queue()

    if posts:
        post = posts.pop(0)
        text = post["text"]
        source = "queue"
    else:
        topic = os.getenv("POST_TOPIC", "テクノロジーとAIの最新情報")
        logger.info(f"キューが空のため AI でコンテンツを生成します。テーマ: {topic}")
        text = generate_post(topic)
        post = {"text": text}
        source = "ai_generated"

    logger.info(f"[{source}] 投稿開始: {text[:50]}...")
    result = post_tweet(text, dry_run=dry_run)

    if result["success"]:
        record_sent(post, result)
        if source == "queue":
            save_queue(posts)
        logger.info("投稿成功!")
    else:
        logger.error("投稿失敗。キューは変更しません。")


# ── スケジューラー起動 ────────────────────────────────────

def start_scheduler() -> None:
    """
    環境変数 POST_SCHEDULE (cron形式) に従ってスケジューラーを起動する。
    例: "0 9,18 * * *" = 毎日 9:00 と 18:00 に投稿
    """
    schedule = os.getenv("POST_SCHEDULE", "0 9,18 * * *")
    timezone = os.getenv("TIMEZONE", "Asia/Tokyo")

    scheduler = BlockingScheduler(timezone=timezone)
    scheduler.add_job(
        job_post_from_queue,
        CronTrigger.from_crontab(schedule, timezone=timezone),
        id="x_auto_post",
        name="X自動投稿",
        replace_existing=True,
    )

    next_run = scheduler.get_job("x_auto_post").next_run_time
    logger.info(f"スケジューラー起動 | スケジュール: {schedule} | 次回実行: {next_run}")
    logger.info("Ctrl+C で停止します")

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("スケジューラーを停止しました")
