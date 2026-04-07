"""
ディスカッションエージェント（Step6）
====================================
4人による3ラウンドディスカッションに特化。Meta広告主軸。
参照資料なし（ワイヤーフレーム結果のみで議論する）。Web検索なし。
"""

from pathlib import Path

from agents.base import call_claude, load_prompt, save_output, console, is_batch_mode
from rich.panel import Panel
from rich.markdown import Markdown
from rich.prompt import Prompt

TOTAL_STEPS = 7
MAX_TOKENS = 16000

# ラウンドテーマ（5→3ラウンドに集約）
ROUND_THEMES = [
    "ラウンド1: LP全体の方向性＆ファーストビュー — 本命案と対抗案、どちらが勝ち筋か？ターゲットのcustomer awarenessと合っているか？Meta広告の勝ちパターンとの整合性は？ビッグアイデアは何か？どのLead Typeが最適か？キャッチコピーは本当に刺さるか？Meta広告からの着地体験は最適か？",
    "ラウンド2: LP中盤〜CTA・オファー設計 — 証拠・実績・お客様の声のセクション。信頼性は十分か？行動経済学の観点から、どの心理トリガーを使うべきか？構成の順序は最適か？CTAの文言・配置・回数は適切か？オファーの強さは十分か？離脱ポイントはどこか？行動の障壁を下げるために何ができるか？Meta広告文→CTAの一貫性は？",
    "ラウンド3: 最終統合＆仕上げ＆フレームワーク破壊の検証 — 全体を通してThe Power of Oneが貫かれているか？競合との差別化は十分か？異業界から転用したアイデアは活きているか？【重要】ワイヤーフレームの「フレームワーク破壊箇所」は有効か？もっと大胆に破るべきか？「正しいLP」ではなく「売れるLP」になっているか？Meta広告経由のユーザー体験を踏まえた最終改善案をまとめる。LP目的の達成度を明確に評価し、不足があれば改善案を出すこと。",
]


def _build_system(who: str) -> str:
    """ディスカッション専用のsystem prompt"""
    return (
        "あなたはLP制作に関するディスカッションのファシリテーターです。\n"
        "以下の4名のメンバーになりきって、リアルな議論をシミュレーションしてください。\n\n"
        "【メンバー】\n"
        "A（マーケティング戦略担当）: マーケティング&行動経済学に精通。視座が高く経営目線。\n"
        "  行動経済学のフレームワーク（プロスペクト理論、アンカリング、フレーミング効果、\n"
        "  損失回避、社会的証明、希少性バイアス等）を具体的に適用する。\n"
        "B（LPコピーライター担当）: マーケティング&行動経済学に精通。具体のコピーが強い。\n"
        "  The Power of One、4U、ビッグアイデア、Lead Typeを実務で使いこなす。\n"
        "  具体的なコピー案や表現の改善を提案する。\n"
        "C（批判的思考担当）: 前提を覆し本質を見抜く。問いを設定する力が高い。\n"
        "  「本当にそうか？」と問いかけ、代替案も提示する。\n"
        f"D（ペルソナ代表）: ターゲット「{who}」ど真ん中の人物。\n"
        "  専門家に迎合しない。消費者目線の率直な感想・違和感を述べる。\n\n"
        "【⚠️ C（批判的思考）の発言ルール — 最重要】\n"
        "Cは他のメンバーの意見に簡単に同意してはいけません。以下を厳守：\n"
        "- 各ラウンドで最低2回は「本当にそうか？」「前提が間違っていないか？」と問い直すこと\n"
        "- 他メンバーが合意に向かっている時こそ、あえて反論・別の視点を出すこと\n"
        "- 代替案なき批判は禁止。必ず「こうしたほうがいいのでは？」をセットで提示すること\n"
        "- A・Bの専門的な意見にも「それは理論の話で、実際のユーザーはどうか？」と現実を突きつけること\n"
        "- 議論の中で見落とされているリスクや矛盾を積極的に指摘すること\n\n"
        "【重要ルール】\n"
        "- 1ラウンド = 7,000〜10,000文字で議論すること（短すぎNG）\n"
        "- 各メンバーの発言は「**A（マーケ戦略）:**」等で始める\n"
        "- 独り言の羅列ではなく、お互いの発言に反応・反論・補足すること\n"
        "- Dは専門家に流されず消費者目線を貫くこと\n"
        "- 行動経済学の具体的な理論・効果を引用すること\n"
        "- このLPはMeta広告（Facebook/Instagram）からの流入を主軸に議論すること\n"
        "- ラウンド末尾に「✅ 決まったこと」「🔄 次の議題」「⚠️ オーナー確認事項（あれば）」をまとめる\n"
        "- 【最重要】Who/What定義の冒頭にある【LP目的】を常に意識すること\n"
        "- 全ての議論は「LP目的を達成できるか？」で判断すること\n"
        "- ラウンド3では必ずLP目的の達成度を評価し、不足があれば改善案を出すこと\n\n"
        "日本語で回答してください。"
    )


class DiscussionAgent:
    """4人ディスカッション特化エージェント"""

    def _extract_conclusions(self, round_text: str, round_num: int) -> str:
        """ラウンドから「✅ 決まったこと」「🔄 次の議題」「⚠️ オーナー確認事項」だけ抽出する"""
        lines = round_text.split("\n")
        conclusion_lines = []
        capturing = False
        for line in lines:
            if any(marker in line for marker in ["✅", "🔄", "⚠️"]):
                capturing = True
            if capturing:
                conclusion_lines.append(line)
        if conclusion_lines:
            return f"## ラウンド{round_num}の結論\n\n" + "\n".join(conclusion_lines)
        # フォールバック: 末尾1000文字を使う
        return f"## ラウンド{round_num}の結論（末尾抜粋）\n\n{round_text[-1000:]}"

    def run(
        self,
        wireframe: str,
        who_what: str,
        competitor_research: str,
        cross_industry_research: str,
        ad_context: str,
        who: str,
        project_dir: Path,
    ) -> str:
        """Step6: 4人ディスカッション（3ラウンド）"""
        console.print(Panel(
            f"[bold red]Step 6/{TOTAL_STEPS}: 4人ディスカッション[/bold red]\n"
            "A（マーケ戦略）× B（コピーライター）× C（批判的思考）× D（ペルソナ）\n"
            f"{len(ROUND_THEMES)}ラウンド、各7,000〜10,000文字で議論します\n"
            "[dim]🧠 ディスカッションエージェントが担当[/dim]",
            border_style="red",
        ))

        template = load_prompt("step6_discussion.md")
        system = _build_system(who)

        all_rounds = []
        previous_rounds_text = ""

        for i in range(len(ROUND_THEMES)):
            round_num = i + 1
            console.print(f"\n[bold red]── ラウンド {round_num}/{len(ROUND_THEMES)} ──[/bold red]")

            prompt = (
                template
                .replace("{wireframe}", wireframe)
                .replace("{who_what}", who_what)
                .replace("{competitor_research}", competitor_research)
                .replace("{cross_industry_research}", cross_industry_research)
                .replace("{ad_context}", ad_context)
                .replace("{round_number}", str(round_num))
                .replace("{total_rounds}", str(len(ROUND_THEMES)))
                .replace("{previous_rounds}", previous_rounds_text if previous_rounds_text else "（初回ラウンドのため、前回の議論はありません）")
                .replace("{round_theme}", ROUND_THEMES[i])
            )

            result = call_claude(system, prompt, use_web_search=False, max_tokens=MAX_TOKENS)

            save_output(f"step6_ラウンド{round_num}.md", result, project_dir)
            all_rounds.append(f"## ラウンド{round_num}\n\n{result}")
            console.print(f"[green]ラウンド {round_num} 完了![/green]")

            # オーナー確認事項チェック
            if "⚠️ オーナー確認事項" in result:
                confirm_part = result.split("⚠️ オーナー確認事項")[-1][:500]
                if not any(skip in confirm_part[:50] for skip in ["なし", "特になし", "ありません"]):
                    if is_batch_mode():
                        console.print(f"[yellow][batch] オーナー確認事項あり（ラウンド{round_num}）— スキップ[/yellow]")
                    else:
                        console.print()
                        console.print(Panel("[bold red]⚠️ 重要な論点が出ました！[/bold red]", border_style="red"))
                        console.print(Markdown(f"⚠️ オーナー確認事項{confirm_part}"))

                        owner_input = Prompt.ask("[red]確認事項への回答（なければEnter）[/red]", default="")
                        if owner_input:
                            previous_rounds_text += f"\n\n### オーナーからの回答（ラウンド{round_num}後）\n{owner_input}"

            # 次ラウンドには結論のみ引き継ぐ（トークン圧迫対策）
            previous_rounds_text += "\n\n---\n\n" + self._extract_conclusions(result, round_num)

            if round_num < len(ROUND_THEMES):
                console.print(f"[dim]次のラウンドに進みます...[/dim]")

        full_discussion = "\n\n---\n\n".join(all_rounds)
        save_output("step6_ディスカッション全体.md", full_discussion, project_dir)

        # ── 結論サマリーを生成 ──
        console.print(f"\n[bold yellow]── 結論サマリー生成中 ──[/bold yellow]")
        summary = self._generate_summary(full_discussion)
        save_output("step6_結論サマリー.md", summary, project_dir)
        console.print("[green]結論サマリーを保存しました[/green]")

        return full_discussion, summary

    def _generate_summary(self, full_discussion: str) -> str:
        """3ラウンドの議論から結論サマリーを生成"""
        system = (
            "あなたは議論の要約のプロです。\n"
            "3ラウンドのディスカッション結果を、1ページ（2,000〜3,000文字）の結論サマリーにまとめてください。\n"
            "制作チームがこのサマリーだけ読めば、何を変えるべきかわかるようにすること。\n"
            "日本語で回答してください。"
        )

        prompt = (
            "## 3ラウンドのディスカッション全体\n\n"
            f"{full_discussion}\n\n"
            "---\n\n"
            "## 出力フォーマット（厳守）\n\n"
            "```\n"
            "# ディスカッション結論サマリー\n\n"
            "## 最終推奨案\n"
            "（本命案 / 対抗案 / ハイブリッド）\n"
            "選定理由: \n\n"
            "## ワイヤーフレーム修正指示（優先度順）\n"
            "1. 【必須修正】\n"
            "2. 【必須修正】\n"
            "3. 【推奨修正】\n"
            "4. ...\n\n"
            "## ファーストビューの最終方針\n"
            "- ヘッドコピーの方向性: \n"
            "- ビジュアルの方向性: \n"
            "- Meta広告経由の着地: \n\n"
            "## CTA・オファーの最終方針\n"
            "- CTA文言: \n"
            "- オファー内容: \n"
            "- 保証: \n\n"
            "## LP目的の達成度評価\n"
            "- 達成度（○/△/×）: \n"
            "- 不足している要素: \n"
            "- 追加すべき要素: \n\n"
            "## 4人の最終見解（一言ずつ）\n"
            "- A（マーケ戦略）: \n"
            "- B（コピーライター）: \n"
            "- C（批判的思考）: \n"
            "- D（ペルソナ）: \n"
            "```\n"
        )

        return call_claude(system, prompt, use_web_search=False, max_tokens=8000)
