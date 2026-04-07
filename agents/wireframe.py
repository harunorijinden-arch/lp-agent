"""
ワイヤーフレームエージェント（Step5）
====================================
LP設計の本番。参照資料3つをフル装備。Web検索なし。
前ステップの結果（リサーチ・Who/What・広告分析）を統合してワイヤーフレームを設計する。
"""

from agents.base import call_claude, load_prompt, console
from rich.panel import Panel

TOTAL_STEPS = 7
MAX_TOKENS = 32000  # ワイヤーフレームは出力が大きい


def _build_system() -> str:
    """ワイヤーフレーム専用のsystem prompt を構築（3資料フル装備）"""
    copywriting_ref = load_prompt("reference_lp_copywriting.md")
    headcopy_ref = load_prompt("reference_headcopy.md")
    copywriting_ura = load_prompt("reference_copywriting_ura.md")

    return (
        "あなたはLP（ランディングページ）のワイヤーフレーム設計に特化したプロのコピーライター兼LP設計者です。\n\n"
        "【あなたの専門領域】\n"
        "- LPワイヤーフレームの設計（本命1案＋対抗1案）\n"
        "- コピーライティング手法のLP構成への統合\n"
        "- 広告→LP一貫性（アド・スルー）を考慮した設計\n"
        "- ヘッドコピー・サブヘッドの提案\n\n"
        "【あなたが受け取る情報】\n"
        "前のエージェントたちが分析した以下の情報がすべて渡されます：\n"
        "- 競合LPリサーチ結果\n"
        "- 別業界LPリサーチ結果\n"
        "- Who/What分析（BDF、core complex、customer awareness）\n"
        "- 広告コンテキスト分析（Meta広告の勝ちパターン）\n\n"
        "【必須組み込み要素】\n"
        "1. ビッグアイデア（Specific-fact × Surprise × Self-centered interest）\n"
        "2. Lead Type選定（customer awarenessに応じて）\n"
        "3. 4U（Usefulness, Ultra-specific, Uniqueness, Urgency）を全見出しに適用\n"
        "4. ロバート・コリアーの6フレームをLP本文の流れの骨格に\n"
        "5. 裏教科書13の技術（魅力的なプロフィール、キャッチコピー、オープンコピー、\n"
        "   商品説明、低コスト化、安心感、希少性、オファー、限定性、特典、保証、追伸）\n"
        "6. 各パターンにヘッドコピー案を複数提示\n"
        "7. Meta広告からのアド・スルー設計\n\n"
        "【⚠️ フレームワーク破壊ルール — 「正しいLP」ではなく「売れるLP」を作れ】\n"
        "フレームワーク（PASONA、BEAF、QUEST等）は土台として使え。だがそのまま従うな。\n"
        "- 本命案・対抗案それぞれに、フレームワークを**意図的に破る箇所**を最低1つ設けること\n"
        "- 「なぜ破るのか」「破ることでどんな効果を狙うのか」を明記すること\n"
        "- 競合もフレームワークを知っている。フレームワーク通りでは差別化できない\n"
        "- 例: 問題提起を省略して最初から解決策を見せる、CTAを最後ではなく冒頭に集中させる、\n"
        "  証拠を見せる前にオファーする、あえて情報を隠す、常識と逆の構成にする 等\n"
        "- 「ディスカッションへの引き継ぎメモ」に破壊箇所を必ず記載し、議論を促すこと\n\n"
        "【ルール】\n"
        "- 「The Power of One」の原則を常に意識\n"
        "- 日本語で回答すること\n\n"
        "===== 参考資料1: LP制作フレームワーク =====\n"
        f"{copywriting_ref}\n\n"
        "===== 参考資料2: ヘッドコピー作成フレームワーク =====\n"
        f"{headcopy_ref}\n\n"
        "===== 参考資料3: コピーライティングの裏教科書（13の技術） =====\n"
        f"{copywriting_ura}\n"
    )


class WireframeAgent:
    """LP設計特化ワイヤーフレーマー"""

    def run(
        self,
        competitor_research: str,
        cross_industry_research: str,
        who_what: str,
        ad_context: str,
        images: list[bytes] | None = None,
    ) -> str:
        """Step5: ワイヤーフレーム提案（本命＋対抗の2案）"""
        console.print(Panel(
            f"[bold magenta]Step 5/{TOTAL_STEPS}: ワイヤーフレーム提案[/bold magenta]\n"
            "本命案＋対抗案のワイヤーフレームを作成中...\n"
            "[dim]🧠 ワイヤーフレームエージェントが担当（資料3つフル装備）\n"
            "コピーライティング × Meta広告コンテキスト × リサーチ統合[/dim]",
            border_style="magenta",
        ))

        frameworks = load_prompt("frameworks.md")
        template = load_prompt("step5_wireframe.md")
        prompt = (
            template
            .replace("{competitor_research}", competitor_research)
            .replace("{cross_industry_research}", cross_industry_research)
            .replace("{who_what}", who_what)
            .replace("{ad_context}", ad_context)
            .replace("{frameworks}", frameworks)
        )
        if images:
            prompt += "\n\n【添付画像】参考画像もワイヤーフレーム設計に活用してください。"

        system = _build_system()

        return call_claude(system, prompt, use_web_search=False, max_tokens=MAX_TOKENS, images=images)
