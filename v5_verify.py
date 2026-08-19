#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
第5版の検証。第4版に残っていた2つの穴に手を入れた記録。
数値の結論（消費税21.1%など）は第4版から変わらない。変わったのは根拠である。

  穴1 「なぜ収束率57%なのか」の根拠がない
    → 解消。収束『率』ではなく収束『速度』で置き直すと、標準的な実証則に一致した。
       Barro–Sala-i-Martin の「2%収束則」：経済は目標とのギャップを年約2%で埋め、
       その速度だと35年でギャップの半分が消える。
       本書の中位（5割収束）は、この標準速度そのものだった。

  穴2 各政策から再配置への経路がない
    → 部分的に解消。唯一の外部推計（OECD）と照合し、個別政策の数字が
       過大であることを確認した。合計は天井×収束速度から出しており、
       個別の積み上げではないことを明示する。

  python3 v5_verify.py
"""
from typing import Iterable

YEARS = 35
JP_GAP, US_GAP = 0.40, 0.062
CEILING = (1 + JP_GAP) / (1 + US_GAP) - 1     # 米国並みへの伸びしろ +31.8%
HUMAN, CAPITAL = 0.02, 0.07                    # 算術で計算できる分（pt）
TFP_BASE, TFP_GROW = 0.5, 1.4                  # 内閣府 ベースライン／成長実現ケース
W = 94


def annual(total: float, years: int = YEARS) -> float:
    return ((1 + total) ** (1 / years) - 1) * 100


def closed_by(speed: float, years: int = YEARS) -> float:
    """収束速度 speed（年）で years 年後に解消しているギャップの割合"""
    return 1 - (1 - speed) ** years


def boost_at(speed: float) -> float:
    """収束速度から生産性の上積み(pt)を出す"""
    return annual(CEILING * closed_by(speed)) + HUMAN + CAPITAL


SPEEDS: Iterable[tuple[float, str]] = [
    (0.010, "悲観（標準の半分）"),
    (0.020, "Barro–Sala-i-Martin の「2%収束則」"),
    (0.035, "やや速い"),
    (0.100, "Islam(1995) のパネル推定"),
]

if __name__ == "__main__":
    print("=" * W)
    print("【1】穴1 ── 収束「率」を収束「速度」に置き直す")
    print("=" * W)
    print("  成長論の標準的な実証則：経済は目標水準とのギャップを年約2%の速さで埋める。")
    print("  この速度だと『ギャップの半分が消えるのに約35年』かかる。")
    print()
    print(f"  検算  (1 − 0.02)^35 = {0.98**35:.4f} → 35年で {closed_by(0.02)*100:.1f}% が解消")
    print("  → 第3版・第4版が中位に置いた『5割収束』は、この標準速度そのものだった。")
    print("     恣意的な仮定ではなかったが、そうと知らずに置いていた。")
    print()
    print(f"{'収束速度':<12}{'典拠':<34}{'35年で解消':>11}{'生産性の上積み':>15}")
    for sp, src in SPEEDS:
        mark = "  ← 採用" if abs(sp - 0.020) < 1e-9 else ""
        print(f"  年{sp*100:>4.1f}%{'':<4}{src:<34}{closed_by(sp)*100:>10.1f}%"
              f"{boost_at(sp):>+14.2f}pt{mark}")
    print()
    print("  → 4つのケースはすべて、実証則のレンジの中に位置づけられる。")
    print("     第2版が置いていた+0.87ptは、Islam の年10%収束に近い。極端に強気だった。")
    print()

    print("=" * W)
    print("【2】天井の3重チェック")
    print("=" * W)
    checks = [
        ("(A) 企業間の資源配分の歪みから（RIETI / Hsieh-Klenow）",
         f"日本+40% ／ 米国+6.2% → 伸びしろ+{CEILING*100:.1f}% "
         f"→ TFP {TFP_BASE}%+{annual(CEILING):.2f}pt = {TFP_BASE+annual(CEILING):.2f}%"),
        ("(B) 日本自身の過去の実績から（内閣府 成長実現ケース）",
         f"TFP {TFP_GROW:.1f}%（デフレ状況に入る前の期間の平均程度）"),
        ("(C) 収束速度の実証則から（Barro–Sala-i-Martin）",
         f"年2%収束 → 35年でギャップの{closed_by(0.02)*100:.0f}%が解消 "
         f"→ 上積み{boost_at(0.02):+.2f}pt"),
    ]
    for nm, val in checks:
        print(f"  {nm}\n      {val}")
    print()
    print(f"  (A)と(B)の差は {abs(TFP_BASE+annual(CEILING)-TFP_GROW):.2f}pt。")
    print("  (C)は(A)の天井に到達する速さを与える。3つとも互いに独立な出どころである。")
    print()

    print("=" * W)
    print("【3】穴2 ── 個別政策の数字を、唯一の外部推計と照合する")
    print("=" * W)
    print("  OECD『The walking dead?』(2018) の反実仮想：")
    print("    ・ゾンビ資本シェアが危機前から上がらなければ、資本再配分のMFPへの寄与は")
    print("      2013年にイタリア+0.7%／スペイン+1.0% 高かった")
    print("    ・他国でもゾンビ滞留を産業内の最小水準まで下げればMFPは最大+0.5%")
    print("    ※ いずれも『水準』への効果。年率ではない")
    print()
    mine = 0.20
    cum = (1 + mine / 100) ** YEARS - 1
    print(f"  本書が『事業承継＋信用保証の縮小』に割り当てていた値 : 年+{mine:.2f}pt")
    print(f"    35年の累積 = +{cum*100:.1f}%   OECD推計(+0.5〜1.0%)の "
          f"{cum*100/1.0:.0f}〜{cum*100/0.5:.0f}倍")
    print()
    print("  ただし単純比較はできない：")
    print("    ・OECDが測っているのは『産業内の資本再配分』という1経路だけ")
    print("    ・労働の再配分、産業間の移動、参入・退出は含まれない")
    print("    ・そして日本はOECDの分析から除外されている（生産性データ不足のため）")
    print()
    print("  → 個別政策の数字は『指標』であって『推計』ではない、と明示する。")
    print("     合計は天井×収束速度から出しており、個別の積み上げではない。")
    print()

    print("=" * W)
    print("【4】ゾンビ経路は、天井のどこに位置するか")
    print("=" * W)
    for lo, hi in [(0.5, 1.0)]:
        print(f"  Hsieh-Klenow の天井（全ての歪み）           +{CEILING*100:.1f}%")
        print(f"  OECD のゾンビ経路（産業内の資本再配分のみ）   +{lo}〜{hi}%")
        print(f"  → ゾンビ経路は天井の {lo/(CEILING*100)*100:.1f}〜{hi/(CEILING*100)*100:.1f}%")
    print()
    print("  『ゾンビ企業をなくせば生産性が上がる』は正しいが、それだけでは")
    print("  全体のごく一部にしか届かない。天井の大半は、労働の再配分と")
    print("  参入・退出と産業間の移動にある。")
    print("  本計画の重心が『移動の罰則を外す』側にあるのは、そのためである。")
    print()

    print("=" * W)
    print("【5】残る穴")
    print("=" * W)
    print("  ・日本の実際の収束速度は『負』である（RIETI：資源配分の非効率は過去30年")
    print("    トレンドとして悪化。参入効果は正だが退出効果は負）。")
    print("    したがって本計画の主張は『負である収束速度を国際標準の年2%に転じさせる』")
    print("    ことであって、ゼロから2%ではない。これは控えめな想定ではない。")
    print()
    print("  ・個別政策の弾性値は、日本を含む推計がほぼ存在しない。")
    print("    OECDの分析からも日本は除外されている。この穴は本書では埋まらない。")
    print("    代わりに、資源配分の歪み（TFPGAP）を毎年測定・公表し、")
    print("    収束速度が実際に正に転じたかを外部機関が判定する運用を置く。")
