"""
Claude APIを使ったXポスト内容の自動生成モジュール
"""
import os
import logging
import anthropic

logger = logging.getLogger(__name__)

client = anthropic.Anthropic()  # ANTHROPIC_API_KEY 環境変数を自動で使用


def generate_post(topic: str) -> str:
    """
    Claude APIを使って指定したテーマのXポスト文を生成する

    Args:
        topic: 投稿テーマ（例: "AIとテクノロジーの最新情報"）

    Returns:
        生成されたポスト文（280文字以内）
    """
    system_prompt = """あなたはXのソーシャルメディア専門家です。
指定されたテーマに関して、エンゲージメントが高い日本語のポストを1つ作成してください。

ルール:
- 必ず280文字以内にすること
- ハッシュタグを2〜3個含めること
- 親しみやすく、読者が興味を持つ内容にすること
- ポスト本文のみ出力すること（説明文や前置きは不要）"""

    response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=512,
        system=system_prompt,
        messages=[
            {"role": "user", "content": f"テーマ: {topic}"}
        ]
    )

    generated_text = response.content[0].text.strip()
    logger.info(f"コンテンツ生成完了: {len(generated_text)}文字")
    return generated_text
