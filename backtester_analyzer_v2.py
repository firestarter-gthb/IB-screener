"""
Backtest-analyse v2 voor de IB-screener.

Verbeteringen t.o.v. backtester_analyzer.py:
  * Target = EXCESS return t.o.v. het gelijk-gewogen universum per datum (marktbias eruit),
    plus een BETA-NEUTRALE variant (per datum residu na regressie op Beta).
  * Cross-sectionele evaluatie per datum (deciel/kwintiel per snapshot, niet gepoold).
  * Information Coefficient (Spearman) per factor, incl. t-stat en hit-rate.
  * Top-N portefeuilles incl. turnover, kosten, Sharpe, max drawdown, CAPM-alpha en
    Monte-Carlo vergelijking met willekeurige portefeuilles.
  * Sub-periode- en regime-analyse (kalenderjaar, bull/bear maand).
  * Walk-forward (expanding window) ML met baselines; geen in-sample fit.
"""
import os
import warnings
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from scipy.stats import spearmanr
from sklearn.linear_model import Ridge
from sklearn.ensemble import RandomForestRegressor, HistGradientBoostingRegressor

warnings.filterwarnings('ignore')

DATA = 'backtest_dataset.csv'
ART_DIR = r'C:\Users\ROB5293\.gemini\antigravity-ide\brain\30eea252-fae6-416d-8868-437e67716977'
TABLES_MD = os.path.join(ART_DIR, 'backtest_v2_tables.md')
RNG = np.random.default_rng(42)
COST_ROUNDTRIP = 0.002   # 0,20% per vervangen positie (aankoop + verkoop)
MIN_TRAIN = 18           # minimaal aantal snapshots voor de eerste walk-forward fit

plt.style.use('seaborn-v0_8-whitegrid')


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
                cells.append(f.format(v) if f else f'{v:.3f}')
            else:
                cells.append(str(v))
        lines.append('| ' + ' | '.join(cells) + ' |')
    return '\n'.join(lines) + '\n'


def tstat(s):
    s = pd.Series(s).dropna()
    if len(s) < 3 or s.std() == 0:
        return np.nan
    return s.mean() / (s.std() / np.sqrt(len(s)))


def ic_per_date(df, col, target):
    return df.groupby('Date').apply(lambda g: spearmanr(g[col], g[target])[0])


def ic_summary(s):
    s = s.dropna()
    sd = s.std()
    return {'Gem. IC': s.mean(), 'IC-IR': s.mean() / sd if sd else np.nan,
            't-stat': tstat(s), '% maanden > 0': (s > 0).mean() * 100}


def max_drawdown(r):
    cum = (1 + pd.Series(r)).cumprod()
    return (cum / cum.cummax() - 1).min()


def capm(y, x):
    X = np.c_[np.ones(len(x)), x]
    b = np.linalg.lstsq(X, y, rcond=None)[0]
    res = y - X @ b
    s2 = res @ res / (len(y) - 2)
    cov = s2 * np.linalg.inv(X.T @ X)
    return b[0], b[0] / np.sqrt(cov[0, 0]), b[1]


def bootstrap_ci(x, n=5000):
    x = np.asarray(x)
    means = RNG.choice(x, size=(n, len(x)), replace=True).mean(axis=1)
    return np.percentile(means, [2.5, 97.5])


# ----------------------------------------------------------------------------- data
def load():
    df = pd.read_csv(DATA, sep='|', parse_dates=['Snapshot Date']).rename(columns={'Snapshot Date': 'Date'})
    n0 = len(df)
    df = df.dropna(subset=['Forward Return 1M']).copy()
    df['Mom 3-1'] = (1 + df['Last 3 months']) / (1 + df['Last month']) - 1
    df['Mom 12-1'] = (1 + df['Last year']) / (1 + df['Last month']) - 1
    df['Sector mom (neg rank)'] = -df['Sector momentum rank']
    df['Screener score (-Total)'] = -df['Total score']
    df['Screener incl beta (-Total)'] = -df['Total score incl beta']

    g = df.groupby('Date')
    df['Mkt'] = g['Forward Return 1M'].transform('mean')
    df['Excess'] = df['Forward Return 1M'] - df['Mkt']

    def resid(x):
        X = np.c_[np.ones(len(x)), x['Beta'].values]
        y = x['Excess'].values
        coef = np.linalg.lstsq(X, y, rcond=None)[0]
        return pd.Series(y - X @ coef, index=x.index)

    df['Excess BN'] = df.groupby('Date', group_keys=False).apply(resid)

    r = g['Total score'].rank(method='first')
    n = g['Total score'].transform('size')
    df['Decile'] = np.ceil(r / n * 10).astype(int)
    df['Quintile'] = np.ceil(r / n * 5).astype(int)
    return df, n0


# ----------------------------------------------------------------------------- analyses
def decile_analysis(df):
    piv = df.pivot_table(index='Date', columns='Decile', values='Excess', aggfunc='mean')
    beta = df.groupby('Decile')['Beta'].mean()
    med = df.groupby('Decile')['Excess'].median()
    out = pd.DataFrame({
        'Gem. excess/mnd %': piv.mean() * 100,
        'Mediaan stock excess %': med * 100,
        'SE %': piv.std() / np.sqrt(len(piv)) * 100,
        't-stat': piv.apply(tstat),
        '% mnd > markt': (piv > 0).mean() * 100,
        'Gem. Beta': beta,
    })
    out.index.name = 'Deciel (1=beste)'
    return out, piv


def long_short(df):
    q = df.pivot_table(index='Date', columns='Quintile', values='Excess', aggfunc='mean')
    ls = q[1] - q[5]
    ci = bootstrap_ci(ls)
    return q, ls, ci


def topn_portfolio(df, n, col='Total score', best_is_low=True):
    rows, prev = [], set()
    for d, g in df.groupby('Date'):
        top = g.nsmallest(n, col) if best_is_low else g.nlargest(n, col)
        names = set(top['yf_ticker'])
        turnover = 1.0 if not prev else 1 - len(names & prev) / n
        prev = names
        rows.append({'Date': d, 'gross': top['Forward Return 1M'].mean(), 'mkt': g['Forward Return 1M'].mean(),
                     'beta': top['Beta'].mean(), 'turnover': turnover,
                     'ex_bn': top['Excess BN'].mean()})
    p = pd.DataFrame(rows).set_index('Date')
    p['net'] = p['gross'] - p['turnover'] * COST_ROUNDTRIP
    return p


def portfolio_stats(p):
    m = len(p)
    ann = lambda r: (1 + r).prod() ** (12 / m) - 1
    alpha, a_t, b = capm(p['gross'].values, p['mkt'].values)
    return {
        'Ann. rend. bruto %': ann(p['gross']) * 100,
        'Ann. rend. netto %': ann(p['net']) * 100,
        'Ann. rend. universum %': ann(p['mkt']) * 100,
        'Sharpe netto': p['net'].mean() / p['net'].std() * np.sqrt(12),
        'Sharpe universum': p['mkt'].mean() / p['mkt'].std() * np.sqrt(12),
        'Max DD netto %': max_drawdown(p['net']) * 100,
        'Max DD universum %': max_drawdown(p['mkt']) * 100,
        'Gem. excess bruto %/mnd': (p['gross'] - p['mkt']).mean() * 100,
        't-stat excess': tstat(p['gross'] - p['mkt']),
        'CAPM alpha %/mnd': alpha * 100,
        'alpha t-stat': a_t,
        'Beta portf. (vs universum)': b,
        'Gem. Beta aandelen': p['beta'].mean(),
        'Beta-neutraal excess %/mnd': p['ex_bn'].mean() * 100,
        'Turnover/mnd %': p['turnover'].iloc[1:].mean() * 100,
    }


def random_baseline(df, n, actual_mean, sims=3000):
    """Verdeling van gemiddeld maandrendement van willekeurige n-aandelen portefeuilles."""
    per_date = [g['Forward Return 1M'].values for _, g in df.groupby('Date')]
    acc = np.zeros(sims)
    for arr in per_date:
        idx = np.argsort(RNG.random((sims, len(arr))), axis=1)[:, :n]
        acc += arr[idx].mean(axis=1)
    acc /= len(per_date)
    return (acc >= actual_mean).mean(), np.percentile(acc, [5, 50, 95])


def sector_composition(df, n=25):
    top = df.groupby('Date', group_keys=False).apply(lambda g: g.nsmallest(n, 'Total score'))
    a = top['GICS sector'].value_counts(normalize=True)
    b = df['GICS sector'].value_counts(normalize=True)
    out = pd.DataFrame({'Top25 aandeel %': a * 100, 'Universum %': b * 100}).fillna(0)
    out['Over/onderweging (x)'] = out['Top25 aandeel %'] / out['Universum %']
    return out.sort_values('Over/onderweging (x)', ascending=False)


# ----------------------------------------------------------------------------- walk-forward ML
ML_FEATS = ['Last month', 'Last 3 months', 'Last year', '200 avg', 'Z-score 20MA',
            'Beta', 'Sharpe Ratio', 'Efficiency Score', 'Sector mom (neg rank)']


def walk_forward(df):
    d = df.copy()
    for f in ML_FEATS:
        d[f + '_cs'] = d.groupby('Date')[f].rank(pct=True)           # cross-sectioneel, stationair
    d['y'] = d.groupby('Date')['Excess'].rank(pct=True) - 0.5          # robuust tegen uitschieters
    cs = [f + '_cs' for f in ML_FEATS]

    dates = sorted(d['Date'].unique())
    models = {
        'Ridge': lambda: Ridge(alpha=50.0),
        'RandomForest': lambda: RandomForestRegressor(n_estimators=200, max_depth=4, min_samples_leaf=200,
                                                       n_jobs=1, random_state=0),
        'GradBoost': lambda: HistGradientBoostingRegressor(max_depth=3, learning_rate=0.05, max_iter=150,
                                                           min_samples_leaf=200, random_state=0),
    }
    recs, coefs, pimp = [], [], []
    for i in range(MIN_TRAIN, len(dates)):
        tr = d[d['Date'].isin(dates[:i])]
        te = d[d['Date'] == dates[i]].copy()
        preds = {
            'Screener score': te['Screener score (-Total)'].values,
            'Alleen Beta': te['Beta'].values,
            'Willekeurig': RNG.random(len(te)),
        }
        fitted = {}
        for name, mk in models.items():
            m = mk().fit(tr[cs], tr['y'])
            preds[name] = m.predict(te[cs])
            fitted[name] = m
            if name == 'Ridge':
                coefs.append(pd.Series(m.coef_, index=ML_FEATS, name=dates[i]))
        for name, p in preds.items():
            te['pred'] = p
            q = np.ceil(te['pred'].rank(method='first', ascending=False) / len(te) * 5)
            top = te[q == 1]
            bot = te[q == 5]
            recs.append({'Date': dates[i], 'Model': name,
                         'IC': spearmanr(p, te['Excess'])[0],
                         'IC BN': spearmanr(p, te['Excess BN'])[0],
                         'Top-kwintiel excess': top['Excess'].mean(),
                         'Top-kwintiel excess BN': top['Excess BN'].mean(),
                         'LS (Q1-Q5)': top['Excess'].mean() - bot['Excess'].mean(),
                         'Beta top': top['Beta'].mean()})
        # permutation importance (IC-daling) op de out-of-sample datum
        for name in ('Ridge', 'RandomForest'):
            base = spearmanr(fitted[name].predict(te[cs]), te['Excess'])[0]
            for f in ML_FEATS:
                drops = []
                for _ in range(3):
                    t2 = te[cs].copy()
                    t2[f + '_cs'] = RNG.permutation(t2[f + '_cs'].values)
                    drops.append(base - spearmanr(fitted[name].predict(t2), te['Excess'])[0])
                pimp.append({'Model': name, 'Feature': f, 'drop': np.mean(drops)})
    return pd.DataFrame(recs), pd.DataFrame(coefs), pd.DataFrame(pimp)


# ----------------------------------------------------------------------------- spy referentie
def spy_forward(dates):
    try:
        import yfinance as yf
        spy = yf.download('SPY', period='6y', progress=False, auto_adjust=True)['Close'].squeeze().dropna()
        if getattr(spy.index, 'tz', None) is not None:
            spy.index = spy.index.tz_localize(None)
        out = {}
        for d in dates:
            pos = spy.index.searchsorted(pd.Timestamp(d))
            if pos + 21 < len(spy):
                out[d] = spy.iloc[pos + 21] / spy.iloc[pos] - 1
        return pd.Series(out)
    except Exception as e:  # netwerk niet beschikbaar -> overslaan
        print('SPY ophalen mislukt:', e)
        return None


# ----------------------------------------------------------------------------- main
def main():
    df, n0 = load()
    dates = sorted(df['Date'].unique())
    T = []   # tabellen-md
    add = lambda s: T.append(s + '\n')

    add('# Backtest v2 – ruwe tabellen\n')
    add(f'- Rijen: {len(df)} (van {n0}), snapshots: {len(dates)} ({pd.Timestamp(dates[0]).date()} t/m {pd.Timestamp(dates[-1]).date()})')
    add(f'- Aandelen per snapshot: {df.groupby("Date").size().min()}–{df.groupby("Date").size().max()}')
    fr = df['Forward Return 1M']
    add(f'- Forward return: gem {fr.mean()*100:.2f}%, mediaan {fr.median()*100:.2f}%, p1 {fr.quantile(.01)*100:.1f}%, '
        f'p99 {fr.quantile(.99)*100:.1f}%, max {fr.max()*100:.0f}%')
    mk = df.groupby('Date')['Mkt'].first()
    add(f'- Universum (gelijk gewogen) maandrendement: gem {mk.mean()*100:.2f}%, % positieve maanden {(mk>0).mean()*100:.0f}%, '
        f'cumulatief {((1+mk).prod()-1)*100:.0f}%')
    spy = spy_forward(dates)
    if spy is not None and len(spy) > 10:
        add(f'- SPY (zelfde maand-vensters): cumulatief {((1+spy).prod()-1)*100:.0f}% vs universum '
            f'{((1+mk.loc[spy.index]).prod()-1)*100:.0f}%')

    # 1. Deciel
    dec, piv = decile_analysis(df)
    add('\n## 1. Deciel-analyse per datum (excess vs universum)\n')
    add(md_table(dec, {'Gem. excess/mnd %': '{:.2f}', 'Mediaan stock excess %': '{:.2f}', 'SE %': '{:.2f}',
                       't-stat': '{:.2f}', '% mnd > markt': '{:.0f}', 'Gem. Beta': '{:.2f}'}))
    rho = spearmanr(dec.index, dec['Gem. excess/mnd %'])[0]
    add(f'Spearman(decielnr, excess) = {rho:.2f} (-1 = perfect monotoon: lage score → hoger rendement)')

    q, ls, ci = long_short(df)
    add('\n## 2. Long-short Q1 (beste) – Q5 (slechtste)\n')
    add(f'- Gem. spread {ls.mean()*100:.2f}%/mnd, t = {tstat(ls):.2f}, bootstrap 95%-CI [{ci[0]*100:.2f}%, {ci[1]*100:.2f}%], '
        f'% maanden > 0: {(ls>0).mean()*100:.0f}%')
    add('- Gem. excess per kwintiel (%): ' + ', '.join(f'Q{int(k)}={v*100:.2f}' for k, v in q.mean().items()))
    q_bn = df.pivot_table(index='Date', columns='Quintile', values='Excess BN', aggfunc='mean')
    add('- Beta-neutraal excess per kwintiel (%): ' + ', '.join(f'Q{int(k)}={v*100:.2f}' for k, v in q_bn.mean().items()))
    ls_bn = q_bn[1] - q_bn[5]
    add(f'- Beta-neutrale spread Q1-Q5: {ls_bn.mean()*100:.2f}%/mnd, t = {tstat(ls_bn):.2f}')

    # 3. IC
    factors = ['Last month', 'Last 3 months', 'Mom 3-1', 'Last year', 'Mom 12-1', 'YTD Performance', '200 avg',
               'Z-score 20MA', 'Beta', 'Sharpe Ratio', 'Efficiency Score', 'Sector mom (neg rank)',
               'Screener score (-Total)', 'Screener incl beta (-Total)']
    rows = []
    for f in factors:
        a = ic_summary(ic_per_date(df, f, 'Excess'))
        b = ic_summary(ic_per_date(df, f, 'Excess BN'))
        rows.append({'Factor': f, 'IC': a['Gem. IC'], 'IC-IR': a['IC-IR'], 't': a['t-stat'],
                     '% mnd>0': a['% maanden > 0'], 'IC (beta-neutraal)': b['Gem. IC'], 't (BN)': b['t-stat']})
    ic_df = pd.DataFrame(rows).set_index('Factor')
    add('\n## 3. Information Coefficient per factor (Spearman, per datum; positief = hogere waarde → hoger excess rendement)\n')
    add(md_table(ic_df, {'IC': '{:+.3f}', 'IC-IR': '{:+.2f}', 't': '{:+.2f}', '% mnd>0': '{:.0f}',
                         'IC (beta-neutraal)': '{:+.3f}', 't (BN)': '{:+.2f}'}))

    # 4. portefeuilles
    add('\n## 4. Top-N portefeuilles (gelijk gewogen, maandelijks herbalanceren, kosten 0,20%/vervangen positie)\n')
    port = {}
    stats = {}
    for n in (10, 25, 50):
        p = topn_portfolio(df, n)
        port[n] = p
        s = portfolio_stats(p)
        pval, pct = random_baseline(df, n, p['gross'].mean())
        s['p-waarde vs willekeurig'] = pval
        s['Willekeurig p5/p50/p95 %/mnd'] = f'{pct[0]*100:.2f} / {pct[1]*100:.2f} / {pct[2]*100:.2f}'
        stats[f'Top {n}'] = s
    st = pd.DataFrame(stats)
    pb = topn_portfolio(df, 25, col='Beta', best_is_low=False)
    sb = portfolio_stats(pb)
    sb['p-waarde vs willekeurig'] = np.nan
    sb['Willekeurig p5/p50/p95 %/mnd'] = '-'
    st['Top 25 hoogste Beta (baseline)'] = pd.Series(sb)
    add_beta_note = (pb['gross'] - port[25]['gross']).mean() * 100
    st.index.name = 'Metriek'
    add(md_table(st))
    add(f'\nVerschil Top25 screener minus Top25 hoogste-Beta (bruto): {-add_beta_note:+.2f}%/mnd, '
        f't = {tstat(port[25]["gross"] - pb["gross"]):.2f}')

    # 5. sub-perioden
    add('\n## 5. Stabiliteit: kalenderjaar en marktregime\n')
    p25 = port[25]
    ic_s = ic_per_date(df, 'Screener score (-Total)', 'Excess')
    sub = pd.DataFrame({'Top25 excess %': (p25['gross'] - p25['mkt']) * 100,
                        'Q1-Q5 %': ls * 100, 'IC': ic_s, 'Universum %': p25['mkt'] * 100})
    sub['Jaar'] = sub.index.year
    by_year = sub.groupby('Jaar').agg(**{'N mnd': ('IC', 'size'), 'Top25 excess %': ('Top25 excess %', 'mean'),
                                         'Q1-Q5 %': ('Q1-Q5 %', 'mean'), 'IC': ('IC', 'mean'),
                                         'Universum %/mnd': ('Universum %', 'mean')})
    add(md_table(by_year, {'Top25 excess %': '{:+.2f}', 'Q1-Q5 %': '{:+.2f}', 'IC': '{:+.3f}', 'Universum %/mnd': '{:+.2f}'}))
    sub['Regime'] = np.where(sub['Universum %'] > 0, 'Markt omhoog', 'Markt omlaag')
    by_reg = sub.groupby('Regime').agg(**{'N mnd': ('IC', 'size'), 'Top25 excess %': ('Top25 excess %', 'mean'),
                                          'Q1-Q5 %': ('Q1-Q5 %', 'mean'), 'IC': ('IC', 'mean')})
    add('\n' + md_table(by_reg, {'Top25 excess %': '{:+.2f}', 'Q1-Q5 %': '{:+.2f}', 'IC': '{:+.3f}'}))
    add('\n### Sectorsamenstelling Top 25\n')
    add(md_table(sector_composition(df), {'Top25 aandeel %': '{:.1f}', 'Universum %': '{:.1f}', 'Over/onderweging (x)': '{:.2f}'}))

    # 6. walk-forward
    print('Walk-forward ML...')
    wf, coefs, pimp = walk_forward(df)
    add(f'\n## 6. Walk-forward (expanding window, eerste {MIN_TRAIN} snapshots alleen training, '
        f'OOS-maanden: {wf["Date"].nunique()})\n')
    agg = wf.groupby('Model').agg(**{
        'IC': ('IC', 'mean'), 'IC t': ('IC', tstat), 'IC BN': ('IC BN', 'mean'), 'IC BN t': ('IC BN', tstat),
        'Top-kw. excess %/mnd': ('Top-kwintiel excess', lambda s: s.mean() * 100),
        'Top-kw. t': ('Top-kwintiel excess', tstat),
        'Top-kw. excess BN %/mnd': ('Top-kwintiel excess BN', lambda s: s.mean() * 100),
        'LS Q1-Q5 %/mnd': ('LS (Q1-Q5)', lambda s: s.mean() * 100),
        'Gem. Beta top': ('Beta top', 'mean')}).sort_values('IC', ascending=False)
    add(md_table(agg, {'IC': '{:+.3f}', 'IC t': '{:+.2f}', 'IC BN': '{:+.3f}', 'IC BN t': '{:+.2f}',
                       'Top-kw. excess %/mnd': '{:+.2f}', 'Top-kw. t': '{:+.2f}',
                       'Top-kw. excess BN %/mnd': '{:+.2f}', 'LS Q1-Q5 %/mnd': '{:+.2f}', 'Gem. Beta top': '{:.2f}'}))
    add('\n### Ridge-coëfficiënten (cross-sectionele rank-features, gemiddeld over folds)\n')
    cf = pd.DataFrame({'Gem. coëf.': coefs.mean(), '% folds positief': (coefs > 0).mean() * 100})
    cf.index.name = 'Feature'
    add(md_table(cf.sort_values('Gem. coëf.', key=abs, ascending=False), {'Gem. coëf.': '{:+.4f}', '% folds positief': '{:.0f}'}))
    add('\n### Permutation importance (gem. IC-daling op out-of-sample maand)\n')
    pv = pimp.groupby(['Feature', 'Model'])['drop'].mean().unstack().sort_values('RandomForest', ascending=False)
    add(md_table(pv, {'Ridge': '{:+.4f}', 'RandomForest': '{:+.4f}'}))

    # ---- figuren
    fig, ax = plt.subplots(figsize=(9, 4.5))
    ax.bar(dec.index, dec['Gem. excess/mnd %'], yerr=1.96 * dec['SE %'], capsize=3, color='#4c78a8')
    ax.axhline(0, color='k', lw=0.8)
    ax.set_xlabel('Deciel (1 = beste screener-score)'); ax.set_ylabel('Gem. excess rendement %/mnd')
    ax2 = ax.twinx(); ax2.plot(dec.index, dec['Gem. Beta'], color='#e45756', marker='o'); ax2.set_ylabel('Gem. Beta', color='#e45756')
    ax2.grid(False); ax.set_title('Excess rendement per deciel (±95% CI) en gemiddelde Beta')
    fig.tight_layout(); fig.savefig(os.path.join(ART_DIR, 'v2_deciles.png'), dpi=130); plt.close(fig)

    fig, ax = plt.subplots(figsize=(9, 4.5))
    for n, c in zip((10, 25, 50), ('#e45756', '#4c78a8', '#72b7b2')):
        ax.plot((1 + port[n]['net']).cumprod(), label=f'Top {n} (netto)', color=c)
    ax.plot((1 + p25['mkt']).cumprod(), label='Universum (gelijk gew.)', color='k', ls='--')
    if spy is not None and len(spy) > 10:
        ax.plot((1 + spy.reindex(p25.index).fillna(0)).cumprod(), label='SPY', color='gray', ls=':')
    ax.set_title('Groei van 1 euro'); ax.legend()
    fig.tight_layout(); fig.savefig(os.path.join(ART_DIR, 'v2_equity.png'), dpi=130); plt.close(fig)

    fig, ax = plt.subplots(figsize=(9, 5))
    ic_plot = ic_df.sort_values('IC')
    ax.barh(ic_plot.index, ic_plot['IC'], color='#4c78a8', label='IC')
    ax.barh(ic_plot.index, ic_plot['IC (beta-neutraal)'], color='#f58518', alpha=0.6, height=0.4, label='IC beta-neutraal')
    ax.axvline(0, color='k', lw=0.8); ax.legend(); ax.set_title('Gem. Information Coefficient per factor')
    fig.tight_layout(); fig.savefig(os.path.join(ART_DIR, 'v2_ic.png'), dpi=130); plt.close(fig)

    fig, ax = plt.subplots(figsize=(9, 4.5))
    for m, g in wf.groupby('Model'):
        ax.plot(g['Date'], (1 + g['Top-kwintiel excess']).cumprod(), label=m)
    ax.axhline(1, color='k', lw=0.8); ax.set_title('Walk-forward OOS: cumulatief excess van top-kwintiel (per model)'); ax.legend()
    fig.tight_layout(); fig.savefig(os.path.join(ART_DIR, 'v2_walkforward.png'), dpi=130); plt.close(fig)

    with open(TABLES_MD, 'w', encoding='utf-8') as f:
        f.write('\n'.join(T))
    print('\n'.join(T).encode('ascii', 'replace').decode('ascii'))


if __name__ == '__main__':
    main()
