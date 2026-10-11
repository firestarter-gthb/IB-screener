"""
Analyse van de samenstelling van de Total score.

Huidige formule (effectieve gewichten, som = 100%):
  1M 10,5% | 3M 28% | 1J 31,5% | 200MA 20% | Sector 10%
  = (((1M*0.15)+(3M*0.40)+(1J*0.45))*0.70) + (200MA*0.20) + (Sector*0.10)

DEEL A - beschrijvend (in-sample, alle data):
  A1  IC per component (+ beta-neutraal, per helft)
  A2  Onderlinge correlatie van de componenten (overlap)
  A3  Drop-one / only-one t.o.v. de huidige gewichten
  A4  Gewichtenlandschap: alle 1001 combinaties (stappen 10%) van de 5 componenten;
      waar staat de huidige formule, en hoe stabiel is 'de beste' tussen helft 1 en helft 2?

DEEL B - walk-forward (out-of-sample): kunnen gewichten die ALLEEN op het verleden zijn gekozen
  de huidige vaste formule verslaan? Methoden:
    - Huidig (vast), Gelijk gewogen (5 componenten)
    - Grid-optimaal 5 componenten (hoogste gem. IC in het verleden)
    - Grid-optimaal 8 componenten (+ 12-1 momentum, Sharpe, Efficiency; stappen 20%)
    - IC-gewogen 8 (gewicht ~ historische IC, negatief -> 0)
    - Ridge 8 (regressie op rank-features)
  Eerste 36 maanden alleen training. Beslisregel: beter als gepaarde t > 2 voor IC EN Top-25 rendement.
"""
import os
import sys
import itertools
import warnings
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from scipy.stats import rankdata, spearmanr
from sklearn.linear_model import Ridge

import backtester_analyzer_v2 as an

warnings.filterwarnings('ignore')
PATH = sys.argv[1] if len(sys.argv) > 1 else 'backtest_dataset_10y_fix.csv'
TAG = sys.argv[2] if len(sys.argv) > 2 else '10y'
ONE_WAY = 0.001
N = 25
MIN_TRAIN = 36

BASE = ['1M', '3M', '1J', '200MA', 'Sector']
EXTRA = ['12-1', 'Sharpe', 'Eff']
ALLC = BASE + EXTRA
CURRENT = {'1M': 0.105, '3M': 0.28, '1J': 0.315, '200MA': 0.20, 'Sector': 0.10}


def wvec(d):
    return np.array([d.get(c, 0.0) for c in ALLC])


def fmt_w(w):
    return ' / '.join(f'{c} {w[i]*100:.0f}%' for i, c in enumerate(ALLC) if w[i] > 1e-9)


# ----------------------------------------------------------------------------- data
def prep():
    an.DATA = PATH
    df, _ = an.load()
    df = df.drop_duplicates(['Date', 'yf_ticker']).reset_index(drop=True)
    raw = {'1M': df['Last month'], '3M': df['Last 3 months'], '1J': df['Last year'], '200MA': df['200 avg'],
           'Sector': -df['Scaled sector rank'], '12-1': df['Mom 12-1'], 'Sharpe': df['Sharpe Ratio'],
           'Eff': df['Efficiency Score']}
    for k, v in raw.items():
        df['p_' + k] = v.groupby(df['Date']).rank(pct=True)
    return df


def rank_norm(a):
    r = rankdata(a)
    r = r - r.mean()
    n = np.sqrt((r ** 2).sum())
    return r / n if n > 0 else r


def build(df):
    D = []
    for d, g in df.groupby('Date'):
        X = g[['p_' + c for c in ALLC]].values
        X = np.where(np.isnan(X), 0.5, X)
        D.append(dict(date=d, X=X, ry=rank_norm(g['Excess'].values), rb=rank_norm(g['Excess BN'].values),
                      r=g['Forward Return 1M'].values, beta=g['Beta'].values, tick=g['yf_ticker'].values,
                      mkt=g['Forward Return 1M'].mean(), ypct=g['Excess'].rank(pct=True).values - 0.5))
    return D


def evaluate(D, wfun, idxs=None):
    idxs = range(len(D)) if idxs is None else idxs
    rows, prev = [], None
    for t in idxs:
        x = D[t]
        w = wfun(t)
        s = x['X'] @ w
        rs = rank_norm(s)
        o = np.argsort(-s, kind='stable')
        idx = o[:N]
        cur = set(x['tick'][idx])
        to = 0.5 if prev is None else 1 - len(cur & prev) / N
        prev = cur
        q = len(s) // 5
        rows.append({'date': x['date'], 'ic': rs @ x['ry'], 'icb': rs @ x['rb'],
                     'net': x['r'][idx].mean() - to * 2 * ONE_WAY, 'turn': to, 'beta': x['beta'][idx].mean(),
                     'ls': x['r'][o[:q]].mean() - x['r'][o[-q:]].mean(), 'mkt': x['mkt']})
    return pd.DataFrame(rows).set_index('date')


def summ(p):
    a, t, b = an.capm(p['net'].values, p['mkt'].values)
    return {'IC': p['ic'].mean(), 'IC t': an.tstat(p['ic']), 'IC BN': p['icb'].mean(), 'IC BN t': an.tstat(p['icb']),
            'Q1-Q5 %/mnd': p['ls'].mean() * 100, 'Top25 ann. %': ((1 + p['net']).prod() ** (12 / len(p)) - 1) * 100,
            'Top25 Sharpe': p['net'].mean() / p['net'].std() * np.sqrt(12),
            'Alpha %/mnd': a * 100, 'Alpha t': t, 'Beta': b, 'Turnover %': p['turn'].iloc[1:].mean() * 100}


FM = {'IC': '{:+.3f}', 'IC t': '{:+.2f}', 'IC BN': '{:+.3f}', 'IC BN t': '{:+.2f}', 'Q1-Q5 %/mnd': '{:+.2f}',
      'Top25 ann. %': '{:.1f}', 'Top25 Sharpe': '{:.2f}', 'Alpha %/mnd': '{:+.2f}', 'Alpha t': '{:+.2f}',
      'Beta': '{:.2f}', 'Turnover %': '{:.0f}', 'ΔIC': '{:+.3f}', 'ΔIC t': '{:+.2f}',
      'ΔTop25 %/mnd': '{:+.2f}', 'ΔTop25 t': '{:+.2f}'}


def simplex(k, steps):
    for c in itertools.combinations(range(steps + k - 1), k - 1):
        parts, prev = [], -1
        for ci in c:
            parts.append(ci - prev - 1)
            prev = ci
        parts.append(steps + k - 1 - prev - 1)
        yield np.array(parts, dtype=float) / steps


# ----------------------------------------------------------------------------- main
def main():
    df = prep()
    D = build(df)
    dates = [x['date'] for x in D]
    T = len(D)
    half = T // 2
    out = []
    A = lambda s: out.append(s + '\n')
    A(f'# Analyse Total score ({TAG})\n')
    A(f'- Dataset {PATH}: {len(df)} rijen, {T} maanden ({pd.Timestamp(dates[0]).date()} t/m {pd.Timestamp(dates[-1]).date()})')

    wc = wvec(CURRENT)
    cur = evaluate(D, lambda t: wc)
    chk = np.mean([spearmanr(D[t]['X'] @ wc, -df[df['Date'] == dates[t]]['Total score'].values)[0] for t in range(0, T, 10)])
    A(f'- Controle: reconstructie huidige formule vs Total score in dataset, gem. Spearman = {chk:.3f}')

    # ---------------- A1 componenten
    comp = {}
    rows = []
    for i, c in enumerate(ALLC):
        e = np.zeros(len(ALLC)); e[i] = 1
        p = evaluate(D, lambda t, e=e: e)
        comp[c] = p
        rows.append({'Component': c + (' (in Total score)' if c in BASE else ' (kandidaat)'),
                     'Eff. gewicht nu': CURRENT.get(c, 0) * 100,
                     'IC': p['ic'].mean(), 'IC t': an.tstat(p['ic']), 'IC BN': p['icb'].mean(), 'IC BN t': an.tstat(p['icb']),
                     'IC H1': p['ic'].iloc[:half].mean(), 'IC H2': p['ic'].iloc[half:].mean(),
                     '% mnd IC>0': (p['ic'] > 0).mean() * 100})
    A('\n## A1. Voorspellende waarde per component (IC = Spearman met excess rendement volgende maand)\n')
    A(an.md_table(pd.DataFrame(rows), {'Eff. gewicht nu': '{:.1f}', 'IC': '{:+.3f}', 'IC t': '{:+.2f}', 'IC BN': '{:+.3f}',
                                       'IC BN t': '{:+.2f}', 'IC H1': '{:+.3f}', 'IC H2': '{:+.3f}', '% mnd IC>0': '{:.0f}'}, index=False))
    r_tot = {'Component': 'TOTAL SCORE (huidig)', 'Eff. gewicht nu': 100.0, 'IC': cur['ic'].mean(), 'IC t': an.tstat(cur['ic']),
             'IC BN': cur['icb'].mean(), 'IC BN t': an.tstat(cur['icb']), 'IC H1': cur['ic'].iloc[:half].mean(),
             'IC H2': cur['ic'].iloc[half:].mean(), '% mnd IC>0': (cur['ic'] > 0).mean() * 100}
    A(an.md_table(pd.DataFrame([r_tot]), {'Eff. gewicht nu': '{:.0f}', 'IC': '{:+.3f}', 'IC t': '{:+.2f}', 'IC BN': '{:+.3f}',
                                          'IC BN t': '{:+.2f}', 'IC H1': '{:+.3f}', 'IC H2': '{:+.3f}', '% mnd IC>0': '{:.0f}'}, index=False))

    # ---------------- A2 correlaties
    C = np.zeros((len(ALLC), len(ALLC)))
    for x in D:
        R = np.apply_along_axis(rankdata, 0, x['X'])
        C += np.corrcoef(R.T)
    C /= T
    cdf = pd.DataFrame(C, index=ALLC, columns=ALLC)
    cdf.index.name = 'Spearman'
    A('\n## A2. Gemiddelde onderlinge correlatie (per maand, Spearman)\n')
    A(an.md_table(cdf, {c: '{:.2f}' for c in ALLC}))

    # ---------------- A3 drop-one / only-one
    rows = [dict(Variant='Huidig', **summ(cur))]
    for c in BASE:
        d = {k: v for k, v in CURRENT.items() if k != c}
        s = sum(d.values())
        w = wvec({k: v / s for k, v in d.items()})
        p = evaluate(D, lambda t, w=w: w)
        dd = p['net'] - cur['net']
        r = dict(Variant=f'Zonder {c}', **summ(p))
        r.update({'ΔIC': (p['ic'] - cur['ic']).mean(), 'ΔIC t': an.tstat(p['ic'] - cur['ic']),
                  'ΔTop25 %/mnd': dd.mean() * 100, 'ΔTop25 t': an.tstat(dd)})
        rows.append(r)
    A('\n## A3. Drop-one: huidige formule zonder één component (overige gewichten herschaald)\n')
    A(an.md_table(pd.DataFrame(rows), FM, index=False))
    rows = [dict(Variant=f'Alleen {c}', **summ(comp[c])) for c in ALLC if c != 'Sector']
    A('\n### Only-one: Top 25 op basis van één component\n')
    A(an.md_table(pd.DataFrame(rows), FM, index=False))

    # ---------------- A4 gewichtenlandschap (5 componenten, stap 10%)
    print('Grid 5...')
    G5 = [np.r_[w, np.zeros(len(EXTRA))] for w in simplex(len(BASE), 10)]
    g5 = [evaluate(D, lambda t, w=w: w) for w in G5]
    IC5 = np.array([p['ic'].values for p in g5])
    NET5 = np.array([p['net'].values for p in g5])
    sh = lambda a: a.mean(axis=-1) / a.std(axis=-1) * np.sqrt(12)
    ic_all, sh_all = IC5.mean(1), sh(NET5)
    ic_h1, ic_h2 = IC5[:, :half].mean(1), IC5[:, half:].mean(1)
    sh_h1, sh_h2 = sh(NET5[:, :half]), sh(NET5[:, half:])
    pct = lambda arr, v: (arr < v).mean() * 100
    cur_ic, cur_sh = cur['ic'].mean(), cur['net'].mean() / cur['net'].std() * np.sqrt(12)
    A('\n## A4. Gewichtenlandschap: 1001 combinaties van de 5 componenten (stappen van 10%)\n')
    A(f'- Gem. IC over alle combinaties: p5 {np.percentile(ic_all,5):+.3f} | mediaan {np.median(ic_all):+.3f} | p95 {np.percentile(ic_all,95):+.3f} | max {ic_all.max():+.3f}')
    A(f'- Huidige formule: IC {cur_ic:+.3f} = percentiel {pct(ic_all, cur_ic):.0f}')
    A(f'- Top-25 Sharpe over alle combinaties: p5 {np.percentile(sh_all,5):.2f} | mediaan {np.median(sh_all):.2f} | p95 {np.percentile(sh_all,95):.2f} | max {sh_all.max():.2f}')
    A(f'- Huidige formule: Sharpe {cur_sh:.2f} = percentiel {pct(sh_all, cur_sh):.0f}')
    A(f'- **Stabiliteit**: Spearman(IC helft 1, IC helft 2) over combinaties = {spearmanr(ic_h1, ic_h2)[0]:+.2f}; '
      f'Spearman(Sharpe H1, Sharpe H2) = {spearmanr(sh_h1, sh_h2)[0]:+.2f}')
    top10_h1 = np.argsort(-ic_h1)[:100]
    A(f'- De beste 10% combinaties in helft 1 (op IC) halen in helft 2 een gem. IC van {ic_h2[top10_h1].mean():+.3f} '
      f'(alle combinaties: {ic_h2.mean():+.3f}; huidig: {cur["ic"].iloc[half:].mean():+.3f})')
    best_ic = np.argsort(-ic_all)[:10]
    rows = [{'Gewichten': fmt_w(G5[i]), 'IC': ic_all[i], 'IC H1': ic_h1[i], 'IC H2': ic_h2[i], 'Top25 Sharpe': sh_all[i]} for i in best_ic]
    A('\n### Top 10 combinaties op IC (IN-SAMPLE - niet direct overnemen!)\n')
    A(an.md_table(pd.DataFrame(rows), {'IC': '{:+.3f}', 'IC H1': '{:+.3f}', 'IC H2': '{:+.3f}', 'Top25 Sharpe': '{:.2f}'}, index=False))
    # marginale gemiddelde IC per gewicht van elke component
    W5 = np.array(G5)[:, :len(BASE)]
    rows = []
    for i, c in enumerate(BASE):
        r = {'Component': c}
        for lvl in (0.0, 0.2, 0.4, 0.6):
            m = np.isclose(W5[:, i], lvl)
            r[f'IC bij {int(lvl*100)}%'] = ic_all[m].mean()
        rows.append(r)
    A('\n### Gemiddelde IC van alle combinaties met een bepaald gewicht voor één component\n')
    A(an.md_table(pd.DataFrame(rows), {k: '{:+.3f}' for k in ['IC bij 0%', 'IC bij 20%', 'IC bij 40%', 'IC bij 60%']}, index=False))

    # ---------------- B walk-forward
    print('Grid 8...')
    G8 = list(simplex(len(ALLC), 5))
    IC8 = np.array([evaluate(D, lambda t, w=w: w)['ic'].values for w in G8])
    COMPIC = np.array([comp[c]['ic'].values for c in ALLC])
    oos = range(MIN_TRAIN, T)

    chosen5, chosen8, chosen_icw, chosen_r = {}, {}, {}, {}
    for t in oos:
        chosen5[t] = G5[int(np.argmax(IC5[:, :t].mean(1)))]
        chosen8[t] = G8[int(np.argmax(IC8[:, :t].mean(1)))]
        m = np.clip(COMPIC[:, :t].mean(1), 0, None)
        chosen_icw[t] = m / m.sum() if m.sum() > 0 else np.ones(len(ALLC)) / len(ALLC)
        Xtr = np.vstack([D[j]['X'] for j in range(t)]) - 0.5
        ytr = np.concatenate([D[j]['ypct'] for j in range(t)])
        chosen_r[t] = Ridge(alpha=50.0, fit_intercept=False).fit(Xtr, ytr).coef_

    eq5 = wvec({c: 0.2 for c in BASE})
    methods = {
        'Huidig (vast)': lambda t: wc,
        'Gelijk gewogen 5': lambda t: eq5,
        'Grid-optimaal 5 (WF)': lambda t: chosen5[t],
        'Grid-optimaal 8 (WF)': lambda t: chosen8[t],
        'IC-gewogen 8 (WF)': lambda t: chosen_icw[t],
        'Ridge 8 (WF)': lambda t: chosen_r[t],
    }
    P = {k: evaluate(D, f, oos) for k, f in methods.items()}
    base = P['Huidig (vast)']
    rows = []
    for k, p in P.items():
        r = dict(Methode=k, **summ(p))
        if k != 'Huidig (vast)':
            di, dn = p['ic'] - base['ic'], p['net'] - base['net']
            r.update({'ΔIC': di.mean(), 'ΔIC t': an.tstat(di), 'ΔTop25 %/mnd': dn.mean() * 100, 'ΔTop25 t': an.tstat(dn)})
        rows.append(r)
    A(f'\n## B. Walk-forward: gewichten alleen gekozen op het verleden (OOS {len(oos)} maanden: '
      f'{pd.Timestamp(dates[MIN_TRAIN]).date()} t/m {pd.Timestamp(dates[-1]).date()})\n')
    A(an.md_table(pd.DataFrame(rows), FM, index=False))

    # stabiliteit gekozen gewichten
    W5c = pd.DataFrame({t: chosen5[t][:len(BASE)] for t in oos}, index=BASE).T
    W5c.index = [dates[t] for t in oos]
    n_switch = int((W5c.diff().abs().sum(axis=1) > 1e-9).sum())
    A(f'\n- Grid-optimaal 5: de gekozen gewichten wisselden {n_switch} keer in {len(oos)} maanden. Laatst gekozen: {fmt_w(chosen5[T-1])}')
    A(f'- Grid-optimaal 8, laatst gekozen: {fmt_w(chosen8[T-1])}')
    A(f'- IC-gewogen 8, laatst: {fmt_w(np.round(chosen_icw[T-1], 3))}')
    A(f'- Ridge 8, laatste coëfficiënten (relatief): ' +
      ' / '.join(f'{c} {v/np.abs(chosen_r[T-1]).sum()*100:+.0f}%' for c, v in zip(ALLC, chosen_r[T-1])))

    with open(os.path.join(an.ART_DIR, f'totalscore_{TAG}_tables.md'), 'w', encoding='utf-8') as f:
        f.write('\n'.join(out))

    # ---------------- figuren
    fig, axs = plt.subplots(1, 3, figsize=(15, 4.2))
    axs[0].hist(ic_all, bins=40, color='#4c78a8'); axs[0].axvline(cur_ic, color='#e45756', lw=2, label='Huidig')
    axs[0].set_title('Gem. IC van 1001 gewichtcombinaties'); axs[0].legend()
    axs[1].hist(sh_all, bins=40, color='#72b7b2'); axs[1].axvline(cur_sh, color='#e45756', lw=2, label='Huidig')
    axs[1].set_title('Top-25 Sharpe van 1001 combinaties'); axs[1].legend()
    axs[2].scatter(ic_h1, ic_h2, s=6, alpha=0.5)
    axs[2].scatter([cur['ic'].iloc[:half].mean()], [cur['ic'].iloc[half:].mean()], color='#e45756', s=60, label='Huidig')
    axs[2].set_xlabel('IC helft 1'); axs[2].set_ylabel('IC helft 2'); axs[2].set_title('Stabiliteit: IC H1 vs H2'); axs[2].legend()
    fig.tight_layout(); fig.savefig(os.path.join(an.ART_DIR, f'totalscore_{TAG}_landscape.png'), dpi=130); plt.close(fig)

    fig, axs = plt.subplots(1, 2, figsize=(14, 4.5))
    axs[0].stackplot(W5c.index, W5c.T.values, labels=BASE)
    axs[0].set_title('Walk-forward gekozen gewichten (grid 5)'); axs[0].legend(loc='upper left', fontsize=8); axs[0].set_ylim(0, 1)
    for k, p in P.items():
        axs[1].plot((1 + p['net']).cumprod(), label=k, lw=2 if k == 'Huidig (vast)' else 1)
    axs[1].plot((1 + base['mkt']).cumprod(), 'k--', label='Universum')
    axs[1].set_yscale('log'); axs[1].set_title('OOS Top-25 netto groei'); axs[1].legend(fontsize=7)
    fig.tight_layout(); fig.savefig(os.path.join(an.ART_DIR, f'totalscore_{TAG}_walkforward.png'), dpi=130); plt.close(fig)
    print('klaar')


if __name__ == '__main__':
    main()
