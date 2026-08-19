#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
消費税を10%に据え置いたまま国債残高が膨らんだ場合、円の価値はどうなるか。

考え方
  自国通貨建ての債務は、返せなくなっても「返さない」（デフォルト）とは限らない。
  実際に起きるのは次の3つのどれかである。
    (1) 増税する         → 本計画。消費税21.1%（改革あり）／38.3%（改革なし）
    (2) 給付を削る       → 年金・医療の実質削減
    (3) インフレで薄める → 通貨の購買力が落ちる ＝ 円安

  ここでは (1) も (2) もやらない場合、つまり (3) だけで帳尻を合わせる場合に
  必要なインフレ率を逆算し、そこから円の対ドル価値を出す。

  重要な限界（フィッシャー効果）
    インフレが続くと予想されれば、名目金利もその分だけ上がる。したがって
    インフレで薄められるのは「すでに発行済みで金利が固定されている国債」だけ。
    日本の国債の平均残存は約9年なので、効くのはその期間ぶんに限られる。
    つまりインフレは債務問題を解決しない。時間を買うだけである。
    それでも帳尻を合わせようとすると、必要なインフレ率は跳ね上がる。

  為替は購買力平価（PPP）で置く。長期の目安であって予測ではない。
  実際の為替はPPPから何十年も離れることがある（現に日本円はいま大きく円安側）。

  python3 v6_yen.py
"""
from __future__ import annotations
from typing import Iterable, Optional
import numpy as np
from model_v2 import (POP, WAP, OLD, AT, AI, BL, DT, DI, GDP0, KT0, KI0, L0, H0,
                      R0, R_RAMP, REV, EXP, DEBT0, VATPT, DEBT_ANCHOR, LAMBDA,
                      AVG_MATURITY, MULT_TAX, MULT_SPEND, GAP_PERSIST, GAP_PASS,
                      HYSTERESIS, HYST_CAP, ramp)
from v2_plan import KIM

W = 96
USDJPY_2026 = 159.0        # 2026年8月時点の実勢（7月に163円台、8月は159円前後）
US_INFLATION = 0.020       # 米国の物価上昇率（FRBの目標）
BASE_INFLATION = 0.020     # 本計画が置いている日本の物価上昇率


def run_inf(inflation: float, vat_step: float = 0.0, vat_start: int = 4,
            boost: float = 0.0, inv: float = 0.030, part: float = 0.020,
            extra: Optional[dict] = None, years: int = 35,
            repression: Optional[float] = None) -> dict:
    """
    インフレ率を変えて走らせる。
      repression=None … 名目金利はフィッシャー効果で調整（市場に任せる）
      repression=x    … 名目金利を x に抑え込む（金融抑圧。日銀が国債を買い支える）
    """
    ex = dict(KIM) if extra is None else dict(extra)
    A, Kt, Ki, debt, price = 1.0, KT0, KI0, DEBT0, 1.0
    scale = GDP0 / (KT0 ** AT * KI0 ** AI * ((L0 * H0) / 1e4) ** BL)
    d = DEBT0 / GDP0
    gap = gap_ma = 0.0
    tax_prev = spend_prev = 0.0
    Y_prev = GDP0
    r_eff = R0
    # フィッシャー効果：期待インフレが上がった分だけ名目金利も上がる
    fisher = inflation - BASE_INFLATION
    out = {k: [] for k in ["year", "d", "r", "price", "gdp_pc", "pb"]}

    for t, year in enumerate(range(2026, 2026 + years)):
        emp = WAP[year] * (L0 / WAP[2025] + ramp(t, 8, part)) + OLD[year] * 0.005
        hours = H0 * 0.997 ** t
        pen = min(HYST_CAP, HYSTERESIS * max(0.0, -gap_ma))
        A *= (1 + 0.005 + ramp(t, 10, boost) - pen)
        Kt = Kt * (1 - DT) + 0.155 * Y_prev
        Ki = Ki * (1 - DI) + (0.030 + ramp(t, 10, inv - 0.030)) * Y_prev
        Y_pot = scale * A * Kt ** AT * Ki ** AI * (emp * hours / 1e4) ** BL

        vat = 0.10 + (ramp(t - vat_start, 10, vat_step) / 100
                      if vat_step and t >= vat_start else 0.0)
        tax_now = (vat - 0.10) * 100 * VATPT + ramp(t, 8, ex.get("carbon", 0.0)) \
            + (ex.get("food_vat_cut", 0.0) if t < ex.get("food_vat_years", 0) else 0.0) * -1
        spend_now = ramp(t, 5, ex.get("train_invest", 0.0)) \
            + (ramp(t - ex.get("credit_start", 3), 3, ex.get("credit", 0.0))
               if t >= ex.get("credit_start", 3) else 0.0) \
            + (-ex.get("food_vat_cut", 0.0) if t < ex.get("food_vat_years", 0) else 0.0) \
            - ramp(t, 15, ex.get("iryo", 0.0)) - ramp(t, 10, ex.get("hosho", 0.0))
        impulse = ((tax_now - tax_prev) * MULT_TAX
                   - (spend_now - spend_prev) * MULT_SPEND) / Y_prev
        gap = GAP_PERSIST * gap - impulse
        Y_act = Y_pot * (1 + GAP_PASS * min(0.0, gap))
        gap_ma = 0.7 * gap_ma + 0.3 * min(0.0, gap)
        tax_prev, spend_prev, Y_prev = tax_now, spend_now, Y_act

        price *= (1 + inflation + 0.3 * gap)
        Ynom = Y_act * price
        q = Y_act / GDP0

        rev = (REV["所得税"] + REV["法人税"] + REV["その他税"] + REV["社保"]
               + REV["その他"] + REV["消費税"] + (vat - 0.10) * 100 * VATPT) * q * price
        rev += ex.get("wall178", 0.0) * price
        rev += ramp(t, 3, ex.get("shakai_kakudai", 0.0)) * price
        if t < ex.get("food_vat_years", 0):
            rev += ex.get("food_vat_cut", 0.0) * price
        rev += ramp(t, 5, ex.get("imm_dep", 0.0)) * price
        rev += ramp(t, 8, ex.get("carbon", 0.0)) * price

        soc = EXP["社会保障"] * (OLD[year] / OLD[2025]) * price * 1.004 ** t
        soc -= ramp(t, 15, ex.get("iryo", 0.0)) * price
        soc += ramp(t, 3, -ex.get("zaishoku", 0.0)) * price
        pexp = soc + (EXP["一般"] + EXP["地方"]) * q * price
        pexp += ramp(t, 5, ex.get("train_invest", 0.0)) * price
        pexp -= ramp(t, 10, ex.get("hosho", 0.0)) * price
        if t >= ex.get("credit_start", 3):
            pexp += ramp(t - ex.get("credit_start", 3), 3, ex.get("credit", 0.0)) * price

        if repression is None:
            r_base = R0 + (0.022 - R0) * min(1.0, (t + 1) / R_RAMP) + fisher
            r_mkt = min(r_base + LAMBDA * max(0.0, d - DEBT_ANCHOR), 0.30)
        else:
            r_mkt = repression          # 金利を抑え込む
        r_eff += (r_mkt - r_eff) / AVG_MATURITY
        pb = rev - pexp
        debt -= (pb - debt * r_eff)
        d = min(debt / Ynom, 30.0)

        for k, v in zip(out, [year, d, r_eff, price, Y_act / POP[year] * 1e4, pb]):
            out[k].append(v)
    return {k: np.array(v) for k, v in out.items()}


def slope(r: dict) -> float:
    return (r["d"][-1] - r["d"][-6]) / 5 * 100


def solve_inflation(hi0: float = 0.60, repression: Optional[float] = None) -> float:
    """消費税10%据え置き・改革なしで、債務を止めるのに必要なインフレ率"""
    lo, hi = 0.0, hi0
    for _ in range(60):
        mid = (lo + hi) / 2
        if slope(run_inf(mid, repression=repression)) > 0:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def usdjpy(jp_inf: float, years: int) -> float:
    """購買力平価で置いた対ドル相場"""
    return USDJPY_2026 * ((1 + jp_inf) / (1 + US_INFLATION)) ** years


if __name__ == "__main__":
    print("=" * W)
    print("【1】インフレでは債務は止まらない。円の価値だけが落ちる")
    print("=" * W)
    print(f"{'日本のインフレ率':<16}{'2040年の円':>12}{'2060年の円':>13}"
          f"{'円の購買力':>11}{'2060年 債務':>12}{'金利':>8}{'判定':>7}")
    for inf in [0.02, 0.03, 0.04, 0.06, 0.08, 0.10]:
        r = run_inf(inf)
        sl = slope(r)
        v = "安定" if sl < 0.3 else ("収束" if sl < 1.2 else "発散")
        y40, y60 = usdjpy(inf, 14), usdjpy(inf, 34)
        print(f"  年{inf*100:>4.1f}%{'':<7}{y40:>10,.0f}円{y60:>11,.0f}円"
              f"{USDJPY_2026/y60*100:>10.1f}%{r['d'][-1]*100:>11.0f}%"
              f"{r['r'][-1]*100:>7.1f}%{v:>7}")
    print()
    print("  どのインフレ率でも債務は止まらない。名目金利が同じだけ上がるためである")
    print("  （フィッシャー効果）。インフレで薄められるのは、すでに発行済みで金利が")
    print("  固定されている分だけ。日本国債の平均残存は約9年なので、効果はその期間に限られる。")
    print()

    print("=" * W)
    print("【2】金利を抑え込む場合（金融抑圧＝日銀が国債を買い支える）")
    print("=" * W)
    print(f"{'インフレ率':<14}{'2060年 純債務/GDP':>20}{'2060年の円':>14}{'判定':>8}")
    for inf in [0.02, 0.05, 0.10, 0.15, 0.20, 0.30]:
        r = run_inf(inf, repression=0.010)
        sl = slope(r)
        v = "安定" if sl < 0.3 else ("収束" if sl < 1.2 else "発散")
        print(f"  年{inf*100:>4.1f}%{'':<5}{r['d'][-1]*100:>17.0f}%"
              f"{usdjpy(inf,34):>12,.0f}円{v:>8}")
    print()
    print("  金利を抑え込めば債務比率は下がる。ただし必要なインフレ率は年30%規模になる。")
    print("  金利を抑え込むとは、預金・年金・国債の実質価値を削るということである。")
    print("  つまり『増税しない』を選んでも負担は消えない。取られ方が変わるだけである。")
    print()

    print("=" * W)
    print("【3】3つの道の比較")
    print("=" * W)
    from v4_plan import solve, go, boost_for, CONV, B_
    b = boost_for(CONV["中位（5割収束）"])
    st = solve(b, B_)
    plan = go(b, B_, st)
    print(f"{'':<30}{'消費税':>8}{'物価':>8}{'2060年の円':>13}{'一人当たり所得':>15}")
    print(f"{'A 改革あり・増税（本計画）':<30}{10+st:>7.1f}%{'年2%':>8}"
          f"{usdjpy(0.02,34):>11,.0f}円{plan['gdp_pc'][-1]:>13.0f}万円")
    print(f"{'B 改革なし・増税':<30}{38.3:>7.1f}%{'年2%':>8}"
          f"{usdjpy(0.02,34):>11,.0f}円{479:>13.0f}万円")
    print(f"{'C 増税せず・インフレ年6%':<30}{10.0:>7.1f}%{'年6%':>8}"
          f"{usdjpy(0.06,34):>11,.0f}円{494:>13.0f}万円")
    print()
    print("  ※ 一人当たり所得は実質（2026年価格）。Cはインフレでも実質所得は増えない。")
    print("     名目の数字だけが膨らみ、買えるものは変わらない。しかも債務は止まっていない。")
