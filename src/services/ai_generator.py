"""
Claude AI コンテンツジェネレーター

分析データとトレンドを元に、Threadsへの投稿コンテンツを
Claude claude-opus-4-6 で自動生成する。
"""
import anthropic
from datetime import datetime
from src.core.config import settings


class ContentGenerator:
    """Claude APIを使ったThreads投稿コンテンツ生成エンジン"""

    def __init__(self):
        self.client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        self.model = "claude-opus-4-6"

    async def generate_post(
        self,
        topic: str,
        context: str = "",
        tone: str = "informative",
        max_length: int = 500,
        examples: list[dict] = None,
    ) -> dict:
        """
        投稿コンテンツを生成する

        Args:
            topic: 投稿のテーマ
            context: 背景情報（過去の高エンゲージメント投稿など）
            tone: トーン (informative/casual/inspiring/provocative)
            max_length: 最大文字数
            examples: 参考にする高エンゲージメント投稿例

        Returns:
            {"content": str, "hashtags": list, "best_time": str, "reasoning": str}
        """
        examples_text = ""
        if examples:
            examples_text = "\n\n## 高エンゲージメントの参考投稿:\n"
            for ex in examples[:5]:
                examples_text += f"- いいね:{ex.get('likes', 0)} | 内容: {ex.get('content', '')[:100]}\n"

        system_prompt = f"""あなたはMeta Threadsの投稿コンテンツ専門家です。
与えられたトピックに関して、高いエンゲージメントを獲得できる投稿を作成します。

## 制約:
- 最大{max_length}文字
- トーン: {tone}
- 言語: 日本語
- Threadsの特性（短い投稿、会話促進型、ハッシュタグは最小限）を意識する

## 出力形式 (必ずJSON形式で返すこと):
{{
  "content": "投稿本文",
  "hashtags": ["ハッシュタグ1", "ハッシュタグ2"],
  "reasoning": "この投稿が効果的な理由の簡単な説明"
}}"""

        user_message = f"## トピック:\n{topic}"
        if context:
            user_message += f"\n\n## 追加コンテキスト:\n{context}"
        if examples_text:
            user_message += examples_text

        async with self.client.messages.stream(
            model=self.model,
            max_tokens=2048,
            thinking={"type": "adaptive"},
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        ) as stream:
            final = await stream.get_final_message()

        text = next(
            (b.text for b in final.content if b.type == "text"), ""
        )

        import json
        import re
        # JSON部分を抽出
        json_match = re.search(r'\{.*\}', text, re.DOTALL)
        if json_match:
            try:
                result = json.loads(json_match.group())
                return {
                    "content": result.get("content", ""),
                    "hashtags": result.get("hashtags", []),
                    "reasoning": result.get("reasoning", ""),
                    "model": self.model,
                    "topic": topic,
                    "generated_at": datetime.utcnow().isoformat(),
                }
            except json.JSONDecodeError:
                pass

        # JSONパース失敗時はテキストをそのまま返す
        return {
            "content": text[:max_length],
            "hashtags": [],
            "reasoning": "",
            "model": self.model,
            "topic": topic,
            "generated_at": datetime.utcnow().isoformat(),
        }

    async def generate_optimized_post(
        self,
        topic: str,
        my_analytics: dict,
        competitor_analytics: list[dict] = None,
    ) -> dict:
        """
        自分の分析データと競合データを元に最適化された投稿を生成

        Args:
            topic: テーマ
            my_analytics: 自分の投稿分析データ（高エンゲージメント傾向など）
            competitor_analytics: 競合・参考アカウントの分析データ
        """
        context_parts = []

        if my_analytics:
            context_parts.append(
                f"自分の過去分析:\n"
                f"- 平均エンゲージメント率: {my_analytics.get('avg_engagement_rate', 0):.2%}\n"
                f"- 高エンゲージメント投稿の特徴: {my_analytics.get('top_post_patterns', '不明')}\n"
                f"- 最適投稿時間帯: {my_analytics.get('best_posting_hours', '不明')}"
            )

        if competitor_analytics:
            comp_text = "参考アカウントのトレンド:\n"
            for comp in competitor_analytics[:3]:
                comp_text += (
                    f"- @{comp.get('username', '?')}: "
                    f"高エンゲージメントパターン={comp.get('pattern', '不明')}\n"
                )
            context_parts.append(comp_text)

        context = "\n\n".join(context_parts)

        return await self.generate_post(
            topic=topic,
            context=context,
            tone="engaging",
        )

    async def analyze_post_performance(self, post_content: str, metrics: dict) -> dict:
        """
        投稿パフォーマンスをAIで分析し、改善提案を生成

        Args:
            post_content: 投稿テキスト
            metrics: エンゲージメント指標 (likes, replies, reposts, views)

        Returns:
            分析結果と改善提案
        """
        prompt = f"""以下のThreads投稿とそのパフォーマンス指標を分析してください。

## 投稿内容:
{post_content}

## パフォーマンス指標:
- いいね: {metrics.get('likes', 0)}
- リプライ: {metrics.get('replies', 0)}
- リポスト: {metrics.get('reposts', 0)}
- 表示回数: {metrics.get('views', 0)}
- エンゲージメント率: {metrics.get('engagement_rate', 0):.2%}

以下をJSON形式で出力してください:
{{
  "performance_level": "high/medium/low",
  "strengths": ["強み1", "強み2"],
  "weaknesses": ["弱み1", "弱み2"],
  "improvement_suggestions": ["改善案1", "改善案2", "改善案3"],
  "learnings": "次回の投稿に活かせる学び"
}}"""

        async with self.client.messages.stream(
            model=self.model,
            max_tokens=1500,
            thinking={"type": "adaptive"},
            messages=[{"role": "user", "content": prompt}],
        ) as stream:
            final = await stream.get_final_message()

        import json
        import re
        text = next((b.text for b in final.content if b.type == "text"), "{}")
        json_match = re.search(r'\{.*\}', text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass
        return {"error": "解析失敗", "raw": text}

    async def analyze_competitor_posts(self, posts: list[dict]) -> dict:
        """
        他スレッドの投稿群をAIで分析してパターンを抽出

        Args:
            posts: 投稿リスト [{"content": str, "likes": int, ...}]

        Returns:
            パターン分析と活用可能なインサイト
        """
        posts_text = "\n\n".join([
            f"[いいね:{p.get('likes', 0)}, リプライ:{p.get('replies', 0)}]\n{p.get('content', '')[:200]}"
            for p in posts[:20]
        ])

        prompt = f"""以下のThreadsアカウントの投稿群を分析し、成功パターンを特定してください。

## 投稿データ:
{posts_text}

以下をJSON形式で出力してください:
{{
  "posting_patterns": {{
    "best_content_types": ["コンテンツタイプ1", "コンテンツタイプ2"],
    "successful_hooks": ["効果的な冒頭パターン1", "効果的な冒頭パターン2"],
    "optimal_length": "最適な文字数の傾向",
    "hashtag_strategy": "ハッシュタグ戦略の傾向"
  }},
  "engagement_drivers": ["エンゲージメント要因1", "エンゲージメント要因2"],
  "topics_that_resonate": ["共感されやすいトピック1", "共感されやすいトピック2"],
  "actionable_insights": ["活用できるインサイト1", "活用できるインサイト2", "活用できるインサイト3"]
}}"""

        async with self.client.messages.stream(
            model=self.model,
            max_tokens=2000,
            thinking={"type": "adaptive"},
            messages=[{"role": "user", "content": prompt}],
        ) as stream:
            final = await stream.get_final_message()

        import json
        import re
        text = next((b.text for b in final.content if b.type == "text"), "{}")
        json_match = re.search(r'\{.*\}', text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass
        return {"error": "解析失敗", "raw": text}
