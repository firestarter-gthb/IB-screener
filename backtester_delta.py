"""
Onderzoek: heeft de DELTA-kolom (Rank all past - Rank all, ~1 maand geleden) voorspellende waarde?

Opzet (zelfde dataset/conventies als backtester_analyzer_v2.py):
  * Data: backtest_dataset_10y_fix.csv (maandelijkse snapshots, ~21 handelsdagen uit elkaar).
  * Delta wordt per snapshot gereconstrueerd uit Rank all van de vorige snapshot (zelfde definitie
    als ib_momentum_screener.py). Naast de ruwe Delta ook Delta in percentielpunten, omdat het
    universum groeit (237 -> 289 aandelen) en ruwe rankverschillen dan niet vergelijkbaar zijn.
  * Target = EXCESS rendement t.o.v. het gelijk-gewogen universum op die datum (marktbias eruit),
    voor 1 maand en 3 maanden (3M = 3 opeenvolgende, niet-overlappende maandrendementen).
  * Alles cross-sectioneel per datum; geen in-sample fit en geen parameter-optimalisatie.

Onderdelen:
  1. Mechanica: wat zit er eigenlijk in Delta (hangt samen met 1M-rendement en het rank-niveau)?
  2. Information Coefficient (Spearman) per datum, incl. HAC t-stat.
  3. Fama-MacBeth: voegt Delta iets toe BOVEN Rank all (+ Beta / 1M-rendement)?
  4. Dubbele sortering binnen Top 25 / 50 / 100: risers vs fallers, en 'nieuwkomers' vs 'blijvers'.
  5. Top-N portefeuilles met Delta-regels, incl. turnover, kosten, Sharpe, max drawdown.
  6. Stabiliteit: kalenderjaren, eerste/tweede helft, marktmaand omhoog/omlaag.
"""
import os
import sys
import argparse
import warnings
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from scipy.stats import spearmanr

warnings.filterwarnings('ignore')
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

DATA = 'backtest_dataset_10y_fix.csv'
ART_DIR = r'C:\Users\ROB5293\.gemini\antigravity-ide\brain\208c0e93-f426-47b9-8641-da26a59d824d'
COST_ROUNDTRIP = 0.002   # 0,20% per vervangen positie (aankoop + verkoop), net als v2
RNG = np.random.default_rng(42)

plt.style.use('seaborn-v0_8-whitegrid')
OUT = []


def say(s=''):
    print(s)
    OUT.append(s)


# ----------------------------------------------------------------------------- helpers
def md_table(df, fmts=None, index=True):
    fmts = fmts or {}
    cols = ([df.index.name or ''] if index else []) + [str(c) for c in df.columns]
    lines = ['| ' + ' | '.join(cols) + ' |', '| ' + ' | '.join([':---'] * len(cols)) + ' |']
    for idx, row in df.iterrows():
        cells = [str(idx)] if index else []
        for c in df.columns:
            v = row[c]
            f = fmts.get(c)
            if isinstance(v, (float, np.floating)):
                cells.append('-' if pd.isna(v) else (f.format(v) if f else f'{v:.3f}'))
            else:
                cells.append(str(v))
        lines.append('| ' + ' | '.join(cells) + ' |')
    return '\n'.join(lines) + '\n'


def nw_t(s, lag=0):
    """t-stat van het gemiddelde met Newey-West (Bartlett) correctie voor autocorrelatie."""
    x = pd.Series(s).dropna().values.astype(float)
    n = len(x)
    if n < 8 or x.std() == 0:
        return np.nan
    e = x - x.mean()
    v = e @ e / n
    for k in range(1, lag + 1):
        v += 2 * (1 - k / (lag + 1)) * (e[k:] @ e[:-k]) / n
    return x.mean() / np.sqrt(v / n)


def max_drawdown(r):
    cum = (1 + pd.Series(r)).cumprod()
    return (cum / cum.cummax() - 1).min()


def zs(s):
    sd = s.std()
    return (s - s.mean()) / sd if sd and sd > 0 else s * 0


def wins(s, lo=0.01, hi=0.99):
    return s.clip(s.quantile(lo), s.quantile(hi))


# ----------------------------------------------------------------------------- data
def load(path):
    d = pd.read_csv(path, sep='|', parse_dates=['Snapshot Date']).rename(columns={'Snapshot Date': 'Date'})
    dates = sorted(d['Date'].unique())
    d['t'] = d['Date'].map({dt: i for i, dt in enumerate(dates)})
    d['n'] = d.groupby('t')['Rank all'].transform('size')

    # Rank in percentielpunten: 0 = beste, 100 = slechtste (vergelijkbaar bij wisselend universum)
    d['RankPct'] = (d['Rank all'] - 1) / (d['n'] - 1) * 100
    d['R1MPct'] = (d['Rank 1M'] - 1) / (d['n'] - 1) * 100

    # Rank van de vorige snapshot (~1 maand eerder), zelfde definitie als de live screener
    prev = d[['yf_ticker', 't', 'Rank all', 'RankPct']].copy()
    prev['t'] += 1
    prev = prev.rename(columns={'Rank all': 'Rank prev', 'RankPct': 'RankPct prev'})
    d = d.merge(prev, on=['yf_ticker', 't'], how='left')
    d['Delta'] = d['Rank prev'] - d['Rank all']              # positief = gestegen (zoals in screener)
    d['DeltaPct'] = d['RankPct prev'] - d['RankPct']          # idem in percentielpunten

    # Excess 1M t.o.v. gelijk-gewogen universum
    d['Mkt'] = d.groupby('t')['Forward Return 1M'].transform('mean')
    d['Ex1'] = d['Forward Return 1M'] - d['Mkt']

    # 3M vooruit: 3 opeenvolgende maandrendementen (snapshots liggen exact 21 dagen uit elkaar)
    piv = d.pivot(index='t', columns='yf_ticker', values='Forward Return 1M')
    f3 = ((1 + piv) * (1 + piv.shift(-1)) * (1 + piv.shift(-2)) - 1).stack().rename('Fwd3').reset_index()
    d = d.merge(f3, on=['t', 'yf_ticker'], how='left')
    d['Mkt3'] = d.groupby('t')['Fwd3'].transform('mean')
    d['Ex3'] = d['Fwd3'] - d['Mkt3']
    return d, dates


def prepare_signals(a):
    """Z-scores en geortogonaliseerde Delta; alles per datum."""
    a['Ex1w'] = a.groupby('t')['Ex1'].transform(wins)
    a['Ex3w'] = a.groupby('t')['Ex3'].transform(wins)

    def orth(g):
        x, y = g['RankPct'].values, g['DeltaPct'].values
        b = np.polyfit(x, y, 1)
        return pd.Series(y - np.polyval(b, x), index=g.index)

    a['DeltaOrth'] = a.groupby('t', group_keys=False).apply(orth)
    a['zRank'] = -a.groupby('t')['RankPct'].transform(zs)
    a['zDelta'] = a.groupby('t')['DeltaPct'].transform(zs)
    a['zDeltaOrth'] = a.groupby('t')['DeltaOrth'].transform(zs)
    a['zR1M'] = -a.groupby('t')['R1MPct'].transform(zs)
    a['zBeta'] = a.groupby('t')['Beta'].transform(zs).clip(-3, 3)
    a['zPrevRank'] = -a.groupby('t')['RankPct prev'].transform(zs)
    return a


# ----------------------------------------------------------------------------- 1. mechanica
def mechanics(a):
    say('## 1. Wat zit er in Delta?\n')
    c1 = a.groupby('t').apply(lambda g: spearmanr(g['DeltaPct'], g['R1MPct'])[0]).mean()
    c2 = a.groupby('t').apply(lambda g: spearmanr(g['DeltaPct'], g['RankPct'])[0]).mean()
    c3 = a.groupby('t').apply(lambda g: spearmanr(g['DeltaPct'], g['RankPct prev'])[0]).mean()
    say(f'* Gem. cross-sectionele Spearman tussen Delta (pct) en **Rank 1M**: **{-c1:+.2f}** '
        f'(positief = Delta stijgt met het 1M-rendement; Rank 1M is rank 1=beste).')
    say(f'* Spearman tussen Delta (pct) en huidige Rank all: {-c2:+.2f} (positief = hoge Delta zit vaker bovenin).')
    say(f'* Spearman tussen Delta (pct) en Rank all van een maand geleden: {-c3:+.2f} '
        f'(negatief = wie vorige maand al bovenin stond, kan niet meer veel stijgen).\n')

    tmp = a.copy()
    tmp['Groep'] = pd.cut(tmp['Rank all'], [0, 25, 50, 100, 200, 10_000],
                          labels=['Top 25', '26-50', '51-100', '101-200', '>200'])
    out = tmp.groupby('Groep').agg(**{
        'Gem. Delta (ruw)': ('Delta', 'mean'),
        'Gem. Delta (pct-pnt)': ('DeltaPct', 'mean'),
        '% met Delta>0': ('Delta', lambda x: (x > 0).mean() * 100),
        'Aantal obs.': ('Delta', 'size')})
    out.index.name = 'Rank-groep nu'
    say(md_table(out, {'Gem. Delta (ruw)': '{:.1f}', 'Gem. Delta (pct-pnt)': '{:.1f}',
                       '% met Delta>0': '{:.0f}%', 'Aantal obs.': '{:.0f}'}))


# ----------------------------------------------------------------------------- 2. IC
def ic_series(a, col, tgt):
    out = {}
    for t, g in a.groupby('t'):
        g = g[[col, tgt]].dropna()
        if len(g) >= 30:
            out[t] = spearmanr(g[col], g[tgt])[0]
    return pd.Series(out)


def ic_table(a):
    say('## 2. Information Coefficient (Spearman, per maand) t.o.v. EXCESS rendement\n')
    say('IC > 0 betekent: een hogere score gaat samen met een beter excess-rendement erna. '
        't-stat met Newey-West (1M: geen lag, 3M: lag 2 vanwege overlap in de meting).\n')
    sigs = {
        'Rank all (score, als referentie)': 'zRank',
        'Rank all van 1 maand geleden': 'zPrevRank',
        'Delta (percentielpunten)': 'zDelta',
        'Delta ruw (zoals in screener)': 'Delta',
        'Delta ORTHOGONAAL aan Rank all': 'zDeltaOrth',
        '1M-rendement (puur)': 'Last month',
    }
    series, rows = {}, []
    for name, col in sigs.items():
        row = {}
        for h, tgt, lag in (('1M', 'Ex1', 0), ('3M', 'Ex3', 2)):
            s = ic_series(a, col, tgt)
            series[(name, h)] = s
            row[f'IC {h}'] = s.mean()
            row[f't {h}'] = nw_t(s, lag)
            row[f'% mnd>0 {h}'] = (s > 0).mean() * 100
        rows.append(pd.Series(row, name=name))
    out = pd.DataFrame(rows)
    out.index.name = 'Signaal'
    say(md_table(out, {'IC 1M': '{:+.3f}', 'IC 3M': '{:+.3f}', 't 1M': '{:+.2f}', 't 3M': '{:+.2f}',
                       '% mnd>0 1M': '{:.0f}%', '% mnd>0 3M': '{:.0f}%'}))
    return series


# ----------------------------------------------------------------------------- 3. Fama-MacBeth
def fama_macbeth(a, ycol, xcols, lag):
    rows = []
    for t, g in a.groupby('t'):
        g = g[[ycol] + xcols].dropna()
        if len(g) < 50:
            continue
        X = np.c_[np.ones(len(g)), g[xcols].values]
        rows.append(np.linalg.lstsq(X, g[ycol].values, rcond=None)[0])
    B = pd.DataFrame(rows, columns=['const'] + xcols)
    return B, {c: (B[c].mean() * 100, nw_t(B[c], lag)) for c in xcols}


def fm_table(a):
    say('## 3. Fama-MacBeth: voegt Delta iets toe BOVEN Rank all?\n')
    say('Per maand een regressie van het (gewinsoriseerde) excess-rendement op gestandaardiseerde '
        'kenmerken. Coëfficiënt = extra excess-rendement in **%-punt per 1 standaarddeviatie** van het kenmerk. '
        'Rank all is hier omgedraaid zodat + = beter.\n')
    models = {
        'M1: alleen Rank all': ['zRank'],
        'M2: alleen Delta': ['zDelta'],
        'M3: Rank all + Delta': ['zRank', 'zDelta'],
        'M4: Rank all + Delta + Beta': ['zRank', 'zDelta', 'zBeta'],
        'M5: Rank all + Delta + Rank 1M + Beta': ['zRank', 'zDelta', 'zR1M', 'zBeta'],
    }
    names = {'zRank': 'Rank all', 'zDelta': 'Delta', 'zBeta': 'Beta', 'zR1M': 'Rank 1M'}
    for h, y, lag in (('1 maand', 'Ex1w', 0), ('3 maanden', 'Ex3w', 2)):
        say(f'**Horizon {h}**\n')
        rows = []
        for mname, xs in models.items():
            _, res = fama_macbeth(a, y, xs, lag)
            row = {'Model': mname}
            for x in ['zRank', 'zDelta', 'zR1M', 'zBeta']:
                if x in res:
                    row[names[x]] = f'{res[x][0]:+.2f} (t={res[x][1]:+.1f})'
                else:
                    row[names[x]] = ''
            rows.append(row)
        say(md_table(pd.DataFrame(rows).set_index('Model')))


# ----------------------------------------------------------------------------- 4. dubbele sortering
def group_stats(per_date_mean):
    s = per_date_mean.dropna()
    return s.mean() * 100, nw_t(s, 0), len(s)


def double_sort(a):
    say('## 4. Dubbele sortering: binnen de Top-N, doen risers het beter dan fallers?\n')
    say('Per maand: pak de Top-N op Rank all en splits die op Delta. '
        'Getoond: gemiddeld excess-rendement de maand erna (%-punt, gelijk-gewogen) en t-stat over maanden.\n')
    rows = []
    diffs = {}
    for N in (25, 50, 100):
        sub = a[a['Rank all'] <= N].copy()
        sub['G'] = np.where(sub['Delta'] > 0, 'Riser', np.where(sub['Delta'] < 0, 'Daler', 'Gelijk'))
        for h, y in (('1M', 'Ex1'), ('3M', 'Ex3')):
            m = sub.groupby(['t', 'G'])[y].mean().unstack()
            for grp in ['Riser', 'Daler']:
                mean, t, n = group_stats(m[grp])
                med = sub[sub['G'] == grp][y].median() * 100
                rows.append({'Top-N': N, 'Horizon': h, 'Groep': grp, 'Gem. obs./mnd':
                             sub[sub['G'] == grp].groupby('t').size().mean(), 'Excess %': mean,
                             't': t, 'Mediaan stock %': med})
            diff = (m['Riser'] - m['Daler'])
            mean, t, n = group_stats(diff)
            rows.append({'Top-N': N, 'Horizon': h, 'Groep': 'Riser − Daler', 'Gem. obs./mnd': np.nan,
                         'Excess %': mean, 't': t, 'Mediaan stock %': np.nan})
            diffs[(N, h)] = diff
    out = pd.DataFrame(rows).set_index(['Top-N', 'Horizon', 'Groep'])
    say(md_table(out, {'Gem. obs./mnd': '{:.1f}', 'Excess %': '{:+.2f}', 't': '{:+.2f}',
                       'Mediaan stock %': '{:+.2f}'}))

    # Nieuwkomers vs blijvers
    say('**Nieuwkomers vs blijvers.** Nieuwkomer = stond vorige maand NIET in de Top-N, blijver = wel.\n')
    rows = []
    for N in (25, 50):
        sub = a[a['Rank all'] <= N].copy()
        sub['G'] = np.where(sub['Rank prev'] <= N, 'Blijver', 'Nieuwkomer')
        m = sub.groupby(['t', 'G'])['Ex1'].mean().unstack()
        for grp in ['Blijver', 'Nieuwkomer']:
            mean, t, n = group_stats(m[grp])
            rows.append({'Top-N': N, 'Groep': grp, 'Gem. aantal/mnd': sub[sub['G'] == grp].groupby('t').size().mean(),
                         'Excess 1M %': mean, 't': t})
        mean, t, n = group_stats(m['Nieuwkomer'] - m['Blijver'])
        rows.append({'Top-N': N, 'Groep': 'Nieuwkomer − Blijver', 'Gem. aantal/mnd': np.nan, 'Excess 1M %': mean, 't': t})
    say(md_table(pd.DataFrame(rows).set_index(['Top-N', 'Groep']),
                 {'Gem. aantal/mnd': '{:.1f}', 'Excess 1M %': '{:+.2f}', 't': '{:+.2f}'}))
    return diffs


def delta_buckets(a):
    """Delta-kwintielen: binnen heel universum en binnen Top 50."""
    say('**Delta-kwintielen (1 = grootste stijgers) en het excess-rendement de maand erna**\n')
    rows = []
    res = {}
    for label, sub in (('Heel universum', a), ('Binnen Top 50', a[a['Rank all'] <= 50])):
        s = sub.copy()
        s['Q'] = s.groupby('t')['DeltaPct'].transform(lambda x: pd.qcut(x.rank(method='first'), 5, labels=False) + 1
                                                       if len(x) >= 10 else np.nan)
        # Omdraaien: 1 = grootste stijgers
        s['Q'] = 6 - s['Q']
        m = s.groupby(['t', 'Q'])['Ex1'].mean().unstack()
        res[label] = m
        for q in [1, 2, 3, 4, 5]:
            if q in m:
                mean, t, n = group_stats(m[q])
                rows.append({'Set': label, 'Kwintiel': q, 'Excess 1M %': mean, 't': t, 'Maanden': n})
        mean, t, n = group_stats(m[1] - m[5])
        rows.append({'Set': label, 'Kwintiel': '1 − 5', 'Excess 1M %': mean, 't': t, 'Maanden': n})
    say(md_table(pd.DataFrame(rows).set_index(['Set', 'Kwintiel']),
                 {'Excess 1M %': '{:+.2f}', 't': '{:+.2f}', 'Maanden': '{:.0f}'}))
    return res


# ----------------------------------------------------------------------------- 5. portefeuilles
def sel_A(g, N): return g.nsmallest(N, 'Rank all')
def sel_B(g, N): return g[g['Delta'] > 0].nsmallest(N, 'Rank all')
def sel_C(g, N): return g[g['Delta'] <= 0].nsmallest(N, 'Rank all')
def sel_D(g, N): return g.nsmallest(2 * N, 'Rank all').nlargest(N, 'Delta')
def sel_E(g, N): return g.nsmallest(2 * N, 'Rank all').nsmallest(N, 'Delta')
def sel_F(g, N): return g.nlargest(N, 'Delta')
def sel_G(g, N): return g[g['DeltaPct'] >= -10].nsmallest(N, 'Rank all')


STRATS = {
    'A  Top-N op Rank all (baseline)': sel_A,
    'B  Top-N, alleen Delta > 0 (risers)': sel_B,
    'C  Top-N, alleen Delta ≤ 0': sel_C,
    'D  Uit Top-2N de N grootste Delta': sel_D,
    'E  Uit Top-2N de N kleinste Delta': sel_E,
    'F  Puur de N grootste Delta (heel universum)': sel_F,
    'G  Top-N, zonder harde dalers (Δ < −10 pct-pnt)': sel_G,
}


def run_portfolio(a, selector, N):
    rows, prev = [], set()
    for t, g in a.groupby('t'):
        top = selector(g, N)
        names = set(top['yf_ticker'])
        turnover = 1.0 if not prev else 1 - len(names & prev) / max(len(names), 1)
        prev = names
        rows.append({'t': t, 'Date': g['Date'].iloc[0], 'gross': top['Forward Return 1M'].mean(),
                     'mkt': g['Forward Return 1M'].mean(), 'beta': top['Beta'].mean(),
                     'turnover': turnover, 'n': len(top)})
    p = pd.DataFrame(rows).set_index('t')
    p['net'] = p['gross'] - p['turnover'] * COST_ROUNDTRIP
    return p


def portfolio_table(a, N):
    res = {k: run_portfolio(a, f, N) for k, f in STRATS.items()}
    base = res['A  Top-N op Rank all (baseline)']
    rows = []
    for k, p in res.items():
        m = len(p)
        ann = lambda r: (1 + r).prod() ** (12 / m) - 1
        ex = p['gross'] - p['mkt']
        dif = p['net'] - base['net']
        rows.append({'Strategie': k,
                     'Ann. netto %': ann(p['net']) * 100,
                     'Sharpe netto': p['net'].mean() / p['net'].std() * np.sqrt(12),
                     'Max DD %': max_drawdown(p['net']) * 100,
                     'Excess/mnd %': ex.mean() * 100, 't excess': nw_t(ex, 0),
                     'Δ netto vs A %/mnd': dif.mean() * 100 if k[0] != 'A' else np.nan,
                     't vs A': nw_t(dif, 0) if k[0] != 'A' else np.nan,
                     'Turnover %': p['turnover'].iloc[1:].mean() * 100,
                     'Gem. Beta': p['beta'].mean()})
    mk = base['mkt']
    rows.append({'Strategie': 'Universum (gelijk gewogen)', 'Ann. netto %': ((1 + mk).prod() ** (12 / len(mk)) - 1) * 100,
                 'Sharpe netto': mk.mean() / mk.std() * np.sqrt(12), 'Max DD %': max_drawdown(mk) * 100})
    out = pd.DataFrame(rows).set_index('Strategie')
    return out, res


def portfolios(a):
    say('## 5. Portefeuilles met Delta-regels (maandelijks herschikt, gelijk gewogen, 0,20% kosten per vervanging)\n')
    all_res = {}
    for N in (25, 50):
        say(f'**N = {N}** ({len(a["t"].unique())} maanden)\n')
        out, res = portfolio_table(a, N)
        say(md_table(out, {'Ann. netto %': '{:.1f}', 'Sharpe netto': '{:.2f}', 'Max DD %': '{:.1f}',
                           'Excess/mnd %': '{:+.2f}', 't excess': '{:+.2f}', 'Δ netto vs A %/mnd': '{:+.2f}',
                           't vs A': '{:+.2f}', 'Turnover %': '{:.0f}', 'Gem. Beta': '{:.2f}'}))
        all_res[N] = res
    return all_res


# ----------------------------------------------------------------------------- 6. stabiliteit
def stability(a, diffs, port_res):
    say('## 6. Is het resultaat stabiel in de tijd?\n')
    say('Maandelijks verschil in excess-rendement **Riser − Daler binnen de Top 50** (1M), uitgesplitst:\n')
    d50 = diffs[(50, '1M')].rename('diff').to_frame()
    tmap = a.drop_duplicates('t').set_index('t')[['Date', 'Mkt']]
    d50 = d50.join(tmap)
    d50['Jaar'] = d50['Date'].dt.year
    d50['Periode'] = np.where(d50['Date'] < d50['Date'].median(), 'Eerste helft', 'Tweede helft')
    d50['Markt'] = np.where(d50['Mkt'] > 0, 'Marktmaand omhoog', 'Marktmaand omlaag')
    rows = []
    for col in ['Jaar', 'Periode', 'Markt']:
        for key, g in d50.groupby(col):
            rows.append({'Splitsing': f'{col}: {key}', 'Maanden': len(g), 'Gem. Riser−Daler %': g['diff'].mean() * 100,
                         '% mnd > 0': (g['diff'] > 0).mean() * 100})
    ex_covid = d50[(d50['Date'] < '2020-02-01') | (d50['Date'] > '2020-12-31')]
    rows.append({'Splitsing': 'Zonder 2020', 'Maanden': len(ex_covid), 'Gem. Riser−Daler %': ex_covid['diff'].mean() * 100,
                 '% mnd > 0': (ex_covid['diff'] > 0).mean() * 100})
    out = pd.DataFrame(rows).set_index('Splitsing')
    say(md_table(out, {'Maanden': '{:.0f}', 'Gem. Riser−Daler %': '{:+.2f}', '% mnd > 0': '{:.0f}%'}))


# ----------------------------------------------------------------------------- grafieken
def charts(a, ic, buckets, port_res):
    os.makedirs(ART_DIR, exist_ok=True)

    # 1. Delta-kwintielen
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.2), sharey=True)
    for ax, (label, m) in zip(axes, buckets.items()):
        mean = m.mean() * 100
        se = m.std() / np.sqrt(m.count()) * 100
        cols = ['#1a9e73' if q == 1 else '#9aa5b1' for q in mean.index]
        ax.bar([f'K{int(q)}' for q in mean.index], mean.values, yerr=1.96 * se.values, color=cols, capsize=4)
        ax.axhline(0, color='k', lw=0.8)
        ax.set_title(label)
        ax.set_xlabel('Delta-kwintiel (K1 = grootste stijgers, K5 = grootste dalers)')
    axes[0].set_ylabel('Gem. excess-rendement volgende maand (%-punt, ±95% CI)')
    fig.suptitle('Excess-rendement volgende maand per Delta-kwintiel')
    fig.tight_layout()
    fig.savefig(os.path.join(ART_DIR, 'delta_kwintielen.png'), dpi=140)
    plt.close(fig)

    # 2. Cumulatief
    res = port_res[25]
    fig, ax = plt.subplots(figsize=(11, 5))
    styles = {'A': ('#111111', 2.4), 'B': ('#1a9e73', 1.4), 'C': ('#d9534f', 1.4),
              'D': ('#3b82f6', 1.2), 'E': ('#f59e0b', 1.2)}
    for k, p in res.items():
        if k[0] in styles:
            c, lw = styles[k[0]]
            ax.plot(p['Date'], (1 + p['net']).cumprod(), label=k, color=c, lw=lw)
    mk = res['A  Top-N op Rank all (baseline)']
    ax.plot(mk['Date'], (1 + mk['mkt']).cumprod(), label='Universum', color='#888888', lw=1.4, ls='--')
    ax.set_yscale('log')
    ax.set_title('Top 25: groei van 1 (netto na kosten, logschaal)')
    ax.legend(fontsize=8, loc='upper left')
    fig.tight_layout()
    fig.savefig(os.path.join(ART_DIR, 'delta_portefeuilles.png'), dpi=140)
    plt.close(fig)

    # 3. IC-tijdreeks (12-maands voortschrijdend)
    fig, ax = plt.subplots(figsize=(11, 4.2))
    tmap = a.drop_duplicates('t').set_index('t')['Date']
    for (name, h), s in ic.items():
        if h == '1M' and name in ('Delta (percentielpunten)', 'Delta ORTHOGONAAL aan Rank all',
                                  'Rank all (score, als referentie)'):
            r = s.rolling(12).mean()
            ax.plot(tmap.reindex(r.index), r.values, label=name)
    ax.axhline(0, color='k', lw=0.8)
    ax.set_title('Voortschrijdend 12-maands gemiddelde IC (1M vooruit)')
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(os.path.join(ART_DIR, 'delta_ic_rolling.png'), dpi=140)
    plt.close(fig)


# ----------------------------------------------------------------------------- main
def main():
    global ART_DIR
    ap = argparse.ArgumentParser()
    ap.add_argument('--data', default=DATA)
    ap.add_argument('--out', default=ART_DIR)
    args = ap.parse_args()
    ART_DIR = args.out

    d, dates = load(args.data)
    a = d[d['Delta'].notna()].copy()        # snapshot 1 en nieuwe tickers hebben geen Delta
    a = prepare_signals(a)

    say('# Onderzoek: heeft de Delta-kolom voorspellende waarde?\n')
    say(f'* Dataset: `{args.data}`, {len(dates)} maandelijkse snapshots '
        f'({pd.Timestamp(dates[0]).date()} t/m {pd.Timestamp(dates[-1]).date()}).')
    say(f'* Analyse-sample (met Delta): {len(a):,} aandeel-maanden, {a["t"].nunique()} maanden, '
        f'{a["yf_ticker"].nunique()} aandelen; {len(d) - len(a):,} rijen zonder Delta weggelaten '
        f'(eerste snapshot en nieuw toegevoegde tickers).')
    say(f'* 3M-doelwaarde beschikbaar voor {a["Ex3"].notna().sum():,} rijen (laatste 2 snapshots missen die).')
    say(f'* Gem. verschil universum 1M: {a.groupby("t")["Mkt"].first().mean() * 100:+.2f}% per maand.\n')

    mechanics(a)
    ic = ic_table(a)
    fm_table(a)
    diffs = double_sort(a)
    buckets = delta_buckets(a)
    port = portfolios(a)
    stability(a, diffs, port)
    charts(a, ic, buckets, port)

    os.makedirs(ART_DIR, exist_ok=True)
    with open(os.path.join(ART_DIR, 'delta_analysis_tables.md'), 'w', encoding='utf-8') as f:
        f.write('\n'.join(OUT))
    print('\nKlaar. Tabellen + grafieken staan in', ART_DIR)


if __name__ == '__main__':
    main()
