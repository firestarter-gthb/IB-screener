import pandas as pd

# Read data.csv and extract unique tickers and sectors
df = pd.read_csv('data.csv', skiprows=14)
df.columns = [str(c).strip() for c in df.columns]

df = df.dropna(subset=['Ticker'])
df = df[df['Ticker'] != '#N/A']

# Extract Ticker, Name, and GICS sector
tickers_df = df[['Ticker', 'Name', 'GICS sector']].drop_duplicates(subset=['Ticker'])

# Clean up tickers (remove NASDAQ:, NYSE: etc. for yfinance)
def clean_ticker(t):
    if ':' in t:
        return t.split(':')[1]
    return t

tickers_df['yf_ticker'] = tickers_df['Ticker'].apply(clean_ticker)

tickers_df.to_csv('ib_tickers.csv', index=False)
print(f"Extracted {len(tickers_df)} tickers to ib_tickers.csv")
