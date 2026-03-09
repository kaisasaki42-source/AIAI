"""
X (Twitter) への投稿モジュール
"""
import os
import logging
import tweepy

logger = logging.getLogger(__name__)


def get_x_client() -> tweepy.Client:
    """X API v2 クライアントを取得する"""
    client = tweepy.Client(
        bearer_token=os.environ["X_BEARER_TOKEN"],
        consumer_key=os.environ["X_API_KEY"],
        consumer_secret=os.environ["X_API_SECRET"],
        access_token=os.environ["X_ACCESS_TOKEN"],
        access_token_secret=os.environ["X_ACCESS_TOKEN_SECRET"],
    )
    return client


def post_tweet(text: str, dry_run: bool = False) -> dict:
    """
    Xにツイートを投稿する

    Args:
        text: 投稿テキスト（280文字以内）
        dry_run: Trueの場合、実際には投稿せずログだけ出力

    Returns:
        投稿結果の辞書 {"success": bool, "tweet_id": str|None, "text": str}
    """
    if len(text) > 280:
        logger.warning("テキストが280文字を超えています。切り詰めます。")
        text = text[:277] + "..."

    if dry_run:
        logger.info(f"[DRY RUN] 投稿内容:\n{text}")
        return {"success": True, "tweet_id": None, "text": text}

    try:
        client = get_x_client()
        response = client.create_tweet(text=text)
        tweet_id = response.data["id"]
        logger.info(f"投稿成功! Tweet ID: {tweet_id}")
        return {"success": True, "tweet_id": tweet_id, "text": text}
    except tweepy.TweepyException as e:
        logger.error(f"投稿失敗: {e}")
        return {"success": False, "tweet_id": None, "text": text}
