"""
Vooraf vastgelegde test van screener-varianten (geen parameters gefit op de data).

HYPOTHESEN (gedefinieerd VOOR het bekijken van resultaten, gebaseerd op literatuur + review v2):
  V0  Huidige screener (Total score)                           -> referentie
  V1  Zonder sectorfactor (alleen 1M/3M/1Y/200MA ranks)
  V2  12-1 momentum (rendement 12M excl. laatste maand)
  V3  Trendkwaliteit = 50% Sharpe + 50% Efficiency
  V4  40% 12-1 momentum + 30% Sharpe + 30% Efficiency
  V5  Laagste Beta (referentie voor low-beta anomalie)
  V6  70% V4 + 30% laag-Beta
Elke variant (behalve V5) ook in een BETA-NEUTRALE versie ("BN"): per datum residu van
score-percentiel na regressie op Beta-percentiel (alleen informatie van die datum).
Extra overlay "TF": SPY-trendfilter - alleen beleggen als SPY-slotkoers > SMA200 op de snapshot-datum,
anders cash (0%).

BESLISREGELS (vooraf):
  * Primaire toets = CAPM-alpha van de Top-25 (netto, na kosten) t.o.v. het gelijk-gewogen universum.
  * 'Sterk' : alpha t > 2,9 (Bonferroni voor ~13 varianten) EN alpha > 0 in beide helften van de periode.
  * 'Suggestief' : t > 2,0 EN alpha > 0 in beide helften.
  * Anders: geen bewijs.
"""
import os
import sys
import warnings
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

import backtester_analyzer_v2 as an

warnings.filterwarnings('ignore')
ART_DIR = an.ART_DIR
ONE_WAY = 0.001   # 0,10% per gekochte/verkochte positie
N_TOP = 25


def pct(df, col, ascending=True):
    return df.groupby('Date')[col].rank(pct=True, ascending=ascending)


def build_scores(df):
    d = df
    d['_p_m12_1'] = pct(d, 'Mom 12-1')
    d['_p_sharpe'] = pct(d, 'Sharpe Ratio')
    d['_p_eff'] = pct(d, 'Efficiency Score')
    d['_p_lowbeta'] = pct(d, 'Beta', ascending=False)
    d['_p_beta'] = pct(d, 'Beta')

    base = (((d['Rank 1M'] * 0.15 + d['Rank 3M'] * 0.40 + d['Rank 1 Jaar'] * 0.45) * 0.70) + d['Rank 200 MAVG'] * 0.20)
    scores = {
        'V0 Huidige screener': -d['Total score'],
        'V1 Zonder sectorfactor': -base,
        'V2 Momentum 12-1': d['_p_m12_1'],
        'V3 Trendkwaliteit (Sharpe+Eff)': 0.5 * d['_p_sharpe'] + 0.5 * d['_p_eff'],
        'V4 Mom12-1 + trendkwaliteit': 0.4 * d['_p_m12_1'] + 0.3 * d['_p_sharpe'] + 0.3 * d['_p_eff'],
    }
    # V6 gebruikt percentiel van V4
    d['_v4'] = scores['V4 Mom12-1 + trendkwaliteit']
    scores['V6 V4 + laag-beta tilt'] = 0.7 * pct(d, '_v4') + 0.3 * d['_p_lowbeta']
    scores['V5 Laagste Beta (referentie)'] = d['_p_lowbeta']
    return scores


def beta_neutralize(df, score):
    tmp = pd.DataFrame({'Date': df['Date'], 's': pct_series(df, score), 'b': df['_p_beta']}, index=df.index)

    def res(g):
        X = np.c_[np.ones(len(g)), g['b'].values]
        coef = np.linalg.lstsq(X, g['s'].values, rcond=None)[0]
        return pd.Series(g['s'].values - X @ coef, index=g.index)
    return tmp.groupby('Date', group_keys=False).apply(res)


def pct_series(df, s):
    return s.groupby(df['Date']).rank(pct=True)


def trend_filter(dates):
    import yfinance as yf
    spy = yf.download('SPY', period='13y', progress=False, auto_adjust=True)['Close'].squeeze().dropna()
    if getattr(spy.index, 'tz', None) is not None:
        spy.index = spy.index.tz_localize(None)
    sma = spy.rolling(200).mean()
    on = {}
    for d in dates:
        pos = spy.index.searchsorted(pd.Timestamp(d), side='right') - 1
        on[d] = bool(pos >= 199 and spy.iloc[pos] > sma.iloc[pos])
    return pd.Series(on)


def run_portfolio(df, score_col, invest_mask=None, n=N_TOP):
    rows, prev, prev_inv = [], set(), False
    for d, g in df.groupby('Date'):
        inv = True if invest_mask is None else bool(invest_mask.get(d, True))
        mkt = g['Forward Return 1M'].mean()
        if inv:
            top = g.nlargest(n, score_col)
            names = set(top['yf_ticker'])
            if prev_inv and prev:
                cost = (1 - len(names & prev) / n) * 2 * ONE_WAY
            else:
                cost = ONE_WAY            # volledige aankoop vanuit cash
            gross = top['Forward Return 1M'].mean()
            beta = top['Beta'].mean()
            prev = names
        else:
            cost = ONE_WAY if prev_inv else 0.0   # verkoop naar cash
            gross, beta = 0.0, 0.0
            prev = set()
        prev_inv = inv
        rows.append({'Date': d, 'gross': gross, 'net': gross - cost, 'mkt': mkt, 'beta': beta, 'inv': inv,
                     'turnover': cost / (2 * ONE_WAY)})
    return pd.DataFrame(rows).set_index('Date')


def summarize(p):
    m = len(p)
    ann = lambda r: (1 + r).prod() ** (12 / m) - 1
    alpha, t, b = an.capm(p['net'].values, p['mkt'].values)
    half = m // 2
    a1 = an.capm(p['net'].values[:half], p['mkt'].values[:half])[0]
    a2 = an.capm(p['net'].values[half:], p['mkt'].values[half:])[0]
    sd = p['net'].std()
    return {'Ann. netto %': ann(p['net']) * 100,
            'Sharpe': p['net'].mean() / sd * np.sqrt(12) if sd > 0 else np.nan,
            'Max DD %': an.max_drawdown(p['net']) * 100,
            'Alpha %/mnd': alpha * 100, 'Alpha t': t, 'Beta': b,
            'Alpha H1': a1 * 100, 'Alpha H2': a2 * 100,
            'Turnover %': p['turnover'].mean() * 100,
            '% belegd': p['inv'].mean() * 100}


def verdict(r):
    both = r['Alpha H1'] > 0 and r['Alpha H2'] > 0
    if r['Alpha t'] > 2.9 and both:
        return 'STERK'
    if r['Alpha t'] > 2.0 and both:
        return 'suggestief'
    return 'geen bewijs'


def main(path, tag):
    an.DATA = path
    df, n0 = an.load()
    df = df.reset_index(drop=True)
    dates = sorted(df['Date'].unique())
    scores = build_scores(df)
    on = trend_filter(dates)

    out = []
    A = lambda s: out.append(s + '\n')
    A(f'# Variant-test ({tag})\n')
    A(f'- Dataset: {path}; {len(df)} rijen, {len(dates)} snapshots '
      f'({pd.Timestamp(dates[0]).date()} t/m {pd.Timestamp(dates[-1]).date()}); '
      f'aandelen/snapshot {df.groupby("Date").size().min()}-{df.groupby("Date").size().max()}')
    mk = df.groupby('Date')['Mkt'].first()
    A(f'- Universum: cumulatief {((1+mk).prod()-1)*100:.0f}%, ann. {((1+mk).prod()**(12/len(mk))-1)*100:.1f}%, '
      f'Sharpe {mk.mean()/mk.std()*np.sqrt(12):.2f}, max DD {an.max_drawdown(mk)*100:.1f}%')
    A(f'- SPY-trendfilter: {on.mean()*100:.0f}% van de snapshots belegd')

    rows, ports = [], {}
    for name, s in scores.items():
        flavors = [('raw', s)]
        if 'V5' not in name:
            flavors.append(('BN', beta_neutralize(df, s)))
        for fl, sc in flavors:
            col = f'_s_{len(rows)}'
            df[col] = sc.values
            ic = an.ic_summary(an.ic_per_date(df, col, 'Excess'))
            icb = an.ic_summary(an.ic_per_date(df, col, 'Excess BN'))
            for tf in (False, True):
                p = run_portfolio(df, col, invest_mask=on if tf else None)
                r = summarize(p)
                r.update({'Variant': name, 'Type': fl, 'TF': 'ja' if tf else 'nee',
                          'IC': ic['Gem. IC'], 'IC t': ic['t-stat'], 'IC BN': icb['Gem. IC'], 'IC BN t': icb['t-stat']})
                r['Oordeel'] = verdict(r)
                rows.append(r)
                ports[(name, fl, tf)] = p
    res = pd.DataFrame(rows)

    bench = []
    for lab, p in [('Universum (gelijk gew.)', pd.DataFrame({'net': mk, 'mkt': mk, 'turnover': 0, 'inv': True})),
                   ('Top25 hoogste Beta', an.topn_portfolio(df, 25, col='Beta', best_is_low=False).assign(inv=True))]:
        pp = p.copy()
        if 'net' not in pp: pp['net'] = pp['gross']
        bench.append((lab, pp))

    cols = ['Variant', 'Type', 'IC', 'IC t', 'IC BN', 'IC BN t', 'Ann. netto %', 'Sharpe', 'Max DD %',
            'Alpha %/mnd', 'Alpha t', 'Beta', 'Alpha H1', 'Alpha H2', 'Turnover %', 'Oordeel']
    fm = {'IC': '{:+.3f}', 'IC t': '{:+.2f}', 'IC BN': '{:+.3f}', 'IC BN t': '{:+.2f}', 'Ann. netto %': '{:.1f}',
          'Sharpe': '{:.2f}', 'Max DD %': '{:.1f}', 'Alpha %/mnd': '{:+.2f}', 'Alpha t': '{:+.2f}', 'Beta': '{:.2f}',
          'Alpha H1': '{:+.2f}', 'Alpha H2': '{:+.2f}', 'Turnover %': '{:.0f}'}

    A('\n## A. Top-25 per variant, zonder trendfilter (netto na kosten)\n')
    A(an.md_table(res[res['TF'] == 'nee'][cols], fm, index=False))
    A('\n## B. Met SPY-trendfilter (cash bij SPY < SMA200)\n')
    colsb = cols + ['% belegd']
    fm['% belegd'] = '{:.0f}'
    A(an.md_table(res[res['TF'] == 'ja'][colsb], fm, index=False))

    A('\n## C. Benchmarks\n')
    brow = []
    for lab, p in bench:
        r = summarize(p.assign(turnover=p.get('turnover', 0)))
        r['Variant'] = lab
        brow.append(r)
    bdf = pd.DataFrame(brow)[['Variant', 'Ann. netto %', 'Sharpe', 'Max DD %', 'Alpha %/mnd', 'Alpha t', 'Beta']]
    A(an.md_table(bdf, fm, index=False))

    # Kalenderjaar-tabel voor beste (hoogste alpha t) variant zonder TF + V0
    best = res[(res['TF'] == 'nee')].sort_values('Alpha t', ascending=False).iloc[0]
    A(f'\n## D. Per kalenderjaar: V0 vs beste variant ({best["Variant"]} {best["Type"]})\n')
    yr = pd.DataFrame({
        'Universum %': mk.groupby(mk.index.year).apply(lambda x: ((1 + x).prod() - 1) * 100),
        'V0 %': ports[('V0 Huidige screener', 'raw', False)]['net'].groupby(
            ports[('V0 Huidige screener', 'raw', False)].index.year).apply(lambda x: ((1 + x).prod() - 1) * 100),
        'Beste %': ports[(best['Variant'], best['Type'], False)]['net'].groupby(
            ports[(best['Variant'], best['Type'], False)].index.year).apply(lambda x: ((1 + x).prod() - 1) * 100)})
    yr.index.name = 'Jaar'
    A(an.md_table(yr, {c: '{:+.1f}' for c in yr.columns}))

    with open(os.path.join(ART_DIR, f'variants_{tag}_tables.md'), 'w', encoding='utf-8') as f:
        f.write('\n'.join(out))

    # figuur: V0, top 3 alpha-t varianten, universum, + TF van beste
    top3 = res[res['TF'] == 'nee'].sort_values('Alpha t', ascending=False).head(3)
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot((1 + mk).cumprod(), 'k--', label='Universum')
    ax.plot((1 + ports[('V0 Huidige screener', 'raw', False)]['net']).cumprod(), label='V0 Huidige screener', color='#e45756')
    for _, r in top3.iterrows():
        ax.plot((1 + ports[(r['Variant'], r['Type'], False)]['net']).cumprod(), label=f'{r["Variant"]} ({r["Type"]})')
    ax.plot((1 + ports[(best['Variant'], best['Type'], True)]['net']).cumprod(), ':', label=f'{best["Variant"]} ({best["Type"]}) + trendfilter')
    ax.set_yscale('log'); ax.legend(fontsize=8); ax.set_title(f'Top-25 netto groei van 1 euro ({tag})')
    fig.tight_layout(); fig.savefig(os.path.join(ART_DIR, f'variants_{tag}_equity.png'), dpi=130); plt.close(fig)
    print('klaar', tag)


if __name__ == '__main__':
    path = sys.argv[1] if len(sys.argv) > 1 else 'backtest_dataset.csv'
    tag = sys.argv[2] if len(sys.argv) > 2 else '5y'
    main(path, tag)
