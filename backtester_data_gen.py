import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
import numpy as np
import os
import logging
from tqdm import tqdm
import argparse

logging.getLogger('yfinance').setLevel(logging.CRITICAL)

def calc_efficiency_ratio(closes):
    if len(closes) < 2: return np.nan
    change = abs(closes.iloc[-1] - closes.iloc[0])
    volatility = sum(abs(closes.diff().dropna()))
    if volatility == 0: return 0
    return change / volatility

def get_metrics_at_date(closes, spy_returns, spy_var, current_year_start):
    """
    Computes metrics assuming the last element in `closes` is the 'current' day.
    """
    if len(closes) < 50:
        return None

    raw_price = closes.iloc[-1].item() if hasattr(closes.iloc[-1], 'item') else closes.iloc[-1]
    current_price = round(float(raw_price), 2)
    
    # Momentum metrics
    ret_1m = (current_price / closes.iloc[-22]) - 1 if len(closes) >= 22 else np.nan
    ret_3m = (current_price / closes.iloc[-64]) - 1 if len(closes) >= 64 else np.nan
    ret_1y = (current_price / closes.iloc[-252]) - 1 if len(closes) >= 252 else np.nan
    
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
    
    # Beta & Sharpe Ratio
    daily_returns = closes.tail(252).pct_change().dropna() # Use trailing 1y for beta/sharpe
    
    beta = np.nan
    if not spy_returns.empty and len(daily_returns) > 30:
        aligned_returns = pd.concat([daily_returns, spy_returns.tail(len(daily_returns))], axis=1, join='inner').dropna()
        if len(aligned_returns) > 30:
            # Covariantie en SPY-variantie over exact dezelfde handelsdagen (gelijk aan live screener)
            spy_var_aligned = aligned_returns.iloc[:, 1].var()
            if spy_var_aligned > 0:
                beta = aligned_returns.cov().iloc[0, 1] / spy_var_aligned
    
    sharpe_ratio = np.nan
    mean_ret = daily_returns.mean()
    std_ret = daily_returns.std()
    if std_ret > 0:
        sharpe_ratio = (mean_ret / std_ret) * np.sqrt(252)
        
    efficiency_score = calc_efficiency_ratio(closes.tail(252)) # Traling 1y efficiency
    
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

def rank_cross_section(df):
    """
    Ranks stocks cross-sectionally for a given snapshot.
    """
    if len(df) == 0: return df
    
    df['Rank 1M'] = df['Last month'].rank(ascending=False, method='min')
    df['Rank 3M'] = df['Last 3 months'].rank(ascending=False, method='min')
    df['Rank 1 Jaar'] = df['Last year'].rank(ascending=False, method='min')
    df['Rank 200 MAVG'] = df['200 avg'].rank(ascending=False, method='min')
    
    df['Sharp ratio rank'] = df['Sharpe Ratio'].rank(ascending=False, method='min')
    df['Rank efficiency'] = df['Efficiency Score'].rank(ascending=False, method='min')
    
    df['Trend rank'] = df['Trend'].apply(lambda x: 1 if x == 'Bullish' else 2)
    
    # Base score
    base_score = (((df['Rank 1M'] * 0.15) + (df['Rank 3M'] * 0.40) + (df['Rank 1 Jaar'] * 0.45)) * 0.70) + (df['Rank 200 MAVG'] * 0.20)
    
    # Calculate Sector rank (Unknown/ETF/sectoren < 3 aandelen tellen niet mee; gelijk aan live screener)
    counts = df['GICS sector'].value_counts()
    valid_sectors = [s for s in counts.index if s not in {'Unknown', 'ETF'} and counts[s] >= 3]
    df_valid = df[df['GICS sector'].isin(valid_sectors)]
    sector_base = df_valid.groupby('GICS sector').apply(lambda g: (((g['Rank 1M'].mean() * 0.15) + (g['Rank 3M'].mean() * 0.40) + (g['Rank 1 Jaar'].mean() * 0.45)) * 0.70) + (g['Rank 200 MAVG'].mean() * 0.20))
    sector_scores = sector_base.rank(ascending=True, method='min')
    
    num_sectors = len(sector_scores)
    num_stocks = len(df)
    scaled_sector_scores = (sector_scores / num_sectors) * num_stocks
    
    df['Sector momentum rank'] = df['GICS sector'].map(sector_scores).astype('Int64')
    df['Scaled sector rank'] = df['GICS sector'].map(scaled_sector_scores).fillna(num_stocks / 2)

    # Final score
    df['Total score'] = base_score + (df['Scaled sector rank'] * 0.10)
    df['Total score incl beta'] = df['Total score'] * (1 + (df['Beta'].fillna(1.0) - 1)*0.1)
    
    df = df.sort_values(by='Total score', ascending=True).reset_index(drop=True)
    df['Rank all'] = range(1, len(df) + 1)
    
    return df

def generate_backtest_dataset(period='5y', out_file='backtest_dataset.csv'):
    print("1. Tickers inlezen...")
    if not os.path.exists('ib_tickers.csv'):
        print("Kan ib_tickers.csv niet vinden. Run extract_tickers.py eerst.")
        return

    df_tickers = pd.read_csv('ib_tickers.csv')
    tickers = df_tickers['yf_ticker'].dropna().unique().tolist()
    
    if 'SPY' not in tickers:
        tickers.append('SPY')
        
    print(f"-> {len(tickers)} tickers (incl SPY) klaar voor verwerking.")

    print(f"\n2. Ophalen historische data ({period})... dit kan even duren.")
    hist = yf.download(tickers, period=period, threads=True, progress=False)
    
    if hist.empty:
        print("Data ophalen mislukt.")
        return

    # Prepare SPY returns
    if isinstance(hist.columns, pd.MultiIndex):
        spy_closes = hist.xs('SPY', level=1, axis=1)['Close'].dropna() if 'SPY' in hist.columns.get_level_values(1) else pd.Series()
    else:
        spy_closes = hist['Close'].dropna() if 'SPY' in hist.columns else pd.Series()
        
    spy_returns_all = spy_closes.pct_change().dropna()
    
    all_trading_days = spy_closes.index.tolist()
    
    # We want snapshots every 21 trading days (approx 1 month), starting from 1 year into the data
    # so we have enough history to calculate 200MA and 1Y returns.
    start_idx = 260
    end_idx = len(all_trading_days) - 22 # Need at least 22 days ahead for forward return

    if start_idx >= end_idx:
        print("Niet genoeg historische data om backtest uit te voeren.")
        return

    snapshot_indices = list(range(start_idx, end_idx, 21))
    
    all_snapshots = []
    
    print("\n3. Start 'Walk-Forward' Simulatie...")
    for snap_idx in tqdm(snapshot_indices, desc="Snapshots verwerken"):
        current_date = all_trading_days[snap_idx]
        forward_date_1m = all_trading_days[snap_idx + 21]
        
        current_year_start = pd.to_datetime(str(current_date.year) + '-01-01').tz_localize(current_date.tz)
        
        snapshot_results = []
        
        # Calculate metrics for each ticker
        for idx, row in df_tickers.iterrows():
            t = row['yf_ticker']
            if pd.isna(t): continue
            
            try:
                if isinstance(hist.columns, pd.MultiIndex):
                    if t not in hist.columns.get_level_values(1): continue
                    df_t = hist.xs(t, level=1, axis=1)
                else:
                    if t not in [tickers[0]]: continue
                    df_t = hist
                    
                closes = df_t['Close']
                
                # Slicing up to current date
                closes_upto = closes[closes.index <= current_date].dropna()
                if len(closes_upto) < 252: # Need 1 year history
                    continue
                    
                # Slicing forward to get target return
                closes_forward = closes[(closes.index > current_date) & (closes.index <= forward_date_1m)].dropna()
                
                if len(closes_forward) == 0:
                    continue
                    
                spy_returns = spy_returns_all[spy_returns_all.index <= current_date]
                spy_var = spy_returns.tail(252).var()
                
                curr = get_metrics_at_date(closes_upto, spy_returns, spy_var, current_year_start)
                
                if curr and curr['Last year'] is not np.nan:
                    price_now = curr['Current price']
                    price_future = closes_forward.iloc[-1].item() if hasattr(closes_forward.iloc[-1], 'item') else closes_forward.iloc[-1]
                    fwd_return_1m = (price_future / price_now) - 1
                    
                    curr['Snapshot Date'] = current_date.strftime("%Y-%m-%d")
                    curr['Ticker'] = row['Ticker']
                    curr['yf_ticker'] = t
                    curr['GICS sector'] = row.get('GICS sector', 'Unknown')
                    curr['Forward Return 1M'] = fwd_return_1m
                    
                    snapshot_results.append(curr)
                    
            except Exception as e:
                pass
                
        # Rank cross-sectionally for the snapshot
        if len(snapshot_results) > 0:
            df_snap = rank_cross_section(pd.DataFrame(snapshot_results))
            all_snapshots.append(df_snap)
            
    if all_snapshots:
        final_dataset = pd.concat(all_snapshots, ignore_index=True)
        final_dataset.to_csv(out_file, index=False, sep='|')
        print(f"\nBacktest dataset gegenereerd met {len(final_dataset)} rijen over {len(all_snapshots)} tijdsperiodes!")
        print(f"Opgeslagen als '{out_file}'.")
    else:
        print("\nGeen data kunnen genereren.")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument('--period', default='5y')
    ap.add_argument('--out', default='backtest_dataset.csv')
    a = ap.parse_args()
    generate_backtest_dataset(a.period, a.out)
