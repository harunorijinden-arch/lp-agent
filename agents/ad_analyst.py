"""
広告アナリストエージェント（Step4）
==================================
Meta広告（Facebook/Instagram）の分析に特化。参照資料なし。Web検索なし。
アド・スルー設計（広告→LP一貫性）を整理する。
※ Google広告はスコープ外
"""

from agents.base import call_claude, load_prompt, console
from rich.panel import Panel

TOTAL_STEPS = 7

SYSTEM = (
    "あなたはMeta広告（Facebook/Instagram）運用とLP設計の接点に特化した広告アナリストです。\n\n"
    "【あなたの専門領域】\n"
    "- Meta広告（Facebook/Instagram）の分析（クリエイティブ、訴求軸、ユーザー心理）\n"
    "- アド・スルー設計（広告クリエイティブ→LP一貫性の最適化）\n"
    "- 受動的ユーザー（SNSフィード閲覧中）の心理理解\n\n"
    "【スコープ】\n"
    "- Meta広告（Facebook/Instagram）のみが対象\n"
    "- Google広告はスコープ外\n\n"
    "【あなたがやらないこと】\n"
    "- LP構成の設計（それは後のワイヤーフレームエージェントの仕事）\n"
    "- ターゲット分析（それは前のストラテジストの仕事）\n"
    "- 広告運用の改善提案（LPに活かせる分析のみ）\n"
    "- 情報の創作（不足している情報は「⚠️ 不足情報」として明記する）\n\n"
    "【ルール】\n"
    "- Meta広告は受動的なユーザーが対象。「興味→共感→行動」の流れを意識すること\n"
    "- 勝ちパターンから「なぜ効いているのか」を分析すること\n"
    "- LP設計への具体的な示唆を出すこと（次のワイヤーフレームエージェントが使いやすいように）\n"
    "- 日本語で回答すること\n"
)


class AdAnalystAgent:
    """Meta広告分析特化アナリスト"""

    def run(self, who_what: str, ad_info: str, images: list[bytes] | None = None) -> str:
        """Step4: Meta広告コンテキスト分析"""
        console.print(Panel(
            f"[bold blue]Step 4/{TOTAL_STEPS}: Meta広告コンテキスト分析[/bold blue]\n"
            "Meta広告（Facebook/Instagram）の勝ちパターンを分析中...\n"
            "[dim]🧠 広告アナリストエージェントが担当\n"
            "アド・スルー設計（広告→LP一貫性）を整理[/dim]",
            border_style="blue",
        ))

        template = load_prompt("step4_ad_context.md")
        prompt = (
            template
            .replace("{who_what}", who_what)
            .replace("{ad_info}", ad_info)
        )
        if images:
            prompt += "\n\n【添付画像】Meta広告クリエイティブのスクリーンショットなど参考画像も分析に活用してください。"

        return call_claude(SYSTEM, prompt, use_web_search=False, images=images)
