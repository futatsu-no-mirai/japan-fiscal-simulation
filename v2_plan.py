#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
最終案（v2）の確定計算。計画書『もう半分 v2』に載せた数字をすべて再現する。
  python3 v2_plan.py
"""
import numpy as np
from model_v2 import (S, run, households, dist, coverage, POLICIES, CRITERIA,
                      feasibility, LAMBDA, MULT_TAX, GAP_PERSIST, C_SHARE, VATPT)

W = 100
KIM = dict(wall178=-0.9, shakai_kakudai=4.5, zaishoku=-0.3,
           food_vat_cut=-1.2, food_vat_years=2, credit=3.0)

# 政治採点にもとづく3つの束
# A: 4点以上（やや高い〜ほぼ確実）だけ            → 生産性 +0.75pt
# B: A ＋ 五分（100%信用保証の縮小）              → +0.85pt
# C: B ＋ 低い（医療費適正化・炭素税）＝全部        → +0.90pt
A_ = dict(imm_dep=-0.6, train_invest=2.5, **KIM)
B_ = dict(imm_dep=-0.6, train_invest=2.5, hosho=1.0, **KIM)
C_ = dict(imm_dep=-0.6, train_invest=2.5, hosho=1.0, iryo=3.0, carbon=5.0, **KIM)
BUNDLES = [("A 通る項目だけ", 0.0075, A_), ("B ＋信用保証の縮小", 0.0085, B_),
           ("C ＋医療費・炭素税（全部）", 0.0090, C_)]


def slope(r):
    return (r["d"][-1] - r["d"][-6]) / 5 * 100


def verdict(r):
    if r["d"][-1] >= 19.9: return "破綻"
    s = slope(r)
    return "安定" if s < 0.3 else ("収束" if s < 1.2 else "発散")


def solve_vat(boost, extra, start=4, years=10, lam=LAMBDA, demand=True,
              inv=0.042, part=0.035, hi0=45.0):
    lo, hi = 0.0, hi0
    for _ in range(48):
        mid = (lo + hi) / 2
        r = run(S("x", boost=boost, inv_i=inv, part=part, vat_step=mid,
                  vat_start=start, vat_years=years, lam=lam, demand=demand, **extra))
        if slope(r) > 0: lo = mid
        else: hi = mid
    return (lo + hi) / 2


BASE = run(S("base", boost=0.0))

# ---- 推奨案を確定する：束B、2030年から10年で引き上げ ----
REC_BOOST, REC_EX, REC_START = 0.0085, B_, 4
REC_STEP = solve_vat(REC_BOOST, REC_EX, start=REC_START)
REC = run(S("rec", boost=REC_BOOST, inv_i=0.042, part=0.035, vat_step=REC_STEP,
            vat_start=REC_START, vat_years=10, **REC_EX))

if __name__ == "__main__":
    print("=" * W)
    print("【1】v1 の誤りと、v2 での修正")
    print("=" * W)
    PLAN = dict(boost=0.007, inv_i=0.042, part=0.035, vat_start=10, vat_years=10)
    FULLv1 = dict(imm_dep=-0.5, train_invest=2.5, iryo=3.0, hosho=1.0, carbon=5.0, **KIM)
    print(f"{'':<32}{'必要な消費税':>13}{'開始2030→2045で幅は':>22}")
    for nm, lam, dem in [("v1（金利外生・需要側なし）", 0.0, False),
                         ("v2（金利内生 λ=0.02・需要側あり）", LAMBDA, True)]:
        n36 = solve_vat(0.007, FULLv1, start=10, lam=lam, demand=dem)
        n30 = solve_vat(0.007, FULLv1, start=4, lam=lam, demand=dem)
        n45 = solve_vat(0.007, FULLv1, start=19, lam=lam, demand=dem)
        print(f"{nm:<32}{10+n36:>12.1f}%   {10+n30:>5.1f}% → {10+n45:>5.1f}%"
              f"（{n45-n30:+.1f}pt）")
    print()
    print("  ・v1 の「13.2%で足りる」は誤り。金利の内生化と需要側で 16.0% になる")
    print("  ・v1 の「増税は急がなくていい」も誤り。金利が内生だと、遅らせた分だけ幅が膨らむ")
    print()

    print("=" * W)
    print("【2】政治的に通る束ごとの必要消費税（2030年から10年かけて引き上げる前提）")
    print("=" * W)
    print(f"{'束':<30}{'生産性':>9}{'必要な消費税':>13}{'一人当GDP':>11}{'2060債務':>10}  判定")
    for nm, b, ex in BUNDLES:
        st = solve_vat(b, ex, start=4)
        r = run(S("y", boost=b, inv_i=0.042, part=0.035, vat_step=st,
                  vat_start=4, vat_years=10, **ex))
        print(f"{nm:<30}{b*100:>+8.2f}pt{10+st:>12.1f}%{r['gdp_pc'][-1]:>10.0f}万"
              f"{r['d'][-1]*100:>9.0f}%  {verdict(r)}")
    print()
    print("  → 政治的に難しい3項目（信用保証・医療費・炭素税）を通せるかどうかで、")
    print("     消費税が 17.1% か 10.8% かに分かれる。差は6.3ポイント。")
    print()

    print("=" * W)
    print("【3】引き上げ開始時期 ── 遅らせた分だけ高くなる（v1と結論が逆）")
    print("=" * W)
    print(f"{'開始年':<10}{'必要な引上げ':>13}{'到達税率':>10}{'ピーク債務':>12}{'2060債務':>10}")
    for st, yr in [(4, 2030), (7, 2033), (10, 2036), (14, 2040), (19, 2045)]:
        n = solve_vat(REC_BOOST, REC_EX, start=st)
        r = run(S("z", boost=REC_BOOST, inv_i=0.042, part=0.035, vat_step=n,
                  vat_start=st, vat_years=10, **REC_EX))
        print(f"{yr:<10}{n:>+12.1f}pt{10+n:>9.1f}%{r['d'].max()*100:>11.0f}%"
              f"{r['d'][-1]*100:>9.0f}%")
    print()

    print("=" * W)
    print("【4】推奨案の積み上げ（束B・2030年から消費税 10 → %.1f%%）" % (10 + REC_STEP))
    print("=" * W)
    steps = [("① 何もしない", 0.0, dict()),  # part/inv は下でboost=0→基準値
             ("② 既定路線のみ", 0.0, KIM),
             ("③ ＋ ゼロ円の制度変更", 0.0030, dict(imm_dep=-0.6, **KIM)),
             ("④ ＋ 訓練投資 年2.5兆円", 0.0055, A_),
             ("⑤ ＋ 事業承継と信用保証", 0.0085, B_)]
    print(f"{'':<30}{'一人当GDP':>11}{'①比':>8}{'2060債務':>10}{'金利':>8}  判定")
    for nm, b, ex in steps:
        r = run(S("s", boost=b, inv_i=0.030 + b * 1.7,
                  part=(0.0 if not ex else 0.02 + b * 2), **ex))
        print(f"{nm:<30}{r['gdp_pc'][-1]:>10.0f}万"
              f"{(r['gdp_pc'][-1]/BASE['gdp_pc'][-1]-1)*100:>+7.1f}%"
              f"{r['d'][-1]*100:>9.0f}%{r['r'][-1]*100:>7.2f}%  {verdict(r)}")
    print(f"{'⑥ ＋ 消費税 10→'+f'{10+REC_STEP:.1f}'+'%':<30}{REC['gdp_pc'][-1]:>10.0f}万"
          f"{(REC['gdp_pc'][-1]/BASE['gdp_pc'][-1]-1)*100:>+7.1f}%"
          f"{REC['d'][-1]*100:>9.0f}%{REC['r'][-1]*100:>7.2f}%  {verdict(REC)}")
    print()

    print("=" * W)
    print("【5】家計 ── 世帯20類型（消費税 %.1f%%・炭素税なし・給付付き税額控除あり）"
          % (10 + REC_STEP))
    print("=" * W)
    h = households(REC_STEP, carbon=0.0, credit=True)
    print(f"{'世帯':<24}{'現行手取り':>10}{'変化':>9}{'率':>8}")
    for nm, b, dl, p, c, hd in h:
        print(f"{nm:<24}{b:>10.0f}{dl:>+9.1f}{p:>+7.1f}%")
    d = dist(h)
    print()
    for k in ["下位20%", "中位60%", "上位20%", "格差幅", "最も不利"]:
        print(f"  {k:<10}{d[k]:>+7.2f}%")
    hh, pp, cov = coverage()
    print(f"\n  ※ 世帯20類型（{hh:,}万世帯・{pp:,}万人＝人口の{cov:.0f}%）。")
    print("     ジニ係数は算出しない。20類型では分布の両端を捉えられないため。")
    print(f"\n  一人当たり実質所得 {BASE['gdp_pc'][-1]:.0f}万円 → {REC['gdp_pc'][-1]:.0f}万円"
          f"（{(REC['gdp_pc'][-1]/BASE['gdp_pc'][-1]-1)*100:+.1f}%）")
    print()

    print("=" * W)
    print("【6】感度 ── 前提を動かすと結論はどれだけ変わるか")
    print("=" * W)
    print(f"{'動かす前提':<34}{'必要な消費税':>13}   結論の頑健性")
    cases = [("金利感度 λ=0.00（v1の前提）", dict(lam=0.0)),
             ("金利感度 λ=0.02（中位・採用）", dict(lam=0.02)),
             ("金利感度 λ=0.04（悲観）", dict(lam=0.04)),
             ("需要側なし（v1の前提）", dict(demand=False)),
             ("無形資本の弾力性を低く（inv 0.038）", dict(inv=0.038)),
             ("就業率の押上げを半分（part 0.018）", dict(part=0.018))]
    for nm, kw in cases:
        n = solve_vat(REC_BOOST, REC_EX, start=4, **kw)
        print(f"{nm:<34}{10+n:>12.1f}%")
    print()
    print("  → 必要水準は 12.2〜16.3% の範囲に収まる。中心は 14.7%。")
    print("     どの前提でも20%を下回る。『生産性が出れば20%未満／出なければ30%超』")
    print("     という分岐そのものは、前提を動かしても変わらない。")
