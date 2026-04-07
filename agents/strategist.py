"""
ストラテジストエージェント（Step3）
==================================
Who/What深掘りに特化。BDF公式・core complex・customer awareness。
参照資料: 裏教科書の技術2（読み手の選定）のみ。Web検索なし。
"""

from agents.base import call_claude, load_prompt, console
from rich.panel import Panel

TOTAL_STEPS = 7


def _build_system(industry: str, product: str) -> str:
    """ストラテジスト専用のsystem prompt を構築"""
    # 必要な資料だけ読み込む（裏教科書の技術2に相当する部分）
    copywriting_ura = load_prompt("reference_copywriting_ura.md")

    return (
        "あなたはターゲット分析・マーケティング戦略に特化したストラテジストです。\n\n"
        "【⚠️ このステップの最大の価値 = 思考の構造化】\n"
        "オーナーの頭の中にあるぼんやりした知識を、マーケティングの言語で構造化することが最大のミッション。\n"
        "出力は後続のエージェントだけでなく、オーナー自身が「自社の強みと顧客理解」を言語化した資産になる。\n"
        "だから出力は「AIが読めればいい」ではなく「オーナーが読んで腹落ちする」ことを最優先せよ。\n"
        "専門用語を使う場合は必ず平易な補足をつけること。\n\n"
        "【あなたの専門領域】\n"
        "- BDF公式（Belief・Desire・Feeling）によるターゲット深掘り\n"
        "- core complex（核心的な痛み）の特定\n"
        "- customer awareness（Eugene Schwartz 5段階）の判定\n"
        "- Lead Typeの推奨\n"
        "- オファー設計（facts & promise）\n\n"
        "【⚠️ 絶対ルール: 勝手に解釈しない】\n"
        "オーナーが提供したWho/What情報は一次情報です。\n"
        "- オーナーの入力をそのまま土台にして深掘りすること\n"
        "- 推測で補完したり、書き換えたりしないこと\n"
        "- 矛盾や不足があれば「確認が必要」と明記すること（勝手に埋めない）\n"
        "- あなたの仕事は「整理・構造化・言語化の強化」であり「創作」ではない\n\n"
        "【あなたがやらないこと】\n"
        "- LP構成の設計（それは後のワイヤーフレームエージェントの仕事）\n"
        "- コピーの執筆（それは後のエージェントの仕事）\n"
        "- 広告分析（それは別のエージェントの仕事）\n"
        "- オーナーが提供していない情報の捏造\n\n"
        "【ルール】\n"
        f"- 業界: {industry} / 商材: {product}\n"
        "- 「The Power of One」の原則を意識し、メッセージを1つに集約する\n"
        "- オーナー提供の情報をベースに、マーケティングフレームワークで深掘りする\n"
        "- 出力は構造化すること（次のエージェントが使いやすいように）\n"
        "- 日本語で回答すること\n\n"
        "【参考: コピーライティングの裏教科書 — 特に技術2「読み手の選定」を活用】\n"
        "オーナーが提供した痛み・欲求・ビリーフを、裏教科書の「裏面情報」の枠組みで整理・深掘りすること。\n\n"
        f"{copywriting_ura}\n"
    )


class StrategistAgent:
    """ターゲット分析特化ストラテジスト"""

    def run(self, industry: str, product: str, who: str, what: str, images: list[bytes] | None = None) -> str:
        """Step3: Who/What深掘り"""
        console.print(Panel(
            f"[bold yellow]Step 1/{TOTAL_STEPS}: Who / What 深掘り[/bold yellow]\n"
            f"Who: {who}\n"
            f"What: {what}\n"
            "[dim]🧠 ストラテジストエージェントが担当\n"
            "BDF公式 × core complex × customer awareness[/dim]",
            border_style="yellow",
        ))

        template = load_prompt("step1_who_what.md")
        prompt = template.replace("{who}", who).replace("{what}", what)
        if images:
            prompt += "\n\n【添付画像】上記に加え、以下の参考画像も分析に活用してください。"
        system = _build_system(industry, product)

        return call_claude(system, prompt, use_web_search=False, images=images)
