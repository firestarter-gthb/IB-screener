import pandas as pd
from datetime import datetime
import json

def generate_top25_report(csv_file, output_html):
    df = pd.read_csv(csv_file, sep='|')
    
    # 1. Toepassen van de filters zoals gevraagd in de JS code
    filtered_df = df[
        (df['Trend'] == 'Bullish') & 
        (df['Action'] != 'S') & 
        (df['Sharpe Ratio'] >= 0.8) & 
        (df['Rank longterm'] <= 100)
    ]
    
    # 2. Sorteer op Total score (laagste score is de beste)
    sorted_df = filtered_df.sort_values(by='Total score', ascending=True)
    
    # 3. Pak de Top 25
    top25_df = sorted_df.head(25)
    
    # Zorg dat lege waarden None/null worden voor JSON
    top25_df = top25_df.where(pd.notnull(top25_df), None)
    
    # Haal de kolomnamen op
    columns = top25_df.columns.tolist()
    if 'Action' in columns:
        columns.insert(0, columns.pop(columns.index('Action')))
        
    data = top25_df.to_dict(orient='records')
    data_json = json.dumps(data)
    
    current_time = datetime.now().strftime("%d-%m-%Y %H:%M:%S")

    html = f"""<!DOCTYPE html>
<html lang="nl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>IB Top 25 Portfolio</title>
    <link rel="icon" href="data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22><text y=%22.9em%22 font-size=%2290%22>&#11088;</text></svg>">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg-color: #0f172a;
            --surface-color: #1e293b;
            --surface-hover: #334155;
            --border-color: #334155;
            --text-primary: #f8fafc;
            --text-secondary: #94a3b8;
            --accent-color: #f59e0b;
            --accent-hover: #fbbf24;
            --positive: #10b981;
            --negative: #ef4444;
        }}
        
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}

        body {{
            font-family: 'Inter', sans-serif;
            background-color: var(--bg-color);
            color: var(--text-primary);
            line-height: 1.5;
            min-height: 100vh;
            display: flex;
            flex-direction: column;
        }}

        header {{
            background: rgba(30, 41, 59, 0.7);
            backdrop-filter: blur(12px);
            -webkit-backdrop-filter: blur(12px);
            border-bottom: 1px solid var(--border-color);
            padding: 1.5rem 2rem;
            position: sticky;
            top: 0;
            z-index: 100;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}

        h1 {{
            font-size: 1.5rem;
            font-weight: 700;
            letter-spacing: -0.025em;
            background: linear-gradient(to right, #f59e0b, #fbbf24);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }}

        .meta-info {{
            font-size: 0.875rem;
            color: var(--text-secondary);
            display: flex;
            align-items: center;
            gap: 1.5rem;
        }}

        .meta-info .badge {{
            background: var(--surface-hover);
            padding: 0.25rem 0.75rem;
            border-radius: 9999px;
            font-weight: 500;
            color: var(--text-primary);
        }}

        main {{
            padding: 2rem;
            flex: 1;
            overflow: hidden;
            display: flex;
            flex-direction: column;
        }}

        .table-container {{
            background: var(--surface-color);
            border: 1px solid var(--border-color);
            border-radius: 0.75rem;
            overflow: auto;
            flex: 1;
            box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05);
        }}

        table {{ width: 100%; border-collapse: collapse; text-align: left; white-space: nowrap; }}
        thead {{ position: sticky; top: 0; z-index: 10; background: var(--surface-color); }}
        th {{ padding: 0.75rem 1rem; border-bottom: 2px solid var(--border-color); vertical-align: top; }}
        
        .col-title {{
            font-size: 0.75rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: var(--text-secondary);
        }}

        tbody tr {{ border-bottom: 1px solid var(--border-color); transition: background-color 0.15s; }}
        tbody tr:hover {{ background-color: rgba(51, 65, 85, 0.5); }}
        td {{ padding: 0.75rem 1rem; font-size: 0.875rem; }}

        /* Rijen waarbij de koers binnen ±0.5 Z-score van de 20MA zit (pullback/consolidatie zone) */
        tbody tr.near-20ma {{ background-color: rgba(16, 185, 129, 0.07); }}
        tbody tr.near-20ma:hover {{ background-color: rgba(16, 185, 129, 0.14); }}
        tbody tr.near-20ma td {{ color: #6ee7b7; }}
        tbody tr.near-20ma td:first-child {{ font-weight: 600; }}

        /* Rijen waarbij koers onder de 50MA zit (verkoop/zwak) */
        tbody tr.under-50ma {{ background-color: rgba(239, 68, 68, 0.07); }}
        tbody tr.under-50ma:hover {{ background-color: rgba(239, 68, 68, 0.14); }}
        tbody tr.under-50ma td {{ color: #fca5a5; }}
        tbody tr.under-50ma td:first-child {{ font-weight: 600; }}

        .trend-bullish {{ color: #10b981; font-weight: bold; }}
        .trend-bearish {{ color: #ef4444; font-weight: bold; }}
        
        .delta-positive {{ color: #10b981; }}
        .delta-negative {{ color: #ef4444; }}

        .rank-top {{ background: rgba(16, 185, 129, 0.1); color: #34d399; font-weight: 600; }}

        ::-webkit-scrollbar {{ width: 8px; height: 8px; }}
        ::-webkit-scrollbar-track {{ background: var(--bg-color); }}
        ::-webkit-scrollbar-thumb {{ background: var(--surface-hover); border-radius: 4px; }}
        ::-webkit-scrollbar-thumb:hover {{ background: var(--text-secondary); }}
        
        #no-results {{ text-align: center; padding: 3rem; color: var(--text-secondary); display: none; }}
    </style>
</head>
<body>
    <header>
        <h1>IB Top 25 Zes Maanden Portfolio ⭐</h1>
        <div class="meta-info">
            <span>Laatste update: <strong>{current_time}</strong></span>
            <span class="badge" id="row-count">25 Aandelen</span>
        </div>
    </header>

    <main>
        <div class="table-container">
            <table id="data-table">
                <thead>
                    <tr id="table-headers"></tr>
                </thead>
                <tbody id="table-body"></tbody>
            </table>
            <div id="no-results">Geen aandelen gevonden die aan de strenge criteria voldoen.</div>
        </div>
    </main>

    <script>
        const rawData = {data_json};
        const columns = {json.dumps(columns)};

        const tableHeaders = document.getElementById('table-headers');
        const tableBody = document.getElementById('table-body');
        const noResults = document.getElementById('no-results');

        function renderHeaders() {{
            tableHeaders.innerHTML = '';
            columns.forEach(col => {{
                const th = document.createElement('th');
                const title = document.createElement('div');
                title.className = 'col-title';
                title.innerHTML = col;
                th.appendChild(title);
                tableHeaders.appendChild(th);
            }});
        }}

        function formatVal(col, val) {{
            if (val === null || val === undefined) return '';
            
            if (typeof val === 'number') {{
                // Percentage columns
                if (['Last month', 'Last 3 months', 'Last year', 'YTD Performance', '200 avg'].includes(col)) {{
                    return (val * 100).toFixed(2) + '%';
                }}
                
                // Keep some decimals for others
                if (['Beta', 'Efficiency Score', 'Sharpe Ratio', 'Z-score 20MA', 'Total score', 'Total score incl beta'].includes(col)) {{
                    return val.toFixed(2);
                }}
            }}
            return val;
        }}

        function renderTable() {{
            renderHeaders();

            tableBody.innerHTML = '';
            
            if (rawData.length === 0) {{
                noResults.style.display = 'block';
                return;
            }}
            
            noResults.style.display = 'none';

            rawData.forEach(row => {{
                const tr = document.createElement('tr');
                
                const action = row['Action'];
                if (action === 'S') {{
                    tr.classList.add('under-50ma');
                }} else if (action === 'B') {{
                    tr.classList.add('near-20ma');
                }}
                
                columns.forEach(col => {{
                    const td = document.createElement('td');
                    let val = row[col];
                    
                    let displayVal = formatVal(col, val);
                    
                    if (col === 'Trend') {{
                        if (val === 'Bullish') td.classList.add('trend-bullish');
                        else if (val === 'Bearish') td.classList.add('trend-bearish');
                    }}
                    
                    if (col === 'Delta') {{
                        if (val > 0) {{
                            td.classList.add('delta-positive');
                            displayVal = '+' + displayVal;
                        }} else if (val < 0) {{
                            td.classList.add('delta-negative');
                        }}
                    }}
                    
                    if (String(col).includes('Rank') && typeof val === 'number' && val <= 10 && val > 0) {{
                        td.classList.add('rank-top');
                    }}
                    
                    td.innerText = displayVal;
                    tr.appendChild(td);
                }});
                tableBody.appendChild(tr);
            }});
        }}

        // Init
        renderTable();
    </script>
</body>
</html>
"""
    with open(output_html, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"Top 25 HTML rapport gegenereerd: {output_html}")

if __name__ == "__main__":
    generate_top25_report('ib_screener_result_final.csv', 'ib_top25_portfolio.html')
