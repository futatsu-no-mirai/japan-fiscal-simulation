#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v2 の確定計算。金利内生化＋需要側＋世帯20類型＋政治的実現可能性の採点。
  python3 v2_final.py
"""
import numpy as np
from model_v2 import (S, run, households, dist, coverage, HH,
                      POLICIES, CRITERIA, PASSED, BLOCKED, feasibility, LAMBDA)

W = 100

KIM = dict(wall178=-0.9, shakai_kakudai=4.5, zaishoku=-0.3,
           food_vat_cut=-1.2, food_vat_years=2, credit=3.0)
STAGE1 = dict(imm_dep=-0.5, **KIM)
STAGE2 = dict(imm_dep=-0.5, train_invest=2.5, **KIM)
STAGE3 = dict(imm_dep=-0.5, train_invest=2.5, iryo=3.0, hosho=1.0, **KIM)
FULL = dict(imm_dep=-0.5, train_invest=2.5, iryo=3.0, hosho=1.0, carbon=5.0, **KIM)


def slope(r):
    return (r["d"][-1] - r["d"][-6]) / 5 * 100


def verdict(r):
    if r["d"][-1] >= 19.9:
        return "破綻"
    s = slope(r)
    return "安定" if s < 0.3 else ("収束" if s < 1.2 else "発散")


def solve_vat(boost, inv, part, extra=FULL, start=10, years=10, lam=LAMBDA,
              demand=True, hi0=40.0):
    lo, hi = 0.0, hi0
    for _ in range(48):
        mid = (lo + hi) / 2
        r = run(S("x", boost=boost, inv_i=inv, part=part, vat_step=mid,
                  vat_start=start, vat_years=years, lam=lam, demand=demand, **extra))
        if slope(r) > 0:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


SCEN = [
    ("① 何もしない",                      S("a", boost=0.0)),
    ("② 既定路線のみ",                    S("b", boost=0.0, part=0.020, **KIM)),
    ("③ ＋ 段階1（ゼロ円の制度変更）",      S("c", boost=0.003, inv_i=0.033, part=0.030, **STAGE1)),
    ("④ ＋ 段階2（訓練投資 年2.5兆円）",   S("d", boost=0.005, inv_i=0.038, part=0.032, **STAGE2)),
    ("⑤ ＋ 段階3（新陳代謝）",             S("e", boost=0.007, inv_i=0.042, part=0.035, **STAGE3)),
    ("⑥ ＋ 炭素税5兆円",                  S("f", boost=0.007, inv_i=0.042, part=0.035, **FULL)),
]

if __name__ == "__main__":
    print("=" * W)
    print("【0】v1 → v2 で何が変わったか")
    print("=" * W)
    PLAN = dict(boost=0.007, inv_i=0.042, part=0.035, vat_start=10, vat_years=10)
    for nm, lam, dem in [("v1（金利外生・需要側なし）", 0.0, False),
                         ("　＋ 金利を内生化", LAMBDA, False),
                         ("　＋ 需要側も入れる ＝ v2", LAMBDA, True)]:
        need = solve_vat(0.007, 0.042, 0.035, lam=lam, demand=dem)
        r = run(S("z", vat_step=need, lam=lam, demand=dem, **PLAN, **FULL))
        print(f"{nm:<28} 必要な消費税 {10+need:>5.1f}%   2060年 一人当{r['gdp_pc'][-1]:>5.0f}万 "
              f"債務{r['d'][-1]*100:>4.0f}% {verdict(r)}")
    print()
    print("  金利の内生化で +1.8pt、需要側の追加でさらに動く。v1の「13.2%」は誤りだった。")
    print()

    print("=" * W)
    print("【1】積み上げ（v2：金利内生 λ=0.02・需要側あり）")
    print("=" * W)
    base = run(SCEN[0][1])
    print(f"{'':<34}{'一人当GDP':>10}{'①比':>8}{'2060債務':>9}{'金利':>7}{'傾き':>9}  判定")
    for nm, sc in SCEN:
        r = run(sc)
        print(f"{nm:<34}{r['gdp_pc'][-1]:>9.0f}万"
              f"{(r['gdp_pc'][-1]/base['gdp_pc'][-1]-1)*100:>+7.1f}%"
              f"{r['d'][-1]*100:>8.0f}%{r['r'][-1]*100:>6.2f}%{slope(r):>+8.2f}pt  {verdict(r)}")
    need = solve_vat(0.007, 0.042, 0.035)
    r7 = run(S("g", boost=0.007, inv_i=0.042, part=0.035, vat_step=need,
               vat_start=10, vat_years=10, **FULL))
    print(f"{'⑦ ＋ 消費税 10→'+f'{10+need:.1f}'+'%（2036年から10年）':<34}"
          f"{r7['gdp_pc'][-1]:>9.0f}万"
          f"{(r7['gdp_pc'][-1]/base['gdp_pc'][-1]-1)*100:>+7.1f}%"
          f"{r7['d'][-1]*100:>8.0f}%{r7['r'][-1]*100:>6.2f}%{slope(r7):>+8.2f}pt  {verdict(r7)}")
    print()

    print("=" * W)
    print("【2】必要な消費税率は、生産性の実現度で決まる（v2）")
    print("=" * W)
    print(f"{'生産性の上積み':<22}{'v1（外生・需要なし）':>20}{'v2（内生・需要あり）':>20}   備考")
    for label, b, inv, pt in [("年+0.7pt", 0.007, 0.042, 0.035),
                              ("年+0.5pt", 0.005, 0.038, 0.030),
                              ("年+0.3pt", 0.003, 0.033, 0.025),
                              ("　  0pt", 0.0, 0.030, 0.020)]:
        v1 = solve_vat(b, inv, pt, lam=0.0, demand=False)
        v2 = solve_vat(b, inv, pt)
        note = "世界に前例なし" if 10 + v2 > 27 else ("北欧超" if 10 + v2 > 25 else
               ("北欧並み" if 10 + v2 > 20 else "英・仏(20%)以下"))
        print(f"{label:<22}{10+v1:>19.1f}%{10+v2:>19.1f}%   {note}")
    print()

    print("=" * W)
    print("【3】金利の感度（生産性+0.7ptの計画）")
    print("=" * W)
    print(f"{'λ':>6}{'':3}{'必要な消費税':>12}{'2060債務':>10}{'2060金利':>10}")
    for lam in [0.0, 0.01, 0.02, 0.03, 0.04]:
        nd = solve_vat(0.007, 0.042, 0.035, lam=lam)
        r = run(S("h", boost=0.007, inv_i=0.042, part=0.035, vat_step=nd,
                  vat_start=10, vat_years=10, lam=lam, **FULL))
        print(f"{lam:>6.2f}{'':3}{10+nd:>11.1f}%{r['d'][-1]*100:>9.0f}%{r['r'][-1]*100:>9.2f}%")
    print()

    print("=" * W)
    print("【4】家計 ── 世帯20類型（消費税+"
          f"{need:.1f}pt・炭素税5兆円・給付付き税額控除あり。万円/年、2026年価格）")
    print("=" * W)
    rows = households(need, carbon=5.0, credit=True)
    print(f"{'世帯':<24}{'現行手取り':>10}{'変化':>10}{'率':>8}")
    for nm, b, dl, p, c, h in rows:
        print(f"{nm:<24}{b:>10.0f}{dl:>+10.1f}{p:>+7.1f}%")
    d = dist(rows)
    print()
    for k in ["下位20%", "中位60%", "上位20%", "格差幅", "最も不利"]:
        print(f"  {k:<10}{d[k]:>+7.2f}%")
    hh, pp, cov = coverage()
    print(f"\n  ※ 20類型で世帯 {hh:,}万・人口 {pp:,}万（カバー率{cov:.0f}%）。")
    print("     v1で出していたジニ係数は削除した。20類型では分布の両端を捉えられず、")
    print("     水準も変化幅も信用できない。両端を欠いても読める指標だけを載せた。")
    print()
    print(f"  そして一人当たり実質所得は {base['gdp_pc'][-1]:.0f}万円 → {r7['gdp_pc'][-1]:.0f}万円"
          f"（{(r7['gdp_pc'][-1]/base['gdp_pc'][-1]-1)*100:+.1f}%）。")
    print()

    print("=" * W)
    print("【5】政治的実現可能性 ── 実データから抽出した3基準で採点")
    print("=" * W)
    print("  通った政策（"+str(len(PASSED))+"件）と止まった政策（"+str(len(BLOCKED))+"件）を並べて")
    print("  違いを抽出した結果、判定基準は次の3つになった。")
    for i, (c, why) in enumerate(CRITERIA, 1):
        print(f"\n  基準{i}: {c}")
        print(f"        {why}")
    print()
    print("-" * W)
    print(f"{'政策':<40}{'基1':>4}{'基2':>4}{'基3':>4}{'計':>4}{'通る確率':>10}"
          f"{'生産性':>8}{'財政':>8}")
    print("-" * W)
    for nm, sc, prod, fis, note in POLICIES:
        print(f"{nm:<40}{sc[0]:>4}{sc[1]:>4}{sc[2]:>4}{sum(sc):>4}"
              f"{feasibility(sc):>10}{prod:>+8.2f}{fis:>+8.1f}")
    print("-" * W)
    ok = [p for p in POLICIES if sum(p[1]) >= 4]
    ng = [p for p in POLICIES if sum(p[1]) <= 2]
    print(f"\n  「やや高い」以上（4点以上）だけを積むと 生産性 "
          f"{sum(p[2] for p in ok):+.2f}pt／財政 {sum(p[3] for p in ok):+.1f}兆円")
    print(f"  「低い」以下（2点以下）の合計は     生産性 "
          f"{sum(p[2] for p in ng):+.2f}pt／財政 {sum(p[3] for p in ng):+.1f}兆円")
    print()
    for nm, sc, prod, fis, note in POLICIES:
        if sum(sc) <= 2:
            print(f"  ✕ {nm}\n      {note}")
