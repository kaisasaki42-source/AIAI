"""
X自動投稿スケジューラー エントリーポイント

使い方:
  # スケジューラーとして常時起動（.envのPOST_SCHEDULEに従って自動投稿）
  python main.py

  # 今すぐ1回だけテスト投稿（実際には投稿しないドライラン）
  python main.py --now --dry-run

  # 今すぐ1回だけ実際に投稿
  python main.py --now
"""
import argparse
import logging
import os
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

from src.scheduler import start_scheduler, job_post_from_queue


def main() -> None:
    parser = argparse.ArgumentParser(description="X自動投稿スケジューラー")
    parser.add_argument(
        "--now",
        action="store_true",
        help="スケジューラーを起動せず今すぐ1回だけ投稿する",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="実際には投稿せず内容だけ確認する",
    )
    args = parser.parse_args()

    if args.now:
        job_post_from_queue(dry_run=args.dry_run)
    else:
        start_scheduler()


if __name__ == "__main__":
    main()
