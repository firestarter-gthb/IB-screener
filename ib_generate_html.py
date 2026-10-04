from ds_layout import apply_theme
import pandas as pd
from datetime import datetime
import json

def generate_html_report(csv_file, output_html):
    df = pd.read_csv(csv_file, sep='|')
    # Zorg dat lege waarden None/null worden voor JSON
    df = df.where(pd.notnull(df), None)
    
    # Haal de kolomnamen op
    columns = df.columns.tolist()
    if 'Action' in columns:
        columns.insert(0, columns.pop(columns.index('Action')))
        
    data = df.to_dict(orient='records')
    data_json = json.dumps(data)
    
    current_time = datetime.now().strftime("%d-%m-%Y %H:%M:%S")

    html = f"""<!DOCTYPE html>
<html lang="nl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>IB Momentum Screener</title>
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

        .clear-btn {{
            background: rgba(239, 68, 68, 0.1);
            color: #ef4444;
            border: 1px solid rgba(239, 68, 68, 0.2);
            padding: 0.375rem 0.75rem;
            border-radius: 0.375rem;
            font-size: 0.75rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s;
        }}
        .clear-btn:hover {{
            background: rgba(239, 68, 68, 0.2);
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
            font-size: 0.75rem;
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

        .filter-input, .filter-select {{
            width: 100%;
            background: var(--bg-color);
            border: 1px solid var(--border-color);
            color: var(--text-primary);
            padding: 0.375rem 0.5rem;
            border-radius: 0.375rem;
            font-size: 0.75rem;
            outline: none;
            transition: all 0.2s;
            font-family: inherit;
        }}

        .filter-input:focus, .filter-select:focus {{
            border-color: var(--accent-color);
            box-shadow: 0 0 0 1px var(--accent-color);
        }}
        
        .filter-select option {{ background: var(--surface-color); color: var(--text-primary); }}

        /* Multi-select Checkbox styling */
        .multi-select-container {{ position: relative; width: 100%; }}
        .multi-select-btn {{
            width: 100%;
            background: var(--bg-color);
            border: 1px solid var(--border-color);
            color: var(--text-primary);
            padding: 0.375rem 0.5rem;
            border-radius: 0.375rem;
            font-size: 0.75rem;
            cursor: pointer;
            text-align: left;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }}
        .multi-select-dropdown {{
            display: none;
            position: absolute;
            top: 100%;
            left: 0;
            min-width: 200px;
            max-height: 250px;
            overflow-y: auto;
            background: var(--surface-color);
            border: 1px solid var(--border-color);
            border-radius: 0.375rem;
            z-index: 1000;
            padding: 0.5rem;
            box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.5);
            margin-top: 4px;
        }}
        .multi-select-dropdown.show {{ display: block; }}
        .checkbox-item {{
            display: flex;
            align-items: center;
            gap: 0.5rem;
            padding: 0.25rem 0;
            color: var(--text-primary);
            cursor: pointer;
            font-size: 0.75rem;
        }}
        .checkbox-item input {{ cursor: pointer; }}
        .checkbox-item:hover {{ color: var(--accent-color); }}

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
        <h1>IB Momentum Screener</h1>
        <div class="meta-info">
            <button class="clear-btn" onclick="clearAllFilters()">✖ Filters wissen</button>
            <span>Laatste update: <strong>{current_time}</strong></span>
            <span class="badge" id="row-count">0 Aandelen</span>
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
            <div id="no-results">Geen aandelen gevonden die aan je filters voldoen.</div>
        </div>
    </main>

    <script>
        const rawData = {data_json};
        const columns = {json.dumps(columns)};
        
        const dropdownCols = ['Action', 'Trend'];
        const multiSelectCols = ['GICS sector', 'GICS industry'];
        
        let currentData = [...rawData];
        let filters = {{}};
        let sortCol = 'Rank all';
        let sortAsc = true;

        const tableHeaders = document.getElementById('table-headers');
        const tableBody = document.getElementById('table-body');
        const rowCount = document.getElementById('row-count');
        const noResults = document.getElementById('no-results');

        const uniqueValues = {{}};
        [...dropdownCols, ...multiSelectCols].forEach(col => {{
            const values = new Set();
            rawData.forEach(row => {{
                if (row[col] !== null && row[col] !== undefined) {{
                    values.add(String(row[col]));
                }}
            }});
            uniqueValues[col] = Array.from(values).sort();
        }});

        function toggleMultiSelect(col) {{
            const dropdown = document.getElementById(`multi-select-dropdown-${{col}}`);
            dropdown.classList.toggle('show');
        }}

        window.onclick = function(event) {{
            if (!event.target.matches('.multi-select-btn') && !event.target.closest('.multi-select-dropdown')) {{
                const dropdowns = document.getElementsByClassName('multi-select-dropdown');
                for (let i = 0; i < dropdowns.length; i++) {{
                    if (dropdowns[i].classList.contains('show')) {{
                        dropdowns[i].classList.remove('show');
                    }}
                }}
            }}
        }}

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
                
                if (multiSelectCols.includes(col)) {{
                    const container = document.createElement('div');
                    container.className = 'multi-select-container';
                    
                    const btn = document.createElement('button');
                    btn.className = 'multi-select-btn';
                    const activeCount = (filters[col] && filters[col].values) ? filters[col].values.length : 0;
                    btn.innerText = activeCount > 0 ? `${{activeCount}} geselecteerd` : 'Filter...';
                    btn.onclick = (e) => {{ e.stopPropagation(); toggleMultiSelect(col); }};
                    
                    const dropdown = document.createElement('div');
                    dropdown.className = 'multi-select-dropdown';
                    dropdown.id = `multi-select-dropdown-${{col}}`;
                    
                    const selectAllLabel = document.createElement('label');
                    selectAllLabel.className = 'checkbox-item select-all-item';
                    selectAllLabel.style.borderBottom = '1px solid var(--border-color)';
                    selectAllLabel.style.paddingBottom = '8px';
                    selectAllLabel.style.marginBottom = '8px';
                    selectAllLabel.style.fontWeight = '600';
                    
                    const selectAllCb = document.createElement('input');
                    selectAllCb.type = 'checkbox';
                    const isAllSelected = filters[col] && filters[col].values && filters[col].values.length === uniqueValues[col].length;
                    selectAllCb.checked = isAllSelected;
                    
                    selectAllCb.onchange = (e) => handleMultiFilterSelectAll(col, e.target.checked);
                    
                    selectAllLabel.appendChild(selectAllCb);
                    selectAllLabel.appendChild(document.createTextNode(' (Alle selecteren)'));
                    dropdown.appendChild(selectAllLabel);
                    
                    uniqueValues[col].forEach(val => {{
                        const label = document.createElement('label');
                        label.className = 'checkbox-item';
                        
                        const cb = document.createElement('input');
                        cb.type = 'checkbox';
                        cb.value = val;
                        
                        if (filters[col] && filters[col].values && filters[col].values.includes(val)) {{
                            cb.checked = true;
                        }}
                        
                        cb.onchange = (e) => handleMultiFilter(col, val, e.target.checked);
                        
                        label.appendChild(cb);
                        label.appendChild(document.createTextNode(val));
                        dropdown.appendChild(label);
                    }});
                    
                    container.appendChild(btn);
                    container.appendChild(dropdown);
                    content.appendChild(container);
                    
                }} else if (dropdownCols.includes(col)) {{
                    const filterElement = document.createElement('select');
                    filterElement.className = 'filter-select';
                    
                    const defaultOption = document.createElement('option');
                    defaultOption.value = '';
                    defaultOption.innerText = 'Alle...';
                    filterElement.appendChild(defaultOption);
                    
                    uniqueValues[col].forEach(val => {{
                        const option = document.createElement('option');
                        option.value = val.toLowerCase();
                        option.innerText = val;
                        if (filters[col] && filters[col].type === 'exact' && filters[col].value === val.toLowerCase()) {{
                            option.selected = true;
                        }}
                        filterElement.appendChild(option);
                    }});
                    
                    filterElement.onchange = (e) => handleTextFilter(col, e.target.value, true);
                    content.appendChild(filterElement);
                    
                }} else {{
                    const filterElement = document.createElement('input');
                    filterElement.id = 'filter-input-' + col.replace(/\\s+/g, '-');
                    filterElement.className = 'filter-input';
                    filterElement.placeholder = 'Filter...';
                    filterElement.type = 'text';
                    filterElement.value = (filters[col] && filters[col].type === 'text') ? filters[col].value : '';
                    filterElement.oninput = (e) => handleTextFilter(col, e.target.value, false);
                    content.appendChild(filterElement);
                }}
                
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
            applyFiltersAndSort();
        }}

        function handleTextFilter(col, value, isExactMatch) {{
            if (!value) {{
                delete filters[col];
            }} else {{
                filters[col] = {{ type: isExactMatch ? 'exact' : 'text', value: value.toLowerCase() }};
            }}
            applyFiltersAndSort();
        }}
        
        function handleMultiFilterSelectAll(col, isChecked) {{
            if (isChecked) {{
                filters[col] = {{ type: 'multi', values: [...uniqueValues[col]] }};
            }} else {{
                delete filters[col];
            }}
            applyFiltersAndSort();
        }}

        function handleMultiFilter(col, value, isChecked) {{
            if (!filters[col]) {{
                filters[col] = {{ type: 'multi', values: [] }};
            }}
            
            if (isChecked) {{
                if (!filters[col].values.includes(value)) {{
                    filters[col].values.push(value);
                }}
            }} else {{
                filters[col].values = filters[col].values.filter(v => v !== value);
            }}
            
            if (filters[col].values.length === 0) {{
                delete filters[col];
            }}
            
            applyFiltersAndSort();
        }}

        function clearAllFilters() {{
            filters = {{}};
            applyFiltersAndSort();
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
                // Percentage columns
                if (['Last month', 'Last 3 months', 'Last year', 'YTD Performance', '200 avg'].includes(col)) {{
                    return (val * 100).toFixed(2) + '%';
                }}
                
                // Keep some decimals for others
                if (['Current price', 'Beta', 'Efficiency Score', 'Sharpe Ratio', 'Z-score 20MA', 'Total score', 'Total score incl beta'].includes(col)) {{
                    return val.toFixed(2);
                }}
            }}
            return val;
        }}

        function applyFiltersAndSort() {{
            currentData = rawData.filter(row => {{
                for (const [col, filterObj] of Object.entries(filters)) {{
                    const cellVal = String(row[col] || '');
                    
                    if (filterObj.type === 'multi') {{
                        if (!filterObj.values.includes(cellVal)) return false;
                    }} else if (filterObj.type === 'exact') {{
                        if (cellVal.toLowerCase() !== filterObj.value) return false;
                    }} else if (filterObj.type === 'text') {{
                        if (!cellVal.toLowerCase().includes(filterObj.value)) return false;
                    }}
                }}
                return true;
            }});

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

            renderTable();
        }}

        function renderTable() {{
            const activeElem = document.activeElement;
            const activeId = activeElem ? activeElem.id : null;

            renderHeaders();
            
            if (activeId) {{
                const el = document.getElementById(activeId);
                if (el) {{
                    el.focus();
                    if (typeof el.selectionStart == "number") {{
                        el.selectionStart = el.selectionEnd = el.value.length;
                    }}
                }}
            }}

            tableBody.innerHTML = '';
            rowCount.innerText = `${{currentData.length}} Aandelen`;
            
            if (currentData.length === 0) {{
                noResults.style.display = 'block';
                return;
            }}
            
            noResults.style.display = 'none';
            
            const renderData = currentData.slice(0, 500);

            renderData.forEach(row => {{
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
        applyFiltersAndSort();
    </script>
</body>
</html>
"""
    with open(output_html, 'w', encoding='utf-8') as f:
        f.write(apply_theme(html, 'ib'))
    print(f"HTML rapport gegenereerd: {output_html}")

if __name__ == "__main__":
    generate_html_report('ib_screener_result_final.csv', 'ib_screener_dashboard.html')
