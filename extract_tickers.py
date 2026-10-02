import pandas as pd
import yfinance as yf
import concurrent.futures

# Read data.csv and extract unique tickers
df = pd.read_csv('data.csv')
df.columns = [str(c).strip() for c in df.columns]

if 'Ticker' not in df.columns:
    raise ValueError("The 'Ticker' column is missing in data.csv")

df = df.dropna(subset=['Ticker'])
df = df[df['Ticker'] != '#N/A']

# Extract Ticker
tickers_df = df[['Ticker']].drop_duplicates(subset=['Ticker']).copy()

# Clean up tickers (remove NASDAQ:, NYSE: etc. for yfinance)
def clean_ticker(t):
    if ':' in t:
        return t.split(':')[1]
    return t

tickers_df['yf_ticker'] = tickers_df['Ticker'].apply(clean_ticker)

print(f"Ophalen van actuele Sectoren (1) en Industries (2) voor {len(tickers_df)} aandelen via Yahoo Finance. Dit duurt ca. 1-2 minuten...")

def fetch_info(t):
    try:
        info = yf.Ticker(t).info
        name = info.get('longName', info.get('shortName', 'Unknown'))
        return name, info.get('sector', 'Unknown'), info.get('industry', 'Unknown')
    except Exception:
        return 'Unknown', 'Unknown', 'Unknown'

# Gebruik ThreadPool om ze snel parallel op te halen
names = []
sectors = []
industries = []
with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
    results = list(executor.map(fetch_info, tickers_df['yf_ticker'].tolist()))

for n, s, i in results:
    names.append(n)
    sectors.append(s)
    industries.append(i)

tickers_df['Name'] = names
tickers_df['GICS sector'] = sectors
tickers_df['GICS industry'] = industries

tickers_df.to_csv('ib_tickers.csv', index=False)
print(f"Bestand opgeslagen als ib_tickers.csv met geüpdatete sectoren!")
