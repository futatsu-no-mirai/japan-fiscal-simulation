#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
3つのパターンの比較
  A 生産性に賭ける（減税国家）   参照: シンガポール、アイルランド、エストニア
  B 分配に賭ける（北欧国家）     参照: スウェーデン、デンマーク
  C 外に賭ける（投資国家）       参照: シンガポール NIRC、ノルウェー GPFG
  D 統合案
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
REV = {"所得税": 33.0, "法人税": 20.0, "消費税": 30.0, "その他税": 30.0,
       "社保": 77.0, "その他": 20.0}
EXP = {"社会保障": 137.0, "一般": 60.0, "地方": 20.0}
DEBT0, VATPT, BASIC_PEN = 960.0, 3.0, 80.0
PATH = 1.55


@dataclass
class P:
    name: str
    boost: float = 0.009
    inv_i: float = 0.045
    part: float = 0.035
    reform: float = 21.8
    r_end: float = 0.022
    abolish: bool = False
    link: bool = True
    flat_tax: float = 0.0
    carbon: float = 5.0
    shift: bool = False
    inherit: float = 4.0
    soc_restraint: float = 8.0
    vat0: float = 0.13
    vat_max: float = 0.25
    grant0: float = 12.0
    grant_per_pt: float = 0.9
    prod_invest: float = 6.0      # 生産性計画の投資
    almp: float = 0.0             # 積極的労働市場政策の追加支出
    swf_init: float = 0.0         # ソブリン・ファンドの初期規模(兆円)
    swf_return: float = 0.045     # 実質期待収益率
    swf_draw: float = 0.03        # 繰入率(ノルウェー方式)
    fdi_revenue: float = 0.0      # 対内直接投資拡大・還流課税による追加税収
    gov: bool = True
    slide: bool = True
    asset_sale: bool = True


def ramp(t, n, f):
    return f if n <= 0 else f * min(1.0, (t + 1) / n)


def run(sc: P, boost_override=None, r_override=None):
    boost = sc.boost if boost_override is None else boost_override
    r_end = sc.r_end if r_override is None else r_override
    ach = max(0.0, min(1.0, boost / 0.009))
    keys = ["year", "gdp_pc", "gdp_nom", "pb", "d", "vat", "grant", "cut", "slide", "swf"]
    res = {k: [] for k in keys}
    A, Kt, Ki, debt, price = 1.0, KT0, KI0, DEBT0, 1.0
    scale = GDP0 / (KT0 ** AT * KI0 ** AI * ((L0 * H0) / 1e4) ** BL)
    vat, sl, dprev = sc.vat0, 0.0, DEBT0 / GDP0
    swf = sc.swf_init

    for t, year in enumerate(YEARS):
        if sc.gov:
            if dprev > PATH + 0.03:
                vat = min(sc.vat_max, vat + 0.005)
                if sc.slide:
                    sl = min(0.15, sl + 0.003)
            elif dprev < PATH - 0.03:
                vat = max(sc.vat0, vat - 0.005)
                if sc.slide:
                    sl = max(0.0, sl - 0.003)
        grant = sc.grant0 + (vat - sc.vat0) * 100 * sc.grant_per_pt

        # ALMP は就業率と生産性を押し上げる（デンマークはGDP比2.05%、OECD平均の4倍）
        almp_boost = 0.0015 * min(1.0, sc.almp / 6.0) if sc.almp else 0.0
        part = sc.part + (0.005 if sc.almp else 0.0)

        emp = WAP[year] * (L0 / WAP[2025] + ramp(t, 8, part)) + OLD[year] * 0.005
        hours = H0 * 0.997 ** t
        A *= (1 + 0.005 + ramp(t, 10, boost + almp_boost))
        Y = scale * A * Kt ** AT * Ki ** AI * (emp * hours / 1e4) ** BL
        Kt = Kt * (1 - DT) + 0.155 * Y
        Ki = Ki * (1 - DI) + (0.030 + ramp(t, 10, sc.inv_i - 0.030)) * Y
        price *= (1 + INF); Ynom = Y * price; q = Y / GDP0
        cut = ramp(t, 10, 1.0) * (ach if sc.link else 1.0) if sc.abolish else 0.0

        # ソブリン・ファンド（実質ベースで運用し、3%を繰り入れる）
        draw = swf * sc.swf_draw if swf else 0.0
        swf = swf * (1 + sc.swf_return) - draw if swf else 0.0

        rev = (REV["所得税"] * (1 - cut) + REV["法人税"] + REV["その他税"] + REV["社保"]
               + REV["その他"] + REV["消費税"] + (vat - 0.10) * 100 * VATPT) * q * price
        rev += (sc.carbon + ramp(t, 8, sc.reform) + ramp(t, 8, sc.inherit)
                + ramp(t, 10, sc.fdi_revenue) + draw) * price
        rev += ramp(t, 5, sc.flat_tax) * q * price * cut
        if sc.asset_sale and t < 5 and not sc.swf_init:
            rev += 7.0 * price

        soc = EXP["社会保障"] * (OLD[year] / OLD[2025]) * price * 1.004 ** t
        soc -= ramp(t, 20, sc.soc_restraint) * price
        soc *= (1 - sl * 0.55)
        pexp = soc + (EXP["一般"] + EXP["地方"]) * q * price
        pexp += ramp(t, 5, sc.prod_invest + sc.almp) * price
        pexp += ramp(t, 3, grant) / 1e4 * POP[year] * price

        r = R0 + (r_end - R0) * min(1.0, (t + 1) / RRAMP)
        pb = rev - pexp
        debt -= (pb - debt * r)
        dprev = debt / Ynom
        for k, v in zip(keys, [year, Y / POP[year] * 1e4, Ynom, pb, dprev,
                               vat, grant, cut, sl, swf]):
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
        d += -energy * 0.13
        d += -(cons * 0.6) * (vat - 0.10)
        d += -max(0.0, pen - BASIC_PEN * heads) * sl
        d += grant * heads
        rows.append((name, inc - tax - si, d, d / max(inc - tax - si, 1) * 100, cnt))
    return rows


def gini(rows):
    v = np.array([b + n for _, b, n, _, _ in rows], float)
    w = np.array([c for *_, c in rows], float)
    o = np.argsort(v); v, w = v[o], w[o]
    cw = np.cumsum(w) / w.sum(); cv = np.cumsum(v * w) / (v * w).sum()
    return 1 - np.sum((cv[1:] + cv[:-1]) * np.diff(cw))


PATTERNS = [
    ("現状維持（何もしない）",
     P("now", boost=0.0, inv_i=0.030, part=0.0, reform=0.0, carbon=0.0,
       inherit=0.0, soc_restraint=0.0, vat0=0.10, vat_max=0.10, grant0=0.0,
       prod_invest=0.0, gov=False, slide=False, asset_sale=False)),

    ("A 生産性に賭ける（減税国家）",
     P("A", abolish=True, flat_tax=4.5, shift=True, vat0=0.13, grant0=12.0)),

    ("B 分配に賭ける（北欧国家）",
     P("B", abolish=False, vat0=0.20, vat_max=0.28, grant0=24.0,
       soc_restraint=4.0, almp=6.0, shift=False)),

    ("C 外に賭ける（投資国家）",
     P("C", abolish=True, flat_tax=4.5, shift=True, vat0=0.13, grant0=12.0,
       swf_init=150.0, fdi_revenue=4.0, boost=0.010)),

    ("D 統合案",
     P("D", abolish=True, flat_tax=4.5, shift=True, vat0=0.13, grant0=15.0,
       swf_init=150.0, fdi_revenue=4.0, almp=6.0, boost=0.010)),
]

if __name__ == "__main__":
    print("=" * 112)
    print("【1】中心ケース ── 生産性が計画どおり出た場合")
    print("=" * 112)
    print(f"{'パターン':<26}{'一人当GDP':>10}{'純債務':>8}{'傾き':>9}{'消費税':>8}"
          f"{'給付':>8}{'最も不利':>9}{'ジニ':>8}  判定")
    base = None
    store = {}
    for nm, sc in PATTERNS:
        r = run(sc); h = household(sc, r); store[nm] = (sc, r, h)
        if base is None:
            base = r
        d = r["d"]; s = (d[-1] - d[-6]) / 5 * 100
        v = "安定" if s < 0.3 else ("収束" if s < 1.2 else "発散")
        print(f"{nm:<26}{r['gdp_pc'][-1]:>9.0f}万{d[-1]*100:>7.0f}%{s:>+8.2f}pt"
              f"{r['vat'][-1]*100:>7.1f}%{r['grant'][-1]:>7.1f}万"
              f"{min(x[3] for x in h):>+8.1f}%{gini(h):>8.4f}  {v}")
    print(f"{'（参考）現行のジニ係数':<26}{'':>52}{0.2962:>8.4f}")
    print()

    print("=" * 112)
    print("【2】ストレス ── 生産性が計画の半分しか出ない場合")
    print("=" * 112)
    print(f"{'パターン':<26}{'一人当GDP':>10}{'純債務':>8}{'傾き':>9}{'消費税':>8}"
          f"{'最も不利':>9}  判定")
    for nm, sc in PATTERNS:
        b = 0.0 if sc.boost == 0 else sc.boost / 2
        r = run(sc, boost_override=b); h = household(sc, r)
        d = r["d"]; s = (d[-1] - d[-6]) / 5 * 100
        v = "安定" if s < 0.3 else ("収束" if s < 1.2 else "発散")
        print(f"{nm:<26}{r['gdp_pc'][-1]:>9.0f}万{d[-1]*100:>7.0f}%{s:>+8.2f}pt"
              f"{r['vat'][-1]*100:>7.1f}%{min(x[3] for x in h):>+8.1f}%  {v}")
    print()

    print("=" * 112)
    print("【3】ストレス ── 金利が3.5%まで上がる場合")
    print("=" * 112)
    print(f"{'パターン':<26}{'純債務':>8}{'傾き':>9}{'消費税':>8}  判定")
    for nm, sc in PATTERNS:
        r = run(sc, r_override=0.035)
        d = r["d"]; s = (d[-1] - d[-6]) / 5 * 100
        v = "安定" if s < 0.3 else ("収束" if s < 1.2 else "発散")
        print(f"{nm:<26}{d[-1]*100:>7.0f}%{s:>+8.2f}pt{r['vat'][-1]*100:>7.1f}%  {v}")
    print()

    print("=" * 112)
    print("【4】家計への効果（万円/年、2026年価格・中心ケース）")
    print("=" * 112)
    show = [n for n, _ in PATTERNS[1:]]
    print(f"{'世帯':<17}{'現行':>7}", end="")
    for n in show:
        print(f"{n.split('（')[0]:>18}", end="")
    print()
    for i, name in enumerate([h[0] for h in store[show[0]][2]]):
        print(f"{name:<17}{store[show[0]][2][i][1]:>7.0f}", end="")
        for n in show:
            h = store[n][2][i]
            print(f"{h[2]:>+10.1f}({h[3]:>+5.1f}%)", end="")
        print()
    print()

    print("=" * 112)
    print("【5】ソブリン・ファンドの推移（パターンC / D、兆円・実質）")
    print("=" * 112)
    rc = store["C 外に賭ける（投資国家）"][1]
    print(f"{'年':>6}{'基金残高':>12}{'毎年の繰入':>12}")
    for y in [2026, 2035, 2045, 2055, 2060]:
        i = y - 2026
        print(f"{y:>6}{rc['swf'][i]:>11.0f}兆{rc['swf'][i]*0.03:>11.1f}兆")
