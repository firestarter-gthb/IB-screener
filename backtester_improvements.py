"""
Onderzoek naar verdere verbeteringen (10-jaars dataset).

VOORAF VASTGELEGDE VRAGEN
  Q1  Helpen de 4 filters van het Top 25 dashboard (ib_generate_top25_html.py)?
        Trend == Bullish, Action != 'S', Sharpe >= 0.8, Rank longterm <= 100
      -> S1 (dashboard) vs S0 (ongefilterd), plus ablatie: S1 zonder elk filter afzonderlijk.
  Q2  Signaalverval: hoe lang voorspelt de score? (IC voor maand t+1 ... t+6)
      -> bepaalt of maandelijks herbalanceren nodig is.
  Q3  Portefeuilleregels bovenop het dashboard (S1):
        a) Buffer: houd een aandeel zolang het in de top 50 staat (minder turnover)
        b) Sectorlimiet: max 5 aandelen per sector
        c) Houdperiode 3 maanden (3 overlappende tranches)
        d) Sorteren op Rank BN i.p.v. Total score (binnen dezelfde filters)
        e) Sorteren op Rank 12-1 i.p.v. Total score (binnen dezelfde filters)
  Q4  Diagnostiek: voorspelt Delta (rangverbetering t.o.v. vorige maand) iets? Wat doen Action B/N/S?

BESLISREGEL (gepaarde toets op maandelijkse netto rendementen t.o.v. de basis):
  'robuust'    : t > 2.7 (Bonferroni ~10 vergelijkingen) EN zelfde teken in beide helften
  'suggestief' : t > 2.0 EN zelfde teken in beide helften
  'slechter'   : t < -2.0
  anders       : 'geen verschil'
"""
import os
import sys
import warnings
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from scipy.stats import spearmanr

import backtester_analyzer_v2 as an

warnings.filterwarnings('ignore')
PATH = sys.argv[1] if len(sys.argv) > 1 else 'backtest_dataset_10y.csv'
TAG = sys.argv[2] if len(sys.argv) > 2 else '10y'
ONE_WAY = 0.001
N = 25


# ----------------------------------------------------------------------------- data
def prep():
    an.DATA = PATH
    df, _ = an.load()
    df = df.drop_duplicates(['Date', 'yf_ticker']).reset_index(drop=True)
    lt = df['Rank 1 Jaar'] * 0.25 + df['Rank 200 MAVG'] * 0.20 + df['Sharp ratio rank'] * 0.20
    df['Rank longterm'] = lt.groupby(df['Date']).rank(method='min')

    def bn(g):   # identiek aan live 'Rank BN'
        ps = (-g['Total score']).rank(pct=True)
        pb = g['Beta'].rank(pct=True).fillna(0.5)
        X = np.c_[np.ones(len(g)), pb.values]
        c = np.linalg.lstsq(X, ps.values, rcond=None)[0]
        return pd.Series(ps.values - X @ c, index=g.index)
    df['BN score'] = df.groupby('Date', group_keys=False).apply(bn)

    dates = sorted(df['Date'].unique())
    di = {d: i for i, d in enumerate(dates)}
    df['di'] = df['Date'].map(di)
    prev = df[['yf_ticker', 'di', 'Rank all']].copy()
    prev['di'] += 1
    df = df.merge(prev.rename(columns={'Rank all': 'Rank prev'}), on=['yf_ticker', 'di'], how='left')
    df['Delta'] = df['Rank prev'] - df['Rank all']          # positief = gestegen in ranglijst
    df['Neg Total'] = -df['Total score']
    return df, dates


FILTERS = {
    'Trend': lambda g: g['Trend'] == 'Bullish',
    'Action': lambda g: g['Action'] != 'S',
    'Sharpe': lambda g: g['Sharpe Ratio'] >= 0.8,
    'Longterm': lambda g: g['Rank longterm'] <= 100,
}


def combo(names):
    if not names:
        return None
    return lambda g: np.logical_and.reduce([FILTERS[k](g).values for k in names])


ALL = list(FILTERS)


# ----------------------------------------------------------------------------- selectors
def top_by(col, asc=True, filt=None, n=N):
    def f(g, held):
        x = g if filt is None else g[filt(g)]
        x = x.nsmallest(n, col) if asc else x.nlargest(n, col)
        return x['yf_ticker'].tolist()
    return f


def buffer_sel(col='Total score', filt=None, n=N, keep=50):
    def f(g, held):
        x = g if filt is None else g[filt(g)]
        r = x.set_index('yf_ticker')[col].rank(method='first')
        keepers = sorted([t for t in held if t in r.index and r[t] <= keep], key=lambda t: r[t])[:n]
        cands = [t for t in r.sort_values().index if t not in keepers]
        return keepers + cands[:n - len(keepers)]
    return f


def sector_cap(col='Total score', filt=None, n=N, cap=5):
    def f(g, held):
        x = g if filt is None else g[filt(g)]
        out, cnt = [], {}
        for t, s in zip(x.sort_values(col)['yf_ticker'], x.sort_values(col)['GICS sector']):
            if cnt.get(s, 0) < cap:
                out.append(t)
                cnt[s] = cnt.get(s, 0) + 1
            if len(out) == n:
                break
        return out
    return f


# ----------------------------------------------------------------------------- engine
def backtest(df, dates, select, h=1):
    by_date = {d: g.set_index('yf_ticker', drop=False) for d, g in df.groupby('Date')}
    mkt = df.groupby('Date')['Forward Return 1M'].mean()
    nets, turns, ns, betas = [], [], [], []
    for o in range(h):
        held, prev = [], set()
        r_, t_, n_, b_ = {}, {}, {}, {}
        for i, d in enumerate(dates):
            g = by_date[d]
            if (i - o) % h == 0 or not held:
                held = select(g, set(held))
                cur = set(held)
                to = (1 - len(cur & prev) / max(len(cur), 1)) if prev else 0.5
            else:
                held = [t for t in held if t in g.index]
                to = 0.0
            prev = set(held)
            if held:
                r = g.loc[held, 'Forward Return 1M'].mean()
                b = g.loc[held, 'Beta'].mean()
            else:
                r, b = 0.0, 0.0
            r_[d], t_[d], n_[d], b_[d] = r - to * 2 * ONE_WAY, to, len(held), b
        nets.append(pd.Series(r_)); turns.append(pd.Series(t_)); ns.append(pd.Series(n_)); betas.append(pd.Series(b_))
    p = pd.DataFrame({'net': pd.concat(nets, axis=1).mean(axis=1), 'turn': pd.concat(turns, axis=1).mean(axis=1),
                      'n': pd.concat(ns, axis=1).mean(axis=1), 'beta_st': pd.concat(betas, axis=1).mean(axis=1)})
    p['mkt'] = mkt.reindex(p.index)
    return p


def stats(p, base=None):
    m = len(p)
    net = p['net']
    a, t, b = an.capm(net.values, p['mkt'].values)
    out = {'Ann. netto %': ((1 + net).prod() ** (12 / m) - 1) * 100,
           'Sharpe': net.mean() / net.std() * np.sqrt(12),
           'Max DD %': an.max_drawdown(net) * 100,
           'Alpha %/mnd': a * 100, 'Alpha t': t, 'Beta': b,
           'Turnover %/mnd': p['turn'].iloc[1:].mean() * 100, 'Gem. # pos.': p['n'].mean()}
    if base is not None:
        d = (net - base['net']).dropna()
        h = len(d) // 2
        out.update({'Δ %/mnd': d.mean() * 100, 'Δ t': an.tstat(d),
                    'Δ H1': d.iloc[:h].mean() * 100, 'Δ H2': d.iloc[h:].mean() * 100})
        same = np.sign(out['Δ H1']) == np.sign(out['Δ H2']) == np.sign(out['Δ %/mnd'])
        if out['Δ t'] > 2.7 and same:
            v = 'robuust beter'
        elif out['Δ t'] > 2.0 and same:
            v = 'suggestief beter'
        elif out['Δ t'] < -2.0:
            v = 'slechter'
        else:
            v = 'geen verschil'
        out['Oordeel'] = v
    return out


# ----------------------------------------------------------------------------- main
def main():
    df, dates = prep()
    out = []
    A = lambda s: out.append(s + '\n')
    A(f'# Verbeteronderzoek ({TAG})\n')
    A(f'- {len(df)} rijen, {len(dates)} maanden ({pd.Timestamp(dates[0]).date()} t/m {pd.Timestamp(dates[-1]).date()})')
    fm = {'Ann. netto %': '{:.1f}', 'Sharpe': '{:.2f}', 'Max DD %': '{:.1f}', 'Alpha %/mnd': '{:+.2f}',
          'Alpha t': '{:+.2f}', 'Beta': '{:.2f}', 'Turnover %/mnd': '{:.0f}', 'Gem. # pos.': '{:.1f}',
          'Δ %/mnd': '{:+.2f}', 'Δ t': '{:+.2f}', 'Δ H1': '{:+.2f}', 'Δ H2': '{:+.2f}'}

    # ---------------- Q1 filters
    P = {}
    P['S0 Top25 ongefilterd'] = backtest(df, dates, top_by('Total score'))
    P['S1 Dashboard (4 filters)'] = backtest(df, dates, top_by('Total score', filt=combo(ALL)))
    for k in ALL:
        P[f'S1 zonder {k}-filter'] = backtest(df, dates, top_by('Total score', filt=combo([x for x in ALL if x != k])))
    for k in ALL:
        P[f'S0 + alleen {k}-filter'] = backtest(df, dates, top_by('Total score', filt=combo([k])))
    mk = P['S0 Top25 ongefilterd']['mkt']
    univ = pd.DataFrame({'net': mk, 'mkt': mk, 'turn': 0.0, 'n': np.nan})

    rows = [dict(Strategie='Universum (gelijk gew.)', **stats(univ))]
    rows.append(dict(Strategie='S0 Top25 ongefilterd', **stats(P['S0 Top25 ongefilterd'])))
    rows.append(dict(Strategie='S1 Dashboard (4 filters)', **stats(P['S1 Dashboard (4 filters)'], P['S0 Top25 ongefilterd'])))
    A('\n## Q1a. Dashboard-filters vs ongefilterd (Δ t.o.v. S0)\n')
    A(an.md_table(pd.DataFrame(rows), fm, index=False))

    rows = [dict(Strategie=k, **stats(P[k], P['S1 Dashboard (4 filters)'])) for k in P if k.startswith('S1 zonder')]
    A('\n## Q1b. Ablatie: dashboard ZONDER één filter (Δ t.o.v. S1; positief = filter weglaten is beter)\n')
    A(an.md_table(pd.DataFrame(rows), fm, index=False))
    rows = [dict(Strategie=k, **stats(P[k], P['S0 Top25 ongefilterd'])) for k in P if k.startswith('S0 + alleen')]
    A('\n## Q1c. Elk filter afzonderlijk op S0 (Δ t.o.v. S0; positief = filter helpt)\n')
    A(an.md_table(pd.DataFrame(rows), fm, index=False))

    # filter-diagnostiek op aandeelniveau
    rows = []
    top50 = df['Rank all'] <= 50
    for k, f in FILTERS.items():
        m = pd.Series(f(df).values, index=df.index)
        for lab, sub in (('Universum', pd.Series(True, index=df.index)), ('Top 50 screener', top50)):
            d = df[sub]
            mm = m[sub]
            a = d[mm].groupby('Date')['Excess'].mean()
            b = d[~mm].groupby('Date')['Excess'].mean()
            diff = (a - b).dropna()
            abn = d[mm].groupby('Date')['Excess BN'].mean() - d[~mm].groupby('Date')['Excess BN'].mean()
            rows.append({'Filter': k, 'Groep': lab, '% voldoet': mm.mean() * 100,
                         'Excess wel %': a.mean() * 100, 'Excess niet %': b.mean() * 100,
                         'Verschil %': diff.mean() * 100, 't': an.tstat(diff),
                         'Verschil BN %': abn.mean() * 100, 't BN': an.tstat(abn.dropna())})
    A('\n## Q1d. Filters op aandeelniveau: gem. excess/mnd van aandelen die wel/niet aan het filter voldoen\n')
    A(an.md_table(pd.DataFrame(rows), {'% voldoet': '{:.0f}', 'Excess wel %': '{:+.2f}', 'Excess niet %': '{:+.2f}',
                                       'Verschil %': '{:+.2f}', 't': '{:+.2f}', 'Verschil BN %': '{:+.2f}', 't BN': '{:+.2f}'}, index=False))

    # ---------------- Q2 signaalverval
    E = df.pivot_table(index='Date', columns='yf_ticker', values='Excess', aggfunc='first')
    rows = []
    decay = {}
    for col, lab in (('Neg Total', 'Total score'), ('BN score', 'Rank BN'), ('Mom 12-1', 'Mom 12-1'), ('Delta', 'Delta (rangverbetering)')):
        S = df.pivot_table(index='Date', columns='yf_ticker', values=col, aggfunc='first')
        r = {'Score': lab}
        decay[lab] = []
        for j in range(6):
            Ej = E.shift(-j)
            ics = []
            for d in S.index:
                s, e = S.loc[d], Ej.loc[d]
                mm = s.notna() & e.notna()
                if mm.sum() > 30:
                    ics.append(spearmanr(s[mm], e[mm])[0])
            r[f'IC mnd {j+1}'] = np.mean(ics)
            r[f't {j+1}'] = an.tstat(ics)
            decay[lab].append(np.mean(ics))
        rows.append(r)
    A('\n## Q2. Signaalverval: IC van score op t met excess rendement in maand t+1 ... t+6\n')
    dd = pd.DataFrame(rows)
    A(an.md_table(dd, {c: ('{:+.3f}' if c.startswith('IC') else '{:+.2f}') for c in dd.columns if c != 'Score'}, index=False))

    # ---------------- Q3 portefeuilleregels
    base = P['S1 Dashboard (4 filters)']
    Q = {
        'a) Buffer (houd tot rank 50)': backtest(df, dates, buffer_sel(filt=combo(ALL))),
        'b) Sectorlimiet max 5': backtest(df, dates, sector_cap(filt=combo(ALL))),
        'c) Houdperiode 3 mnd (3 tranches)': backtest(df, dates, top_by('Total score', filt=combo(ALL)), h=3),
        'd) Sorteren op Rank BN': backtest(df, dates, top_by('BN score', asc=False, filt=combo(ALL))),
        'e) Sorteren op Rank 12-1': backtest(df, dates, top_by('Mom 12-1', asc=False, filt=combo(ALL))),
    }
    rows = [dict(Strategie='S1 Dashboard (basis)', **stats(base))]
    rows += [dict(Strategie=k, **stats(p, base)) for k, p in Q.items()]
    A('\n## Q3. Portefeuilleregels bovenop het dashboard (Δ t.o.v. S1)\n')
    A(an.md_table(pd.DataFrame(rows), fm, index=False))

    # zelfde regels op S0 ter controle (zonder filters)
    b0 = P['S0 Top25 ongefilterd']
    Q0 = {
        'a) Buffer': backtest(df, dates, buffer_sel()),
        'b) Sectorlimiet 5': backtest(df, dates, sector_cap()),
        'c) Houdperiode 3 mnd': backtest(df, dates, top_by('Total score'), h=3),
        'd) Rank BN': backtest(df, dates, top_by('BN score', asc=False)),
    }
    rows = [dict(Strategie=k, **stats(p, b0)) for k, p in Q0.items()]
    A('\n### Controle: dezelfde regels zonder dashboard-filters (Δ t.o.v. S0)\n')
    A(an.md_table(pd.DataFrame(rows), fm, index=False))

    # ---------------- Q4 diagnostiek
    rows = []
    for lab, sub in (('Universum', pd.Series(True, index=df.index)), ('Top 50 screener', top50)):
        d = df[sub]
        for act in ('B', 'N', 'S'):
            x = d[d['Action'] == act].groupby('Date')['Excess'].mean()
            rows.append({'Groep': lab, 'Action': act, '% van groep': (d['Action'] == act).mean() * 100,
                         'Gem. excess %/mnd': x.mean() * 100, 't': an.tstat(x)})
    A('\n## Q4a. Action-signaal (B = pullback naar 20MA, N = neutraal, S = onder 50MA)\n')
    A(an.md_table(pd.DataFrame(rows), {'% van groep': '{:.0f}', 'Gem. excess %/mnd': '{:+.2f}', 't': '{:+.2f}'}, index=False))

    d50 = df[top50 & df['Delta'].notna()].copy()
    d50['Dq'] = d50.groupby('Date')['Delta'].transform(lambda s: pd.qcut(s.rank(method='first'), 3, labels=['Gedaald', 'Stabiel', 'Gestegen']))
    piv = d50.pivot_table(index='Date', columns='Dq', values='Excess', aggfunc='mean')
    spread = (piv['Gestegen'] - piv['Gedaald']).dropna()
    A('\n## Q4b. Delta binnen de Top 50: excess/mnd per tertiel rangverandering t.o.v. vorige maand\n')
    A('- ' + ', '.join(f'{c}: {piv[c].mean()*100:+.2f}%' for c in piv.columns) +
      f'; Gestegen − Gedaald = {spread.mean()*100:+.2f}%/mnd (t = {an.tstat(spread):+.2f})')

    with open(os.path.join(an.ART_DIR, f'improvements_{TAG}_tables.md'), 'w', encoding='utf-8') as f:
        f.write('\n'.join(out))

    # ---------------- figuren
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot((1 + mk).cumprod(), 'k--', label='Universum')
    for k, c in (('S0 Top25 ongefilterd', '#e45756'), ('S1 Dashboard (4 filters)', '#4c78a8')):
        ax.plot((1 + P[k]['net']).cumprod(), label=k, color=c)
    for k, p in Q.items():
        ax.plot((1 + p['net']).cumprod(), label='S1 + ' + k, lw=0.9, alpha=0.8)
    ax.set_yscale('log'); ax.legend(fontsize=7); ax.set_title('Netto groei van 1 euro (log)')
    fig.tight_layout(); fig.savefig(os.path.join(an.ART_DIR, f'improvements_{TAG}_equity.png'), dpi=130); plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 4))
    for lab, v in decay.items():
        ax.plot(range(1, 7), v, marker='o', label=lab)
    ax.axhline(0, color='k', lw=0.8); ax.set_xlabel('Maand na signaal'); ax.set_ylabel('Gem. IC (excess)')
    ax.set_title('Signaalverval'); ax.legend()
    fig.tight_layout(); fig.savefig(os.path.join(an.ART_DIR, f'improvements_{TAG}_decay.png'), dpi=130); plt.close(fig)
    print('klaar')


if __name__ == '__main__':
    main()
