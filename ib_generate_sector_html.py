from ds_layout import apply_theme
import pandas as pd
from datetime import datetime
import json

def generate_sector_html_report(csv_file, output_html):
    df = pd.read_csv(csv_file, sep='|')
    # Zorg dat lege waarden None/null worden voor JSON
    df = df.where(pd.notnull(df), None)
    
    # Rename for cleaner display if needed
    df = df.rename(columns={
        'Sector_Rank': 'Rank',
        'Sector_Rank_past': 'Rank past (30d)',
        'GICS sector': 'Sector'
    })
    
    # Haal de kolomnamen op
    columns = df.columns.tolist()
        
    data = df.to_dict(orient='records')
    data_json = json.dumps(data)
    
    current_time = datetime.now().strftime("%d-%m-%Y %H:%M:%S")

    html = f"""<!DOCTYPE html>
<html lang="nl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>IB Sector Performance</title>
    <link rel="icon" href="data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22><text y=%22.9em%22 font-size=%2290%22>&#128200;</text></svg>">
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
            --accent-color: #3b82f6;
            --accent-hover: #60a5fa;
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
            background: linear-gradient(to right, #60a5fa, #a78bfa);
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

        .nav-links a {{
            color: var(--accent-color);
            text-decoration: none;
            font-weight: 500;
            margin-right: 15px;
        }}
        .nav-links a:hover {{
            text-decoration: underline;
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
        th {{ padding: 0; border-bottom: 2px solid var(--border-color); vertical-align: top; }}
        .th-content {{ padding: 0.75rem 1rem; display: flex; flex-direction: column; gap: 0.5rem; }}

        .col-title {{
            font-size: 0.875rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: var(--text-secondary);
            cursor: pointer;
            display: flex;
            align-items: center;
            gap: 0.25rem;
            user-select: none;
        }}
        
        .col-title:hover {{ color: var(--text-primary); }}

        tbody tr {{ border-bottom: 1px solid var(--border-color); transition: background-color 0.15s; }}
        tbody tr:hover {{ background-color: rgba(51, 65, 85, 0.5); }}
        td {{ padding: 0.75rem 1rem; font-size: 1rem; }}

        .delta-positive {{ color: #10b981; font-weight: 600; }}
        .delta-negative {{ color: #ef4444; font-weight: 600; }}
        
        .rank-top {{ background: rgba(16, 185, 129, 0.1); color: #34d399; font-weight: 700; }}

        ::-webkit-scrollbar {{ width: 8px; height: 8px; }}
        ::-webkit-scrollbar-track {{ background: var(--bg-color); }}
        ::-webkit-scrollbar-thumb {{ background: var(--surface-hover); border-radius: 4px; }}
        ::-webkit-scrollbar-thumb:hover {{ background: var(--text-secondary); }}
    </style>
</head>
<body>
    <header>
        <div>
            <h1>IB Sector Performance</h1>
            <div class="nav-links">
                <a href="ib_screener_dashboard.html">Terug naar Aandelen Overzicht</a>
            </div>
        </div>
        <div class="meta-info">
            <span>Laatste update: <strong>{current_time}</strong></span>
            <span class="badge" id="row-count">0 Sectoren</span>
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
        </div>
    </main>

    <script>
        const rawData = {data_json};
        const columns = {json.dumps(columns)};
        
        let sortCol = 'Rank';
        let sortAsc = true;

        const tableHeaders = document.getElementById('table-headers');
        const tableBody = document.getElementById('table-body');
        const rowCount = document.getElementById('row-count');

        function renderHeaders() {{
            tableHeaders.innerHTML = '';
            columns.forEach(col => {{
                const th = document.createElement('th');
                const content = document.createElement('div');
                content.className = 'th-content';
                
                const title = document.createElement('div');
                title.className = 'col-title';
                title.innerHTML = `${{col}} ${{sortCol === col ? (sortAsc ? '↑' : '↓') : ''}}`;
                title.onclick = () => handleSort(col);
                
                content.appendChild(title);
                th.appendChild(content);
                tableHeaders.appendChild(th);
            }});
        }}

        function handleSort(col) {{
            if (sortCol === col) {{
                sortAsc = !sortAsc;
            }} else {{
                sortCol = col;
                sortAsc = true;
            }}
            renderTable();
        }}

        function parseNum(val) {{
            if (val === null || val === undefined || val === 'N/A' || val === '') return null;
            if (typeof val === 'number') return val;
            let s = String(val).replace('%', '').trim();
            if (s.includes(',') && !s.includes('.')) {{
                s = s.replace(',', '.');
            }}
            const num = parseFloat(s);
            return isNaN(num) ? val : num;
        }}

        function formatVal(col, val) {{
            if (val === null || val === undefined) return '';
            
            if (typeof val === 'number') {{
                if (['Delta'].includes(col) && val > 0) {{
                    return '+' + val;
                }}
                if (Number.isInteger(val)) return val;
                return val.toFixed(1);
            }}
            return val;
        }}

        function renderTable() {{
            renderHeaders();
            
            let currentData = [...rawData];

            currentData.sort((a, b) => {{
                let valA = parseNum(a[sortCol]);
                let valB = parseNum(b[sortCol]);

                if (valA === null) return 1;
                if (valB === null) return -1;

                if (typeof valA === 'string' && typeof valB === 'string') {{
                    return sortAsc ? valA.localeCompare(valB) : valB.localeCompare(valA);
                }}

                if (valA < valB) return sortAsc ? -1 : 1;
                if (valA > valB) return sortAsc ? 1 : -1;
                return 0;
            }});

            tableBody.innerHTML = '';
            rowCount.innerText = `${{currentData.length}} Sectoren`;
            
            currentData.forEach(row => {{
                const tr = document.createElement('tr');
                
                columns.forEach(col => {{
                    const td = document.createElement('td');
                    let val = row[col];
                    
                    let displayVal = formatVal(col, val);
                    
                    if (col === 'Delta') {{
                        if (val > 0) {{
                            td.classList.add('delta-positive');
                        }} else if (val < 0) {{
                            td.classList.add('delta-negative');
                        }}
                    }}
                    
                    if (['Rank', 'Rank past (30d)'].includes(col) && typeof val === 'number' && val <= 3 && val > 0) {{
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
        f.write(apply_theme(html, 'ib'))
    print(f"Sector HTML rapport gegenereerd: {output_html}")

if __name__ == "__main__":
    generate_sector_html_report('ib_sector_result.csv', 'ib_sector_dashboard.html')
