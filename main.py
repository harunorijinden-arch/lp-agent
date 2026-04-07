"""
LP制作エージェント（v3 — 後戻り対応）
==============================
6つの専門エージェントが順番に仕事をする。main.pyは指揮者。
途中再開＆後戻り機能あり。

使い方:
  cd lp-agent
  uv run python main.py
"""

from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from dotenv import load_dotenv

from agents.base import (
    confirm_step, revise_with_feedback, save_output, GoBackRequest,
    set_batch_mode, is_batch_mode, save_unresolved_flags,
)
from agents.checkpoint import save_checkpoint, ask_resume, ask_import_past_results
from agents.knowledge import save_project_learning, get_relevant_knowledge
from agents import (
    ResearcherAgent,
    StrategistAgent,
    AdAnalystAgent,
    WireframeAgent,
    DiscussionAgent,
    FinalizerAgent,
)

load_dotenv()
console = Console()
OUTPUT_DIR = Path(__file__).parent / "output"
TOTAL_STEPS = 7


def gather_inputs() -> dict:
    """全ての初期入力を収集して返す（シンプル版）"""

    # ── LP目的 ──
    console.print(Panel(
        "[bold white on red] 最初に確認 [/bold white on red]\n\n"
        "今回のLP制作で、顧客にどのような状態になってほしいですか？\n"
        "（LPを見た人に最終的にどうなってほしいか）",
        border_style="red",
    ))
    console.print()
    console.print("[dim]例: 無料相談に申し込んでもらう → その先に、売上の不安から解放されてほしい[/dim]")
    lp_purpose = Prompt.ask("[red]LPの目的（顧客にどうなってほしいか）[/red]")
    console.print()

    # ── 基本情報 ──
    console.print("[bold]━━━ 基本情報 ━━━[/bold]")
    console.print()
    industry = Prompt.ask("[cyan]業界[/cyan]（例: 美容、不動産、SaaS、飲食）")
    product = Prompt.ask("[cyan]商材[/cyan]（例: 美容液、マンション、勤怠管理ツール）")
    console.print()

    # ── リサーチ用LP ──
    console.print("[bold]━━━ リサーチ用LP ━━━[/bold]")
    console.print()
    console.print("[dim]競合LP: このLPを起点に同業界をリサーチします[/dim]")
    competitor_url = Prompt.ask("[cyan]競合LP URL[/cyan]")
    console.print()
    console.print("[dim]別業界LP: このLPを起点に異業界をリサーチします[/dim]")
    cross_industry_url = Prompt.ask("[cyan]別業界LP URL[/cyan]")
    console.print()

    # ── Who（自由記述） ──
    console.print(Panel(
        "[bold yellow]━━━ Who（ターゲット）━━━[/bold yellow]\n\n"
        "お客さんのことを自由に教えてください。\n"
        "どんな人？ 何に悩んでる？ どうなりたい？ 思い込みは？\n"
        "思いつくまま書いてOK。ストラテジストAIが整理・深掘りします。",
        border_style="yellow",
    ))
    console.print()
    console.print("[dim]例: 35歳女性のマーケ担当。集客が伸びなくて焦ってる。[/dim]")
    console.print("[dim]    本当は「このままだと居場所がなくなる」って怖い。[/dim]")
    console.print("[dim]    LPは綺麗にデザインしないと売れないと思い込んでる。[/dim]")
    console.print("[dim]    安定してリードが入って、自信持って仕事したいと思ってる。[/dim]")
    console.print()
    console.print("[dim]複数行入力OK。入力完了したら空行でEnter[/dim]")
    who_lines = []
    while True:
        line = Prompt.ask("[yellow]Who[/yellow]", default="")
        if not line:
            break
        who_lines.append(line)
    who_text = "\n".join(who_lines)
    console.print()

    # ── What（自由記述） ──
    console.print(Panel(
        "[bold yellow]━━━ What（提供価値）━━━[/bold yellow]\n\n"
        "あなたの商品・サービスの強みを自由に教えてください。\n"
        "一番の売りは？ 使うとどんな気持ちに？ 競合との違いは？\n"
        "思いつくまま書いてOK。ストラテジストAIが整理・深掘りします。",
        border_style="yellow",
    ))
    console.print()
    console.print("[dim]例: AIが自動でLP構成を設計。専門知識なしでプロ品質のLPが作れる。[/dim]")
    console.print("[dim]    「もうLPで悩まなくていい」という安心感。[/dim]")
    console.print("[dim]    業界唯一のAI×コピーライティング統合。[/dim]")
    console.print()
    console.print("[dim]複数行入力OK。入力完了したら空行でEnter[/dim]")
    what_lines = []
    while True:
        line = Prompt.ask("[yellow]What[/yellow]", default="")
        if not line:
            break
        what_lines.append(line)
    what_text = "\n".join(what_lines)
    console.print()

    # ── Meta広告情報（任意・事前入力） ──
    console.print(Panel(
        "[bold blue]━━━ Meta広告情報（任意）━━━[/bold blue]\n\n"
        "Meta広告（Facebook/Instagram）の勝ちパターンがあれば、今のうちに入力できます。\n"
        "（後のStep4でも入力できるので、スキップしてもOK）",
        border_style="blue",
    ))
    console.print()
    if Confirm.ask("[blue]Meta広告情報を今入力しますか？[/blue]", default=False):
        console.print("[dim]勝ちパターンのクリエイティブ、広告文、訴求軸など[/dim]")
        console.print("[dim]複数行入力OK。入力完了したら空行でEnter[/dim]")
        console.print()
        meta_lines = []
        while True:
            line = Prompt.ask("[blue]Meta広告[/blue]", default="")
            if not line:
                break
            meta_lines.append(line)
        ad_info_pre = "## Meta広告（Facebook/Instagram）\n" + ("\n".join(meta_lines) if meta_lines else "（情報なし）")
    else:
        ad_info_pre = ""
    console.print()

    # 構造化
    who = f"【LP目的】{lp_purpose}\n\n【ターゲット情報（オーナー自由記述）】\n{who_text}"
    what = f"【提供価値（オーナー自由記述）】\n{what_text}"

    return {
        "lp_purpose": lp_purpose,
        "industry": industry,
        "product": product,
        "competitor_url": competitor_url,
        "cross_industry_url": cross_industry_url,
        "who": who,
        "what": what,
        "ad_info_pre": ad_info_pre,
    }


# ──────────────────────────────────────────────────────────
# 各ステップの実行関数
# ──────────────────────────────────────────────────────────

def _check_unresolved_flags(result: str) -> list[str]:
    """未解決の確認事項だけを抽出する（見出しや「なし」は除外）"""
    flags = []
    in_confirm_section = False
    for raw_line in result.splitlines():
        line = raw_line.strip()
        if "⚠️ 確認が必要な点" in line:
            in_confirm_section = True
            continue
        if in_confirm_section:
            if not line:
                continue
            if (line.startswith("## ") or line.startswith("■ ")) and "⚠️" not in line:
                break
            if "なし" in line or "解決済み" in line:
                continue
            if line.startswith(("-", "*", "1.", "2.", "3.")) or line.startswith("Q:"):
                flags.append(line)
    return flags


def _check_insufficient_info(result: str) -> list[str]:
    """不足情報セクションから未解決の項目を抽出する"""
    flags = []
    in_section = False
    for raw_line in result.splitlines():
        line = raw_line.strip()
        if "⚠️ 不足情報" in line:
            in_section = True
            continue
        if in_section:
            if not line:
                continue
            if (line.startswith("## ") or line.startswith("■ ")) and "⚠️" not in line:
                break
            if "なし" in line:
                continue
            if line.startswith(("-", "*", "1.", "2.", "3.")):
                flags.append(line)
    return flags


def _resolve_flags(result: str, flags: list[str], system_role: str, project_dir, filename: str, gate_type: str = "confirm") -> str:
    """未解決フラグをユーザーに確認して解決し、結果を更新する"""
    if gate_type == "insufficient":
        title = "🚫 不足情報あり — 次のステップに進めません"
        desc = "分析に必要な情報が不足しています。\n以下に回答してください。全て解決するまで次に進めません。"
    else:
        title = "🚫 確認事項あり — 次のステップに進めません"
        desc = "確認が必要な項目があります。\n以下に回答してください。全て解決するまで次に進めません。"

    console.print()
    console.print(Panel(
        f"[bold red]{title}[/bold red]\n\n{desc}",
        border_style="red",
    ))
    console.print()

    answers = []
    for i, flag in enumerate(flags, 1):
        console.print(f"  [red]{i}. {flag}[/red]")
        answer = Prompt.ask(f"  [yellow]→ 回答[/yellow]")
        answers.append(f"Q: {flag}\nA: {answer}")
        console.print()

    # 回答を反映して再生成
    feedback = "以下のオーナー確認事項に対する回答を反映してください。⚠️マークは解決済みとして削除してください。\n\n" + "\n\n".join(answers)
    updated = revise_with_feedback(system_role, result, feedback)
    save_output(filename, updated, project_dir)
    return updated


def _run_step1(results, inputs, industry, product, who, project_dir):
    """Step 1: Who/What深掘り — 設計ブリーフ確定フェーズ"""
    # 過去のナレッジがあれば取得してWhatに付加
    past_knowledge = get_relevant_knowledge(industry)
    what_with_knowledge = inputs["what"]
    if past_knowledge:
        what_with_knowledge += f"\n\n---\n\n{past_knowledge}"
        console.print("[dim]📚 過去のナレッジDBから関連知見を取得しました[/dim]")

    strategist = StrategistAgent()
    results["result1"] = strategist.run(industry, product, who, what_with_knowledge)
    save_output("step1_Who_What定義.md", results["result1"], project_dir)

    # ⚠️ 確認が必要フラグのチェック（未解決なら次に進めない）
    flags = _check_unresolved_flags(results["result1"])
    if flags:
        if is_batch_mode():
            save_unresolved_flags(flags, "Step 1: Who/What", project_dir)
        else:
            while flags:
                results["result1"] = _resolve_flags(
                    results["result1"], flags,
                    "あなたはターゲット分析のプロです。日本語で回答。",
                    project_dir, "step1_Who_What定義.md")
                flags = _check_unresolved_flags(results["result1"])

    feedback = confirm_step("Step 1: Who/What深掘り（設計ブリーフ確定）", results["result1"], current_step=1)
    if feedback:
        results["result1"] = revise_with_feedback(
            "あなたはターゲット分析のプロです。日本語で回答。", results["result1"], feedback)
        save_output("step1_Who_What定義.md", results["result1"], project_dir)


def _run_step2(results, inputs, industry, product, project_dir):
    """Step 2: 競合LPリサーチ"""
    researcher = ResearcherAgent()
    results["result2"] = researcher.run_competitor(
        industry, product, inputs["competitor_url"], who_what=results["result1"])
    save_output("step2_競合LPリサーチ.md", results["result2"], project_dir)

    feedback = confirm_step("Step 2: 競合LPリサーチ", results["result2"], current_step=2)
    if feedback:
        results["result2"] = revise_with_feedback(
            "あなたはLP構成分析のプロです。日本語で回答。", results["result2"], feedback, use_web_search=True)
        save_output("step2_競合LPリサーチ.md", results["result2"], project_dir)


def _run_step3(results, inputs, industry, project_dir):
    """Step 3: 別業界LPリサーチ"""
    researcher = ResearcherAgent()
    results["result3"] = researcher.run_cross_industry(
        industry, inputs["cross_industry_url"], who_what=results["result1"])
    save_output("step3_別業界LPリサーチ.md", results["result3"], project_dir)

    feedback = confirm_step("Step 3: 別業界LPリサーチ", results["result3"], current_step=3)
    if feedback:
        results["result3"] = revise_with_feedback(
            "あなたはLP構成分析のプロです。日本語で回答。", results["result3"], feedback, use_web_search=True)
        save_output("step3_別業界LPリサーチ.md", results["result3"], project_dir)


def _run_step4(results, inputs, project_dir, is_resumed):
    """Step 4: 広告コンテキスト分析"""
    ad_info_pre = inputs.get("ad_info_pre", "") if not is_resumed else ""
    if is_batch_mode():
        # バッチモード: YAMLの事前入力を使う
        ad_info = ad_info_pre if ad_info_pre else "## Meta広告（Facebook/Instagram）\n（情報なし）"
        console.print(Panel(
            f"[bold blue]Step 4/{TOTAL_STEPS}: 広告コンテキスト分析[/bold blue]\n"
            "[dim][batch] 設定ファイルの広告情報を使用[/dim]",
            border_style="blue",
        ))
    elif ad_info_pre:
        console.print(Panel(
            f"[bold blue]Step 4/{TOTAL_STEPS}: 広告コンテキスト分析[/bold blue]\n"
            "事前入力された広告情報を使用します",
            border_style="blue",
        ))
        ad_info = ad_info_pre
    else:
        console.print(Panel(
            f"[bold blue]Step 4/{TOTAL_STEPS}: Meta広告情報の入力[/bold blue]\n"
            "Meta広告（Facebook/Instagram）の勝ちパターンを共有してください",
            border_style="blue",
        ))
        console.print()

        console.print("[bold]━━━ Meta広告（Facebook/Instagram）情報 ━━━[/bold]")
        console.print("[dim]勝ちパターンのクリエイティブの切り口、広告文、訴求軸など[/dim]")
        console.print("[dim]複数行入力OK。入力完了したら空行でEnter[/dim]")
        meta_lines = []
        while True:
            line = Prompt.ask("[blue]Meta広告[/blue]", default="")
            if not line:
                break
            meta_lines.append(line)
        console.print()

        ad_info = "## Meta広告（Facebook/Instagram）\n" + ("\n".join(meta_lines) if meta_lines else "（情報なし）")

    ad_analyst = AdAnalystAgent()
    results["result4"] = ad_analyst.run(results["result1"], ad_info)
    save_output("step4_広告コンテキスト.md", results["result4"], project_dir)

    # 不足情報ゲート（Meta広告情報が足りなければ止める）
    flags = _check_insufficient_info(results["result4"])
    if flags:
        if is_batch_mode():
            save_unresolved_flags(flags, "Step 4: 広告コンテキスト", project_dir, gate_type="insufficient")
        else:
            while flags:
                results["result4"] = _resolve_flags(
                    results["result4"], flags,
                    "あなたはMeta広告分析のプロです。日本語で回答。",
                    project_dir, "step4_広告コンテキスト.md",
                    gate_type="insufficient")
                flags = _check_insufficient_info(results["result4"])

    feedback = confirm_step("Step 4: Meta広告コンテキスト分析", results["result4"], current_step=4)
    if feedback:
        results["result4"] = revise_with_feedback(
            "あなたはMeta広告分析のプロです。日本語で回答。", results["result4"], feedback)
        save_output("step4_広告コンテキスト.md", results["result4"], project_dir)


def _run_step5(results, lp_purpose, project_dir):
    """Step 5: ワイヤーフレーム提案"""
    wireframer = WireframeAgent()
    results["result5"] = wireframer.run(
        results["result2"], results["result3"], results["result1"], results["result4"])
    save_output("step5_ワイヤーフレーム提案.md", results["result5"], project_dir)

    feedback = confirm_step("Step 5: ワイヤーフレーム提案", results["result5"], current_step=5)
    if feedback:
        results["result5"] = revise_with_feedback(
            "あなたはLP設計のプロです。日本語で回答。", results["result5"], feedback, max_tokens=32000)
        save_output("step5_ワイヤーフレーム提案.md", results["result5"], project_dir)

    # LP目的達成チェック
    if not is_batch_mode():
        console.print(Panel(
            "[bold white on red] LP目的の達成チェック（ワイヤーフレーム時点） [/bold white on red]\n\n"
            f"最初に設定したLPの目的:\n[bold]{lp_purpose}[/bold]\n\n"
            "このワイヤーフレームで、上記の目的は達成できそうですか？",
            border_style="red",
        ))
        if not Confirm.ask("[red]LP目的は達成できそうですか？[/red]"):
            pf = Prompt.ask("[red]どこが足りない / 修正すべき点を教えてください[/red]")
            results["result5"] = revise_with_feedback(
                f"あなたはLP設計のプロです。【LP目的】{lp_purpose}　この目的が達成できるよう修正。日本語で回答。",
                results["result5"], pf, max_tokens=32000)
            save_output("step5_ワイヤーフレーム提案.md", results["result5"], project_dir)


def _run_step6(results, who, project_dir):
    """Step 6: 4人ディスカッション"""
    discussion = DiscussionAgent()
    results["result6"], results["summary"] = discussion.run(
        results["result5"], results["result1"], results["result2"],
        results["result3"], results["result4"], who, project_dir)


def _run_step7(results, lp_purpose, who, project_dir):
    """Step 7: 最終ワイヤーフレーム生成"""
    finalizer = FinalizerAgent()
    final_wireframe = finalizer.run(
        results["result5"], results["result6"], results["summary"], who)
    save_output("step7_最終ワイヤーフレーム.md", final_wireframe, project_dir)

    # LP目的達成 最終確認
    if not is_batch_mode():
        console.print(Panel(
            "[bold white on red] 最終確認: LP目的の達成チェック [/bold white on red]\n\n"
            f"最初に設定したLPの目的:\n[bold]{lp_purpose}[/bold]\n\n"
            "ディスカッション＆最終ワイヤーフレームを経て、\n"
            "このLPで顧客が上記の状態になれると思いますか？",
            border_style="red",
        ))
        if not Confirm.ask("[red]LP目的は最終的に達成できそうですか？[/red]"):
            ff = Prompt.ask("[red]最終的にどこを修正すべきか教えてください[/red]")
            final_wireframe = revise_with_feedback(
                f"あなたはLP設計のファイナライザーです。【LP目的】{lp_purpose}　日本語で回答。",
                final_wireframe, ff, max_tokens=32000)
            save_output("step7_最終ワイヤーフレーム.md", final_wireframe, project_dir)

    console.print("[green]LP目的の達成を確認しました！[/green]\n")


# ──────────────────────────────────────────────────────────
# メインエントリーポイント
# ──────────────────────────────────────────────────────────

def main():
    console.print(Panel.fit(
        "[bold white on blue] LP制作エージェント（v3 — 後戻り対応） [/bold white on blue]\n\n"
        "6つの専門エージェントがリレー形式で仕事をします：\n"
        "  🎯 ストラテジスト → 🔍 リサーチャー → 📊 広告アナリスト\n"
        "  → 📐 ワイヤーフレーマー → 💬 ディスカッション → 🏁 ファイナライザー\n\n"
        "💡 各ステップで「ok / 修正 / 戻る」を選べます",
        border_style="blue",
    ))
    console.print()

    # ── 途中再開チェック ──
    resume_dir, checkpoint = ask_resume(OUTPUT_DIR)
    is_resumed = bool(resume_dir and checkpoint)

    if is_resumed:
        project_dir = resume_dir
        current_step = checkpoint["last_step"] + 1
        d = checkpoint["data"]
        results = {
            "result1": d.get("result1", ""), "result2": d.get("result2", ""),
            "result3": d.get("result3", ""), "result4": d.get("result4", ""),
            "result5": d.get("result5", ""), "result6": "",
            "summary": d.get("summary", ""),
        }
        inputs = {
            "lp_purpose": d.get("lp_purpose", ""), "industry": d.get("industry", ""),
            "product": d.get("product", ""), "who": d.get("who", ""),
            "what": d.get("what", ""),
            "competitor_url": d.get("competitor_url", ""),
            "cross_industry_url": d.get("cross_industry_url", ""),
            "ad_info_pre": d.get("ad_info_pre", ""),
        }
        console.print(f"[green]Step {current_step} から再開します！[/green]\n")
    else:
        current_step = 1
        results = {
            "result1": "", "result2": "", "result3": "",
            "result4": "", "result5": "", "result6": "", "summary": "",
        }

        # 過去の結果を流用するか確認
        imported = ask_import_past_results(OUTPUT_DIR)
        skip_steps = imported.pop("_skip_steps", set())
        results.update(imported)

        inputs = gather_inputs()

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        project_dir = OUTPUT_DIR / f"{timestamp}_{inputs['industry']}_{inputs['product']}"
        project_dir.mkdir(parents=True, exist_ok=True)

        save_checkpoint(project_dir, 0, {
            "lp_purpose": inputs["lp_purpose"], "industry": inputs["industry"],
            "product": inputs["product"],
            "competitor_url": inputs["competitor_url"],
            "cross_industry_url": inputs["cross_industry_url"],
            "who": inputs["who"], "what": inputs["what"],
            "ad_info_pre": inputs.get("ad_info_pre", ""),
        })

    console.print(f"[dim]出力先: {project_dir}[/dim]\n")

    lp_purpose = inputs["lp_purpose"]
    industry = inputs["industry"]
    product = inputs["product"]
    who = inputs["who"]

    # スキップ対象ステップ（過去結果の流用時のみ）
    if is_resumed:
        skip_steps = set()

    # ══════════════════════════════════════════════════════
    # メインループ（後戻り・スキップ対応）
    # ══════════════════════════════════════════════════════
    while current_step <= 7:
        # スキップ対象ならスキップ
        if current_step in skip_steps:
            console.print(f"[dim]Step {current_step} は過去の結果を流用 → スキップ[/dim]")
            save_checkpoint(project_dir, current_step, results)
            current_step += 1
            continue

        try:
            if current_step == 1:
                _run_step1(results, inputs, industry, product, who, project_dir)
            elif current_step == 2:
                _run_step2(results, inputs, industry, product, project_dir)
            elif current_step == 3:
                _run_step3(results, inputs, industry, project_dir)
            elif current_step == 4:
                _run_step4(results, inputs, project_dir, is_resumed)
            elif current_step == 5:
                _run_step5(results, lp_purpose, project_dir)
            elif current_step == 6:
                _run_step6(results, who, project_dir)
            elif current_step == 7:
                _run_step7(results, lp_purpose, who, project_dir)

            save_checkpoint(project_dir, current_step, results)
            current_step += 1

        except GoBackRequest as e:
            current_step = e.target_step
            console.print(f"\n[bold yellow]⏪ Step {current_step} に戻ります...[/bold yellow]\n")

    # ══════════════════════════════════════════════════════
    # ナレッジ抽出（案件を超えた学習の蓄積）
    # ══════════════════════════════════════════════════════
    save_project_learning(results, industry, product)

    # ══════════════════════════════════════════════════════
    # 完了
    # ══════════════════════════════════════════════════════
    console.print(Panel.fit(
        f"[bold green]全ステップ完了！[/bold green]\n\n"
        f"成果物は以下に保存されています:\n"
        f"[cyan]{project_dir}[/cyan]\n\n"
        f"  🎯 step1_Who_What定義.md ← 思考の構造化\n"
        f"  🔍 step2_競合LPリサーチ.md\n"
        f"  🔍 step3_別業界LPリサーチ.md\n"
        f"  📊 step4_広告コンテキスト.md\n"
        f"  📐 step5_ワイヤーフレーム提案.md\n"
        f"  💬 step6_ラウンド1〜3.md + 結論サマリー.md\n"
        f"  🏁 step7_最終ワイヤーフレーム.md ← 完成品",
        border_style="green",
    ))


# ──────────────────────────────────────────────────────────
# バッチモード（非対話）エントリーポイント
# ──────────────────────────────────────────────────────────

STEP_MAP = {
    1: ("step1_Who_What定義.md", "あなたはターゲット分析のプロです。日本語で回答。"),
    2: ("step2_競合LPリサーチ.md", "あなたはLP構成分析のプロです。日本語で回答。"),
    3: ("step3_別業界LPリサーチ.md", "あなたはLP構成分析のプロです。日本語で回答。"),
    4: ("step4_広告コンテキスト.md", "あなたはMeta広告分析のプロです。日本語で回答。"),
    5: ("step5_ワイヤーフレーム提案.md", "あなたはLP設計のプロです。日本語で回答。"),
    6: ("step6_ディスカッション全体.md", "あなたはLP制作ディスカッションのプロです。日本語で回答。"),
    7: ("step7_最終ワイヤーフレーム.md", "あなたはLP設計のファイナライザーです。日本語で回答。"),
}


def _load_results_from_checkpoint(project_dir: Path) -> dict:
    """既存プロジェクトのcheckpointからresultsを復元"""
    import json
    cp_file = project_dir / "checkpoint.json"
    if cp_file.exists():
        cp = json.loads(cp_file.read_text(encoding="utf-8"))
        d = cp.get("data", {})
        return {
            "result1": d.get("result1", ""),
            "result2": d.get("result2", ""),
            "result3": d.get("result3", ""),
            "result4": d.get("result4", ""),
            "result5": d.get("result5", ""),
            "result6": "",
            "summary": d.get("summary", ""),
        }
    return {
        "result1": "", "result2": "", "result3": "",
        "result4": "", "result5": "", "result6": "", "summary": "",
    }


def main_batch(args):
    """非対話モードのメインエントリーポイント"""
    from config_loader import load_config

    set_batch_mode(True)

    inputs = load_config(args.config)

    console.print(Panel.fit(
        "[bold white on blue] LP制作エージェント（バッチモード） [/bold white on blue]\n\n"
        f"業界: {inputs['industry']} / 商材: {inputs['product']}\n"
        f"LP目的: {inputs['lp_purpose']}",
        border_style="blue",
    ))
    console.print()

    # プロジェクトディレクトリ
    if args.project_dir:
        project_dir = Path(args.project_dir)
        if not project_dir.exists():
            console.print(f"[red]エラー: プロジェクトディレクトリが見つかりません: {args.project_dir}[/red]")
            return
        results = _load_results_from_checkpoint(project_dir)
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        project_dir = OUTPUT_DIR / f"{timestamp}_{inputs['industry']}_{inputs['product']}"
        project_dir.mkdir(parents=True, exist_ok=True)
        results = {
            "result1": "", "result2": "", "result3": "",
            "result4": "", "result5": "", "result6": "", "summary": "",
        }

    console.print(f"[dim]出力先: {project_dir}[/dim]\n")

    # 実行するステップ範囲
    if args.step:
        step_range = [args.step]
    elif args.from_step:
        step_range = list(range(args.from_step, 8))
    else:
        step_range = list(range(1, 8))

    lp_purpose = inputs["lp_purpose"]
    industry = inputs["industry"]
    product = inputs["product"]
    who = inputs["who"]

    # 初回チェックポイント保存
    save_checkpoint(project_dir, 0, {
        "lp_purpose": lp_purpose, "industry": industry,
        "product": product,
        "competitor_url": inputs["competitor_url"],
        "cross_industry_url": inputs["cross_industry_url"],
        "who": who, "what": inputs["what"],
        "ad_info_pre": inputs.get("ad_info_pre", ""),
    })

    for current_step in step_range:
        console.print(f"\n[bold]{'='*50}[/bold]")
        console.print(f"[bold] Step {current_step}/7 実行中...[/bold]")
        console.print(f"[bold]{'='*50}[/bold]\n")

        if current_step == 1:
            _run_step1(results, inputs, industry, product, who, project_dir)
        elif current_step == 2:
            _run_step2(results, inputs, industry, product, project_dir)
        elif current_step == 3:
            _run_step3(results, inputs, industry, project_dir)
        elif current_step == 4:
            _run_step4(results, inputs, project_dir, False)
        elif current_step == 5:
            _run_step5(results, lp_purpose, project_dir)
        elif current_step == 6:
            _run_step6(results, who, project_dir)
        elif current_step == 7:
            _run_step7(results, lp_purpose, who, project_dir)

        save_checkpoint(project_dir, current_step, {
            **{k: v for k, v in inputs.items()},
            **results,
        })
        console.print(f"[green]Step {current_step} 完了！[/green]")

    # ナレッジ抽出（最終ステップまで到達した場合のみ）
    if 7 in step_range and results.get("summary"):
        save_project_learning(results, industry, product)

    console.print(Panel.fit(
        f"[bold green]完了！[/bold green]\n\n"
        f"成果物: [cyan]{project_dir}[/cyan]",
        border_style="green",
    ))


def run_revise(args):
    """指定ステップの結果を修正"""
    set_batch_mode(True)

    project_dir = Path(args.project_dir)
    step_num = args.revise
    feedback = args.feedback

    if step_num not in STEP_MAP:
        console.print(f"[red]エラー: Step {step_num} は修正対象外です[/red]")
        return

    filename, system_role = STEP_MAP[step_num]
    filepath = project_dir / filename

    if not filepath.exists():
        console.print(f"[red]エラー: {filepath} が見つかりません。先にそのステップを実行してください。[/red]")
        return

    console.print(Panel(
        f"[bold yellow]Step {step_num} を修正中...[/bold yellow]\n"
        f"ファイル: {filename}\n"
        f"フィードバック: {feedback}",
        border_style="yellow",
    ))

    original = filepath.read_text(encoding="utf-8")

    # ワイヤーフレーム系は大きめのトークン
    max_tokens = 32000 if step_num in (5, 7) else 16000
    # リサーチ系はWeb検索あり
    use_web_search = step_num in (2, 3)

    revised = revise_with_feedback(
        system_role, original, feedback,
        use_web_search=use_web_search, max_tokens=max_tokens,
    )
    save_output(filename, revised, project_dir)

    # チェックポイントも更新
    results = _load_results_from_checkpoint(project_dir)
    result_key = f"result{step_num}" if step_num <= 5 else ("summary" if step_num == 6 else f"result{step_num}")
    if step_num <= 5:
        results[f"result{step_num}"] = revised
    save_checkpoint(project_dir, step_num, results)

    console.print(f"[green]Step {step_num} の修正完了！ → {filename}[/green]")


# ──────────────────────────────────────────────────────────
# エントリーポイント
# ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    from cli import parse_args

    args = parse_args()

    if args.revise is not None:
        run_revise(args)
    elif args.config:
        main_batch(args)
    else:
        main()
