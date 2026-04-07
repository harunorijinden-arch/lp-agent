"""
LP制作エージェント — Streamlit Web UI
====================================
ブラウザで7ステップのLP制作を進められるUI。

起動: uv run streamlit run app.py
"""

import json
from datetime import datetime
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

from agents.base import (
    set_batch_mode, call_claude, revise_with_feedback, save_output,
)
from agents.checkpoint import save_checkpoint
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
set_batch_mode(True)

OUTPUT_DIR = Path(__file__).parent / "output"

# ── ステップ定義 ──
STEPS = {
    1: {"name": "Who/What深掘り", "icon": "🎯", "desc": "ターゲットと提供価値を深掘りして設計ブリーフを作る"},
    2: {"name": "競合LPリサーチ", "icon": "🔍", "desc": "同業界の競合LPを分析する"},
    3: {"name": "別業界LPリサーチ", "icon": "🔍", "desc": "異業界LPからヒントを見つける"},
    4: {"name": "広告コンテキスト分析", "icon": "📊", "desc": "Meta広告の勝ちパターンを分析する"},
    5: {"name": "ワイヤーフレーム提案", "icon": "📐", "desc": "LP構成を2案設計する"},
    6: {"name": "4人ディスカッション", "icon": "💬", "desc": "AI4人で議論して改善する"},
    7: {"name": "最終ワイヤーフレーム", "icon": "🏁", "desc": "ディスカッション結果を反映した完成品"},
}

REVISE_ROLES = {
    1: "あなたはターゲット分析のプロです。日本語で回答。",
    2: "あなたはLP構成分析のプロです。日本語で回答。",
    3: "あなたはLP構成分析のプロです。日本語で回答。",
    4: "あなたはMeta広告分析のプロです。日本語で回答。",
    5: "あなたはLP設計のプロです。日本語で回答。",
    6: "あなたはLP制作ディスカッションのプロです。日本語で回答。",
    7: "あなたはLP設計のファイナライザーです。日本語で回答。",
}

# 画像を使うステップ（これらのステップにアップロード画像を渡す）
IMAGE_STEPS = {1, 2, 3, 4, 5}


# ──────────────────────────────────────────────────────────
# session_state 初期化
# ──────────────────────────────────────────────────────────

def init_state():
    defaults = {
        "current_step": 0,  # 0 = 未開始
        "results": {f"result{i}": "" for i in range(1, 8)},
        "summary": "",
        "inputs": None,
        "project_dir": None,
        "running": False,
        "images": [],  # アップロード画像のバイトデータリスト
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


init_state()


def get_uploaded_images() -> list[bytes]:
    """session_stateから画像バイトデータのリストを取得"""
    return st.session_state.get("images", [])


# ──────────────────────────────────────────────────────────
# ステップ実行関数
# ──────────────────────────────────────────────────────────

def run_step(step_num: int):
    """指定ステップを実行"""
    inp = st.session_state.inputs
    res = st.session_state.results
    pd = st.session_state.project_dir

    # 画像対応ステップならアップロード画像を取得
    images = get_uploaded_images() if step_num in IMAGE_STEPS else None

    if step_num == 1:
        past_knowledge = get_relevant_knowledge(inp["industry"])
        what_with_knowledge = inp["what"]
        if past_knowledge:
            what_with_knowledge += f"\n\n---\n\n{past_knowledge}"
        agent = StrategistAgent()
        res["result1"] = agent.run(
            inp["industry"], inp["product"], inp["who"], what_with_knowledge,
            images=images)
        save_output("step1_Who_What定義.md", res["result1"], pd)

    elif step_num == 2:
        agent = ResearcherAgent()
        res["result2"] = agent.run_competitor(
            inp["industry"], inp["product"], inp["competitor_url"],
            who_what=res["result1"], images=images)
        save_output("step2_競合LPリサーチ.md", res["result2"], pd)

    elif step_num == 3:
        agent = ResearcherAgent()
        res["result3"] = agent.run_cross_industry(
            inp["industry"], inp["cross_industry_url"],
            who_what=res["result1"], images=images)
        save_output("step3_別業界LPリサーチ.md", res["result3"], pd)

    elif step_num == 4:
        ad_info = inp.get("ad_info_pre", "") or "## Meta広告（Facebook/Instagram）\n（情報なし）"
        agent = AdAnalystAgent()
        res["result4"] = agent.run(res["result1"], ad_info, images=images)
        save_output("step4_広告コンテキスト.md", res["result4"], pd)

    elif step_num == 5:
        agent = WireframeAgent()
        res["result5"] = agent.run(
            res["result2"], res["result3"], res["result1"], res["result4"],
            images=images)
        save_output("step5_ワイヤーフレーム提案.md", res["result5"], pd)

    elif step_num == 6:
        agent = DiscussionAgent()
        full_discussion, summary = agent.run(
            res["result5"], res["result1"], res["result2"],
            res["result3"], res["result4"], inp["who"], pd)
        res["result6"] = full_discussion
        st.session_state.summary = summary

    elif step_num == 7:
        agent = FinalizerAgent()
        final = agent.run(res["result5"], res["result6"], st.session_state.summary, inp["who"])
        res["result7"] = final
        save_output("step7_最終ワイヤーフレーム.md", final, pd)
        save_project_learning(
            {**res, "summary": st.session_state.summary},
            inp["industry"], inp["product"])

    # チェックポイント保存
    save_checkpoint(pd, step_num, {**inp, **res, "summary": st.session_state.summary})


def get_result_for_step(step_num: int) -> str:
    """ステップの結果テキストを取得"""
    if step_num <= 5:
        return st.session_state.results.get(f"result{step_num}", "")
    elif step_num == 6:
        return st.session_state.results.get("result6", "")
    else:
        return st.session_state.results.get("result7", "")


# ──────────────────────────────────────────────────────────
# 過去プロジェクト読み込み
# ──────────────────────────────────────────────────────────

def list_projects() -> list[Path]:
    """output/ 内のプロジェクトフォルダ一覧（新しい順）"""
    if not OUTPUT_DIR.exists():
        return []
    dirs = [d for d in OUTPUT_DIR.iterdir() if d.is_dir() and (d / "checkpoint.json").exists()]
    dirs.sort(key=lambda d: d.name, reverse=True)
    return dirs


def load_project(project_dir: Path):
    """既存プロジェクトを読み込んでsession_stateに復元"""
    cp_file = project_dir / "checkpoint.json"
    cp = json.loads(cp_file.read_text(encoding="utf-8"))
    d = cp.get("data", {})

    st.session_state.project_dir = project_dir
    st.session_state.current_step = cp.get("last_step", 0)
    st.session_state.inputs = {
        "lp_purpose": d.get("lp_purpose", ""),
        "industry": d.get("industry", ""),
        "product": d.get("product", ""),
        "competitor_url": d.get("competitor_url", ""),
        "cross_industry_url": d.get("cross_industry_url", ""),
        "who": d.get("who", ""),
        "what": d.get("what", ""),
        "ad_info_pre": d.get("ad_info_pre", ""),
    }
    st.session_state.results = {
        "result1": d.get("result1", ""),
        "result2": d.get("result2", ""),
        "result3": d.get("result3", ""),
        "result4": d.get("result4", ""),
        "result5": d.get("result5", ""),
        "result6": d.get("result6", ""),
        "result7": d.get("result7", ""),
    }
    st.session_state.summary = d.get("summary", "")


# ──────────────────────────────────────────────────────────
# UI
# ──────────────────────────────────────────────────────────

st.set_page_config(page_title="LP制作エージェント", page_icon="🚀", layout="wide")
st.title("🚀 LP制作エージェント")

# ════════════════════════════════════════════
# サイドバー
# ════════════════════════════════════════════

with st.sidebar:
    st.header("📝 案件情報")

    # 過去プロジェクト読み込み
    projects = list_projects()
    if projects:
        st.subheader("📂 過去のプロジェクト")
        project_names = ["（新規作成）"] + [p.name for p in projects]
        selected = st.selectbox("プロジェクトを選択", project_names)
        if selected != "（新規作成）":
            if st.button("このプロジェクトを読み込む"):
                proj_path = OUTPUT_DIR / selected
                load_project(proj_path)
                st.rerun()

    st.divider()

    # 新規入力フォーム or 進行中表示
    if st.session_state.inputs and st.session_state.current_step > 0:
        inp = st.session_state.inputs
        st.success(f"**{inp['industry']}** / {inp['product']}")
        st.caption(f"LP目的: {inp['lp_purpose']}")
        st.caption(f"出力先: {st.session_state.project_dir}")

        # 進捗バー
        progress = st.session_state.current_step / 7
        st.progress(progress, text=f"Step {st.session_state.current_step}/7 完了")
    else:
        with st.form("input_form"):
            lp_purpose = st.text_input("LP目的 *", placeholder="例: 無料相談に申し込んでもらう")
            industry = st.text_input("業界 *", placeholder="例: 美容、不動産、SaaS")
            product = st.text_input("商材 *", placeholder="例: 美容液、マンション、勤怠管理ツール")
            competitor_url = st.text_input("競合LP URL *", placeholder="https://...")
            cross_industry_url = st.text_input("別業界LP URL *", placeholder="https://...")
            who = st.text_area("ターゲット情報 (Who) *",
                placeholder="どんな人？何に悩んでる？どうなりたい？思い込みは？",
                height=120)
            what = st.text_area("提供価値 (What) *",
                placeholder="一番の売りは？使うとどんな気持ちに？競合との違いは？",
                height=120)
            meta_ad_info = st.text_area("Meta広告情報（任意）",
                placeholder="勝ちパターンのクリエイティブ、広告文、訴求軸など",
                height=80)

            submitted = st.form_submit_button("🚀 プロジェクト開始", use_container_width=True)

            if submitted:
                # バリデーション
                missing = []
                if not lp_purpose: missing.append("LP目的")
                if not industry: missing.append("業界")
                if not product: missing.append("商材")
                if not competitor_url: missing.append("競合LP URL")
                if not cross_industry_url: missing.append("別業界LP URL")
                if not who: missing.append("ターゲット情報")
                if not what: missing.append("提供価値")

                if missing:
                    st.error(f"以下を入力してください: {', '.join(missing)}")
                else:
                    # inputs構築（gather_inputs()と同じ形）
                    who_formatted = f"【LP目的】{lp_purpose}\n\n【ターゲット情報（オーナー自由記述）】\n{who}"
                    what_formatted = f"【提供価値（オーナー自由記述）】\n{what}"
                    ad_info_pre = f"## Meta広告（Facebook/Instagram）\n{meta_ad_info}" if meta_ad_info else ""

                    st.session_state.inputs = {
                        "lp_purpose": lp_purpose,
                        "industry": industry,
                        "product": product,
                        "competitor_url": competitor_url,
                        "cross_industry_url": cross_industry_url,
                        "who": who_formatted,
                        "what": what_formatted,
                        "ad_info_pre": ad_info_pre,
                    }

                    # プロジェクトディレクトリ作成
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    pd = OUTPUT_DIR / f"{timestamp}_{industry}_{product}"
                    pd.mkdir(parents=True, exist_ok=True)
                    st.session_state.project_dir = pd
                    st.session_state.current_step = 0

                    # 初回チェックポイント
                    save_checkpoint(pd, 0, st.session_state.inputs)
                    st.rerun()


# ════════════════════════════════════════════
# メインエリア
# ════════════════════════════════════════════

if st.session_state.inputs is None or st.session_state.project_dir is None:
    st.info("👈 左のサイドバーで案件情報を入力して「プロジェクト開始」を押してください")
    st.stop()

# ── 画像アップロードエリア ──
with st.expander("🖼️ 参考画像をアップロード（競合LPスクショ、Meta広告クリエイティブなど）", expanded=len(get_uploaded_images()) == 0 and st.session_state.current_step < 5):
    st.caption("アップロードした画像はStep 1〜5のAI分析に使われます。大きい画像は自動リサイズされるので、そのまま貼ってOK!")
    uploaded_files = st.file_uploader(
        "画像ファイルを選択（複数OK）",
        type=["png", "jpg", "jpeg", "gif", "webp"],
        accept_multiple_files=True,
        key="image_uploader",
    )
    if uploaded_files:
        # アップロード画像をsession_stateに保存
        st.session_state.images = [f.getvalue() for f in uploaded_files]
        st.success(f"{len(uploaded_files)}枚の画像をアップロード済み")

        # プレビュー表示
        cols = st.columns(min(len(uploaded_files), 4))
        for i, f in enumerate(uploaded_files):
            with cols[i % 4]:
                st.image(f, caption=f.name, use_container_width=True)
    else:
        st.session_state.images = []

# 次に実行すべきステップ
next_step = st.session_state.current_step + 1

# ── 完了済みステップの結果表示 ──
if st.session_state.current_step > 0:
    st.subheader("✅ 完了済みステップ")
    for s in range(1, st.session_state.current_step + 1):
        info = STEPS[s]
        result_text = get_result_for_step(s)
        with st.expander(f"{info['icon']} Step {s}: {info['name']}", expanded=(s == st.session_state.current_step)):
            if result_text:
                st.markdown(result_text)

                # 修正UI
                st.divider()
                feedback_key = f"feedback_{s}"
                feedback = st.text_area(
                    "修正したい場合はフィードバックを入力:",
                    key=feedback_key,
                    height=80,
                    placeholder="例: ペルソナの年齢を40代に変えて",
                )
                if st.button(f"🔄 Step {s} を修正", key=f"revise_{s}"):
                    if feedback:
                        with st.spinner(f"Step {s} を修正中..."):
                            role = REVISE_ROLES[s]
                            max_tokens = 32000 if s in (5, 7) else 16000
                            use_web = s in (2, 3)
                            revised = revise_with_feedback(
                                role, result_text, feedback,
                                use_web_search=use_web, max_tokens=max_tokens)

                            if s <= 5:
                                st.session_state.results[f"result{s}"] = revised
                            elif s == 7:
                                st.session_state.results["result7"] = revised

                            # ファイル保存
                            filenames = {
                                1: "step1_Who_What定義.md", 2: "step2_競合LPリサーチ.md",
                                3: "step3_別業界LPリサーチ.md", 4: "step4_広告コンテキスト.md",
                                5: "step5_ワイヤーフレーム提案.md", 7: "step7_最終ワイヤーフレーム.md",
                            }
                            if s in filenames:
                                save_output(filenames[s], revised, st.session_state.project_dir)

                            save_checkpoint(st.session_state.project_dir, s, {
                                **st.session_state.inputs,
                                **st.session_state.results,
                                "summary": st.session_state.summary,
                            })
                        st.rerun()
                    else:
                        st.warning("フィードバックを入力してください")

    st.divider()

# ── 全ステップ完了 ──
if st.session_state.current_step >= 7:
    st.balloons()
    st.success("🎉 全ステップ完了！最終ワイヤーフレームが完成しました！")
    st.subheader("📁 成果物")
    st.code(str(st.session_state.project_dir))
    st.stop()

# ── 次のステップ実行 ──
if next_step <= 7:
    info = STEPS[next_step]
    st.subheader(f"▶️ 次: Step {next_step} — {info['icon']} {info['name']}")
    st.caption(info["desc"])

    # 画像がアップロードされてればバッジ表示
    img_count = len(get_uploaded_images())
    if img_count > 0 and next_step in IMAGE_STEPS:
        st.info(f"🖼️ {img_count}枚の画像がこのステップのAI分析に使われます")

    # 前のステップが完了してるかチェック
    if next_step >= 2:
        prev_result = get_result_for_step(next_step - 1)
        if not prev_result:
            st.warning(f"Step {next_step - 1} の結果がありません。先に前のステップを完了してください。")
            st.stop()

    if st.button(f"🚀 Step {next_step} を実行", use_container_width=True, type="primary"):
        with st.spinner(f"{info['icon']} Step {next_step}: {info['name']} を実行中... しばらくお待ちください"):
            run_step(next_step)
            st.session_state.current_step = next_step
        st.rerun()

    # 戻るボタン
    if st.session_state.current_step >= 2:
        st.caption("")
        cols = st.columns([3, 1])
        with cols[1]:
            go_back = st.number_input(
                "戻り先Step", min_value=1,
                max_value=st.session_state.current_step,
                value=st.session_state.current_step,
                key="go_back_step")
            if st.button("⏪ 戻る"):
                st.session_state.current_step = go_back - 1
                st.rerun()
