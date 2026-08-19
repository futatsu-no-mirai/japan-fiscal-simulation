#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""統合案D（推奨案）の確定計算。patterns.py を読み込んで実行する。"""
from patterns import P, run, household, gini, PATTERNS

# ソブリン・ファンドは保守前提：外貨準備は政府短期証券で調達した借入金なので、
# 収益は調達コストを差し引いた「スプレッド」として扱う（実質3.5%、繰入2.5%）。
SWF = dict(swf_init=150.0, swf_return=0.035, swf_draw=0.025, fdi_revenue=4.0)

D = P("D 統合案", abolish=True, flat_tax=4.5, shift=True,
      vat0=0.20, vat_max=0.28, grant0=32.0, almp=6.0, boost=0.010, **SWF)

CASES = [("A 生産性に賭ける（減税国家）", PATTERNS[1][1]),
         ("B 分配に賭ける（北欧国家）",   PATTERNS[2][1]),
         ("C 外に賭ける（投資国家）",
          P("C", abolish=True, flat_tax=4.5, shift=True, vat0=0.13,
            grant0=12.0, boost=0.010, **SWF)),
         ("D 統合案（推奨）", D)]

if __name__ == "__main__":
    print("=" * 112); print("4案 × 3シナリオ"); print("=" * 112)
    for nm, sc in CASES:
        for tag, kw in [("計画どおり", {}), ("生産性半分", dict(boost_override=sc.boost / 2)),
                        ("金利3.5%", dict(r_override=0.035))]:
            r = run(sc, **kw); h = household(sc, r)
            d = r["d"]; s = (d[-1] - d[-6]) / 5 * 100
            v = "安定" if s < 0.3 else ("収束" if s < 1.2 else "発散")
            print(f"{nm if tag=='計画どおり' else '':<26}{tag:<10}"
                  f"{r['gdp_pc'][-1]:>7.0f}万{d[-1]*100:>6.0f}%{s:>+7.2f}pt"
                  f"{r['vat'][-1]*100:>6.1f}%{r['grant'][-1]:>6.1f}万"
                  f"  最悪{min(x[3] for x in h):>+6.1f}%  ジニ{gini(h):.4f}  {v}")
        print()

    print("=" * 112); print("統合案Dの家計（万円/年・2026年価格）"); print("=" * 112)
    r1, r2 = run(D), run(D, boost_override=0.005)
    h1, h2 = household(D, r1), household(D, r2)
    print(f"{'世帯':<18}{'現行手取り':>10}{'計画どおり':>20}{'生産性半分':>20}")
    for a, b in zip(h1, h2):
        print(f"{a[0]:<18}{a[1]:>10.0f}{a[2]:>+13.1f}({a[3]:>+5.1f}%)"
              f"{b[2]:>+13.1f}({b[3]:>+5.1f}%)")
    print(f"\n  ジニ  現行 0.2962 → 計画どおり {gini(h1):.4f} / 生産性半分 {gini(h2):.4f}")
    print(f"  ソブリン・ファンド 2060年 {r1['swf'][-1]:.0f}兆円 "
          f"→ 年間繰入 {r1['swf'][-1]*0.025:.1f}兆円")
