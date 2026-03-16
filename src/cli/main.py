"""
AIAI CLI

コマンドラインから自動投稿・分析ツールを操作する。
使い方: python -m src.cli.main --help
"""
import asyncio
import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import print as rprint

app = typer.Typer(
    name="aiai",
    help="AIAI - Meta Threads 自動投稿・分析ツール (Powered by Claude AI)",
    rich_markup_mode="rich",
)
console = Console()

post_app = typer.Typer(help="投稿管理コマンド")
schedule_app = typer.Typer(help="スケジュール管理コマンド")
analytics_app = typer.Typer(help="分析コマンド")
track_app = typer.Typer(help="スレッド追跡コマンド")

app.add_typer(post_app, name="post")
app.add_typer(schedule_app, name="schedule")
app.add_typer(analytics_app, name="analytics")
app.add_typer(track_app, name="track")


def run_async(coro):
    return asyncio.run(coro)


# ──────────────────────────────────────────────
# 投稿コマンド
# ──────────────────────────────────────────────

@post_app.command("generate")
def generate_post(
    topic: str = typer.Argument(..., help="投稿のテーマ"),
    tone: str = typer.Option("informative", help="トーン: informative/casual/inspiring"),
    publish: bool = typer.Option(False, "--publish", "-p", help="生成後すぐに公開する"),
):
    """AIで投稿コンテンツを生成する"""
    async def _run():
        from src.services.ai_generator import ContentGenerator
        console.print(f"[cyan]Claude AIで投稿を生成中... トピック: {topic}[/cyan]")
        generator = ContentGenerator()
        result = await generator.generate_post(topic=topic, tone=tone)

        panel_content = f"{result['content']}\n\n"
        if result.get("hashtags"):
            panel_content += f"[dim]ハッシュタグ: {' '.join(result['hashtags'])}[/dim]"

        console.print(Panel(panel_content, title="[green]生成された投稿[/green]", border_style="green"))

        if result.get("reasoning"):
            console.print(f"[dim]AI分析: {result['reasoning']}[/dim]")

        if publish:
            from src.core.database import AsyncSessionLocal
            from src.models.post import Post, PostStatus, PostType
            from datetime import datetime, timezone

            async with AsyncSessionLocal() as db:
                post = Post(
                    content=result["content"],
                    topic=topic,
                    status=PostStatus.SCHEDULED,
                    post_type=PostType.AI_GENERATED,
                    scheduled_at=datetime.now(timezone.utc),
                    ai_model=result.get("model", ""),
                )
                db.add(post)
                await db.commit()
                await db.refresh(post)

            from src.scheduler.tasks import publish_post
            publish_post.delay(post.id)
            console.print(f"[green]投稿キューに追加しました (ID: {post.id})[/green]")

    run_async(_run())


@post_app.command("list")
def list_posts(
    status: str = typer.Option(None, help="フィルター: draft/scheduled/published/failed"),
    limit: int = typer.Option(10, help="表示件数"),
):
    """投稿一覧を表示する"""
    async def _run():
        from sqlalchemy import select
        from src.core.database import AsyncSessionLocal
        from src.models.post import Post, PostStatus

        async with AsyncSessionLocal() as db:
            query = select(Post).order_by(Post.created_at.desc()).limit(limit)
            if status:
                query = query.where(Post.status == PostStatus(status))
            result = await db.execute(query)
            posts = result.scalars().all()

        table = Table(title="投稿一覧", show_header=True, header_style="bold cyan")
        table.add_column("ID", style="dim", width=6)
        table.add_column("ステータス", width=12)
        table.add_column("内容", width=50)
        table.add_column("トピック", width=15)
        table.add_column("作成日時", width=20)

        status_colors = {
            "published": "green",
            "scheduled": "yellow",
            "draft": "blue",
            "failed": "red",
        }
        for post in posts:
            color = status_colors.get(post.status, "white")
            table.add_row(
                str(post.id),
                f"[{color}]{post.status}[/{color}]",
                post.content[:47] + "..." if len(post.content) > 47 else post.content,
                post.topic or "-",
                post.created_at.strftime("%Y-%m-%d %H:%M") if post.created_at else "-",
            )
        console.print(table)

    run_async(_run())


# ──────────────────────────────────────────────
# スケジュールコマンド
# ──────────────────────────────────────────────

@schedule_app.command("add")
def add_schedule(
    name: str = typer.Argument(..., help="スケジュール名"),
    cron: str = typer.Option(..., "--cron", "-c", help="Cron式 例: '0 9 * * *'"),
    topic: str = typer.Option(None, help="投稿テーマ"),
):
    """定期投稿スケジュールを追加する"""
    async def _run():
        from src.core.database import AsyncSessionLocal
        from src.models.post import PostSchedule

        async with AsyncSessionLocal() as db:
            schedule = PostSchedule(
                name=name,
                cron_expression=cron,
                topic=topic,
                use_ai_generation=True,
            )
            db.add(schedule)
            await db.commit()
            await db.refresh(schedule)

        console.print(f"[green]スケジュールを追加しました (ID: {schedule.id})[/green]")
        console.print(f"  名前: {name}")
        console.print(f"  Cron: {cron}")
        if topic:
            console.print(f"  テーマ: {topic}")

    run_async(_run())


@schedule_app.command("list")
def list_schedules():
    """スケジュール一覧を表示する"""
    async def _run():
        from sqlalchemy import select
        from src.core.database import AsyncSessionLocal
        from src.models.post import PostSchedule

        async with AsyncSessionLocal() as db:
            result = await db.execute(select(PostSchedule).order_by(PostSchedule.created_at.desc()))
            schedules = result.scalars().all()

        table = Table(title="スケジュール一覧", show_header=True, header_style="bold cyan")
        table.add_column("ID", width=6)
        table.add_column("名前", width=20)
        table.add_column("Cron", width=15)
        table.add_column("テーマ", width=20)
        table.add_column("有効", width=6)
        table.add_column("最終実行", width=20)

        for s in schedules:
            table.add_row(
                str(s.id),
                s.name,
                s.cron_expression,
                s.topic or "-",
                "[green]ON[/green]" if s.is_active else "[red]OFF[/red]",
                s.last_run_at.strftime("%Y-%m-%d %H:%M") if s.last_run_at else "未実行",
            )
        console.print(table)

    run_async(_run())


# ──────────────────────────────────────────────
# 分析コマンド
# ──────────────────────────────────────────────

@analytics_app.command("summary")
def show_summary(days: int = typer.Option(30, help="分析期間（日数）")):
    """パフォーマンスサマリーを表示する"""
    async def _run():
        from src.core.database import AsyncSessionLocal
        from src.analytics.engine import AnalyticsEngine

        async with AsyncSessionLocal() as db:
            engine = AnalyticsEngine(db)
            stats = await engine.get_my_performance_summary(days=days)

        console.print(Panel(
            f"[bold]直近{days}日間のパフォーマンス[/bold]\n\n"
            f"総投稿数: [cyan]{stats['total_posts']}[/cyan]\n"
            f"平均いいね: [green]{stats['avg_likes']:.1f}[/green]\n"
            f"平均リプライ: [green]{stats['avg_replies']:.1f}[/green]\n"
            f"平均表示回数: [green]{stats['avg_views']:.0f}[/green]\n"
            f"平均エンゲージメント率: [yellow]{stats['avg_engagement_rate']:.2%}[/yellow]\n"
            f"最高いいね数: [bold green]{stats['max_likes']}[/bold green]",
            title="[bold cyan]AIAI Analytics[/bold cyan]",
            border_style="cyan",
        ))

    run_async(_run())


@analytics_app.command("weekly")
def weekly_report():
    """今週vs先週の比較レポートを表示する"""
    async def _run():
        from src.core.database import AsyncSessionLocal
        from src.analytics.engine import AnalyticsEngine

        async with AsyncSessionLocal() as db:
            engine = AnalyticsEngine(db)
            report = await engine.get_weekly_stats()

        tw = report["this_week"]
        lw = report["last_week"]
        ch = report["changes"]

        def trend_icon(pct):
            return "[green]↑[/green]" if pct > 0 else "[red]↓[/red]" if pct < 0 else "→"

        console.print(Panel(
            f"[bold]投稿数:[/bold] {lw['posts']} → {tw['posts']} "
            f"{trend_icon(ch['posts_change_pct'])} {ch['posts_change_pct']:+.1f}%\n"
            f"[bold]平均いいね:[/bold] {lw['avg_likes']:.1f} → {tw['avg_likes']:.1f} "
            f"{trend_icon(ch['likes_change_pct'])} {ch['likes_change_pct']:+.1f}%\n"
            f"[bold]エンゲージメント率:[/bold] {lw['avg_engagement']:.2%} → {tw['avg_engagement']:.2%} "
            f"{trend_icon(ch['engagement_change_pct'])} {ch['engagement_change_pct']:+.1f}%",
            title="[bold cyan]週次レポート (先週 → 今週)[/bold cyan]",
            border_style="cyan",
        ))

    run_async(_run())


# ──────────────────────────────────────────────
# 追跡コマンド
# ──────────────────────────────────────────────

@track_app.command("add")
def add_track(
    username: str = typer.Argument(..., help="追跡するThreadsユーザー名"),
    reason: str = typer.Option(None, help="追跡理由"),
):
    """追跡するスレッドアカウントを追加する"""
    async def _run():
        from src.core.database import AsyncSessionLocal
        from src.models.post import TrackedThread
        from src.services.threads_client import ThreadsClient, ThreadsAPIError
        from sqlalchemy import select

        console.print(f"[cyan]Threadsユーザー情報を取得中: @{username}[/cyan]")
        try:
            async with ThreadsClient() as client:
                user_info = await client.get_user_by_username(username)
        except ThreadsAPIError as e:
            console.print(f"[red]エラー: {e}[/red]")
            raise typer.Exit(1)

        async with AsyncSessionLocal() as db:
            existing = await db.execute(
                select(TrackedThread).where(TrackedThread.threads_user_id == user_info["id"])
            )
            if existing.scalar_one_or_none():
                console.print(f"[yellow]@{username} は既に追跡中です[/yellow]")
                return

            thread = TrackedThread(
                threads_user_id=user_info["id"],
                username=user_info.get("username", username),
                display_name=user_info.get("name"),
                track_reason=reason,
            )
            db.add(thread)
            await db.commit()

        console.print(f"[green]@{username} の追跡を開始しました[/green]")

    run_async(_run())


@track_app.command("analyze")
def analyze_track(thread_id: int = typer.Argument(..., help="分析するスレッドID")):
    """追跡スレッドのAI分析を実行する"""
    async def _run():
        from src.core.database import AsyncSessionLocal
        from src.analytics.engine import AnalyticsEngine

        console.print(f"[cyan]AI分析を実行中...[/cyan]")
        async with AsyncSessionLocal() as db:
            engine = AnalyticsEngine(db)
            analysis = await engine.get_tracked_thread_analysis(thread_id)

        if "error" in analysis:
            console.print(f"[red]{analysis['error']}[/red]")
            return

        console.print(Panel(
            f"ユーザー: @{analysis.get('username', '?')}\n"
            f"分析投稿数: {analysis.get('total_posts_analyzed', 0)}\n"
            f"平均いいね: {analysis.get('avg_likes', 0):.1f}",
            title="[bold cyan]スレッド分析[/bold cyan]",
        ))

        if "ai_analysis" in analysis and "actionable_insights" in analysis["ai_analysis"]:
            console.print("\n[bold]活用できるインサイト:[/bold]")
            for insight in analysis["ai_analysis"]["actionable_insights"]:
                rprint(f"  • {insight}")

    run_async(_run())


if __name__ == "__main__":
    app()
