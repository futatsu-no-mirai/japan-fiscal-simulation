#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
最終確定計算 ── 同一モデル上で 原案v1 と 最終案 を厳密に比較する。
原案v1 には v2 で追加した措置（生活基礎給付・消費税増・フラット税・
相続一体課税・社会保障抑制・ガバナー・スライド）を一切含めない。
"""

import numpy as np
from dataclasses import dataclass

YEARS = list(range(2026, 2061))
POP_A = {2025: 12340, 2030: 11913, 2040: 11284, 2050: 10469, 2060: 9615}
WAP_A = {2025: 7310, 2030: 7076, 2040: 6213, 2050: 5540, 2060: 4793}
OLD_A = {2025: 3653, 2030: 3696, 2040: 3928, 2050: 3888, 2060: 3642}


def interp(a):
    ys = sorted(a); out = {}
    for y in range(2025, 2061):
        if y in a:
            out[y] = float(a[y]); continue
        lo = max(k for k in ys if k <= y); hi = min(k for k in ys if k >= y)
        w = (y - lo) / (hi - lo); out[y] = a[lo] * (1 - w) + a[hi] * w
    return out


POP, WAP, OLD = interp(POP_A), interp(WAP_A), interp(OLD_A)
AT, AI = 0.35, 0.10
BL = 1 - AT - AI
DT, DI = 0.060, 0.150
GDP0, KT0, KI0, L0, H0 = 620.0, 1900.0, 190.0, 6800.0, 1600.0
INF, R0, RRAMP = 0.020, 0.009, 15
REV = {"所得税": 33.0, "法人税": 20.0, "消費税": 30.0, "その他税": 30.0,
       "社保": 77.0, "その他": 20.0}
EXP = {"社会保障": 137.0, "一般": 60.0, "地方": 20.0}
DEBT0, VATPT, BASIC_PEN = 960.0, 3.0, 80.0
PATH = 1.55


@dataclass
class Sc:
    name: str
    boost: float = 0.0
    inv_i: float = 0.030
    part: float = 0.0
    reform: float = 0.0
    r_end: float = 0.022
    abolish: bool = False       # 所得税・住民税の廃止
    link: bool = False          # 廃止を生産性の達成度に連動させる
    carbon: float = 0.0
    shift: bool = False         # 社保の企業7:個人3への付け替え
    prod_invest: float = 0.0    # 生産性計画の追加支出
    asset_sale: bool = False
    # --- v2 で追加した措置 ---
    grant0: float = 0.0
    grant_per_pt: float = 0.9
    vat0: float = 0.10
    vat_max: float = 0.10
    flat_tax: float = 0.0
    inherit: float = 0.0
    soc_restraint: float = 0.0
    gov: bool = False
    slide: bool = False
    slide_max: float = 0.15


def ramp(t, n, f):
    return f if n <= 0 else f * min(1.0, (t + 1) / n)


def run(sc: Sc):
    keys = ["year", "gdp_pc", "pb", "gdp_nom", "d", "vat", "grant", "cut", "slide"]
    res = {k: [] for k in keys}
    A, Kt, Ki, debt, price = 1.0, KT0, KI0, DEBT0, 1.0
    scale = GDP0 / (KT0 ** AT * KI0 ** AI * ((L0 * H0) / 1e4) ** BL)
    prevY = GDP0
    ach = max(0.0, min(1.0, sc.boost / 0.009))
    vat, sl, dprev = sc.vat0, 0.0, DEBT0 / GDP0

    for t, year in enumerate(YEARS):
        if sc.gov:
            if dprev > PATH + 0.03:
                vat = min(sc.vat_max, vat + 0.005)
                if sc.slide:
                    sl = min(sc.slide_max, sl + 0.003)
            elif dprev < PATH - 0.03:
                vat = max(sc.vat0, vat - 0.005)
                if sc.slide:
                    sl = max(0.0, sl - 0.003)
        grant = sc.grant0 + (vat - sc.vat0) * 100 * sc.grant_per_pt if sc.grant0 else 0.0

        emp = WAP[year] * (L0 / WAP[2025] + ramp(t, 8, sc.part))
        emp += OLD[year] * (0.005 if sc.part > 0 else 0.0)
        hours = H0 * 0.997 ** t
        A *= (1 + 0.005 + ramp(t, 10, sc.boost))
        Y = scale * A * Kt ** AT * Ki ** AI * (emp * hours / 1e4) ** BL
        Kt = Kt * (1 - DT) + 0.155 * Y
        Ki = Ki * (1 - DI) + (0.030 + ramp(t, 10, sc.inv_i - 0.030)) * Y
        price *= (1 + INF); Ynom = Y * price; q = Y / GDP0
        cut = ramp(t, 10, 1.0) * (ach if sc.link else 1.0) if sc.abolish else 0.0

        rev = (REV["所得税"] * (1 - cut) + REV["法人税"] + REV["その他税"] + REV["社保"]
               + REV["その他"] + REV["消費税"] + (vat - 0.10) * 100 * VATPT) * q * price
        rev += (sc.carbon + ramp(t, 8, sc.reform) + ramp(t, 8, sc.inherit)) * price
        rev += ramp(t, 5, sc.flat_tax) * q * price * cut
        if sc.asset_sale and t < 5:
            rev += 7.0 * price

        soc = EXP["社会保障"] * (OLD[year] / OLD[2025]) * price * 1.004 ** t
        soc -= ramp(t, 20, sc.soc_restraint) * price
        soc *= (1 - sl * 0.55)
        pexp = soc + (EXP["一般"] + EXP["地方"]) * q * price
        pexp += ramp(t, 5, sc.prod_invest) * price
        if grant:
            pexp += ramp(t, 3, grant) / 1e4 * POP[year] * price

        r = R0 + (sc.r_end - R0) * min(1.0, (t + 1) / RRAMP)
        pb = rev - pexp
        debt -= (pb - debt * r)
        dprev = debt / Ynom
        prevY = Y
        for k, v in zip(keys, [year, Y / POP[year] * 1e4, pb, Ynom, dprev,
                               vat, grant, cut, sl]):
            res[k].append(v)
    return {k: np.array(v) for k, v in res.items()}


HH = [("年収200万 単身", 200, 8, 29, 185, 32, 1100, 0, 1),
      ("年収300万 単身", 300, 17, 44, 265, 36, 1300, 0, 1),
      ("年収500万 単身", 500, 55, 75, 400, 42, 1200, 0, 1),
      ("年収800万 世帯", 800, 110, 115, 600, 55, 900, 0, 2),
      ("年収1500万 世帯", 1500, 330, 170, 950, 70, 250, 0, 2),
      ("年金 高齢単身", 140, 0, 9, 145, 30, 700, 140, 1),
      ("年金 高齢夫婦", 270, 2, 18, 255, 42, 1400, 270, 2),
      ("生活保護 単身", 120, 0, 0, 120, 26, 170, 0, 1)]


def household(sc, r):
    cut, vat, grant, sl = r["cut"][-1], r["vat"][-1], r["grant"][-1], r["slide"][-1]
    rows = []
    for name, inc, tax, si, cons, energy, cnt, pen, heads in HH:
        d = tax * cut
        if sc.flat_tax and inc > 1000:
            d -= (inc - 1000) * 0.15 * cut
        if sc.shift:
            d += si * 0.4 * cut
        if sc.carbon:
            d += -energy * 0.13
        d += -(cons * 0.6) * (vat - 0.10)
        d += -max(0.0, pen - BASIC_PEN * heads) * sl
        d += grant * heads
        base = inc - tax - si
        rows.append((name, base, d, d / max(base, 1) * 100, cnt))
    return rows


def gini(rows):
    v = np.array([b + n for _, b, n, _, _ in rows], float)
    w = np.array([c for *_, c in rows], float)
    o = np.argsort(v); v, w = v[o], w[o]
    cw = np.cumsum(w) / w.sum(); cv = np.cumsum(v * w) / (v * w).sum()
    return 1 - np.sum((cv[1:] + cv[:-1]) * np.diff(cw))


F = dict(inv_i=0.045, part=0.035, reform=21.8)
S7 = dict(inv_i=0.041, part=0.030, reform=19.0)
H_ = dict(inv_i=0.038, part=0.025, reform=16.0)
Z = dict(inv_i=0.030, part=0.015, reform=10.0)

V1 = dict(abolish=True, carbon=5.0, shift=True, prod_invest=6.0, asset_sale=True)
V2 = dict(**V1, link=True, grant0=12.0, vat0=0.13, vat_max=0.25,
          flat_tax=4.5, inherit=4.0, soc_restraint=8.0, gov=True, slide=True)

SC = [
    ("ベースライン（何もしない）", Sc("b")),
    ("原案v1 計画どおり", Sc("v1a", boost=0.009, **V1, **F)),
    ("原案v1 生産性半分", Sc("v1b", boost=0.0045, **V1, **H_)),
    ("最終案 計画どおり(+1.0pt)", Sc("f1", boost=0.009, **V2, **F)),
    ("最終案 生産性7割(+0.7pt)", Sc("f2", boost=0.0063, **V2, **S7)),
    ("最終案 生産性半分(+0.5pt)", Sc("f3", boost=0.0045, **V2, **H_)),
    ("最終案 生産性ゼロ", Sc("f4", boost=0.0, **V2, **Z)),
    ("最終案 金利3.5%", Sc("f5", boost=0.009, r_end=0.035, **V2, **F)),
    ("最終案 最悪同時", Sc("f6", boost=0.0, r_end=0.035, **V2, **Z)),
]

runs = [(n, s, run(s)) for n, s in SC]

print("=" * 110)
print("【1】財政 ── 純債務/GDP（%）と制度の作動")
print("=" * 110)
print(f"{'シナリオ':<24}{'2035':>7}{'2045':>7}{'2055':>7}{'2060':>7}{'傾き':>10}"
      f"{'消費税':>8}{'給付':>8}{'減税':>7}{'年金':>7}  判定")
for nm, s, r in runs:
    d = r["d"]; sl = (d[-1] - d[-6]) / 5 * 100
    v = "安定" if sl < 0.3 else ("収束" if sl < 1.2 else "発散")
    print(f"{nm:<24}{d[9]*100:>7.0f}{d[19]*100:>7.0f}{d[29]*100:>7.0f}{d[-1]*100:>7.0f}"
          f"{sl:>+9.2f}pt{r['vat'][-1]*100:>7.1f}%{r['grant'][-1]:>7.1f}万"
          f"{r['cut'][-1]*100:>6.0f}%{-r['slide'][-1]*100:>6.1f}%  {v}")
print()

print("=" * 110)
print("【2】生活水準 ── 一人当たり実質GDP（万円、2026年価格）")
print("=" * 110)
b = runs[0][2]
print(f"{'シナリオ':<24}{'2030':>8}{'2040':>8}{'2050':>8}{'2060':>8}{'ベース比':>10}")
for nm, s, r in runs:
    print(f"{nm:<24}{r['gdp_pc'][4]:>8.0f}{r['gdp_pc'][14]:>8.0f}{r['gdp_pc'][24]:>8.0f}"
          f"{r['gdp_pc'][-1]:>8.0f}{(r['gdp_pc'][-1]/b['gdp_pc'][-1]-1)*100:>+9.1f}%")
print()

print("=" * 110)
print("【3】家計 ── 手取りの変化（万円/年、2026年価格・定常時）")
print("=" * 110)
show = [("原案v1 計画どおり", 1), ("最終案 計画どおり(+1.0pt)", 3),
        ("最終案 生産性半分(+0.5pt)", 5), ("最終案 生産性ゼロ", 6)]
hh = {nm: household(runs[i][1], runs[i][2]) for nm, i in show}
print(f"{'世帯':<17}{'現行':>7}", end="")
for nm, _ in show:
    print(f"{nm.replace('(+1.0pt)','').replace('(+0.5pt)',''):>19}", end="")
print()
for i, name in enumerate([h[0] for h in hh[show[0][0]]]):
    print(f"{name:<17}{hh[show[0][0]][i][1]:>7.0f}", end="")
    for nm, _ in show:
        print(f"{hh[nm][i][2]:>+11.1f}({hh[nm][i][3]:>+5.1f}%)", end="")
    print()
print()
for nm, _ in show:
    rw = hh[nm]
    print(f"  {nm:<26} 最も不利な世帯 {min(x[3] for x in rw):>+6.1f}%   "
          f"格差 {rw[4][3]-rw[7][3]:>5.1f}pt   ジニ {gini(rw):.4f}  （現行 0.2962）")
print()

print("=" * 110)
print("【4】要約")
print("=" * 110)
print(f"  {'':<26}{'一人当たりGDP':>15}{'純債務/GDP':>16}{'最も不利な世帯':>16}")
for nm, i in [("ベースライン（何もしない）", 0)] + show:
    s, r = runs[i][1], runs[i][2]
    d = r["d"]; sl = (d[-1] - d[-6]) / 5 * 100
    tag = "安定" if sl < 0.3 else ("収束" if sl < 1.2 else "発散")
    h = hh.get(nm)
    w = f"{min(x[3] for x in h):+.1f}%" if h else "—"
    print(f"  {nm:<26}{r['gdp_pc'][-1]:>12.0f}万円{d[-1]*100:>13.0f}% {tag}{w:>15}")
