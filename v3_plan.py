#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
第3版の確定計算。
第2版からの最大の変更は、生産性の割り当てを「設計上の希望」から
「実証推計にもとづく上限からの逆算」に置き換えたこと。

  出典: RIETI（Hsieh-Klenow 手法を日本の製造業に適用）
    日本 …… 資源配分の歪みをすべて除けば TFP +40%（うち資本の歪みが +21%）
    米国 …… 同手法での TFP gain は +6.2%
  → 日本が米国並みの配分効率になった場合の伸びしろ = (1.40/1.062 − 1) = +31.8%
  → 35年で完全収束すると年率 +0.79pt。これが再配置効果の理論上の天井。

  第2版は再配置に +0.78pt を置いていた。天井の98%＝ほぼ完全収束という前提で、
  強すぎた。第3版は「5割収束」を中位として +0.42pt に引き下げる。

  python3 v3_plan.py
"""
from typing import Any
import numpy as np
from model_v2 import S, run, households, dist, coverage, LAMBDA
from v2_plan import KIM, A_, B_, C_, BASE

W = 100
INV, PART = 0.040, 0.035          # 政策の投入量。収束率によらず一定

# ---- 生産性の分解（実証にもとづく） ----
JP_GAP, US_GAP, YEARS = 0.40, 0.062, 35
CEILING = (1 + JP_GAP) / (1 + US_GAP) - 1          # +31.8%
HUMAN, CAPITAL = 0.02, 0.07                        # 算術で計算できる分（pt）


def annual(total: float, years: int = YEARS) -> float:
    """累積の水準効果を年率(pt)に直す"""
    return ((1 + total) ** (1 / years) - 1) * 100


def boost_for(conv: float) -> float:
    """米国並みへの収束率 conv のときの生産性上積み（小数）"""
    return (annual(CEILING * conv) + HUMAN + CAPITAL) / 100


CONV = {"強気（7割収束）": 0.70, "中位（5割収束）": 0.50, "保守（3割収束）": 0.30}


def slope(r: dict) -> float:
    return (r["d"][-1] - r["d"][-6]) / 5 * 100


def verdict(r: dict) -> str:
    if r["d"][-1] >= 19.9: return "破綻"
    s = slope(r)
    return "安定" if s < 0.3 else ("収束" if s < 1.2 else "発散")


def solve(boost: float, extra: dict, start: int = 4, lam: float = LAMBDA,
          demand: bool = True, inv: float = INV, part: float = PART) -> float:
    lo, hi = 0.0, 60.0
    for _ in range(50):
        mid = (lo + hi) / 2
        r = run(S("x", boost=boost, inv_i=inv, part=part, vat_step=mid,
                  vat_start=start, vat_years=10, lam=lam, demand=demand, **extra))
        if slope(r) > 0: lo = mid
        else: hi = mid
    return (lo + hi) / 2


def go(boost: float, extra: dict, step: float, start: int = 4,
       inv: float = INV, part: float = PART) -> dict:
    return run(S("y", boost=boost, inv_i=inv, part=part, vat_step=step,
                 vat_start=start, vat_years=10, **extra))


# ---- 推奨案を確定 ----
REC_BOOST = boost_for(CONV["中位（5割収束）"])
REC_STEP = solve(REC_BOOST, B_)
REC = go(REC_BOOST, B_, REC_STEP)

if __name__ == "__main__":
    print("=" * W)
    print("【1】生産性の上限を、実証推計から測る")
    print("=" * W)
    print(f"  日本（製造業）の歪みをすべて除いた場合の TFP 上昇   +{JP_GAP*100:.0f}%")
    print(f"  米国の同指標                                  +{US_GAP*100:.1f}%")
    print(f"  → 米国並みの配分効率までの伸びしろ               +{CEILING*100:.1f}%")
    print(f"  → 35年で完全収束した場合の年率                  +{annual(CEILING):.2f}pt")
    print()
    print(f"{'米国並みへの収束率':<20}{'累積TFP':>10}{'再配置(年率)':>13}"
          f"{'＋人的資本・資本':>15}{'生産性の上積み':>14}")
    for nm, c in list(CONV.items()) + [("【第2版】の想定", 0.98)]:
        re_ = annual(CEILING * c)
        print(f"{nm:<20}{CEILING*c*100:>+9.1f}%{re_:>+12.2f}pt"
              f"{HUMAN+CAPITAL:>+14.2f}pt{re_+HUMAN+CAPITAL:>+13.2f}pt")
    print()
    print("  第2版は天井の98%＝ほぼ完全収束を前提にしていた。第3版は5割収束を中位に採る。")
    print()

    print("=" * W)
    print("【2】改定の影響 ── 必要な消費税（2030年から10年かけて引き上げ／束B）")
    print("=" * W)
    print(f"{'ケース':<24}{'生産性':>9}{'必要な消費税':>13}{'一人当GDP':>11}{'2060債務':>10}  判定")
    rows = [("【第2版】の想定", 0.0085)] + [(nm, boost_for(c)) for nm, c in CONV.items()]
    for nm, b in rows:
        st = solve(b, B_); r = go(b, B_, st)
        mark = "  ← 採用" if abs(b - REC_BOOST) < 1e-9 else ""
        print(f"{nm:<24}{b*100:>+8.2f}pt{10+st:>12.1f}%{r['gdp_pc'][-1]:>10.0f}万"
              f"{r['d'][-1]*100:>9.0f}%  {verdict(r)}{mark}")
    print()

    print("=" * W)
    print("【3】どこまで通せるか（政治採点の束）× 中位の生産性")
    print("=" * W)
    print(f"{'束':<26}{'生産性':>9}{'必要な消費税':>13}{'一人当GDP':>11}{'最も不利':>10}  判定")
    for nm, ex, c in [("A 4点以上のみ", A_, 0.42), ("B ＋信用保証（推奨）", B_, 0.50),
                      ("C ＋医療費・炭素税", C_, 0.56)]:
        b = boost_for(c); st = solve(b, ex); r = go(b, ex, st)
        h = households(st, carbon=(5.0 if ex is C_ else 0.0), credit=True)
        print(f"{nm:<26}{b*100:>+8.2f}pt{10+st:>12.1f}%{r['gdp_pc'][-1]:>10.0f}万"
              f"{dist(h)['最も不利']:>+9.1f}%  {verdict(r)}")
    print()

    print("=" * W)
    print("【4】開始時期 ── 先送りの代償は改定で跳ね上がった")
    print("=" * W)
    print(f"{'開始年':<10}{'必要な引上げ':>13}{'到達税率':>10}{'ピーク債務':>12}   評価")
    for st_, yr in [(4, 2030), (7, 2033), (10, 2036), (14, 2040), (19, 2045)]:
        n = solve(REC_BOOST, B_, start=st_)
        r = go(REC_BOOST, B_, n, start=st_)
        note = "世界に前例なし" if 10 + n > 27 else ("北欧超" if 10 + n > 25 else "北欧並み")
        print(f"{yr:<10}{n:>+12.1f}pt{10+n:>9.1f}%{r['d'].max()*100:>11.0f}%   {note}")
    print()

    print("=" * W)
    print(f"【5】推奨案の家計（消費税 {10+REC_STEP:.1f}%・炭素税なし・給付付き税額控除あり）")
    print("=" * W)
    h = households(REC_STEP, carbon=0.0, credit=True)
    for nm, b, dl, p, c, hd in h:
        print(f"  {nm:<24}{b:>7.0f}万 {dl:>+8.1f}万 ({p:>+5.1f}%)")
    d = dist(h)
    print()
    print("  " + "   ".join(f"{k} {d[k]:+.1f}%"
                            for k in ["下位20%", "中位60%", "上位20%", "最も不利"]))
    print(f"\n  一人当たり実質所得 {BASE['gdp_pc'][-1]:.0f}万円 → {REC['gdp_pc'][-1]:.0f}万円"
          f"（{(REC['gdp_pc'][-1]/BASE['gdp_pc'][-1]-1)*100:+.1f}%）")
    print(f"  純債務/GDP {REC['d'][-1]*100:.0f}%（{verdict(REC)}）"
          f"  2060年金利 {REC['r'][-1]*100:.2f}%")
    print()

    print("=" * W)
    print("【6】感度")
    print("=" * W)
    print(f"{'動かす前提':<36}{'必要な消費税':>13}")
    for nm, kw in [("金利 λ=0.00（第1版の前提）", dict(lam=0.0)),
                   ("金利 λ=0.02（採用）", dict(lam=0.02)),
                   ("金利 λ=0.04（悲観）", dict(lam=0.04)),
                   ("需要側なし（第1版の前提）", dict(demand=False)),
                   ("無形投資を低く（0.036）", dict(inv=0.036)),
                   ("就業率の押上げ半分（0.018）", dict(part=0.018))]:
        print(f"{nm:<36}{10+solve(REC_BOOST, B_, **kw):>12.1f}%")
    print()
    print("  ※ 上振れ要因：RIETIの推計は製造業のみ。日本の生産性の穴はサービス業")
    print("    （対米22〜38%）にあるため、経済全体の歪みは製造業より大きい可能性が高い。")
    print("    その場合、同じ収束率でも生産性の上積みはこれより大きくなる。")
