#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
現実解シミュレーション ── 2026年8月時点の日本の政治日程を制約として与える。

【すでに決まっている／動いているもの（前提として織り込む）】
  ・年収の壁178万円（基礎控除104万＋給与所得控除74万）2026年から実施 → 所得税の減収
  ・社会保険の適用拡大：2026年10月に賃金要件（106万円）撤廃予定 → 保険料収入の増
  ・在職老齢年金：基準額を月51万→65万へ（2026年4月、令和7年改正法）
  ・給付付き税額控除：2029年度本格導入で与野党大筋合意（2026年7月）、8月5日 基本方針閣議決定
  ・食料品の消費税 8%→1%（2027年4月から2年間）＋ 残る1%分 約6,000億円を中低所得者へ現金給付

【この計画では前提として「やらない」もの（政治的に不可能）】
  ・所得税・住民税の廃止
  ・消費税の大幅引き上げ（世論はむしろ引き下げ方向）
  ・解雇規制の緩和
  ・外国人労働者の拡大

つまり分配側はすでに動いている。欠けているのは生産性側だけである。
"""

import numpy as np
from dataclasses import dataclass

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

AT, AI = 0.35, 0.10
BL = 1 - AT - AI
DT, DI = 0.060, 0.150
GDP0, KT0, KI0, L0, H0 = 620.0, 1900.0, 190.0, 6800.0, 1600.0
INF, R0, RRAMP = 0.020, 0.009, 15

# 2025年度ベースの財政（兆円）
REV = {"所得税": 33.0, "法人税": 20.0, "消費税": 30.0, "その他税": 30.0,
       "社保": 77.0, "その他": 20.0}
EXP = {"社会保障": 137.0, "一般": 60.0, "地方": 20.0}
DEBT0 = 960.0
VATPT = 3.0          # 消費税1ptあたり約3兆円


@dataclass
class R:
    name: str
    # --- 生産性 ---
    boost: float = 0.0            # 生産性上昇率の上積み（年、pt）
    inv_i: float = 0.030          # 無形資産投資／GDP の到達点
    part: float = 0.0             # 就業率の押し上げ（最終pt）
    # --- すでに決まっているもの ---
    wall178: float = -0.9         # 年収の壁178万円による所得税減収（兆円）
    shakai_kakudai: float = 0.0   # 社会保険の適用拡大による保険料増（兆円）
    zaishoku: float = 0.0         # 在職老齢年金の緩和（給付増＝マイナス）
    food_vat_cut: float = 0.0     # 食料品消費税の引き下げ（兆円、期間限定）
    food_vat_years: int = 0
    kyufu_tax_credit: float = 0.0 # 給付付き税額控除（2029年度〜、兆円）
    credit_start: int = 3         # 2029年度＝t=3
    # --- 追加で提案するもの ---
    train_invest: float = 0.0     # 訓練・無形資産投資（兆円）
    imm_depreciation: float = 0.0 # ソフト・訓練費の即時償却による減収（兆円）
    iryo_tekiseika: float = 0.0   # 医療費適正化（兆円）
    hosho_shukusho: float = 0.0   # 100%信用保証の縮小による歳出減（兆円）
    carbon: float = 0.0           # 炭素税（兆円）
    vat_step: float = 0.0         # 段階的な消費税引き上げ（最終pt数）
    vat_step_start: int = 10      # 引き上げ開始年（t）
    vat_step_years: int = 10      # 引き上げにかける年数
    r_end: float = 0.022


def ramp(t, n, f):
    return f if n <= 0 else f * min(1.0, (t + 1) / n)


def run(sc: R):
    keys = ["year", "gdp_pc", "gdp_nom", "gdp_real", "pb", "d", "rev", "exp",
            "vat", "prod_hour", "r"]
    res = {k: [] for k in keys}
    A, Kt, Ki, debt, price = 1.0, KT0, KI0, DEBT0, 1.0
    scale = GDP0 / (KT0 ** AT * KI0 ** AI * ((L0 * H0) / 1e4) ** BL)

    for t, year in enumerate(YEARS):
        # ---- 供給側 ----
        emp = WAP[year] * (L0 / WAP[2025] + ramp(t, 8, sc.part))
        emp += OLD[year] * (0.005 if sc.zaishoku else 0.0)
        hours = H0 * 0.997 ** t
        A *= (1 + 0.005 + ramp(t, 10, sc.boost))
        Y = scale * A * Kt ** AT * Ki ** AI * (emp * hours / 1e4) ** BL
        Kt = Kt * (1 - DT) + 0.155 * Y
        Ki = Ki * (1 - DI) + (0.030 + ramp(t, 10, sc.inv_i - 0.030)) * Y
        price *= (1 + INF); Ynom = Y * price; q = Y / GDP0

        # ---- 消費税率（段階的引き上げがある場合） ----
        vat = 0.10
        if sc.vat_step and t >= sc.vat_step_start:
            vat += ramp(t - sc.vat_step_start, sc.vat_step_years, sc.vat_step) / 100

        # ---- 歳入 ----
        rev = (REV["所得税"] + REV["法人税"] + REV["その他税"] + REV["社保"]
               + REV["その他"] + REV["消費税"] + (vat - 0.10) * 100 * VATPT) * q * price
        rev += sc.wall178 * price                                  # 178万円の壁（減収）
        rev += ramp(t, 3, sc.shakai_kakudai) * price               # 社会保険の適用拡大
        if t < sc.food_vat_years:
            rev += sc.food_vat_cut * price                         # 食料品減税（減収）
        rev += ramp(t, 5, sc.imm_depreciation) * price             # 即時償却（減収）
        rev += ramp(t, 8, sc.carbon) * price                       # 炭素税

        # ---- 歳出 ----
        soc = EXP["社会保障"] * (OLD[year] / OLD[2025]) * price * 1.004 ** t
        soc -= ramp(t, 15, sc.iryo_tekiseika) * price
        soc += ramp(t, 3, -sc.zaishoku) * price                    # 在職老齢年金の緩和
        pexp = soc + (EXP["一般"] + EXP["地方"]) * q * price
        pexp += ramp(t, 5, sc.train_invest) * price
        pexp -= ramp(t, 10, sc.hosho_shukusho) * price
        if t >= sc.credit_start:
            pexp += ramp(t - sc.credit_start, 3, sc.kyufu_tax_credit) * price

        r = R0 + (sc.r_end - R0) * min(1.0, (t + 1) / RRAMP)
        pb = rev - pexp
        debt -= (pb - debt * r)
        for k, v in zip(keys, [year, Y / POP[year] * 1e4, Ynom, Y, pb, debt / Ynom,
                               rev, pexp, vat, Y / (emp * hours / 1e4), r]):
            res[k].append(v)
    return {k: np.array(v) for k, v in res.items()}


# 世帯：名称, 額面, 所得税+住民税, 社保本人, 年間消費, うち食料, 光熱輸送, 人数(万), 世帯人数
HH = [("年収200万 単身", 200, 8, 29, 185, 46, 32, 1100, 1),
      ("年収300万 単身", 300, 17, 44, 265, 60, 36, 1300, 1),
      ("年収500万 単身", 500, 55, 75, 400, 82, 42, 1200, 1),
      ("年収800万 世帯", 800, 110, 115, 600, 125, 55, 900, 2),
      ("年収1500万 世帯", 1500, 330, 170, 950, 170, 70, 250, 2),
      ("年金 高齢単身", 140, 0, 9, 145, 40, 30, 700, 1),
      ("年金 高齢夫婦", 270, 2, 18, 255, 72, 42, 1400, 2),
      ("生活保護 単身", 120, 0, 0, 120, 36, 26, 170, 1)]


def household(sc: R, credit_per_head_by_income):
    """credit_per_head_by_income: 額面→給付付き税額控除の額（万円）を返す関数"""
    rows = []
    for name, inc, tax, si, cons, food, energy, cnt, heads in HH:
        d = 0.0
        # 年収の壁178万円による所得税減税（低〜中所得ほど相対的に効く）
        d += min(tax, 178 * 0.05) if tax > 0 else 0.0
        # 給付付き税額控除
        d += credit_per_head_by_income(inc) * heads
        # 段階的な消費税引き上げ
        d += -((cons - food) * 0.6 + food * 0.6) * (sc.vat_step / 100)
        # 炭素税の転嫁
        if sc.carbon:
            d += -energy * 0.13 * (sc.carbon / 5.0)
        rows.append((name, inc - tax - si, d, d / max(inc - tax - si, 1) * 100, cnt))
    return rows


def gini(rows):
    v = np.array([b + n for _, b, n, _, _ in rows], float)
    w = np.array([c for *_, c in rows], float)
    o = np.argsort(v); v, w = v[o], w[o]
    cw = np.cumsum(w) / w.sum(); cv = np.cumsum(v * w) / (v * w).sum()
    return 1 - np.sum((cv[1:] + cv[:-1]) * np.diff(cw))


# ============================================================
# シナリオ
# ============================================================
# すでに決まっているものだけ（＝いまの日本の既定路線）
KIMATTA = dict(wall178=-0.9, shakai_kakudai=4.5, zaishoku=-0.3,
               food_vat_cut=-1.2, food_vat_years=2, kyufu_tax_credit=3.0)

SCEN = [
    ("① 何もしない（改革ゼロ）", R("a", boost=0.0)),

    ("② 既定路線のみ（いま決まっている分配策だけ）",
     R("b", boost=0.0, part=0.020, **KIMATTA)),

    ("③ ＋ タダの生産性改革だけ",
     R("c", boost=0.003, inv_i=0.033, part=0.030,
       imm_depreciation=-0.5, **KIMATTA)),

    ("④ ＋ 訓練投資（GDP比0.1→0.5%）",
     R("d", boost=0.005, inv_i=0.038, part=0.032,
       imm_depreciation=-0.5, train_invest=2.5, **KIMATTA)),

    ("⑤ ＋ 新陳代謝（承継・保証縮小・医療適正化）",
     R("e", boost=0.007, inv_i=0.042, part=0.035,
       imm_depreciation=-0.5, train_invest=2.5,
       iryo_tekiseika=3.0, hosho_shukusho=1.0, **KIMATTA)),

    ("⑥ ＋ 炭素税5兆円",
     R("f", boost=0.007, inv_i=0.042, part=0.035,
       imm_depreciation=-0.5, train_invest=2.5,
       iryo_tekiseika=3.0, hosho_shukusho=1.0, carbon=5.0, **KIMATTA)),

    ("⑦ ＋ 消費税を2036年から10年かけて+3pt",
     R("g", boost=0.007, inv_i=0.042, part=0.035,
       imm_depreciation=-0.5, train_invest=2.5,
       iryo_tekiseika=3.0, hosho_shukusho=1.0, carbon=5.0,
       vat_step=3.0, vat_step_start=10, vat_step_years=10, **KIMATTA)),
]

if __name__ == "__main__":
    print("=" * 108)
    print("【現実解の検証】2026年8月時点の政治日程を制約に置いた場合")
    print("=" * 108)
    print(f"{'シナリオ':<40}{'一人当GDP':>10}{'2045':>7}{'2060':>7}{'傾き':>9}  判定")
    base = None
    for nm, sc in SCEN:
        r = run(sc)
        if base is None:
            base = r
        d = r["d"]; s = (d[-1] - d[-6]) / 5 * 100
        v = "安定" if s < 0.3 else ("収束" if s < 1.2 else "発散")
        print(f"{nm:<40}{r['gdp_pc'][-1]:>9.0f}万{d[19]*100:>6.0f}%{d[-1]*100:>6.0f}%"
              f"{s:>+8.2f}pt  {v}")
    print()

    print("=" * 108)
    print("【生活水準】一人当たり実質GDP（万円、2026年価格）")
    print("=" * 108)
    print(f"{'シナリオ':<40}{'2030':>8}{'2040':>8}{'2050':>8}{'2060':>8}{'①比':>9}")
    for nm, sc in SCEN:
        r = run(sc)
        print(f"{nm:<40}{r['gdp_pc'][4]:>8.0f}{r['gdp_pc'][14]:>8.0f}"
              f"{r['gdp_pc'][24]:>8.0f}{r['gdp_pc'][-1]:>8.0f}"
              f"{(r['gdp_pc'][-1]/base['gdp_pc'][-1]-1)*100:>+8.1f}%")
