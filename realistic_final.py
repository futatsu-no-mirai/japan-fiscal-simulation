#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
現実解 計画書『いま、実際にできること』の確定計算。
realistic.py を読み込んで、計画書に載せた数字をすべて再現する。

  python3 realistic_final.py
"""
from realistic import R, run, KIMATTA, HH, gini, SCEN

FULL = dict(imm_depreciation=-0.5, train_invest=2.5, iryo_tekiseika=3.0,
            hosho_shukusho=1.0, carbon=5.0, **KIMATTA)
NOCARBON = dict(imm_depreciation=-0.5, train_invest=2.5, iryo_tekiseika=3.0,
                hosho_shukusho=1.0, **KIMATTA)


def slope(r):
    return (r["d"][-1] - r["d"][-6]) / 5 * 100


def verdict(r):
    s = slope(r)
    return "安定" if s < 0.3 else ("収束" if s < 1.2 else "発散")


def solve_vat(boost, inv, part, extra=FULL, start=10, years=10, hi0=25.0):
    """財政を安定させるのに必要な消費税の引き上げ幅を二分探索で求める"""
    lo, hi = 0.0, hi0
    for _ in range(40):
        mid = (lo + hi) / 2
        r = run(R("x", boost=boost, inv_i=inv, part=part, vat_step=mid,
                  vat_step_start=start, vat_step_years=years, **extra))
        if slope(r) > 0:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


# --- 給付付き税額控除の2つの配り方 ---
def taper(inc):
    if inc <= 200: return 14.0
    if inc <= 300: return 10.0
    if inc <= 500: return 4.0
    return 0.0


def households(vat_up_pt, carbon=5.0, mode="taper"):
    tot = sum(taper(h[1]) * h[8] * h[7] for h in HH)
    flat = tot / sum(h[7] * h[8] for h in HH)
    rows = []
    for name, inc, tax, si, cons, food, energy, cnt, heads in HH:
        d = (taper(inc) if mode == "taper" else flat) * heads
        d += -(cons * 0.6) * (vat_up_pt / 100)
        d += -energy * 0.13 * (carbon / 5.0)
        rows.append((name, inc - tax - si, d, d / max(inc - tax - si, 1) * 100, cnt))
    return rows, flat


if __name__ == "__main__":
    W = 108
    print("=" * W)
    print("【1】積み上げ ── 何をどこまでやると、どうなるか")
    print("=" * W)
    base = run(SCEN[0][1])
    print(f"{'':<42}{'一人当GDP':>10}{'①比':>9}{'2045':>7}{'2060':>7}{'傾き':>9}  判定")
    for nm, sc in SCEN:
        r = run(sc)
        print(f"{nm:<42}{r['gdp_pc'][-1]:>9.0f}万"
              f"{(r['gdp_pc'][-1]/base['gdp_pc'][-1]-1)*100:>+8.1f}%"
              f"{r['d'][19]*100:>6.0f}%{r['d'][-1]*100:>6.0f}%{slope(r):>+8.2f}pt  {verdict(r)}")
    print()

    print("=" * W)
    print("【2】必要な消費税率は、生産性の実現度で決まる")
    print("=" * W)
    print(f"{'生産性の上積み':<24}{'必要な引上げ':>12}{'到達税率':>10}   備考")
    for label, b, inv, pt in [("+0.7pt（計画どおり）", 0.007, 0.042, 0.035),
                              ("+0.5pt（7割の達成）", 0.005, 0.038, 0.030),
                              ("+0.3pt（タダの項目のみ）", 0.003, 0.033, 0.025),
                              ("  0pt（生産性ゼロ）", 0.0, 0.030, 0.020)]:
        need = solve_vat(b, inv, pt)
        note = "世界に前例なし（最高はハンガリー27%）" if 10 + need > 25 else \
               ("英・仏20%より低い" if 10 + need <= 20 else "北欧並み")
        print(f"{label:<24}{need:>+11.1f}pt{10+need:>9.1f}%   {note}")
    print()
    print(f"  炭素税5兆円を入れない場合 → 必要な引上げは "
          f"{solve_vat(0.007, 0.042, 0.035, NOCARBON):+.1f}pt "
          f"（到達 {10+solve_vat(0.007,0.042,0.035,NOCARBON):.1f}%）"
          f"。炭素税は消費税約1.5pt分にあたる。")
    print()

    print("=" * W)
    print("【3】引き上げの開始時期 ── 遅らせるコストは「幅」ではなく「債務の水準」で払う")
    print("=" * W)
    print(f"{'開始年':<10}{'必要な引上げ':>12}{'到達税率':>10}{'ピーク債務':>12}{'2060年':>10}")
    for start, yr in [(4, 2030), (10, 2036), (14, 2040), (19, 2045), (24, 2050)]:
        need = solve_vat(0.007, 0.042, 0.035, start=start)
        r = run(R("y", boost=0.007, inv_i=0.042, part=0.035, vat_step=need,
                  vat_step_start=start, vat_step_years=10, **FULL))
        print(f"{yr:<10}{need:>+11.1f}pt{10+need:>9.1f}%"
              f"{r['d'].max()*100:>11.0f}%{r['d'][-1]*100:>9.0f}%")
    print()

    print("=" * W)
    print("【4】家計 ── 税制だけを見れば、ほとんどの世帯がマイナスになる")
    print("     （消費税+3.2pt・炭素税5兆円・給付付き税額控除の後。2026年価格）")
    print("=" * W)
    a, flat = households(3.2, mode="taper")
    b, _ = households(3.2, mode="flat")
    print(f"{'世帯':<18}{'現行手取り':>10}{'逓減型（既定路線）':>22}{'定額型（同予算）':>22}")
    for x, y in zip(a, b):
        print(f"{x[0]:<18}{x[1]:>10.0f}{x[2]:>+14.1f}({x[3]:>+5.1f}%)"
              f"{y[2]:>+14.1f}({y[3]:>+5.1f}%)")
    print()
    print(f"  最も不利な世帯   逓減型 {min(r[3] for r in a):+.1f}%   定額型 {min(r[3] for r in b):+.1f}%")
    print(f"  ジニ係数        逓減型 {gini(a):.4f}   定額型 {gini(b):.4f}   （現行 0.2962）")
    print(f"  同じ予算を定額で配ると 一人あたり {flat:.1f}万円/年")
    print()
    r7 = run(SCEN[6][1])
    print(f"  ただし一人当たり実質GDPは {base['gdp_pc'][-1]:.0f}万円 → {r7['gdp_pc'][-1]:.0f}万円"
          f"（{(r7['gdp_pc'][-1]/base['gdp_pc'][-1]-1)*100:+.1f}%）。")
    print("  税制の数%より、所得そのものの+44%のほうがはるかに大きい。")
    print("  → 税制で手取りを増やすのをやめて、所得そのものを増やす、というのが本計画の要点。")
