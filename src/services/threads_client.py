"""
Meta Threads API クライアント

Threads API (Instagram Graph API経由) のラッパー。
投稿作成、メディアコンテナ管理、分析データ取得を担当。
"""
import httpx
from datetime import datetime
from tenacity import retry, stop_after_attempt, wait_exponential
from src.core.config import settings


THREADS_API_BASE = "https://graph.threads.net/v1.0"


class ThreadsAPIError(Exception):
    def __init__(self, message: str, status_code: int = 0, response: dict = None):
        super().__init__(message)
        self.status_code = status_code
        self.response = response or {}


class ThreadsClient:
    """Meta Threads API クライアント"""

    def __init__(
        self,
        access_token: str = None,
        user_id: str = None,
    ):
        self.access_token = access_token or settings.threads_access_token
        self.user_id = user_id or settings.threads_user_id
        self._client = httpx.AsyncClient(timeout=30.0)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self._client.aclose()

    def _params(self, **kwargs) -> dict:
        return {"access_token": self.access_token, **kwargs}

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def _get(self, path: str, **params) -> dict:
        url = f"{THREADS_API_BASE}/{path}"
        resp = await self._client.get(url, params=self._params(**params))
        if resp.status_code != 200:
            raise ThreadsAPIError(
                f"GET {path} failed: {resp.text}",
                status_code=resp.status_code,
                response=resp.json() if resp.content else {},
            )
        return resp.json()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def _post(self, path: str, **data) -> dict:
        url = f"{THREADS_API_BASE}/{path}"
        resp = await self._client.post(url, params=self._params(**data))
        if resp.status_code != 200:
            raise ThreadsAPIError(
                f"POST {path} failed: {resp.text}",
                status_code=resp.status_code,
                response=resp.json() if resp.content else {},
            )
        return resp.json()

    # ──────────────────────────────────────────────
    # 投稿系
    # ──────────────────────────────────────────────

    async def create_text_post(self, text: str) -> str:
        """テキスト投稿を作成してスレッドIDを返す"""
        # Step 1: メディアコンテナ作成
        container = await self._post(
            f"{self.user_id}/threads",
            media_type="TEXT",
            text=text,
        )
        container_id = container["id"]

        # Step 2: 公開
        result = await self._post(
            f"{self.user_id}/threads_publish",
            creation_id=container_id,
        )
        return result["id"]

    async def reply_to_post(self, post_id: str, text: str) -> str:
        """投稿にリプライする"""
        container = await self._post(
            f"{self.user_id}/threads",
            media_type="TEXT",
            text=text,
            reply_to_id=post_id,
        )
        result = await self._post(
            f"{self.user_id}/threads_publish",
            creation_id=container["id"],
        )
        return result["id"]

    # ──────────────────────────────────────────────
    # 自分の投稿分析
    # ──────────────────────────────────────────────

    async def get_my_posts(self, limit: int = 25, after: str = None) -> dict:
        """自分の投稿一覧を取得"""
        params = {
            "fields": "id,text,timestamp,media_type,permalink",
            "limit": limit,
        }
        if after:
            params["after"] = after
        return await self._get(f"{self.user_id}/threads", **params)

    async def get_post_insights(self, post_id: str) -> dict:
        """投稿のエンゲージメント指標を取得"""
        data = await self._get(
            f"{post_id}/insights",
            metric="views,likes,replies,reposts,quotes",
        )
        result = {}
        for item in data.get("data", []):
            result[item["name"]] = item.get("values", [{}])[-1].get("value", 0)
        return result

    async def get_my_account_insights(self) -> dict:
        """アカウント全体のインサイトを取得"""
        return await self._get(
            f"{self.user_id}/threads_insights",
            metric="views,likes,replies,reposts,quotes,followers_count",
            period="day",
        )

    # ──────────────────────────────────────────────
    # 他スレッド分析
    # ──────────────────────────────────────────────

    async def get_user_by_username(self, username: str) -> dict:
        """ユーザー名でThreadsユーザー情報を取得"""
        return await self._get(
            "threads_user_by_username",
            username=username,
            fields="id,username,name,threads_profile_picture_url,threads_biography",
        )

    async def get_user_posts(self, user_id: str, limit: int = 25) -> dict:
        """指定ユーザーの投稿一覧を取得"""
        return await self._get(
            f"{user_id}/threads",
            fields="id,text,timestamp,media_type,permalink,likes_count,replies_count",
            limit=limit,
        )

    async def get_post_replies(self, post_id: str) -> dict:
        """投稿のリプライ一覧を取得"""
        return await self._get(
            f"{post_id}/replies",
            fields="id,text,timestamp,username",
        )

    async def get_post_detail(self, post_id: str) -> dict:
        """投稿の詳細を取得"""
        return await self._get(
            post_id,
            fields="id,text,timestamp,media_type,permalink,owner",
        )

    async def search_posts(self, query: str, limit: int = 20) -> list[dict]:
        """
        Threads APIには全文検索がないため、
        トレンドハッシュタグ経由で投稿を収集する簡易実装。
        本番では追加のサードパーティAPIとの組み合わせを推奨。
        """
        # Threads公式APIの制約上、ハッシュタグ検索は非対応
        # 代わりにトラッキング済みユーザーから収集
        return []
