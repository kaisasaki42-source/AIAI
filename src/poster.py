"""
Playwright でブラウザを自動操作して X (Twitter) に投稿するモジュール

初回はログインが必要。セッション情報を session.json に保存し、
2回目以降はログインをスキップする。
"""
import os
import logging
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

logger = logging.getLogger(__name__)

SESSION_FILE = Path("session.json")
X_URL = "https://x.com"


def _login(page, username: str, password: str) -> None:
    """X にログインする"""
    logger.info("ログイン中...")
    page.goto("https://x.com/i/flow/login")

    # ユーザー名入力
    page.get_by_label("電話番号、メールアドレス、ユーザー名").fill(username)
    page.get_by_role("button", name="次へ").click()

    # パスワード入力（追加確認画面が出る場合も考慮）
    try:
        pw_field = page.get_by_label("パスワード", exact=True)
        pw_field.wait_for(timeout=5000)
    except PlaywrightTimeoutError:
        # 英語UIの場合
        pw_field = page.get_by_label("Password", exact=True)

    pw_field.fill(password)
    page.get_by_test_id("LoginButton").click()

    # ホーム画面に遷移するまで待機
    page.wait_for_url("**/home", timeout=30000)
    logger.info("ログイン成功")


def post_tweet(text: str, dry_run: bool = False) -> dict:
    """
    ブラウザを自動操作して X にポストする

    Args:
        text: 投稿テキスト（280文字以内）
        dry_run: True の場合、ブラウザを起動して内容を確認するが実際には送信しない

    Returns:
        {"success": bool, "text": str}
    """
    if len(text) > 280:
        logger.warning("テキストが280文字を超えています。切り詰めます。")
        text = text[:277] + "..."

    if dry_run:
        logger.info(f"[DRY RUN] 投稿内容:\n{text}")
        return {"success": True, "text": text}

    username = os.environ["X_USERNAME"]
    password = os.environ["X_PASSWORD"]
    headless = os.getenv("HEADLESS", "true").lower() == "true"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)

        # セッションが保存済みなら再利用、なければ新規コンテキスト
        if SESSION_FILE.exists():
            context = browser.new_context(storage_state=str(SESSION_FILE))
            logger.info("保存済みセッションを使用します")
        else:
            context = browser.new_context()

        page = context.new_page()

        try:
            # ホームに移動してログイン状態を確認
            page.goto(f"{X_URL}/home", wait_until="domcontentloaded", timeout=20000)

            # ログインページにリダイレクトされたら再ログイン
            if "/login" in page.url or "/flow/login" in page.url:
                _login(page, username, password)

            # セッションを保存（次回のログインスキップのため）
            context.storage_state(path=str(SESSION_FILE))

            # ポスト投稿エリアをクリック
            compose = page.get_by_test_id("tweetTextarea_0")
            compose.wait_for(timeout=15000)
            compose.click()
            compose.fill(text)

            # 「ポストする」ボタンをクリック
            post_btn = page.get_by_test_id("tweetButtonInline")
            post_btn.wait_for(state="enabled", timeout=10000)
            post_btn.click()

            # 送信完了を待つ（テキストエリアがクリアされることで確認）
            page.wait_for_function(
                "() => document.querySelector('[data-testid=\"tweetTextarea_0\"]')?.textContent === ''",
                timeout=15000,
            )

            logger.info("投稿成功!")
            return {"success": True, "text": text}

        except PlaywrightTimeoutError as e:
            logger.error(f"タイムアウトエラー: {e}")
            return {"success": False, "text": text}
        except Exception as e:
            logger.error(f"投稿中にエラー: {e}")
            return {"success": False, "text": text}
        finally:
            browser.close()
