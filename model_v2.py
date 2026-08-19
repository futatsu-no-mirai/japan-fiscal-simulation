#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
モデル v2 ── v1 の3つの欠陥を直したもの

v1 の欠陥（自己採点で判明）:
  (1) 金利が外生 ── 債務比率が上がっても金利が動かない。検証したら結論が反転した
  (2) 需要側がない ── 供給能力だけを解いていた。日本の30年の中心問題は需要不足なのに
  (3) 較正が粗い ── 世帯8類型でジニ係数を出していた

v2 で追加したもの:
  ・金利の内生化      r = r_base + λ×(純債務/GDP − 155%)
  ・需要ブロック      消費関数／消費税の短期効果／需給ギャップ／履歴効果
  ・世帯20類型        給与・自営・年金・生活保護、世帯構成別
  ・政治的実現可能性  実際に通った政策／通らなかった政策から抽出した3基準で採点
"""

import numpy as np
from dataclasses import dataclass, field

YEARS = list(range(2026, 2061))
POP_A = {2025: 12340, 2030: 11913, 2040: 11284, 2050: 10469, 2060: 9615}
WAP_A = {2025: 7310, 2030: 7076, 2040: 6213, 2050: 5540, 2060: 4793}
OLD_A = {2025: 3653, 2030: 3696, 2040: 3928, 2050: 3888, 2060: 3642}


def interp(a):
    ys = sorted(a); o = {}
    for y in range(2025, 2061):
        if y in a:
            o[y] = float(a[y]); continue
        lo = max(k for k in ys if k <= y); hi = min(k for k in ys if k >= y)
        w = (y - lo) / (hi - lo); o[y] = a[lo] * (1 - w) + a[hi] * w
    return o


POP, WAP, OLD = interp(POP_A), interp(WAP_A), interp(OLD_A)

# ---- 生産関数 ----
AT, AI = 0.35, 0.10      # 有形／無形資本の分配率
BL = 1 - AT - AI
DT, DI = 0.060, 0.150    # 減耗率
GDP0, KT0, KI0 = 620.0, 1900.0, 190.0
L0, H0 = 6800.0, 1600.0

# ---- 需要側 ----
#
# 【v2内での修正】最初の実装は「消費税収の全額を恒久的な需要不足として扱う」もので、
# 経済が永久に再均衡しない誤った設計だった（必要消費税率が29%と出て初めて気づいた）。
# 標準的な財政インパルス方式に置き換えた：
#   需給ギャップは財政収支の「水準」ではなく「変化」（＝引き締めの勢い）で動き、
#   AR(1)で減衰して潜在GDPに戻る。恒久的な増税は恒久的な需要不足を作らない。
#
C_SHARE = 0.54           # 民間最終消費／GDP
MULT_TAX = 0.70          # 増税の財政乗数（IMF等の推計レンジ 0.3〜1.0 の中位）
MULT_SPEND = 0.90        # 給付・投資の財政乗数
GAP_PERSIST = 0.70       # 需給ギャップのAR(1)係数（3〜4年で概ね解消）
GAP_PASS = 0.80          # 需給ギャップが実現GDPに伝わる割合
HYSTERESIS = 0.06        # 需給ギャップ-1%が続くとTFP上昇率が下がる幅(pt)
HYST_CAP = 0.004         # 履歴効果の上限(pt)。無制限に効かせない

# ---- 金融 ----
#
# 【v2 内での修正2】利払いの立ち上がりが実績の2.6倍速かった。
# 市場金利の変化を債務の全額に即時適用していたのが原因。実際は満期が来た分だけ
# 入れ替わるので、平均残存期間ぶんの遅れが入る。
#   実績アンカー：金利1%上昇 → 3年後の利払費 +3.7兆円（債務1,145兆円）
#                = 3年で約32%が入れ替わる → 平均残存 約9年
# よって、債務全体にかかる実効金利は市場金利へ 1/9 ずつ近づく形に直した。
#
INF_TARGET = 0.020
R_BASE_END, R_RAMP = 0.022, 15
R0 = 0.009
AVG_MATURITY = 9.0       # 国債の平均残存期間（年）。実効金利の追随速度を決める
LAMBDA = 0.02            # 純債務/GDP 1ptあたりの市場金利の上昇
#
# なお日本の歴史的な λ はほぼゼロである（債務比率が100%→250%になる間、
# 10年債利回りはむしろ低下した）。抑えていたのは財政規律ではなく、国内保有比率の
# 高さと日銀の買入れである。したがって λ を滑らかな係数として扱うのは便宜であり、
# 実態に近いのは「閾値を超えると跳ねる」非線形。regime_lambda() でその形も試せる。
#
LAMBDA_LOW, LAMBDA_HIGH, DEBT_THRESHOLD = 0.005, 0.080, 2.20


def regime_lambda(d: float, thresh: float = DEBT_THRESHOLD) -> float:
    """レジーム転換型の金利感応度。閾値の下ではほぼ平ら、上では急に立つ"""
    return LAMBDA_LOW if d < thresh else LAMBDA_HIGH

# ---- 財政（2025年度、兆円）----
REV = {"所得税": 33.0, "法人税": 20.0, "消費税": 30.0, "その他税": 30.0,
       "社保": 77.0, "その他": 20.0}
EXP = {"社会保障": 137.0, "一般": 60.0, "地方": 20.0}
DEBT0 = 960.0
VATPT = 3.0              # 消費税1ptあたりの税収（兆円）
DEBT_ANCHOR = 1.55       # 金利が上がり始める債務比率


@dataclass
class S:
    name: str
    # 生産性
    boost: float = 0.0
    inv_i: float = 0.030
    part: float = 0.0
    # 既定路線（2026年8月時点で決定済み）
    wall178: float = -0.9
    shakai_kakudai: float = 0.0
    zaishoku: float = 0.0
    food_vat_cut: float = 0.0
    food_vat_years: int = 0
    credit: float = 0.0             # 給付付き税額控除（兆円）
    credit_start: int = 3
    # 追加提案
    train_invest: float = 0.0
    imm_dep: float = 0.0
    iryo: float = 0.0
    hosho: float = 0.0
    carbon: float = 0.0
    vat_step: float = 0.0
    vat_start: int = 10
    vat_years: int = 10
    # モデルの前提
    lam: float = LAMBDA
    demand: bool = True
    r_base_end: float = R_BASE_END
    regime: bool = False            # True でレジーム転換型の金利感応度を使う
    threshold: float = DEBT_THRESHOLD
    maturity: float = AVG_MATURITY


def ramp(t, n, f):
    return f if n <= 0 else f * min(1.0, (t + 1) / n)


def run(S_, boost=None, lam=None, demand=None):
    b = S_.boost if boost is None else boost
    lm = S_.lam if lam is None else lam
    dem = S_.demand if demand is None else demand

    keys = ["year", "y_pot", "y_act", "gdp_pc", "gdp_nom", "gap", "pb", "d", "r",
            "vat", "c_real", "tfp_g"]
    res = {k: [] for k in keys}
    A, Kt, Ki, debt, price = 1.0, KT0, KI0, DEBT0, 1.0
    scale = GDP0 / (KT0 ** AT * KI0 ** AI * ((L0 * H0) / 1e4) ** BL)
    d = DEBT0 / GDP0
    gap, gap_ma = 0.0, 0.0
    tax_prev, spend_prev, Y_prev = 0.0, 0.0, GDP0
    r_eff = R0                      # 債務全体にかかる実効金利

    for t, year in enumerate(YEARS):
        # ---------- 供給（潜在GDP） ----------
        emp = WAP[year] * (L0 / WAP[2025] + ramp(t, 8, S_.part))
        emp += OLD[year] * (0.005 if S_.zaishoku else 0.0)
        hours = H0 * 0.997 ** t
        # 履歴効果：需要不足が続くとTFPの伸びが落ちる（上限つき）
        pen = min(HYST_CAP, HYSTERESIS * max(0.0, -gap_ma)) if dem else 0.0
        gA = 0.005 + ramp(t, 10, b) - pen
        A *= (1 + gA)
        Kt = Kt * (1 - DT) + 0.155 * Y_prev
        Ki = Ki * (1 - DI) + (0.030 + ramp(t, 10, S_.inv_i - 0.030)) * Y_prev
        Y_pot = scale * A * Kt ** AT * Ki ** AI * (emp * hours / 1e4) ** BL

        # ---------- 消費税率 ----------
        vat = 0.10
        if S_.vat_step and t >= S_.vat_start:
            vat += ramp(t - S_.vat_start, S_.vat_years, S_.vat_step) / 100

        # ---------- 需要（財政インパルス方式） ----------
        if dem:
            # 家計から取る側（実質・兆円）
            tax_now = (vat - 0.10) * 100 * VATPT + ramp(t, 8, S_.carbon) \
                + (S_.food_vat_cut if t < S_.food_vat_years else 0.0) * -1
            # 家計・企業に渡す側（実質・兆円）
            spend_now = ramp(t, 5, S_.train_invest) \
                + (ramp(t - S_.credit_start, 3, S_.credit) if t >= S_.credit_start else 0.0) \
                + (-S_.food_vat_cut if t < S_.food_vat_years else 0.0) \
                - ramp(t, 15, S_.iryo) - ramp(t, 10, S_.hosho)
            # 引き締めの「勢い」＝前年からの変化。水準ではない
            impulse = ((tax_now - tax_prev) * MULT_TAX
                       - (spend_now - spend_prev) * MULT_SPEND) / Y_prev
            gap = GAP_PERSIST * gap - impulse
            Y_act = Y_pot * (1 + GAP_PASS * min(0.0, gap))
            gap_ma = 0.7 * gap_ma + 0.3 * min(0.0, gap)
            tax_prev, spend_prev = tax_now, spend_now
        else:
            gap, Y_act = 0.0, Y_pot
        Y_prev = Y_act

        price *= (1 + INF_TARGET + (0.3 * gap if dem else 0.0))
        Ynom = Y_act * price
        q = Y_act / GDP0

        # ---------- 歳入 ----------
        rev = (REV["所得税"] + REV["法人税"] + REV["その他税"] + REV["社保"]
               + REV["その他"] + REV["消費税"] + (vat - 0.10) * 100 * VATPT) * q * price
        rev += S_.wall178 * price
        rev += ramp(t, 3, S_.shakai_kakudai) * price
        if t < S_.food_vat_years:
            rev += S_.food_vat_cut * price
        rev += ramp(t, 5, S_.imm_dep) * price
        rev += ramp(t, 8, S_.carbon) * price

        # ---------- 歳出 ----------
        soc = EXP["社会保障"] * (OLD[year] / OLD[2025]) * price * 1.004 ** t
        soc -= ramp(t, 15, S_.iryo) * price
        soc += ramp(t, 3, -S_.zaishoku) * price
        pexp = soc + (EXP["一般"] + EXP["地方"]) * q * price
        pexp += ramp(t, 5, S_.train_invest) * price
        pexp -= ramp(t, 10, S_.hosho) * price
        if t >= S_.credit_start:
            pexp += ramp(t - S_.credit_start, 3, S_.credit) * price

        # ---------- 金利（内生）と債務 ----------
        # 市場金利：基準金利＋債務比率への反応
        lam_t = regime_lambda(d, S_.threshold) if S_.regime else lm
        r_base = R0 + (S_.r_base_end - R0) * min(1.0, (t + 1) / R_RAMP)
        r_mkt = min(r_base + lam_t * max(0.0, d - DEBT_ANCHOR), 0.15)
        # 実効金利：満期が来た分だけ入れ替わるので、市場金利へ 1/平均残存 ずつ近づく
        r_eff += (r_mkt - r_eff) / S_.maturity
        pb = rev - pexp
        debt -= (pb - debt * r_eff)
        d = debt / Ynom
        if d > 20:                             # 破綻として打ち切る
            d = 20.0

        for k, v in zip(keys, [year, Y_pot, Y_act, Y_act / POP[year] * 1e4, Ynom,
                               gap, pb, d, r_eff, vat, Y_act * C_SHARE, gA]):
            res[k].append(v)
    return {k: np.array(v) for k, v in res.items()}


# ============================================================
# 世帯 20類型
# 名称, 額面, 所得税+住民税, 社保本人, 年間消費, うち食料, 光熱輸送, 世帯数(万), 人数
# ============================================================
#
# 世帯数は「住民基本台帳・国勢調査の世帯構成」に大まかに合わせて較正した。
# 合計は約5,700万世帯・約1億700万人。実際は約5,600万世帯・1億2,340万人なので、
# 3世代世帯・施設入所者などを取りこぼしており、人口カバー率は約87%。
#
HH = [
    ("給与150万 単身(非正規)",   150,   3,  22, 145,  38, 28,  350, 1),
    ("給与200万 単身",           200,   8,  29, 185,  46, 32,  400, 1),
    ("給与250万 ひとり親+子1",   250,   6,  36, 240,  62, 38,   90, 2),
    ("給与300万 単身",           300,  17,  44, 265,  60, 36,  450, 1),
    ("給与300万 夫婦(片働き)",   300,  12,  44, 285,  72, 44,  180, 2),
    ("給与400万 単身",           400,  32,  58, 330,  70, 39,  380, 1),
    ("給与400万 夫婦+子2",       400,  18,  58, 380, 105, 52,  320, 4),
    ("給与500万 単身",           500,  55,  75, 400,  82, 42,  300, 1),
    ("給与500万 夫婦+子2",       500,  32,  75, 455, 120, 55,  350, 4),
    ("給与700万 夫婦+子2",       700,  70, 103, 570, 140, 60,  300, 4),
    ("給与800万 共働き+子1",     800,  95, 118, 610, 138, 56,  180, 3),
    ("給与1000万 夫婦+子2",     1000, 150, 138, 720, 155, 64,  130, 4),
    ("給与1500万 夫婦+子2",     1500, 330, 170, 950, 170, 70,   50, 4),
    ("給与2000万 夫婦",         2000, 530, 185,1050, 165, 68,   20, 2),
    ("自営300万 単身",           300,  14,  36, 270,  64, 38,  240, 1),
    ("自営600万 夫婦",           600,  62,  74, 520, 128, 58,  160, 2),
    ("年金 基礎のみ 単身",         82,   0,   6, 105,  32, 26,  220, 1),
    ("年金 平均 単身",            168,   0,  11, 165,  44, 31,  680, 1),
    ("年金 夫婦",                 270,   2,  18, 255,  72, 42,  730, 2),
    ("生活保護 単身",             120,   0,   0, 120,  36, 26,  165, 1),
]


def taper_credit(inc):
    """給付付き税額控除（逓減型・一人あたり万円）"""
    if inc <= 200: return 14.0
    if inc <= 300: return 10.0
    if inc <= 400: return 7.0
    if inc <= 500: return 4.0
    if inc <= 600: return 2.0
    return 0.0


def households(vat_up_pt, carbon=0.0, credit=True, food_vat_cut=0.0):
    """
    vat_up_pt : 消費税の引き上げ幅（pt）
    carbon    : 炭素税（兆円）。5兆円で光熱輸送費に13%転嫁
    food_vat_cut : 食料品の消費税引き下げ幅（pt、正の値で引き下げ）
    """
    rows = []
    for name, inc, tax, si, cons, food, energy, cnt, heads in HH:
        d = 0.0
        if credit:
            d += taper_credit(inc / heads * (1 if heads == 1 else 1.0)) * heads \
                 if False else taper_credit(inc) * heads
        d += -((cons - food) * 0.6) * (vat_up_pt / 100)
        d += -(food * 0.6) * (vat_up_pt / 100)
        d += (food * 0.6) * (food_vat_cut / 100)
        d += -energy * 0.13 * (carbon / 5.0)
        base = inc - tax - si
        rows.append((name, base, d, d / max(base, 1) * 100, cnt, heads))
    return rows


#
# 【v1からの修正】ジニ係数の算出をやめた。
# 20類型では分布の両端（超高所得・無収入）を捉えられず、水準はもちろん
# 変化の大きさも信用できない。v1では8類型でジニを出して公式統計の隣に
# 並べていたが、あれは誤りだった。
# 代わりに、両端を欠いていても読める指標だけを使う。
#
def dist(rows):
    """
    等価可処分所得（世帯人数の平方根で割る）の低い順に人数で並べ、
    下位20%／中位／上位20%の平均変化率を返す。
    """
    items = sorted(((b + 0) / np.sqrt(h), p, c * h) for _, b, _, p, c, h in rows)
    tot = sum(x[2] for x in items)
    acc, low, mid, high = 0.0, [], [], []
    for _, pct, w in items:
        frac = acc / tot
        (low if frac < 0.2 else high if frac >= 0.8 else mid).append((pct, w))
        acc += w

    def av(g):
        if not g: return float("nan")
        return sum(p * w for p, w in g) / sum(w for _, w in g)
    return {"下位20%": av(low), "中位60%": av(mid), "上位20%": av(high),
            "最も不利": min(p for _, _, _, p, _, _ in rows),
            "格差幅": av(high) - av(low)}


def coverage():
    hh = sum(h[7] for h in HH)
    pp = sum(h[7] * h[8] for h in HH)
    return hh, pp, pp / 12340 * 100


# ============================================================
# 政治的実現可能性の採点
# 実際に通った政策／通らなかった政策から抽出した3基準
# ============================================================
PASSED = ["消費税5→8%(2014)", "消費税8→10%(2019)", "幼保無償化(2019)",
          "社会保険の適用拡大(2016/22/24/26)", "年収の壁103→178万(2025-26)",
          "在職老齢年金の緩和(2026)", "給付付き税額控除の導入決定(2026)",
          "児童手当の現況届廃止", "高額療養費の自動適用", "政策活動費の廃止(2024)",
          "ガソリン暫定税率の廃止(2025-26)", "定額減税(2024)"]
BLOCKED = ["退職金税制の見直し(3年連続見送り)", "金融所得課税の強化(2021に撤回)",
           "相続・贈与の一体化(部分のみ)", "解雇の金銭解決(20年未実現)",
           "配偶者控除の廃止(再三失敗)", "病床の大幅削減",
           "ライドシェアの全面解禁(部分のみ)", "混合診療の解禁"]

CRITERIA = [
    ("損をする集団が組織化されていないか",
     "退職金税制は長期勤続者、配偶者控除は片働き世帯、病床削減は医師会。"
     "組織化された敗者がいる案は例外なく止まっている"),
    ("既存の数値の変更で済むか（新制度の創設でないか）",
     "適用拡大・基準額の変更・控除額の変更は繰り返し通る。"
     "新しい制度の創設は10年単位でかかる"),
    ("手取りが減る方向でないか",
     "2026年の政治条件。名目賃金が物価+2%を超えるまで、増税・保険料引き上げ・"
     "給付削減は通らないという立場が実質的な拒否権を持っている"),
]

# 政策ごとの採点（各基準 2=満たす / 1=部分的 / 0=満たさない）
POLICIES = [
    # (名称, 3基準の点, 生産性への寄与pt, 財政効果(兆円/年), 備考)
    ("退職金税制の勤続年数優遇の廃止（単独）", (0, 2, 0), 0.10, +0.3,
     "3年連続で見送り。長期勤続者の手取りが減るため"),
    ("同上＋平準化課税（10年に分散して累進課税）", (1, 1, 2), 0.10, 0.0,
     "負担増を作らずに中立化できる。これが回避策"),
    ("企業年金・iDeCoのポータビリティ完全化", (2, 2, 2), 0.05, 0.0,
     "損をする主体がいない"),
    ("経営者保証の原則禁止", (2, 1, 2), 0.05, 0.0, "すでに一部進行"),
    ("公共調達の実績要件撤廃・分割発注", (1, 2, 2), 0.05, +0.2,
     "既存受注業者が損をするが組織化は弱い"),
    ("参入規制の全件棚卸しと公表", (2, 2, 2), 0.03, 0.0, "公表のみ。予算ゼロ"),
    ("ソフト・訓練費の即時償却", (2, 2, 2), 0.07, -0.5, "減税なので反対がない"),
    ("訓練投資 GDP比0.1→0.5%（個人口座）", (2, 0, 2), 0.20, -2.5,
     "新制度の創設。給付なので手取りは増える"),
    ("職業資格枠組み（日本版NQF）", (2, 0, 2), 0.10, -0.1, "新制度。時間がかかる"),
    ("事業承継・M&Aの標準化", (2, 1, 2), 0.10, -0.2, "損をする主体がいない"),
    ("100%信用保証の新規停止", (0, 2, 1), 0.10, +1.0,
     "既存の借り手と金融機関が損。受け皿が先"),
    ("医療費の適正化（市販薬類似薬・重複投薬）", (0, 2, 0), 0.00, +3.0,
     "医師会・製薬。最も組織化された反対"),
    ("炭素税5兆円", (1, 1, 0), 0.05, +5.0,
     "ガソリン暫定税率廃止と逆方向。手取りが減る"),
    ("消費税 10→15%（2036年から10年）", (1, 2, 0), 0.00, +15.0,
     "既存税率の変更なので技術的には容易。だが手取りが減る"),
]


def feasibility(score):
    """3基準の合計（0-6）を、通る確率の目安に変える"""
    s = sum(score)
    return {6: "ほぼ確実", 5: "高い", 4: "やや高い", 3: "五分",
            2: "低い", 1: "かなり低い", 0: "ほぼ不可能"}[s]
