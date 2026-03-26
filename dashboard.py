import glob, os, webbrowser
from pathlib import Path
import pandas as pd
import streamlit as st

st.set_page_config(page_title="せどりリサーチ", page_icon="🔍", layout="wide")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;500;700&family=DM+Mono:wght@400;500&display=swap');
:root{--bg:#1A415B;--teal:#3AB2B5;--light:#CAE8E9;--cream:#F3F3E7;--gold:#D1C58C;--card:#1e4d6b;--border:#2a5f7a;--danger:#e07070;--radius:12px;}
.stApp{background:var(--bg);color:var(--cream);font-family:'Noto Sans JP',sans-serif;}
section[data-testid="stSidebar"]{background:#143448!important;border-right:1px solid var(--border);}
section[data-testid="stSidebar"] *{color:var(--cream)!important;}
div[data-testid="stMetric"]{background:var(--card);border:1px solid var(--border);border-radius:var(--radius);padding:12px 16px;}
div[data-testid="stMetric"] label{color:var(--light)!important;font-size:0.75rem;}
div[data-testid="stMetricValue"]{color:var(--teal)!important;font-family:'DM Mono',monospace;}
h1{color:var(--teal)!important;}
div[data-baseweb="select"]>div{background:var(--card)!important;border-color:var(--border)!important;color:var(--cream)!important;}
.stButton>button{background:var(--teal)!important;color:var(--bg)!important;border:none!important;border-radius:8px!important;font-weight:700!important;}
.card{background:var(--card);border:1px solid var(--border);border-radius:var(--radius);padding:16px 20px;margin-bottom:12px;}
.card.honmei{border-left:4px solid var(--teal);}
.card.horyu{border-left:4px solid var(--gold);}
.profit-pos{color:var(--teal);font-size:1.2rem;font-weight:700;font-family:'DM Mono',monospace;}
.profit-neg{color:var(--danger);font-size:1.2rem;font-weight:700;}
.tag{display:inline-block;padding:2px 8px;border-radius:4px;font-size:0.7rem;font-weight:700;margin-right:4px;}
.tag-honmei{background:#1e6b6d;color:var(--teal);}
.tag-horyu{background:#4a3d1a;color:var(--gold);}
.tag-brand{background:#1a3a4d;color:var(--light);}
.tag-site{background:#1a3d4d;color:#8ad4d6;}
.tag-danger{background:#4d1a1a;color:var(--danger);}
.tag-cond{background:#2a3d1a;color:#8dcc6a;}
.tag-hold-reason{background:#3d2a0a;color:#f0a040;border:1px solid #7a5010;}
.tag-cond-warn{background:#4d1a1a;color:#f06060;border:1px solid #8a2020;}
.url-btn{display:inline-block;padding:4px 12px;border-radius:6px;font-size:0.75rem;font-weight:600;text-decoration:none;margin-right:6px;}
.url-primary{background:var(--teal);color:var(--bg);}
.url-secondary{background:var(--border);color:var(--light);}
hr.div{border:none;border-top:1px solid var(--border);margin:8px 0;}
</style>
""", unsafe_allow_html=True)

@st.cache_data(ttl=30)
def load_csv():
    base = Path(".")
    files = glob.glob(str(base/"results"/"*.csv")) + glob.glob(str(base/"output"/"*.csv")) + glob.glob(str(base/"*.csv"))
    files = [f for f in files if "dashboard" not in f]
    if not files: return None
    return pd.read_csv(max(files, key=os.path.getmtime), encoding="utf-8-sig")

RANK_LABEL = {"honmei": "本命", "hold": "保留", "review": "要確認", "reject": "除外"}

def g(row, *keys, default=""):
    for k in keys:
        v = row.get(k, "")
        if str(v) not in ("nan","None","","0"): return str(v).strip()
    return default

st.markdown("## 🔍 せどり利益商品リサーチ")
df = load_csv()

if df is None:
    st.markdown("<div style='text-align:center;padding:80px 0;color:#3AB2B5'><div style='font-size:4rem'>⏳</div><div style='margin-top:16px;color:#CAE8E9'>CSVファイルが見つかりません<br><small>ツールを実行してから更新してください</small></div></div>", unsafe_allow_html=True)
    st.stop()

with st.sidebar:
    st.markdown("### 🎛️ フィルター")
    brands = sorted(df["brand"].dropna().unique()) if "brand" in df.columns else []
    sel_brands = st.multiselect("ブランド", brands)
    sites = sorted(df["source_site"].dropna().unique()) if "source_site" in df.columns else []
    sel_sites = st.multiselect("仕入れサイト", sites)
    sel_rank = st.radio("判定", ["全て","本命","保留","除外"], horizontal=True)
    min_profit = st.number_input("利益額（円以上）", min_value=0, value=0, step=500)
    min_rate = st.number_input("利益率（%以上）", min_value=0, value=0, step=5)
    sort_by = st.selectbox("並び替え", ["新着順","利益額 ↓","利益率 ↓","仕入れ価格 ↑"])
    if st.button("🔄 更新"): st.cache_data.clear(); st.rerun()

dff = df.copy()
if sel_brands and "brand" in dff.columns: dff = dff[dff["brand"].isin(sel_brands)]
if sel_sites and "source_site" in dff.columns: dff = dff[dff["source_site"].isin(sel_sites)]
if sel_rank != "全て" and "candidate_rank" in dff.columns:
    rev_map = {v: k for k, v in RANK_LABEL.items()}
    dff = dff[dff["candidate_rank"].map(lambda x: RANK_LABEL.get(x, x)) == sel_rank]
_profit_col = "gross_profit" if "gross_profit" in dff.columns else "profit"
if _profit_col in dff.columns: dff = dff[pd.to_numeric(dff[_profit_col],errors="coerce").fillna(0)>=min_profit]
if "profit_rate" in dff.columns: dff = dff[pd.to_numeric(dff["profit_rate"],errors="coerce").fillna(0)>=min_rate]
if _profit_col in dff.columns and sort_by=="利益額 ↓": dff=dff.sort_values(_profit_col,ascending=False,key=lambda x:pd.to_numeric(x,errors="coerce"))
elif "profit_rate" in dff.columns and sort_by=="利益率 ↓": dff=dff.sort_values("profit_rate",ascending=False,key=lambda x:pd.to_numeric(x,errors="coerce"))
elif "source_price" in dff.columns and sort_by=="仕入れ価格 ↑": dff=dff.sort_values("source_price",ascending=True,key=lambda x:pd.to_numeric(x,errors="coerce"))

honmei = len(df[df["candidate_rank"]=="honmei"]) if "candidate_rank" in df.columns else 0
horyu  = len(df[df["candidate_rank"].isin(["hold","review"])]) if "candidate_rank" in df.columns else 0
c1,c2,c3,c4 = st.columns(4)
c1.metric("📦 検索対象", f"{len(df)}件")
c2.metric("⭐ 本命", f"{honmei}件")
c3.metric("🔖 保留", f"{horyu}件")
c4.metric("👁 表示中", f"{len(dff)}件")

st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)

if dff.empty:
    st.markdown("<div style='text-align:center;padding:60px 0;color:#3AB2B5'><div style='font-size:3rem'>🔎</div><div style='margin-top:12px;color:#CAE8E9'>該当する候補がありません</div></div>", unsafe_allow_html=True)
else:
    for _,row in dff.iterrows():
        rank    = RANK_LABEL.get(g(row,"candidate_rank","rank"), g(row,"candidate_rank","rank"))
        brand   = g(row,"brand","ブランド")
        title   = g(row,"source_title","title","タイトル","商品名") or "（タイトルなし）"
        src_p   = g(row,"source_price","仕入れ価格")
        mer_p   = g(row,"estimated_sale_price","mercari_price","sell_price")
        profit  = g(row,"gross_profit","profit","利益")
        rate    = g(row,"profit_rate","利益率")
        sold    = g(row,"matched_sold_count","mercari_sample_count","sold_count")
        site    = g(row,"source_site","site","仕入れサイト")
        src_url = g(row,"source_url","url","仕入れURL")
        mer_url = g(row,"mercari_url","メルカリURL")
        cond    = g(row,"condition_rank","condition","状態ランク")
        danger  = g(row,"danger_word","危険語")
        skip    = g(row,"skip_reason","note","除外理由")
        model   = g(row,"model_signature","model_name","モデル名")
        color_  = g(row,"primary_color","color","カラー","色")

        cls = "card honmei" if rank=="本命" else "card horyu" if rank=="保留" else "card"

        try: ph = f'+¥{float(profit.replace(",","")):,.0f}' if float(profit.replace(",",""))>=0 else f'¥{float(profit.replace(",","")):,.0f}'
        except: ph = profit
        try: rh = f'{float(rate.replace("%","")):.1f}%'
        except: rh = rate

        profit_cls = "profit-pos" if (profit and not profit.startswith("-")) else "profit-neg"

        tags = ""
        if rank=="本命": tags+='<span class="tag tag-honmei">⭐ 本命</span>'
        elif rank=="保留": tags+='<span class="tag tag-horyu">🔖 保留</span>'
        if brand: tags+=f'<span class="tag tag-brand">{brand}</span>'
        if site:  tags+=f'<span class="tag tag-site">🏪 {site}</span>'
        if cond:  tags+=f'<span class="tag tag-cond">📊 {cond}</span>'
        if danger:tags+=f'<span class="tag tag-danger">⚠️ {danger}</span>'
        if cond in ("BC", "C"): tags+=f'<span class="tag tag-cond-warn">🔴 状態要確認({cond})</span>'

        # 保留理由タグ（保留カードのみ）
        hold_reason_tags = ""
        if rank == "保留":
            model_match  = g(row, "model_match")
            sell_speed   = g(row, "sell_speed")
            color_align  = g(row, "color_alignment")
            note_text    = g(row, "note", "skip_reason")

            if model_match == "False":
                hold_reason_tags += '<span class="tag tag-hold-reason">🔍 モデル不一致</span>'
            if sell_speed == "slow":
                hold_reason_tags += '<span class="tag tag-hold-reason">🐢 売れ行き遅い</span>'
            if color_align and color_align not in ("strong", ""):
                label = {"near": "色:near(次点)", "neutral": "色:neutral(不一致)", "unknown": "色:unknown(不明)"}.get(color_align, f"色:{color_align}")
                hold_reason_tags += f'<span class="tag tag-hold-reason">🎨 {label}</span>'
            if "mercari_sample_count" in note_text:
                hold_reason_tags += '<span class="tag tag-hold-reason">📊 参照数不足(&lt;8件)</span>'
            if "matched_sold_count" in note_text:
                hold_reason_tags += '<span class="tag tag-hold-reason">📉 SOLD数不足(&lt;5件)</span>'
            if "価格検討枠" in note_text:
                hold_reason_tags += '<span class="tag tag-hold-reason">💰 価格検討枠</span>'

        try: sp=f'¥{float(src_p.replace(",","")):,.0f}'
        except: sp=src_p
        try: mp=f'¥{float(mer_p.replace(",","")):,.0f}'
        except: mp=mer_p

        sold_h = f'<span style="color:#8ad4d6;font-size:0.8rem">💹 SOLD {sold}件</span>' if sold else ""
        sub = ""
        if model: sub+=f'<span style="color:#CAE8E9;font-size:0.8rem">📌 {model}</span> '
        if color_: sub+=f'<span style="color:#CAE8E9;font-size:0.8rem">🎨 {color_}</span>'

        urls=""
        if src_url: urls+=f'<a href="{src_url}" target="_blank" class="url-btn url-primary">🏪 仕入れ先</a>'
        if mer_url: urls+=f'<a href="{mer_url}" target="_blank" class="url-btn url-secondary">📱 メルカリ</a>'

        skip_h = f'<div style="color:#e09070;font-size:0.75rem;margin-top:6px">📋 {skip}</div>' if skip else ""

        st.markdown(f"""
        <div class="{cls}">
          <div style="font-size:0.95rem;font-weight:700;color:#F3F3E7;margin-bottom:6px">{title}</div>
          <div style="margin-bottom:6px">{tags}</div>
          {'<div style="margin-bottom:6px">'+hold_reason_tags+'</div>' if hold_reason_tags else ''}
          {'<div style="margin-bottom:4px">'+sub+'</div>' if sub else ''}
          <hr class="div">
          <div style="font-size:0.85rem;color:#CAE8E9">仕入れ {sp} → メルカリ {mp} &nbsp; {sold_h}</div>
          <div style="margin-top:6px"><span class="{profit_cls}">{ph}</span>
          <span style="color:var(--gold);font-size:0.9rem;margin-left:8px">{rh}</span></div>
          {skip_h}
          <hr class="div">
          <div>{urls}</div>
        </div>
        """, unsafe_allow_html=True)

st.markdown("<div style='text-align:center;color:#3a6a7a;font-size:0.75rem;padding:24px 0 8px'>sedori-search dashboard</div>", unsafe_allow_html=True)
