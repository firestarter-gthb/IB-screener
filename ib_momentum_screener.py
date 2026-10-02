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

def calc_efficiency_ratio(closes):
    if len(closes) < 2: return np.nan
    change = abs(closes.iloc[-1] - closes.iloc[0])
    volatility = sum(abs(closes.diff().dropna()))
    if volatility == 0: return 0
    return change / volatility

def compute_metrics(closes, spy_returns, spy_var, current_year_start, offset=0):
    # Apply offset (offset=0 means today, offset=22 means ~1 month ago)
    if offset > 0:
        if len(closes) <= offset:
            return None
        closes = closes.iloc[:-offset]
        if not spy_returns.empty:
            spy_returns = spy_returns.iloc[:-offset]

    if len(closes) < 50:
        return None

    raw_price = closes.iloc[-1].item() if hasattr(closes.iloc[-1], 'item') else closes.iloc[-1]
    current_price = round(float(raw_price), 2)
    
    # Momentum metrics
    ret_1m = (current_price / closes.iloc[-22]) - 1 if len(closes) >= 22 else np.nan
    ret_3m = (current_price / closes.iloc[-64]) - 1 if len(closes) >= 64 else np.nan
    ret_1y = (current_price / closes.iloc[0]) - 1
    
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
    daily_returns = closes.pct_change().dropna()
    
    beta = np.nan
    if not spy_returns.empty and len(daily_returns) > 30 and spy_var > 0:
        aligned_returns = pd.concat([daily_returns, spy_returns], axis=1, join='inner').dropna()
        if len(aligned_returns) > 30:
            cov = aligned_returns.cov().iloc[0,1]
            beta = cov / spy_var
    
    sharpe_ratio = np.nan
    mean_ret = daily_returns.mean()
    std_ret = daily_returns.std()
    if std_ret > 0:
        sharpe_ratio = (mean_ret / std_ret) * np.sqrt(252)
        
    efficiency_score = calc_efficiency_ratio(closes)
    
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
    sector_base = df.groupby('GICS sector')['Rank 1M'].mean() * 0 # Dummy to align
    sector_base = df.groupby('GICS sector').apply(lambda g: (((g['Rank 1M'].mean() * 0.15) + (g['Rank 3M'].mean() * 0.40) + (g['Rank 1 Jaar'].mean() * 0.45)) * 0.70) + (g['Rank 200 MAVG'].mean() * 0.20))
    sector_scores = sector_base.rank(ascending=True, method='min')
    
    # Scale Sector rank
    num_sectors = len(sector_scores)
    num_stocks = len(df)
    scaled_sector_scores = (sector_scores / num_sectors) * num_stocks
    
    df['Sector momentum rank'] = df['GICS sector'].map(sector_scores).astype(int)
    df['Scaled sector rank'] = df['GICS sector'].map(scaled_sector_scores)

    # Final score
    df['Total score'] = base_score + (df['Scaled sector rank'] * 0.10)
    df['Total score incl beta'] = df['Total score'] * (1 + (df['Beta'].fillna(1.0) - 1)*0.1)
    
    df = df.sort_values(by='Total score', ascending=True).reset_index(drop=True)
    df['Rank all'] = range(1, len(df) + 1)
    
    if is_past:
        # Rename columns to identify them as past metrics
        df = df[['Ticker', 'Rank all', 'Rank shortterm', 'Rank longterm']]
        df = df.rename(columns={
            'Rank all': 'Rank all past',
            'Rank shortterm': 'Rank shortterm past',
            'Rank longterm': 'Rank longterm past'
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

    print("\n2. Data ophalen (1 jaar historie)...")
    hist = yf.download(tickers, period='1y', threads=True, progress=False, timeout=15)
    
    if hist.empty:
        print("Data ophalen mislukt.")
        return
        
    results_current = []
    results_past = []
    
    current_year_start = pd.to_datetime(str(datetime.now().year) + '-01-01').tz_localize(None)
    if hist.index.tz is not None:
        current_year_start = pd.to_datetime(str(datetime.now().year) + '-01-01').tz_localize(hist.index.tz)
    
    if isinstance(hist.columns, pd.MultiIndex):
        spy_closes = hist.xs('SPY', level=1, axis=1)['Close'].dropna() if 'SPY' in hist.columns.get_level_values(1) else pd.Series()
    else:
        spy_closes = hist['Close'].dropna() if 'SPY' in hist.columns else pd.Series()
        
    spy_returns = spy_closes.pct_change().dropna()
    spy_var = spy_returns.var()

    for idx, row in df_tickers.iterrows():
        t = row['yf_ticker']
        if pd.isna(t): continue
        
        try:
            if isinstance(hist.columns, pd.MultiIndex):
                if t not in hist.columns.get_level_values(1): continue
                df_t = hist.xs(t, level=1, axis=1).dropna(how='all')
            else:
                if t not in [tickers[0]]: continue
                df_t = hist.dropna(how='all')
                
            closes = df_t['Close'].dropna()
            
            # Current metrics
            curr = compute_metrics(closes, spy_returns, spy_var, current_year_start, offset=0)
            if curr:
                curr['Name'] = row['Name']
                curr['Ticker'] = row['Ticker']
                curr['yf_ticker'] = t
                curr['GICS sector'] = row.get('GICS sector', 'Unknown')
                curr['GICS industry'] = row.get('GICS industry', 'Unknown')
                results_current.append(curr)
                
            # Past metrics (22 trading days ago ~ 1 month)
            past = compute_metrics(closes, spy_returns, spy_var, current_year_start, offset=22)
            if past:
                past['Name'] = row['Name']
                past['Ticker'] = row['Ticker']
                past['yf_ticker'] = t
                past['GICS sector'] = row.get('GICS sector', 'Unknown')
                past['GICS industry'] = row.get('GICS industry', 'Unknown')
                results_past.append(past)
            
        except Exception as e:
            print(f"Error processing {t}: {e}")

    print(f"\nKlaar! {len(results_current)} aandelen succesvol verwerkt.")

    print("\n3. Ranks en Delta berekenen (incl dynamic past ranks)...")
    
    df_current = rank_dataframe(pd.DataFrame(results_current), is_past=False)
    df_past = rank_dataframe(pd.DataFrame(results_past), is_past=True)
    
    if len(df_current) > 0 and len(df_past) > 0:
        # Merge current and past
        final_df = pd.merge(df_current, df_past, on='Ticker', how='left')
        
        # Calculate Delta
        final_df['Delta'] = final_df['Rank all past'] - final_df['Rank all']
        # For stocks without a past rank, set delta to 0
        final_df['Delta'] = final_df['Delta'].fillna(0)
        final_df['Rank all past'] = final_df['Rank all past'].fillna(final_df['Rank all'])

        output_cols = [
            'Action', 'Rank all', 'Rank all past', 'Delta', 'Rank shortterm', 'Rank longterm', 'Trend', 'Ticker', 'Name', 'GICS sector', 'GICS industry',
            'Current price', 'Beta', 'Last month', 'Last 3 months', 'Last year', 'YTD Performance', '200 avg', 'Z-score 20MA', 
            'Efficiency Score', 'Sharpe Ratio', 'Trend rank', 'Sharp ratio rank', 'Rank efficiency', 
            'Rank 1M', 'Rank 3M', 'Rank 1 Jaar', 'Rank 200 MAVG', 'Total score', 'Total score incl beta', 'Sector momentum rank'
        ]
        
        final_df = final_df[[c for c in output_cols if c in final_df.columns]]
        
        final_df.to_csv('ib_screener_result_final.csv', index=False, sep='|')
        print('Bestand succesvol opgeslagen als ib_screener_result_final.csv!')
        
if __name__ == "__main__":
    run_screener()
