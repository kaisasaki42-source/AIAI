"""データベース初期化スクリプト"""
import asyncio
from src.core.database import init_db

if __name__ == "__main__":
    print("データベースを初期化中...")
    asyncio.run(init_db())
    print("完了!")
