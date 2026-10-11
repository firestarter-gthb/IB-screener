"""
Robuustheidscontroles voor de beste varianten uit backtester_variants.py (10-jaars dataset).
  a) Leave-one-year-out: alpha t-stat zonder elk afzonderlijk kalenderjaar
  b) Winsorized rendementen (1e/99e percentiel per datum)
  c) Zonder de 10 grootste bijdragers (ex-post, conservatieve stress-test op concentratie/survivorship)
  d) Top-N gevoeligheid (15/25/40/60)
  e) Hogere handelskosten (0,25% per positie per kant)
  f) Brede toets: Q1-Q5 beta-neutrale spread per variant (hele universum, niet alleen Top 25)
"""
import os
import sys
import warnings
import numpy as np
import pandas as pd

import backtester_analyzer_v2 as an
import backtester_variants as bv

warnings.filterwarnings('ignore')
PATH = sys.argv[1] if len(sys.argv) > 1 else 'backtest_dataset_10y.csv'
TAG = sys.argv[2] if len(sys.argv) > 2 else '10y'

TESTS = [('V0 Huidige screener', 'raw'), ('V0 Huidige screener', 'BN'), ('V1 Zonder sectorfactor', 'BN'),
         ('V2 Momentum 12-1', 'BN'), ('V4 Mom12-1 + trendkwaliteit', 'BN')]


def alpha_t(p):
    a, t, b = an.capm(p['net'].values, p['mkt'].values)
    return a * 100, t, b


def sharpe(p):
    return p['net'].mean() / p['net'].std() * np.sqrt(12)


def main():
    an.DATA = PATH
    df, _ = an.load()
    df = df.reset_index(drop=True)
    scores = bv.build_scores(df)
    cols = {}
    for name, typ in TESTS:
        s = scores[name]
        sc = s if typ == 'raw' else bv.beta_neutralize(df, s)
        col = f'_t_{len(cols)}'
        df[col] = sc.values
        cols[(name, typ)] = col

    out = []
    A = lambda s: out.append(s + '\n')
    A(f'# Robuustheid ({TAG})\n')
    label = lambda k: f'{k[0].split(" ", 1)[0]} {k[1]}'

    # a) leave-one-year-out
    base = {k: bv.run_portfolio(df, c) for k, c in cols.items()}
    years = sorted(set(d.year for d in base[TESTS[0]].index))
    rows = []
    for k, p in base.items():
        a, t, b = alpha_t(p)
        r = {'Variant': label(k), 'Alpha %/mnd': a, 'Alpha t (alles)': t}
        ts = {}
        for y in years:
            q = p[p.index.year != y]
            ts[y] = alpha_t(q)[1]
        worst = min(ts, key=ts.get)
        r['Laagste t (jaar weggelaten)'] = ts[worst]
        r['Welk jaar'] = worst
        r['Alpha t zonder 2020'] = ts.get(2020, np.nan)
        r['Jaren met t>2'] = sum(v > 2 for v in ts.values())
        rows.append(r)
    A('## a) Leave-one-year-out (alpha t-stat van Top 25 netto)\n')
    A(an.md_table(pd.DataFrame(rows), {'Alpha %/mnd': '{:+.2f}', 'Alpha t (alles)': '{:+.2f}',
                                       'Laagste t (jaar weggelaten)': '{:+.2f}', 'Alpha t zonder 2020': '{:+.2f}'}, index=False))

    # per jaar alpha (V0 BN) om patroon te zien
    yr = pd.DataFrame({label(k): p['net'].groupby(p.index.year).apply(lambda x: ((1 + x).prod() - 1) * 100)
                       for k, p in base.items()})
    yr['Universum'] = base[TESTS[0]]['mkt'].groupby(base[TESTS[0]].index.year).apply(lambda x: ((1 + x).prod() - 1) * 100)
    yr.index.name = 'Jaar'
    A('\n### Rendement per kalenderjaar (%, netto)\n')
    A(an.md_table(yr, {c: '{:+.1f}' for c in yr.columns}))

    # b) winsorized
    dfw = df.copy()
    dfw['Forward Return 1M'] = dfw.groupby('Date')['Forward Return 1M'].transform(
        lambda s: s.clip(s.quantile(.01), s.quantile(.99)))
    rows = []
    for k, c in cols.items():
        p = bv.run_portfolio(dfw, c)
        a, t, b = alpha_t(p)
        rows.append({'Variant': label(k), 'Alpha %/mnd': a, 'Alpha t': t, 'Sharpe': sharpe(p), 'Beta': b})
    A('\n## b) Gewinsoriseerde rendementen (1%/99% per datum)\n')
    A(an.md_table(pd.DataFrame(rows), {'Alpha %/mnd': '{:+.2f}', 'Alpha t': '{:+.2f}', 'Sharpe': '{:.2f}', 'Beta': '{:.2f}'}, index=False))

    # c) zonder top-10 bijdragers
    rows, contrib_tbl = [], None
    for k, c in cols.items():
        contrib = {}
        for d, g in df.groupby('Date'):
            top = g.nlargest(25, c)
            for _, r in top.iterrows():
                contrib[r['yf_ticker']] = contrib.get(r['yf_ticker'], 0) + (r['Forward Return 1M'] - g['Forward Return 1M'].mean()) / 25
        cs = pd.Series(contrib).sort_values(ascending=False)
        tot = cs.sum()
        drop = cs.head(10).index
        if k == ('V0 Huidige screener', 'BN'):
            contrib_tbl = pd.DataFrame({'Cumulatieve bijdrage (pp excess)': cs.head(10) * 100,
                                        'Aandeel van totaal %': cs.head(10) / tot * 100})
            contrib_tbl.index.name = 'Ticker'
        d2 = df[~df['yf_ticker'].isin(drop)].copy()
        p = bv.run_portfolio(d2, c)
        a, t, b = alpha_t(p)
        rows.append({'Variant': label(k), 'Top-10 aandeel in totale excess %': cs.head(10).sum() / tot * 100,
                     'Alpha %/mnd (zonder top-10)': a, 'Alpha t': t, 'Sharpe': sharpe(p)})
    A('\n## c) Zonder de 10 grootste bijdragers (ex-post stress-test)\n')
    A(an.md_table(pd.DataFrame(rows), {'Top-10 aandeel in totale excess %': '{:.0f}', 'Alpha %/mnd (zonder top-10)': '{:+.2f}',
                                       'Alpha t': '{:+.2f}', 'Sharpe': '{:.2f}'}, index=False))
    A('\nGrootste bijdragers voor V0 BN:\n')
    A(an.md_table(contrib_tbl, {'Cumulatieve bijdrage (pp excess)': '{:.0f}', 'Aandeel van totaal %': '{:.1f}'}))

    # d) Top-N
    rows = []
    for k, c in cols.items():
        r = {'Variant': label(k)}
        for n in (15, 25, 40, 60):
            p = bv.run_portfolio(df, c, n=n)
            a, t, b = alpha_t(p)
            r[f'N={n} alpha t'] = t
            r[f'N={n} Sharpe'] = sharpe(p)
        rows.append(r)
    A('\n## d) Top-N gevoeligheid\n')
    A(an.md_table(pd.DataFrame(rows), {c: '{:+.2f}' for c in pd.DataFrame(rows).columns if c != 'Variant'}, index=False))

    # e) kosten
    rows = []
    old = bv.ONE_WAY
    for ow in (0.001, 0.0025, 0.005):
        bv.ONE_WAY = ow
        for k, c in cols.items():
            p = bv.run_portfolio(df, c)
            a, t, b = alpha_t(p)
            rows.append({'Kosten per kant %': ow * 100, 'Variant': label(k), 'Alpha %/mnd': a, 'Alpha t': t, 'Sharpe': sharpe(p)})
    bv.ONE_WAY = old
    A('\n## e) Kostengevoeligheid\n')
    A(an.md_table(pd.DataFrame(rows), {'Kosten per kant %': '{:.2f}', 'Alpha %/mnd': '{:+.2f}', 'Alpha t': '{:+.2f}', 'Sharpe': '{:.2f}'}, index=False))

    # f) Q1-Q5 beta-neutraal over hele universum
    rows = []
    for k, c in cols.items():
        r_ = df.groupby('Date')[c].rank(method='first', ascending=False)
        n_ = df.groupby('Date')[c].transform('size')
        q = np.ceil(r_ / n_ * 5)
        piv = df.assign(Q=q).pivot_table(index='Date', columns='Q', values='Excess BN', aggfunc='mean')
        ls = piv[1.0] - piv[5.0]
        piv2 = df.assign(Q=q).pivot_table(index='Date', columns='Q', values='Excess', aggfunc='mean')
        ls2 = piv2[1.0] - piv2[5.0]
        rows.append({'Variant': label(k), 'Q1-Q5 excess %/mnd': ls2.mean() * 100, 't': an.tstat(ls2),
                     'Q1-Q5 beta-neutraal %/mnd': ls.mean() * 100, 't (BN)': an.tstat(ls),
                     'Q1 excess %': piv2[1.0].mean() * 100, 'Q5 excess %': piv2[5.0].mean() * 100})
    A('\n## f) Brede toets: Q1-Q5 over het hele universum\n')
    A(an.md_table(pd.DataFrame(rows), {c: '{:+.2f}' for c in pd.DataFrame(rows).columns if c != 'Variant'}, index=False))

    with open(os.path.join(an.ART_DIR, f'robustness_{TAG}_tables.md'), 'w', encoding='utf-8') as f:
        f.write('\n'.join(out))
    print('klaar')


if __name__ == '__main__':
    main()
