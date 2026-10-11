"""
Forward tracker: meet hoe de opgeslagen screener-snapshots (map history/) het daarna echt hebben gedaan.

Per snapshot wordt het rendement over de volgende HORIZON handelsdagen (standaard 21 = ~1 maand) berekend
en vergeleken tussen de rangschikkingen:
  - Rank all     (de officiele Total score)
  - Rank ex-1M   (Total score zonder 1M, shadow-kolom)
  - Rank BN      (beta-neutraal, shadow-kolom)
  - Rank 12-1    (12-1 momentum, shadow-kolom)
  - Dashboard Top 25 (Top 25 na de filters van ib_top25_portfolio.html)

Maatstaven:
  - IC        = rangcorrelatie tussen rank en vervolgrendement (hoger = beter voorspeld)
  - Top-N exc = gemiddeld rendement Top N minus gemiddelde van alle aandelen in de snapshot

Alleen niet-overlappende snapshots tellen mee in de statistiek (minimaal HORIZON handelsdagen uit elkaar),
anders tel je dezelfde koersbeweging dubbel. Tip: draai de screener minimaal 1x per maand.

Gebruik:
  python forward_tracker.py                 (standaard: map history/, 21 dagen, Top 25)
  python forward_tracker.py --horizon 63    (3 maanden vooruit)
"""
import argparse
import glob
import os

import numpy as np
import pandas as pd
import yfinance as yf
from scipy.stats import spearmanr

SIGNALS = ['Rank all', 'Rank ex-1M', 'Rank BN', 'Rank 12-1']
DASHBOARD = 'Dashboard Top 25'
MIN_MONTHS_FOR_CONCLUSION = 24


def load_snapshots(folder):
    files = sorted(glob.glob(os.path.join(folder, 'ib_screener_*.csv')))
    snaps = []
    for f in files:
        df = pd.read_csv(f, sep='|')
        if 'Snapshot Date' not in df.columns or 'yf_ticker' not in df.columns:
            print(f'  overgeslagen (oud formaat): {f}')
            continue
        df['Snapshot Date'] = pd.to_datetime(df['Snapshot Date'])
        snaps.append(df)
    return snaps


def dashboard_mask(df):
    need = ['Trend', 'Action', 'Sharpe Ratio', 'Rank longterm']
    if not all(c in df.columns for c in need):
        return pd.Series(False, index=df.index)
    return (df['Trend'] == 'Bullish') & (df['Action'] != 'S') & (df['Sharpe Ratio'] >= 0.8) & (df['Rank longterm'] <= 100)


def download_closes(tickers, start):
    hist = yf.download(sorted(set(tickers)), start=start, auto_adjust=True, threads=True, progress=False, timeout=20)
    if hist.empty:
        return pd.DataFrame()
    closes = hist['Close']
    if isinstance(closes, pd.Series):
        closes = closes.to_frame(tickers[0])
    closes.index = pd.to_datetime(closes.index).tz_localize(None)
    return closes.sort_index()


def tstat(x):
    x = pd.Series(x).dropna()
    if len(x) < 2 or x.std() == 0:
        return np.nan
    return x.mean() / (x.std() / np.sqrt(len(x)))


def evaluate(snaps, closes, horizon, top_n):
    cal = closes.index
    rows = []
    for df in snaps:
        d = df['Snapshot Date'].iloc[0]
        pos = cal.searchsorted(d, side='right') - 1  # laatste handelsdag <= snapshotdatum
        if pos < 0 or pos + horizon >= len(cal):
            continue  # nog niet 'rijp': te weinig koersdagen na de snapshot
        p0, p1 = closes.iloc[pos], closes.iloc[pos + horizon]
        ret = (p1 / p0 - 1).reindex(df['yf_ticker'].values).values
        df = df.assign(fwd=ret).dropna(subset=['fwd'])
        if len(df) < 50:
            continue
        uni = df['fwd'].mean()
        rec = {'Snapshot Date': d.date(), 'cal_pos': pos, 'Exit Date': cal[pos + horizon].date(),
               'N aandelen': len(df), 'Universum %': uni * 100}
        if 'SPY' in closes.columns:
            rec['SPY %'] = (closes['SPY'].iloc[pos + horizon] / closes['SPY'].iloc[pos] - 1) * 100
        for s in SIGNALS:
            if s not in df.columns or df[s].isna().all():
                continue
            sub = df.dropna(subset=[s])
            rec[f'{s} IC'] = spearmanr(-sub[s], sub['fwd'])[0]
            rec[f'{s} TopN exc %'] = (sub.nsmallest(top_n, s)['fwd'].mean() - uni) * 100
        dm = df[dashboard_mask(df)]
        if len(dm) > 0:
            rec[f'{DASHBOARD} TopN exc %'] = (dm.nsmallest(top_n, 'Total score')['fwd'].mean() - uni) * 100
        rows.append(rec)
    return pd.DataFrame(rows)


def non_overlapping(res, horizon):
    keep, last = [], -10**9
    for i, r in res.sort_values('cal_pos').iterrows():
        if r['cal_pos'] - last >= horizon:
            keep.append(i)
            last = r['cal_pos']
    return res.loc[keep]


def summarize(ind, top_n):
    lines = ['| Rangschikking | Gem. IC | IC t | Top-%d excess %%/periode | t | Verschil vs Rank all (Top-%d) | t |' % (top_n, top_n),
             '| :--- | :--- | :--- | :--- | :--- | :--- | :--- |']
    base = ind.get('Rank all TopN exc %')
    for s in SIGNALS + [DASHBOARD]:
        ic_col, ex_col = f'{s} IC', f'{s} TopN exc %'
        if ex_col not in ind.columns:
            continue
        ic = ind[ic_col] if ic_col in ind.columns else pd.Series(dtype=float)
        ex = ind[ex_col]
        if s == 'Rank all' or base is None:
            diff_txt = '- | -'
        else:
            d = ex - base
            diff_txt = f'{d.mean():+.2f} | {tstat(d):+.2f}'
        ic_txt = f'{ic.mean():+.3f} | {tstat(ic):+.2f}' if len(ic.dropna()) else 'n.v.t. | -'
        lines.append(f'| {s} | {ic_txt} | {ex.mean():+.2f} | {tstat(ex):+.2f} | {diff_txt} |')
    return '\n'.join(lines)


def main():
    ap = argparse.ArgumentParser(description='Forward tracking van screener-snapshots')
    ap.add_argument('--dir', default='history', help='map met ib_screener_<datum>.csv snapshots')
    ap.add_argument('--horizon', type=int, default=21, help='aantal handelsdagen vooruit (21 = ~1 maand)')
    ap.add_argument('--top', type=int, default=25, help='grootte van de Top N')
    ap.add_argument('--out', default='forward_tracking', help='prefix voor de uitvoerbestanden')
    args = ap.parse_args()

    print(f'1. Snapshots inlezen uit {args.dir}/ ...')
    snaps = load_snapshots(args.dir)
    if not snaps:
        print('   Geen snapshots gevonden. Draai eerst de screener (run_ib_screener.bat).')
        return
    dates = sorted(s['Snapshot Date'].iloc[0] for s in snaps)
    print(f'   {len(snaps)} snapshot(s): {dates[0].date()} t/m {dates[-1].date()}')

    print('2. Koersen ophalen ...')
    tickers = sorted(set(pd.concat([s['yf_ticker'] for s in snaps]).dropna()) | {'SPY'})
    closes = download_closes(tickers, start=(dates[0] - pd.Timedelta(days=7)).strftime('%Y-%m-%d'))
    if closes.empty:
        print('   Koersen ophalen mislukt.')
        return

    print('3. Rendementen na elke snapshot berekenen ...')
    res = evaluate(snaps, closes, args.horizon, args.top)
    if res.empty:
        print(f'   Nog geen snapshot is oud genoeg: er zijn {args.horizon} handelsdagen na een snapshot nodig.')
        print('   Blijf de screener regelmatig draaien en probeer het later opnieuw.')
        return
    ind = non_overlapping(res, args.horizon)
    res.drop(columns=['cal_pos']).to_csv(f'{args.out}_detail.csv', index=False, sep='|')

    md = [f'# Forward tracking ({args.horizon} handelsdagen vooruit, Top {args.top})', '',
          f'- Gerijpte snapshots: {len(res)} | niet-overlappend (telt mee): **{len(ind)}**',
          f'- Periode: {ind["Snapshot Date"].min()} t/m {ind["Exit Date"].max()}', '',
          summarize(ind, args.top), '',
          'Lees: IC > 0 en Top-N excess > 0 = de rangschikking voorspelde goed. '
          'Een verschil is pas overtuigend bij |t| > 2.', '']
    if len(ind) < MIN_MONTHS_FOR_CONCLUSION:
        md.append(f'> Let op: pas {len(ind)} onafhankelijke periodes. Trek pas conclusies vanaf ~{MIN_MONTHS_FOR_CONCLUSION} '
                  '(liefst 36) maanden; daarvoor is het vooral ruis.')
    md += ['', '## Per snapshot', '',
           '| Snapshot | Exit | Universum % | ' + ' | '.join(f'{s} Top-N exc %' for s in SIGNALS) + ' |',
           '| :--- | :--- | :--- | ' + ' | '.join(':---' for _ in SIGNALS) + ' |']
    for _, r in ind.iterrows():
        vals = ' | '.join(f'{r.get(f"{s} TopN exc %", np.nan):+.2f}' for s in SIGNALS)
        md.append(f'| {r["Snapshot Date"]} | {r["Exit Date"]} | {r["Universum %"]:+.2f} | {vals} |')
    with open(f'{args.out}_result.md', 'w', encoding='utf-8') as f:
        f.write('\n'.join(md))

    print(f'\nKlaar: {len(ind)} onafhankelijke periode(s) geevalueerd.')
    print(f'Resultaat: {args.out}_result.md  (details per snapshot: {args.out}_detail.csv)')


if __name__ == '__main__':
    main()
