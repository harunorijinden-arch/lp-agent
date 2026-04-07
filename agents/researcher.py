"""
リサーチャーエージェント（Step1 & Step2）
========================================
LP分析に特化。参照資料なし。Web検索あり。
- Step1: 競合LPリサーチ（基準LP + 追加4つ以上）
- Step2: 別業界LPリサーチ（参考LP + 追加4つ以上）
"""

from agents.base import call_claude, load_prompt, console, MODEL_HAIKU
from rich.panel import Panel

TOTAL_STEPS = 7

# ─── このエージェント専用のsystem prompt ─────────────────
SYSTEM_COMPETITOR = (
    "あなたはLP（ランディングページ）の構成分析に特化したリサーチのプロフェッショナルです。\n\n"
    "【あなたの専門領域】\n"
    "- LPの構成要素（ファーストビュー、CTA、証拠セクション等）の分析\n"
    "- 訴求パターンの抽象化・パターン認識\n"
    "- 業界共通の構成トレンドの把握\n\n"
    "【ルール】\n"
    "- 必ずWeb検索を使って実際のLPを調査すること\n"
    "- 基準LPを最も詳細に分析し、追加LPは比較対象として分析する\n"
    "- 合計5つ以上のLPを分析すること\n"
    "- 分析結果は構造化して出力すること（次のステップのエージェントが使いやすいように）\n"
    "- Who/What定義が提供されている場合、ターゲット視点でLPを評価すること\n"
    "- 日本語で回答すること\n"
)

SYSTEM_CROSS_INDUSTRY = (
    "あなたはLP（ランディングページ）の構成分析に特化したリサーチのプロフェッショナルです。\n\n"
    "【あなたの専門領域】\n"
    "- 異業界LPの構成要素の分析\n"
    "- 業界を超えた訴求パターンの発見\n"
    "- 異業界からの転用可能なアイデアの抽出\n\n"
    "【ルール】\n"
    "- 必ずWeb検索を使って実際のLPを調査すること\n"
    "- 参考LPを最も詳細に分析し、追加LPはできるだけバラバラな業界から選ぶ\n"
    "  （BtoC/BtoB、高単価/低単価、有形/無形を混ぜる）\n"
    "- 合計5つ以上のLPを分析すること\n"
    "- 各LPの「この業界ならではの工夫」を必ず記載すること\n"
    "- 転用アイデアを具体的に提案すること（次のステップで使えるように）\n"
    "- Who/What定義が提供されている場合、ターゲット視点で転用の適合性を判断すること\n"
    "- 日本語で回答すること\n"
)


class ResearcherAgent:
    """LP分析特化リサーチャー"""

    def run_competitor(self, industry: str, product: str, base_url: str, who_what: str = "", images: list[bytes] | None = None) -> str:
        """Step2: 競合LPリサーチ（Who/What定義を踏まえてリサーチ）"""
        console.print(Panel(
            f"[bold cyan]Step 2/{TOTAL_STEPS}: 競合LPリサーチ[/bold cyan]\n"
            f"基準LP: {base_url}\n"
            "↑ を分析後、同業界のLPを追加4つ以上リサーチ中...\n"
            "[dim]🧠 リサーチャーエージェントが担当（Who/What定義を踏まえて評価）[/dim]",
            border_style="cyan",
        ))

        template = load_prompt("step1_competitor_research.md")
        prompt = (
            template
            .replace("{industry}", industry)
            .replace("{product}", product)
            .replace("{base_url}", base_url)
            .replace("{who_what}", who_what if who_what else "（未定義）")
        )
        if images:
            prompt += "\n\n【添付画像】競合LPのスクリーンショットなど参考画像も分析に活用してください。"

        return call_claude(SYSTEM_COMPETITOR, prompt, use_web_search=True, images=images, model=MODEL_HAIKU)

    def run_cross_industry(self, industry: str, base_url: str, who_what: str = "", images: list[bytes] | None = None) -> str:
        """Step3: 別業界LPリサーチ（Who/What定義を踏まえてリサーチ）"""
        console.print(Panel(
            f"[bold green]Step 3/{TOTAL_STEPS}: 別業界LPリサーチ[/bold green]\n"
            f"参考LP: {base_url}\n"
            "↑ を分析後、さらに異業界のLPを追加4つ以上リサーチ中...\n"
            "[dim]🧠 リサーチャーエージェントが担当（Who/What定義を踏まえて評価）[/dim]",
            border_style="green",
        ))

        template = load_prompt("step2_cross_industry_research.md")
        prompt = (
            template
            .replace("{industry}", industry)
            .replace("{base_url}", base_url)
            .replace("{who_what}", who_what if who_what else "（未定義）")
        )
        if images:
            prompt += "\n\n【添付画像】参考LPのスクリーンショットなど参考画像も分析に活用してください。"

        return call_claude(SYSTEM_CROSS_INDUSTRY, prompt, use_web_search=True, images=images, model=MODEL_HAIKU)
