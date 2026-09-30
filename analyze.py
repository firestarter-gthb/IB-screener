import pandas as pd
import json
import warnings
warnings.filterwarnings('ignore')

# Read the CSV
file_path = 'data.csv'

# Since the header is on row 15 (index 14), we skip the first 14 rows
df = pd.read_csv(file_path, skiprows=14)

# Basic cleanup
df.columns = [str(c).strip() for c in df.columns]

# The first columns relate to ranking and identification
identifying_cols = ['Ticker', 'Name', 'GICS sector']
ranking_cols = ['Rank all', 'Rank all past', 'Delta', 'Trend']

print("Total number of rows:", len(df))

# Let's filter out rows where Ticker is NaN
df = df.dropna(subset=['Ticker'])
print("Total number of valid stocks:", len(df))

# Top 10 by 'Rank all' (assuming 1 is the best)
df['Rank all'] = pd.to_numeric(df['Rank all'], errors='coerce')
top_10 = df.sort_values(by='Rank all').head(10)

print("\n--- Top 10 Stocks by Rank All ---")
for idx, row in top_10.iterrows():
    print(f"{row['Rank all']}. {row['Name']} ({row['Ticker']}) - Sector: {row.iloc[16]} - Trend: {row.iloc[13]}")

# Analysis by Sector
print("\n--- Sector Distribution ---")
sector_col = df.columns[16] # 1st GICS sector column
print(df[sector_col].value_counts())

# Best sectors (average rank)
print("\n--- Average Rank by Sector ---")
print(df.groupby(sector_col)['Rank all'].mean().sort_values())

# Top movers (Biggest positive Delta)
df['Delta'] = pd.to_numeric(df['Delta'], errors='coerce')
top_movers = df.sort_values(by='Delta', ascending=False).head(5)
print("\n--- Top 5 Positive Movers (Delta) ---")
for idx, row in top_movers.iterrows():
    print(f"+{row['Delta']} positions: {row['Name']} ({row['Ticker']}) - Old Rank: {row['Rank all past']} -> New Rank: {row['Rank all']}")

# Top losers (Biggest negative Delta)
top_losers = df.sort_values(by='Delta', ascending=True).head(5)
print("\n--- Top 5 Negative Movers (Delta) ---")
for idx, row in top_losers.iterrows():
    print(f"{row['Delta']} positions: {row['Name']} ({row['Ticker']}) - Old Rank: {row['Rank all past']} -> New Rank: {row['Rank all']}")

