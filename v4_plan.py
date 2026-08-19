#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
第4版の確定計算。第3版に残っていた3つの穴を塞いだもの。

  穴1 収束率50%の根拠がない
    → 独立した2つの推計を突き合わせて天井を検証し、収束率を
      「政府の成長実現ケースの何割を達成するか」という検証可能な問いに置き換えた。
        (A) RIETI（Hsieh-Klenow）：配分の歪みをすべて除けば TFP +40%（米国 +6.2%）
            → 米国並みへの伸びしろ +31.8% → 35年で完全収束なら年 +0.79pt
            → 現状のTFP 0.5% に足すと 1.29%
        (B) 内閣府「成長実現ケース」：TFP 1.4%（デフレ前の期間の平均）
        差は 0.11pt。別々の方法で測って同じ天井に着いた。

  穴2 各政策から収束率への経路がない
    → 未解決。ただし束としての上限は測れた。個別政策には反証可能なKPIを置く。

  穴3 金利係数λが借り物
    → 2点を修正。
      (a) 満期構造を入れた。修正前は金利変化を債務全額に即時適用しており、
          利払いの立ち上がりが実績の3.1倍だった（実績：1%上昇→3年後+3.7兆円）。
          平均残存9年として実効金利を市場金利へ1/9ずつ近づける形に直した。
      (b) 日本の歴史的なλはほぼゼロ（債務100%→250%の間に金利は下落）。
          滑らかな係数は便宜であり、実態は閾値超えで跳ねる非線形。
          regime=True でその形も試せるようにした。

  python3 v4_plan.py
"""
from typing import Any
import numpy as np
from model_v2 import (S, run, households, dist, coverage, LAMBDA, AVG_MATURITY,
                      LAMBDA_LOW, LAMBDA_HIGH)
from v2_plan import KIM, A_, B_, C_, BASE

W = 100
INV, PART = 0.040, 0.035

# ---- 生産性の天井（実証） ----
JP_GAP, US_GAP, YEARS = 0.40, 0.062, 35
CEILING = (1 + JP_GAP) / (1 + US_GAP) - 1
HUMAN, CAPITAL = 0.02, 0.07
TFP_BASE, TFP_GROW = 0.5, 1.4          # 内閣府 ベースライン／成長実現ケース


def annual(total: float, years: int = YEARS) -> float:
    return ((1 + total) ** (1 / years) - 1) * 100


def boost_for(conv: float) -> float:
    return (annual(CEILING * conv) + HUMAN + CAPITAL) / 100


def achieve_rate(boost: float) -> float:
    """成長実現ケース（TFP1.4%）の何割を達成することに相当するか"""
    return (boost * 100) / (TFP_GROW - TFP_BASE) * 100


CONV = {"強気（7割収束）": 0.70, "中位（5割収束）": 0.50, "保守（3割収束）": 0.30}


def slope(r: dict) -> float:
    return (r["d"][-1] - r["d"][-6]) / 5 * 100


def verdict(r: dict) -> str:
    if r["d"][-1] >= 19.9: return "破綻"
    s = slope(r)
    return "安定" if s < 0.3 else ("収束" if s < 1.2 else "発散")


def solve(boost: float, extra: dict, start: int = 4, **kw: Any) -> float:
    lo, hi = 0.0, 60.0
    for _ in range(50):
        mid = (lo + hi) / 2
        r = run(S("x", boost=boost, inv_i=kw.pop("inv", INV) if "inv" in kw else INV,
                  part=kw.pop("part", PART) if "part" in kw else PART,
                  vat_step=mid, vat_start=start, vat_years=10, **{**extra, **kw}))
        if slope(r) > 0: lo = mid
        else: hi = mid
    return (lo + hi) / 2


def go(boost: float, extra: dict, step: float, start: int = 4, **kw: Any) -> dict:
    return run(S("y", boost=boost, inv_i=INV, part=PART, vat_step=step,
                 vat_start=start, vat_years=10, **{**extra, **kw}))


REC_BOOST = boost_for(CONV["中位（5割収束）"])
REC_STEP = solve(REC_BOOST, B_)
REC = go(REC_BOOST, B_, REC_STEP)

if __name__ == "__main__":
    print("=" * W)
    print("【1】穴1 ── 天井を、独立した2つの方法で突き合わせる")
    print("=" * W)
    print(f"  (A) 配分の歪みから   日本+{JP_GAP*100:.0f}% ／ 米国+{US_GAP*100:.1f}%"
          f" → 伸びしろ+{CEILING*100:.1f}% → 年+{annual(CEILING):.2f}pt")
    print(f"      現状のTFP {TFP_BASE:.1f}% に足すと …………… {TFP_BASE+annual(CEILING):.2f}%")
    print(f"  (B) 日本自身の過去の実績から（内閣府 成長実現ケース） … {TFP_GROW:.1f}%")
    print(f"  → 差 {abs(TFP_BASE+annual(CEILING)-TFP_GROW):.2f}pt。互いに独立な推計が"
          f"同じ天井に着いた。")
    print()
    print(f"{'生産性の上積み':<16}{'到達TFP':>9}{'成長実現ケース達成率':>20}{'配分効率の収束率':>17}")
    for nm, c in [("【第2版】", 0.98)] + list(CONV.items()):
        b = boost_for(c)
        mark = "  ← 採用" if abs(b - REC_BOOST) < 1e-9 else ""
        print(f"{nm:<16}{TFP_BASE+b*100:>8.2f}%{achieve_rate(b):>19.0f}%"
              f"{c*100:>16.0f}%{mark}")
    print()
    print("  → 採用値は『政府が毎年掲げて一度も達成していない成長実現ケースの57%を取る』")
    print("     ことに等しい。抽象的な収束率より検証しやすく、かつ相当に強気だと分かる。")
    print()

    print("=" * W)
    print("【2】穴3(a) ── 満期構造を入れた影響")
    print("=" * W)
    sh3 = 1 - (1 - 1 / AVG_MATURITY) ** 3
    print(f"  実績アンカー：金利1%上昇 → 3年後の利払費 +3.7兆円（グロス1,145兆円）")
    print(f"                ネット960兆円換算で {3.7*960/1145:.2f}兆円")
    print(f"  本モデル：平均残存{AVG_MATURITY:.0f}年 → 3年で{sh3*100:.1f}%追随"
          f" → {0.01*sh3*960:.2f}兆円")
    print(f"  → 差 {abs(0.01*sh3*960-3.7*960/1145):.2f}兆円（8%）。整合。")
    print(f"  修正前は債務全額に即時適用しており {0.01*960:.2f}兆円 ＝ 実績の"
          f"{0.01*960/(3.7*960/1145):.1f}倍を計上していた。")
    print()
    print(f"{'ケース':<24}{'生産性':>9}{'修正前':>9}{'修正後':>9}{'差':>9}")
    BEF = {0.0087: 15.1, 0.0067: 19.0, 0.0051: 22.3, 0.0035: 26.0}
    for nm, c in [("【第2版】想定", 0.98)] + list(CONV.items()):
        b = boost_for(c); st = solve(b, B_)
        bf = BEF.get(round(b, 4))
        print(f"{nm:<24}{b*100:>+8.2f}pt{bf:>8.1f}%{10+st:>8.1f}%{10+st-bf:>+8.1f}pt")
    print()

    print("=" * W)
    print("【3】穴3(b) ── レジーム転換型で試す（λが閾値超えで跳ねる形）")
    print("=" * W)
    print(f"  日本の歴史的なλはほぼゼロ。滑らかな係数は便宜であり、")
    print(f"  実態に近いのは閾値超えで跳ねる非線形（λ {LAMBDA_LOW}→{LAMBDA_HIGH}）。")
    print()
    print(f"{'閾値':<10}{'推奨案の2060債務':>18}{'判定':>8}{'既定路線の2060債務':>20}{'判定':>8}")
    for th in [1.80, 2.00, 2.20, 2.50]:
        rp = go(REC_BOOST, B_, REC_STEP, regime=True, threshold=th)
        rb = run(S("b", boost=0.0, inv_i=0.030, part=0.020, regime=True,
                   threshold=th, **KIM))
        print(f"{th*100:>8.0f}%{rp['d'][-1]*100:>17.0f}%{verdict(rp):>8}"
              f"{rb['d'][-1]*100:>19.0f}%{verdict(rb):>8}")
    print()
    print("  → 推奨案はどの閾値でも転換しない。既定路線はどの閾値でも必ず転換する。")
    print("     λの値そのものより『閾値を超えないこと』が設計目標になる。")
    print()

    print("=" * W)
    print(f"【4】推奨案 ── 生産性+{REC_BOOST*100:.2f}pt／消費税 10% → {10+REC_STEP:.1f}%"
          f"（2030年から10年）")
    print("=" * W)
    print(f"  一人当たり実質所得  {BASE['gdp_pc'][-1]:.0f}万円 → {REC['gdp_pc'][-1]:.0f}万円"
          f"（{(REC['gdp_pc'][-1]/BASE['gdp_pc'][-1]-1)*100:+.1f}%）")
    print(f"  純債務/GDP        {REC['d'][-1]*100:.0f}%（{verdict(REC)}）"
          f"  2060年の実効金利 {REC['r'][-1]*100:.2f}%")
    h = households(REC_STEP, carbon=0.0, credit=True); d = dist(h)
    print("  家計  " + "   ".join(f"{k} {d[k]:+.1f}%"
                                 for k in ["下位20%", "中位60%", "上位20%", "最も不利"]))
    print()
    for nm, b, dl, p, c, hd in h:
        print(f"    {nm:<24}{b:>7.0f}万 {dl:>+8.1f}万 ({p:>+5.1f}%)")
    print()

    print("=" * W)
    print("【5】束と開始時期")
    print("=" * W)
    print(f"{'どこまで通せるか':<24}{'生産性':>9}{'必要な消費税':>13}{'一人当GDP':>11}{'最も不利':>10}")
    for nm, ex, c in [("A 4点以上のみ", A_, 0.42), ("B ＋信用保証（推奨）", B_, 0.50),
                      ("C ＋医療費・炭素税", C_, 0.56)]:
        b = boost_for(c); st = solve(b, ex); r = go(b, ex, st)
        hh = households(st, carbon=(5.0 if ex is C_ else 0.0), credit=True)
        print(f"{nm:<24}{b*100:>+8.2f}pt{10+st:>12.1f}%{r['gdp_pc'][-1]:>10.0f}万"
              f"{dist(hh)['最も不利']:>+9.1f}%")
    print()
    print(f"{'開始年':<10}{'必要な引上げ':>13}{'到達税率':>10}{'ピーク債務':>12}   国際的な位置")
    for st_, yr in [(4, 2030), (7, 2033), (10, 2036), (14, 2040), (19, 2045)]:
        n = solve(REC_BOOST, B_, start=st_); r = go(REC_BOOST, B_, n, start=st_)
        pos = "世界に前例なし" if 10 + n > 27 else ("北欧超" if 10 + n > 25 else "北欧並み")
        print(f"{yr:<10}{n:>+12.1f}pt{10+n:>9.1f}%{r['d'].max()*100:>11.0f}%   {pos}")
    print()

    print("=" * W)
    print("【6】感度")
    print("=" * W)
    print(f"{'動かす前提':<38}{'必要な消費税':>13}")
    cases = [("金利 λ=0.00", dict(lam=0.0)), ("金利 λ=0.02（採用）", dict(lam=0.02)),
             ("金利 λ=0.04", dict(lam=0.04)),
             ("レジーム転換型（閾値220%）", dict(regime=True)),
             ("平均残存 6年（短い）", dict(maturity=6.0)),
             ("平均残存 12年（長い）", dict(maturity=12.0)),
             ("需要側なし", dict(demand=False))]
    vals = []
    for nm, kw in cases:
        v = 10 + solve(REC_BOOST, B_, **kw); vals.append(v)
        print(f"{nm:<38}{v:>12.1f}%")
    print(f"\n  → 幅 {min(vals):.1f}〜{max(vals):.1f}%。生産性の収束率を動かすと"
          f"{10+solve(boost_for(0.7),B_):.1f}〜{10+solve(boost_for(0.3),B_):.1f}%。")
    print("     いま最も効くのは依然として生産性であり、金利や満期の前提ではない。")
