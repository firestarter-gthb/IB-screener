import pandas as pd
import yfinance as yf
from datetime import datetime
import numpy as np
import time
import os
import logging
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logging.getLogger('yfinance').setLevel(logging.CRITICAL)
logging.getLogger('urllib3').setLevel(logging.CRITICAL)

# Sectoren die niet meetellen in de sectorrank (zie rank_dataframe)
EXCLUDED_SECTORS = {'Unknown', 'ETF'}
MIN_SECTOR_SIZE = 3

# Elke run wordt met datum opgeslagen in deze map (voor forward testing, zie forward_tracker.py)
HISTORY_DIR = 'history'

def calc_efficiency_ratio(closes):
    if len(closes) < 2: return np.nan
    change = abs(closes.iloc[-1] - closes.iloc[0])
    volatility = sum(abs(closes.diff().dropna()))
    if volatility == 0: return 0
    return change / volatility

def compute_metrics(closes, spy_returns, current_year_start, offset=0):
    # Apply offset (offset=0 means today, offset=22 means ~1 month ago)
    if offset > 0:
        if len(closes) <= offset:
            return None
        closes = closes.iloc[:-offset]
    # SPY op datum afkappen (niet op positie), zodat beide reeksen op dezelfde dag eindigen
    if not spy_returns.empty and len(closes) > 0:
        spy_returns = spy_returns[spy_returns.index <= closes.index[-1]]

    if len(closes) < 50:
        return None

    raw_price = closes.iloc[-1].item() if hasattr(closes.iloc[-1], 'item') else closes.iloc[-1]
    current_price = round(float(raw_price), 2)
    
    # Momentum metrics (12 maanden = 252 handelsdagen, gelijk aan de backtest)
    ret_1m = (current_price / closes.iloc[-22]) - 1 if len(closes) >= 22 else np.nan
    ret_3m = (current_price / closes.iloc[-64]) - 1 if len(closes) >= 64 else np.nan
    # Jonge aandelen (< 1 jaar historie): rendement sinds eerste koers als benadering
    ret_1y = (current_price / closes.iloc[-252]) - 1 if len(closes) >= 252 else (current_price / closes.iloc[0]) - 1
    
    ytd_prices = closes[closes.index >= current_year_start]
    ret_ytd = (current_price / ytd_prices.iloc[0]) - 1 if len(ytd_prices) > 0 else np.nan
    
    # Moving averages
    avg_200 = closes.tail(200).mean() if len(closes) >= 200 else np.nan
    dist_200 = (current_price / avg_200) - 1 if not pd.isna(avg_200) else np.nan
    
    closes_20 = closes.tail(20)
    avg_20 = closes_20.mean()
    std_20 = closes_20.std()
    dist_20 = (current_price - avg_20) / std_20 if std_20 else np.nan
    
    closes_50 = closes.tail(50)
    avg_50 = closes_50.mean()
    if current_price < avg_50:
        action = 'S'
    elif not np.isnan(dist_20) and abs(dist_20) <= 0.5:
        action = 'B'
    else:
        action = 'N'
    
    trend = 'Bullish' if (pd.notna(avg_200) and current_price > avg_200) else 'Bearish'
    
    # Beta & Sharpe Ratio (laatste 12 maanden)
    window = closes.tail(252)
    daily_returns = window.pct_change().dropna()
    
    beta = np.nan
    if not spy_returns.empty and len(daily_returns) > 30:
        aligned_returns = pd.concat([daily_returns, spy_returns], axis=1, join='inner').dropna()
        if len(aligned_returns) > 30:
            # Covariantie en SPY-variantie over exact dezelfde handelsdagen
            spy_var_aligned = aligned_returns.iloc[:, 1].var()
            if spy_var_aligned > 0:
                beta = aligned_returns.cov().iloc[0, 1] / spy_var_aligned
    
    sharpe_ratio = np.nan
    mean_ret = daily_returns.mean()
    std_ret = daily_returns.std()
    if std_ret > 0:
        sharpe_ratio = (mean_ret / std_ret) * np.sqrt(252)
        
    efficiency_score = calc_efficiency_ratio(window)
    
    return {
        'Action': action,
        'Current price': current_price,
        'Last month': ret_1m,
        'Last 3 months': ret_3m,
        'Last year': ret_1y,
        'YTD Performance': ret_ytd,
        '200 avg': dist_200,
        'Z-score 20MA': dist_20,
        'Trend': trend,
        'Beta': beta,
        'Sharpe Ratio': sharpe_ratio,
        'Efficiency Score': efficiency_score
    }

def rank_dataframe(df, is_past=False):
    if len(df) == 0: return df
    
    df['Rank 1M'] = df['Last month'].rank(ascending=False, method='min')
    df['Rank 3M'] = df['Last 3 months'].rank(ascending=False, method='min')
    df['Rank 1 Jaar'] = df['Last year'].rank(ascending=False, method='min')
    df['Rank 200 MAVG'] = df['200 avg'].rank(ascending=False, method='min')
    
    df['Sharp ratio rank'] = df['Sharpe Ratio'].rank(ascending=False, method='min')
    df['Rank efficiency'] = df['Efficiency Score'].rank(ascending=False, method='min')
    
    df['Trend rank'] = df['Trend'].apply(lambda x: 1 if x == 'Bullish' else 2)
    
    # Old shortterm/longterm just for display columns
    score_shortterm = (df['Rank 1M'] * 0.15) + (df['Rank 3M'] * 0.40) + (df['Trend rank'] * 0.10)
    score_longterm = (df['Rank 1 Jaar'] * 0.25) + (df['Rank 200 MAVG'] * 0.20) + (df['Sharp ratio rank'] * 0.20)
    
    df['Total shortterm'] = score_shortterm
    df['Total longterm'] = score_longterm
    
    df['Rank shortterm'] = score_shortterm.rank(ascending=True, method='min').astype(int)
    df['Rank longterm'] = score_longterm.rank(ascending=True, method='min').astype(int)

    # New exact formula Base score
    base_score = (((df['Rank 1M'] * 0.15) + (df['Rank 3M'] * 0.40) + (df['Rank 1 Jaar'] * 0.45)) * 0.70) + (df['Rank 200 MAVG'] * 0.20)
    
    # Calculate Sector rank
    # 'Unknown', 'ETF' en sectoren met minder dan MIN_SECTOR_SIZE aandelen tellen niet mee:
    # een 'sector' van 1-2 aandelen geeft een onbetrouwbaar gemiddelde. Die aandelen krijgen een neutrale sectorscore.
    counts = df['GICS sector'].value_counts()
    valid_sectors = [s for s in counts.index if s not in EXCLUDED_SECTORS and counts[s] >= MIN_SECTOR_SIZE]
    df_valid = df[df['GICS sector'].isin(valid_sectors)]
    sector_base = df_valid.groupby('GICS sector').apply(lambda g: (((g['Rank 1M'].mean() * 0.15) + (g['Rank 3M'].mean() * 0.40) + (g['Rank 1 Jaar'].mean() * 0.45)) * 0.70) + (g['Rank 200 MAVG'].mean() * 0.20))
    sector_scores = sector_base.rank(ascending=True, method='min')
    
    # Scale Sector rank
    num_sectors = len(sector_scores)
    num_stocks = len(df)
    scaled_sector_scores = (sector_scores / num_sectors) * num_stocks
    
    df['Sector momentum rank'] = df['GICS sector'].map(sector_scores).astype('Int64')
    df['Scaled sector rank'] = df['GICS sector'].map(scaled_sector_scores).fillna(num_stocks / 2)

    # Final score
    df['Total score'] = base_score + (df['Scaled sector rank'] * 0.10)
    df['Total score incl beta'] = df['Total score'] * (1 + (df['Beta'].fillna(1.0) - 1)*0.1)
    
    # Extra 'shadow' kolommen: puur ter vergelijking, tellen NIET mee in Total score of Rank all.
    # 1) Rank 12-1: rendement van de afgelopen 12 maanden zonder de laatste maand (1 = beste).
    mom_12_1 = (1 + df['Last year']) / (1 + df['Last month']) - 1
    df['Rank 12-1'] = mom_12_1.rank(ascending=False, method='min')
    
    # 2) Rank BN: Total score gecorrigeerd voor Beta (beta-neutraal, 1 = beste).
    #    Per run: percentiel van de score (hoog = beter) minus de lineaire samenhang met het Beta-percentiel.
    pct_score = (-df['Total score']).rank(pct=True)
    pct_beta = df['Beta'].rank(pct=True).fillna(0.5)
    X = np.c_[np.ones(len(df)), pct_beta.values]
    coef = np.linalg.lstsq(X, pct_score.values, rcond=None)[0]
    beta_neutral = pct_score - X @ coef
    df['Rank BN'] = beta_neutral.rank(ascending=False, method='min')
    
    # 3) Rank ex-1M: Total score zonder de 1M-component (3M en 1J herschaald: 40/85 en 45/85, 1 = beste).
    #    Uit de backtest: zelfde resultaat met minder turnover, maar niet significant -> eerst forward volgen.
    score_ex1m = (((df['Rank 3M'] * 0.40 + df['Rank 1 Jaar'] * 0.45) / 0.85) * 0.70) + (df['Rank 200 MAVG'] * 0.20) + (df['Scaled sector rank'] * 0.10)
    df['Rank ex-1M'] = score_ex1m.rank(ascending=True, method='min')
    
    df = df.sort_values(by='Total score', ascending=True).reset_index(drop=True)
    df['Rank all'] = range(1, len(df) + 1)
    
    if is_past:
        # Rename columns to identify them as past metrics
        df = df[['Ticker', 'GICS sector', 'Rank all', 'Rank shortterm', 'Rank longterm', 'Sector momentum rank']]
        df = df.rename(columns={
            'Rank all': 'Rank all past',
            'Rank shortterm': 'Rank shortterm past',
            'Rank longterm': 'Rank longterm past',
            'Sector momentum rank': 'Sector momentum rank past'
        })
    
    return df

def run_screener():
    print("1. Tickers inlezen...")
    if not os.path.exists('ib_tickers.csv'):
        print("Kan ib_tickers.csv niet vinden. Run extract_tickers.py eerst.")
        return

    df_tickers = pd.read_csv('ib_tickers.csv')
    tickers = df_tickers['yf_ticker'].dropna().unique().tolist()
    
    if 'SPY' not in tickers:
        tickers.append('SPY')
        
    print(f"-> {len(tickers)} tickers (incl SPY) klaar voor verwerking.")

    print("\n2. Data ophalen (2 jaar historie, nodig voor 12 maanden + de rank van 30 dagen terug)...")
    hist = yf.download(tickers, period='2y', threads=True, progress=False, timeout=15)
    
    if hist.empty:
        print("Data ophalen mislukt.")
        return
    
    # Datum van de laatste koersdag in de data (gebruikt voor de snapshot-bestandsnaam)
    data_date = pd.Timestamp(hist.index[-1]).strftime('%Y-%m-%d')
        
    results_current = []
    results_past = []
    skipped = []
    
    current_year_start = pd.to_datetime(str(datetime.now().year) + '-01-01').tz_localize(None)
    if hist.index.tz is not None:
        current_year_start = pd.to_datetime(str(datetime.now().year) + '-01-01').tz_localize(hist.index.tz)
    
    if isinstance(hist.columns, pd.MultiIndex):
        spy_closes = hist.xs('SPY', level=1, axis=1)['Close'].dropna() if 'SPY' in hist.columns.get_level_values(1) else pd.Series()
    else:
        spy_closes = hist['Close'].dropna() if 'SPY' in hist.columns else pd.Series()
        
    spy_returns = spy_closes.pct_change().dropna()

    for idx, row in df_tickers.iterrows():
        t = row['yf_ticker']
        if pd.isna(t): continue
        
        try:
            if isinstance(hist.columns, pd.MultiIndex):
                if t not in hist.columns.get_level_values(1):
                    skipped.append(f"{row['Ticker']} (geen data van Yahoo)")
                    continue
                df_t = hist.xs(t, level=1, axis=1).dropna(how='all')
            else:
                if t not in [tickers[0]]: continue
                df_t = hist.dropna(how='all')
                
            closes = df_t['Close'].dropna()
            
            # Current metrics
            curr = compute_metrics(closes, spy_returns, current_year_start, offset=0)
            if curr:
                curr['Name'] = row['Name']
                curr['Ticker'] = row['Ticker']
                curr['yf_ticker'] = t
                curr['GICS sector'] = row.get('GICS sector', 'Unknown')
                curr['GICS industry'] = row.get('GICS industry', 'Unknown')
                results_current.append(curr)
            else:
                skipped.append(f"{row['Ticker']} (slechts {len(closes)} koersen, minimaal 50 nodig)")
                
            # Past metrics (22 trading days ago ~ 1 month)
            past = compute_metrics(closes, spy_returns, current_year_start, offset=22)
            if past:
                past['Name'] = row['Name']
                past['Ticker'] = row['Ticker']
                past['yf_ticker'] = t
                past['GICS sector'] = row.get('GICS sector', 'Unknown')
                past['GICS industry'] = row.get('GICS industry', 'Unknown')
                results_past.append(past)
            
        except Exception as e:
            skipped.append(f"{row['Ticker']} (fout: {e})")

    print(f"\nKlaar! {len(results_current)} aandelen succesvol verwerkt.")
    if skipped:
        print(f"\nLet op: {len(skipped)} ticker(s) overgeslagen:")
        for s in skipped:
            print(f"   - {s}")

    print("\n3. Ranks en Delta berekenen (incl dynamic past ranks)...")
    
    df_current = rank_dataframe(pd.DataFrame(results_current), is_past=False)
    df_past = rank_dataframe(pd.DataFrame(results_past), is_past=True)
    
    if len(df_current) > 0 and len(df_past) > 0:
        # Merge current and past (sector niet dubbel meenemen, anders verdwijnt 'GICS sector' als _x/_y)
        final_df = pd.merge(df_current, df_past.drop(columns=['GICS sector']), on='Ticker', how='left')
        
        # Calculate Delta
        final_df['Delta'] = final_df['Rank all past'] - final_df['Rank all']
        # For stocks without a past rank, set delta to 0
        final_df['Delta'] = final_df['Delta'].fillna(0)
        final_df['Rank all past'] = final_df['Rank all past'].fillna(final_df['Rank all'])

        output_cols = [
            'Action', 'Rank all', 'Rank all past', 'Delta', 'Rank shortterm', 'Rank longterm', 'Rank BN', 'Rank 12-1', 'Rank ex-1M', 'Trend', 'Ticker', 'Name', 'GICS sector', 'GICS industry',
            'Current price', 'Beta', 'Last month', 'Last 3 months', 'Last year', 'YTD Performance', '200 avg', 'Z-score 20MA', 
            'Efficiency Score', 'Sharpe Ratio', 'Trend rank', 'Sharp ratio rank', 'Rank efficiency', 
            'Rank 1M', 'Rank 3M', 'Rank 1 Jaar', 'Rank 200 MAVG', 'Total score', 'Total score incl beta', 'Sector momentum rank'
        ]
        
        final_df = final_df[[c for c in output_cols if c in final_df.columns]]
        
        final_df.to_csv('ib_screener_result_final.csv', index=False, sep='|')
        print('Bestand succesvol opgeslagen als ib_screener_result_final.csv!')
        
        # Snapshot met datum bewaren (een tweede run op dezelfde koersdag overschrijft die dag)
        save_snapshot(final_df, df_current, data_date)
        
        # Sector Pivot Table
        sector_curr = df_current.groupby('GICS sector').agg(
            Aantal=('Ticker', 'count'),
            Sector_Rank=('Sector momentum rank', 'first')
        ).reset_index()
        
        sector_past = df_past.groupby('GICS sector').agg(
            Sector_Rank_past=('Sector momentum rank past', 'first')
        ).reset_index()
        
        sector_df = pd.merge(sector_curr, sector_past, on='GICS sector', how='left')
        # Unknown/ETF/te kleine groepen hebben geen sectorrank en horen niet in het sectoroverzicht
        sector_df = sector_df.dropna(subset=['Sector_Rank'])
        sector_df['Delta'] = sector_df['Sector_Rank_past'] - sector_df['Sector_Rank']
        sector_df = sector_df.sort_values('Sector_Rank')
        sector_df.to_csv('ib_sector_result.csv', index=False, sep='|')
        print('Sector overzicht succesvol opgeslagen als ib_sector_result.csv!')
        
def save_snapshot(final_df, df_current, data_date):
    """Slaat de uitkomst van deze run op als history/ib_screener_<datum>.csv (incl. yf_ticker voor forward_tracker.py)."""
    try:
        os.makedirs(HISTORY_DIR, exist_ok=True)
        snap = final_df.merge(df_current[['Ticker', 'yf_ticker']], on='Ticker', how='left')
        snap.insert(0, 'Snapshot Date', data_date)
        path = os.path.join(HISTORY_DIR, f'ib_screener_{data_date}.csv')
        snap.to_csv(path, index=False, sep='|')
        n = len([f for f in os.listdir(HISTORY_DIR) if f.startswith('ib_screener_') and f.endswith('.csv')])
        print(f'Snapshot opgeslagen als {path} ({n} snapshot(s) in {HISTORY_DIR}/).')
    except Exception as e:
        print(f'Let op: snapshot opslaan mislukt ({e}). De rest van de run is wel gelukt.')

if __name__ == "__main__":
    run_screener()
