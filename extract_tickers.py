import pandas as pd
import yfinance as yf
import concurrent.futures
import re
import time

# Handmatige correcties voor tickers waarvoor Yahoo geen (juiste) sector teruggeeft.
SECTOR_OVERRIDES = {
    'FISV': ('Technology', 'Information Technology Services'),  # Fiserv: na tickerwissel FI -> FISV geeft Yahoo geen sector
}

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
    t = str(t).strip()
    if ':' in t:
        t = t.split(':')[1]
    # Aandelenklassen: Yahoo gebruikt een streepje (BRK.B -> BRK-B, BF.B -> BF-B).
    # Alleen bij klasse A/B/C, zodat beurs-suffixen zoals ASML.AS of VOD.L intact blijven.
    if re.fullmatch(r'[A-Z]+\.[A-C]', t):
        t = t.replace('.', '-')
    return t

tickers_df['yf_ticker'] = tickers_df['Ticker'].apply(clean_ticker)

print(f"Ophalen van actuele Sectoren (1) en Industries (2) voor {len(tickers_df)} aandelen via Yahoo Finance. Dit duurt ca. 1-2 minuten...")

def fetch_info(t):
    for attempt in range(3):
        try:
            info = yf.Ticker(t).info
            name = info.get('longName') or info.get('shortName') or 'Unknown'
            sector = info.get('sector') or 'Unknown'
            industry = info.get('industry') or 'Unknown'
            if info.get('quoteType') == 'ETF':
                sector, industry = 'ETF', 'ETF'
            if t in SECTOR_OVERRIDES:
                sector, industry = SECTOR_OVERRIDES[t]
            return name, sector, industry
        except Exception:
            time.sleep(1 + attempt)
    if t in SECTOR_OVERRIDES:
        return ('Unknown',) + SECTOR_OVERRIDES[t]
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

unknown = tickers_df[tickers_df['GICS sector'] == 'Unknown']
if len(unknown):
    print(f"\nLet op: {len(unknown)} ticker(s) zonder sector (tellen niet mee in de sectorrank): {', '.join(unknown['Ticker'])}")
    print("Voeg ze eventueel toe aan SECTOR_OVERRIDES bovenin dit script.")
