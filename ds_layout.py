"""
ds_layout.py — DataSente huisstijl (neo-brutalist): één bron voor menu, footer en dashboard-thema.

Dit bestand is de CANONIEKE versie (datasente/tools/ds_layout.py).
Kopieën staan in de bronmappen van de screeners (IB-screener, deGiro-ETF-screener,
SP500-Dashboard) zodat elke nieuwe data-run automatisch in de huisstijl wordt opgemaakt.
Wijzig dit bestand alleen hier en kopieer het daarna met tools/sync_theme.bat.

Gebruik in een generator:
    from ds_layout import apply_theme
    html = apply_theme(html, 'momentum')          # vóór het wegschrijven van het bestand

Gebruik voor de website zelf: zie tools/sync_layout.py.
"""
import colorsys
import json
import re

YEAR = 2026
FONT_LINKS = (
    '<link rel="preconnect" href="https://fonts.googleapis.com">'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
    '<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&amp;family=Space+Mono:wght@400;700&amp;display=swap" rel="stylesheet">'
)

# ---------------------------------------------------------------------------
# Pagina's & navigatiemodel
# ---------------------------------------------------------------------------
PAGES = {  # key: (nl, en)
    'home': ('index_nl.html', 'index.html'),
    'solutions': ('solutions_nl.html', 'solutions.html'),
    'options': ('options_nl.html', 'options.html'),
    'strategies': ('strategies_nl.html', 'strategies.html'),
    'go': ('go_nl.html', 'go.html'),
    'insights': ('insights_nl.html', 'insights.html'),
    'github': ('github_nl.html', 'github.html'),
    'about': ('about_nl.html', 'about.html'),
    'es': ('es_short_put_handleiding.html', 'es_short_put_guide.html'),
    'pres': ('presidential_cycle_handleiding.html', 'presidential_cycle_guide.html'),
    'annual': ('annual_cycle_handleiding.html', 'annual_cycle_guide.html'),
    'cc': ('covered_call_handleiding.html', 'covered_call_guide.html'),
    'meic': ('meic_nl.html', 'meic.html'),
}

# Dashboards: key -> (bestand, titel NL, titel EN, sectie)
DASHBOARDS = {
    'entry': ('entry_dashboard.html', 'S&P 500 Entry-dashboard', 'S&P 500 Entry Dashboard', 'spx'),
    'ib': ('ib_screener_dashboard.html', 'Stock Momentum-screener', 'Stock Momentum Screener', 'ib'),
    'ib25': ('ib_top25_portfolio.html', 'Stock Top 25-portefeuille', 'Stock Top 25 Portfolio', 'ib'),
    'momentum_seasonality': ('momentum_seasonality.html', 'Momentum Seasonality', 'Momentum Seasonality', 'degiro'),
    'momentum': ('momentum_screener_dashboard.html', 'ETF Momentum-screener', 'ETF Momentum Screener', 'degiro'),
    'momentum30': ('momentum_top30_portfolio.html', 'Momentum Top 30-portefeuille', 'Momentum Top 30 Portfolio', 'degiro'),
    'dividend': ('dividend_screener_dashboard.html', 'ETF Dividend-screener', 'ETF Dividend Screener', 'degiro'),
    'dividend30': ('dividend_top30_portfolio.html', 'Dividend Top 30-portefeuille', 'Dividend Top 30 Portfolio', 'degiro'),
    'fundamentals': ('fundamentals_screener_dashboard.html', 'ETF Fundamentals & risico', 'ETF Fundamentals & Risk', 'degiro'),
    'fundamentals30': ('fundamentals_top30_portfolio.html', 'Fundamentals Top 30-portefeuille', 'Fundamentals Top 30 Portfolio', 'degiro'),
}

STRATS = [  # tab-id, naam (NL, EN)
    ('strat-1', 'Short Put (naked)', 'Short Put (naked)'),
    ('strat-2', 'Jade Lizard', 'Jade Lizard'),
    ('strat-3', 'Covered Call', 'Covered Call'),
    ('strat-4', 'Short Put Spread', 'Short Put Spread'),
    ('strat-5', 'Put Ratio Spread', 'Put Ratio Spread'),
    ('strat-6', 'Short Call Spread', 'Short Call Spread'),
    ('strat-7', 'Broken Wing Butterfly', 'Broken Wing Butterfly'),
    ('strat-8', 'Unbalanced Iron Condor', 'Unbalanced Iron Condor'),
    ('strat-9', 'Iron Condor', 'Iron Condor'),
    ('strat-10', 'Short Strangle', 'Short Strangle'),
    ('strat-11', 'Pairs Trading', 'Pairs Trading'),
]

T = {
    'nl': dict(skip='Naar inhoud', main_menu='Hoofdmenu', mobile_menu='Mobiel menu', open='Menu openen',
               close='Menu sluiten', solutions='Oplossingen', strategies='Strategieën', dashboards='Dashboards',
               insights='Insights', about='Over ons', contact='Contact', services='Diensten', knowledge='Kennis',
               sol='Oplossingen & diensten', opt='Optiehandel', go='DataSente & Go', blog='Insights (blog)',
               gh='GitHub-portfolio', guides='Handleidingen & research', systematic='Systematische strategieën',
               all_strats='Alle strategieën', es='ES Short Put', pres='Presidentscyclus', annual='Jaarcyclus',
               cc='Covered Call', meic='MEIC-tranches', core='KERN', study='STUDIE',
               spx='Dashboards', ibg='Stock screener', degiro='ETF screener',
               tagline='Data engineering en trading automation voor family offices en vermogensbeheerders. Behoud het initiatief — behoud Sente.',
               cta='Neem contact op', rights='Alle rechten voorbehouden.',
               disclaimer='Disclaimer: handelen in opties en futures brengt aanzienlijke risico’s met zich mee en is niet geschikt voor iedere belegger. De informatie op deze website is uitsluitend bedoeld voor educatieve doeleinden en vormt geen financieel advies of beleggingsadvies.',
               nav='Navigatie', lang_label='Taal'),
    'en': dict(skip='Skip to content', main_menu='Main menu', mobile_menu='Mobile menu', open='Open menu',
               close='Close menu', solutions='Solutions', strategies='Strategies', dashboards='Dashboards',
               insights='Insights', about='About us', contact='Contact', services='Services', knowledge='Knowledge',
               sol='Solutions & Services', opt='Option Trading', go='DataSente & Go', blog='Insights (blog)',
               gh='GitHub portfolio', guides='Guides & research', systematic='Systematic strategies',
               all_strats='All strategies', es='ES Short Put', pres='Presidential Cycle', annual='Annual Cycle',
               cc='Covered Call', meic='MEIC tranches', core='CORE', study='STUDY',
               spx='Dashboards', ibg='Stock screener', degiro='ETF screener',
               tagline='Data engineering and trading automation for family offices and wealth managers. Keep the initiative — keep Sente.',
               cta='Get in touch', rights='All rights reserved.',
               disclaimer='Disclaimer: trading options and futures involves substantial risk and is not suitable for every investor. The information on this website is for educational purposes only and does not constitute financial or investment advice.',
               nav='Navigation', lang_label='Language'),
}

ICON_CHEV = '<svg viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="square"><path d="m6 9 6 6 6-6"/></svg>'
ICON_CLOSE = '<svg viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="square"><path d="M6 6l12 12M18 6 6 18"/></svg>'


def _esc(s):
    return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def page(key, lang):
    nl, en = PAGES[key]
    return nl if lang == 'nl' else en


def dash(key, lang):
    return f'{DASHBOARDS[key][0]}?lang={lang}'


def nav_model(lang):
    t = T[lang]
    p = lambda k: page(k, lang)
    strat = p('strategies')
    d = lambda k: (DASHBOARDS[k][1] if lang == 'nl' else DASHBOARDS[k][2], dash(k, lang))
    return [
        dict(key='home', label='Home', href=p('home')),
        dict(key='sol', label=t['solutions'], cols=2, narrow=True, groups=[
            dict(title=t['services'], links=[(t['sol'], p('solutions')), (t['opt'], p('options')), (t['go'], p('go'))]),
            dict(title=t['knowledge'], links=[(t['blog'], p('insights')), (t['gh'], p('github'))]),
        ]),
        dict(key='strat', label=t['strategies'], cols=2, wide=True, groups=[
            dict(title=t['guides'], links=[(t['es'], p('es'), t['core']), (t['pres'], p('pres'), t['study']),
                                           (t['annual'], p('annual'), t['study']), (t['cc'], p('cc')),
                                           (t['meic'], p('meic')), (t['all_strats'] + ' →', strat)]),
            dict(title=t['systematic'], two=True,
                 links=[(nl if lang == 'nl' else en, f'{strat}#{sid}') for sid, nl, en in STRATS]),
        ]),
        dict(key='dash', label=t['dashboards'], cols=3, groups=[
            dict(title=t['spx'], links=[d('entry'), d('momentum_seasonality')]),
            dict(title=t['ibg'], links=[d('ib'), d('ib25')]),
            dict(title=t['degiro'], two=True, links=[d('momentum'), d('momentum30'), d('dividend'), d('dividend30'),
                                                     d('fundamentals'), d('fundamentals30')]),
        ]),
        dict(key='insights', label=t['insights'], href=p('insights')),
        dict(key='about', label=t['about'], href=p('about')),
    ]


def _strip_q(h):
    return h.split('?')[0].split('#')[0]


def _link(l, current):
    text, href = l[0], l[1]
    tag = l[2] if len(l) > 2 else None
    cur = ' aria-current="page"' if current and _strip_q(href) == current and '#' not in href else ''
    tg = f'<span class="tag">{tag}</span>' if tag else ''
    return f'<a href="{href}"{cur}>{_esc(text)}{tg}</a>'


def render_header(lang, active=None, current=None, alt_href=None, tag='header', lang_hrefs=None):
    """Header + desktop mega-menu + mobiel overlay-menu.

    lang       'nl' | 'en'
    active     key van het hoofdmenu-item dat actief is (home/sol/strat/dash/insights/about)
    current    bestandsnaam van de huidige pagina (voor aria-current)
    alt_href   link naar dezelfde pagina in de andere taal
    tag        'header' voor site-pagina's, 'div' voor dashboards (voorkomt CSS-conflicten)
    """
    t = T[lang]
    nav = nav_model(lang)
    home = page('home', lang)
    if lang_hrefs is None:
        other = alt_href or page('home', 'en' if lang == 'nl' else 'nl')
        lang_hrefs = {'nl': other if lang == 'en' else current or home, 'en': other if lang == 'nl' else current or home}
    lang_html = (f'<div class="lang" aria-label="{t["lang_label"]}">'
                 f'<a href="{lang_hrefs["en"]}" hreflang="en" lang="en"{" class=on aria-current=true" if lang == "en" else ""}>EN</a>'
                 f'<span class="sep" aria-hidden="true">/</span>'
                 f'<a href="{lang_hrefs["nl"]}" hreflang="nl" lang="nl"{" class=on aria-current=true" if lang == "nl" else ""}>NL</a></div>')
    contact = f'{page("about", lang)}#contact'
    brand = f'<a href="{home}" class="brand" aria-label="DataSente — home"><span class="brand-mark" aria-hidden="true"></span><span class="brand-txt">DataSente</span></a>'

    desk, mob = [], []
    for n in nav:
        act = ' active' if n['key'] == active else ''
        if 'groups' not in n:
            cur = ' aria-current="page"' if current == n['href'] else ''
            desk.append(f'<li class="desk-item"><a class="desk-link{act}" href="{n["href"]}"{cur}>{n["label"]}</a></li>')
            mob.append(f'<a class="m-link{act}" href="{n["href"]}"{cur}>{n["label"]}</a>')
            continue
        mid = f'mega-{n["key"]}'
        cls = 'mega' + (' narrow' if n.get('narrow') else '') + (' wide' if n.get('wide') else '') + f' cols-{n["cols"]}'
        cols = ''.join(
            f'<div class="mega-col{" two-col" if g.get("two") else ""}"><h5>{_esc(g["title"])}</h5>'
            f'<div class="links">{"".join(_link(l, current) for l in g["links"])}</div></div>' for g in n['groups'])
        desk.append(f'<li class="desk-item{act}" data-key="{n["key"]}"><button type="button" class="desk-trigger" '
                    f'aria-expanded="false" aria-controls="{mid}">{n["label"]}{ICON_CHEV}</button>'
                    f'<div class="{cls}" id="{mid}">{cols}</div></li>')
        inner = ''.join(f'<div class="grp">{_esc(g["title"])}</div><div class="{"grid2" if g.get("two") else "list"}">'
                        f'{"".join(_link(l, current) for l in g["links"])}</div>' for g in n['groups'])
        mob.append(f'<div class="acc{act}" data-key="{n["key"]}"><button type="button" class="acc-btn" aria-expanded="false">'
                   f'{n["label"]}{ICON_CHEV}</button><div class="acc-panel"><div class="acc-inner">{inner}</div></div></div>')

    return (
        f'<a class="skip-link" href="#main">{t["skip"]}</a>'
        f'<{tag} class="site-header" id="top"{" role=banner" if tag != "header" else ""}><div class="hdr-inner">{brand}'
        f'<nav class="desk-nav" aria-label="{t["main_menu"]}"><ul class="desk-list">{"".join(desk)}</ul></nav>'
        f'<div class="hdr-actions">{lang_html}<a href="{contact}" class="hdr-cta">{t["contact"]}</a>'
        f'<button type="button" class="menu-btn" aria-label="{t["open"]}" aria-controls="mnav" aria-expanded="false">'
        f'<span></span><span></span><span></span></button></div></div></{tag}>'
        f'<aside class="mnav" id="mnav" aria-label="{t["mobile_menu"]}" aria-hidden="true">'
        f'<div class="mnav-head">{brand}<button type="button" class="mnav-close" data-close aria-label="{t["close"]}">{ICON_CLOSE}</button></div>'
        f'<div class="mnav-body">{"".join(mob)}</div>'
        f'<div class="mnav-foot">{lang_html}<a href="{contact}" class="hdr-cta">{t["contact"]}</a></div></aside>'
        f'<span id="main" class="main-anchor" tabindex="-1"></span>'
    )


def render_footer(lang, tag='footer'):
    t = T[lang]
    p = lambda k: page(k, lang)
    nm = lambda k: DASHBOARDS[k][1] if lang == 'nl' else DASHBOARDS[k][2]
    cols = [
        (t['solutions'], [(t['sol'], p('solutions')), (t['opt'], p('options')), (t['go'], p('go')),
                          (t['blog'], p('insights')), (t['gh'], p('github')), (t['about'], p('about'))]),
        (t['strategies'], [(t['all_strats'], p('strategies')), (t['es'], p('es')), (t['meic'], p('meic')),
                           (t['pres'], p('pres')), (t['annual'], p('annual')), (t['cc'], p('cc'))]),
        (t['dashboards'], [(nm('entry'), dash('entry', lang)), (nm('ib'), dash('ib', lang)),
                           (nm('momentum_seasonality'), dash('momentum_seasonality', lang)),
                           (nm('momentum'), dash('momentum', lang)), (nm('dividend'), dash('dividend', lang)),
                           (nm('fundamentals'), dash('fundamentals', lang))]),
    ]
    def _ul(links):
        return ''.join('<li><a href="%s">%s</a></li>' % (u, _esc(x)) for x, u in links)
    col_html = ''.join(f'<div><h5>{_esc(h)}</h5><ul>{_ul(links)}</ul></div>' for h, links in cols)
    return (
        f'<{tag} class="site-footer"{" role=contentinfo" if tag != "footer" else ""}><div class="ft-wrap"><div class="ft-grid">'
        f'<div class="ft-brand"><a href="{p("home")}" class="brand"><span class="brand-mark" aria-hidden="true"></span>'
        f'<span class="brand-txt">DataSente</span></a><p>{_esc(t["tagline"])}</p>'
        f'<a class="ft-cta" href="{p("about")}#contact">{t["cta"]} →</a></div>{col_html}</div>'
        f'<div class="ft-bottom"><span>&copy; {YEAR} DataSente. {t["rights"]}</span><span>{_esc(t["disclaimer"])}</span></div>'
        f'</div></{tag}>'
    )


# ---------------------------------------------------------------------------
# Layout-CSS (tokens + header + mobiel menu + footer). Wordt door sync_layout.py
# naar css/layout.css geschreven en in dashboards inline opgenomen.
# ---------------------------------------------------------------------------
LAYOUT_CSS = r"""
:root{
  --bg:#f3f0e8;--bg-2:#e9e4d6;--surface:#fff;--surface-2:#f1eee5;
  --ink:#111;--muted:#4a4a4a;--line:#111;
  --lime:#c6f432;--violet:#a78bfa;--coral:#ffb4a2;--sky:#9fd8ff;
  --pos:#0f8a3c;--neg:#d92d20;--link:#5b21b6;
  --font-head:'Space Grotesk',system-ui,sans-serif;--font-body:'Space Grotesk',system-ui,sans-serif;--font-mono:'Space Mono',ui-monospace,monospace;
  --shadow:6px 6px 0 var(--ink);--shadow-sm:4px 4px 0 var(--ink);
  --header-h:72px;--maxw:1200px;--ease:cubic-bezier(.22,1,.36,1);
}
html.nav-open{overflow:hidden}
.skip-link{position:absolute;left:-999px;top:8px;z-index:3000;padding:.5rem 1rem;background:var(--lime);color:var(--ink);border:3px solid var(--ink);font:700 .9rem var(--font-body)}
.skip-link:focus{left:8px}
.main-anchor{display:block;height:0;outline:0}
.site-header{position:sticky;top:0;z-index:1000;height:var(--header-h);background:var(--bg);border-bottom:3px solid var(--ink);font-family:var(--font-body);color:var(--ink);transition:box-shadow .25s}
.site-header.scrolled{box-shadow:0 6px 0 rgba(17,17,17,.12)}
.site-header *,.mnav *,.site-footer *{box-sizing:border-box}
.hdr-inner{position:relative;height:100%;width:min(var(--maxw),100% - 2rem);margin-inline:auto;display:flex;align-items:center;gap:1.25rem}
.brand{display:inline-flex;align-items:center;gap:.6rem;font:700 1.35rem/1 var(--font-head);letter-spacing:-.04em;text-transform:uppercase;color:var(--ink);text-decoration:none;flex-shrink:0}
.brand-mark{width:22px;height:22px;background:var(--ink);box-shadow:3px 3px 0 var(--violet);flex-shrink:0}
.desk-nav{margin-left:auto}
.desk-list{display:flex;align-items:center;gap:.15rem;list-style:none;margin:0;padding:0}
.desk-item{position:static}
.desk-link,.desk-trigger{display:inline-flex;align-items:center;gap:.35rem;padding:.55rem .8rem;font:700 .84rem/1 var(--font-body);text-transform:uppercase;letter-spacing:.01em;color:var(--ink);background:none;border:2px solid transparent;cursor:pointer;text-decoration:none;transition:background .15s,border-color .15s}
.desk-link:hover,.desk-trigger:hover,.desk-item.open>.desk-trigger{background:var(--lime);border-color:var(--ink)}
.desk-link.active,.desk-item.active>.desk-trigger{border-color:var(--ink);background:var(--surface)}
.desk-trigger svg{width:14px;height:14px;transition:transform .2s var(--ease)}
.desk-item.open>.desk-trigger svg{transform:rotate(180deg)}
.mega{position:absolute;top:calc(100% + 6px);left:50%;width:min(940px,calc(100vw - 2rem));transform:translate(-50%,8px);background:var(--surface);border:3px solid var(--ink);box-shadow:8px 8px 0 var(--ink);padding:1.4rem;display:grid;gap:1.5rem;grid-template-columns:repeat(3,minmax(0,1fr));opacity:0;visibility:hidden;pointer-events:none;transition:opacity .15s,transform .2s var(--ease),visibility .15s}
.mega.cols-2{grid-template-columns:1fr 1.4fr}
.mega.cols-3{grid-template-columns:1fr 1fr 1.6fr}
.mega.narrow{width:min(560px,calc(100vw - 2rem));grid-template-columns:1fr 1fr}
.desk-item.open>.mega{opacity:1;visibility:visible;pointer-events:auto;transform:translate(-50%,0)}
.mega-col h5{font:700 .72rem/1.2 var(--font-mono);letter-spacing:.08em;text-transform:uppercase;color:var(--ink);background:var(--violet);display:inline-block;padding:.2rem .5rem;margin:0 0 .7rem}
.mega-col a{display:flex;align-items:center;gap:.6rem;padding:.45rem .6rem;margin-inline:-.6rem;font:500 .93rem/1.3 var(--font-body);color:var(--ink);text-decoration:none;border:2px solid transparent}
.mega-col a:hover,.mega-col a:focus-visible{background:var(--lime);border-color:var(--ink)}
.mega-col a[aria-current]{text-decoration:underline;text-decoration-thickness:3px;text-underline-offset:4px}
.mega-col .tag,.acc-inner .tag{margin-left:auto;font:700 .62rem/1 var(--font-mono);letter-spacing:.04em;padding:.22rem .4rem;background:var(--ink);color:var(--lime)}
.mega-col.two-col .links{display:grid;grid-template-columns:1fr 1fr;column-gap:1.2rem}
.hdr-actions{display:flex;align-items:center;gap:.8rem;flex-shrink:0}
.lang{display:inline-flex;align-items:center;gap:.3rem;font:700 .82rem/1 var(--font-mono)}
.lang a{color:var(--muted);text-decoration:none;padding:.25rem .3rem;border:2px solid transparent}
.lang a:hover{color:var(--ink);border-color:var(--ink)}
.lang a.on{color:var(--ink);background:var(--lime);border-color:var(--ink)}
.lang .sep{opacity:.4}
.hdr-cta,.ft-cta{display:inline-flex;align-items:center;justify-content:center;gap:.4rem;padding:.6rem 1rem;font:700 .82rem/1 var(--font-body);text-transform:uppercase;color:var(--ink);background:var(--lime);border:3px solid var(--ink);box-shadow:var(--shadow-sm);text-decoration:none;white-space:nowrap;transition:transform .15s,box-shadow .15s}
.hdr-cta:hover,.ft-cta:hover{transform:translate(-2px,-2px);box-shadow:6px 6px 0 var(--ink)}
.hdr-cta:active,.ft-cta:active{transform:translate(2px,2px);box-shadow:0 0 0 var(--ink)}
.menu-btn{display:none;position:relative;width:46px;height:46px;border:3px solid var(--ink);background:var(--lime);box-shadow:3px 3px 0 var(--ink);cursor:pointer;padding:0}
.menu-btn span{position:absolute;left:10px;right:10px;height:3px;background:var(--ink);transition:transform .25s var(--ease),opacity .2s}
.menu-btn span:nth-child(1){top:12px}.menu-btn span:nth-child(2){top:19px}.menu-btn span:nth-child(3){top:26px}
html.nav-open .menu-btn span:nth-child(1){transform:translateY(7px) rotate(45deg)}
html.nav-open .menu-btn span:nth-child(2){opacity:0}
html.nav-open .menu-btn span:nth-child(3){transform:translateY(-7px) rotate(-45deg)}
:focus-visible{outline:3px solid var(--ink);outline-offset:2px}
/* Mobiel overlay-menu: altijd binnen 100dvh, scrollt intern */
.mnav{position:fixed;inset:0;z-index:1500;height:100vh;height:100dvh;display:flex;flex-direction:column;background:var(--lime);color:var(--ink);font-family:var(--font-body);visibility:hidden;opacity:0;transform:scale(1.02);transition:opacity .25s,transform .3s var(--ease),visibility .3s}
html.nav-open .mnav{visibility:visible;opacity:1;transform:none}
.mnav-head{display:flex;align-items:center;justify-content:space-between;padding:.9rem 1.1rem;border-bottom:3px solid var(--ink);flex-shrink:0}
.mnav-close{width:46px;height:46px;display:grid;place-items:center;border:3px solid var(--ink);background:var(--surface);box-shadow:3px 3px 0 var(--ink);cursor:pointer;color:var(--ink);padding:0}
.mnav-close svg{width:20px;height:20px}
.mnav-body{flex:1 1 auto;min-height:0;overflow-y:auto;overscroll-behavior:contain;-webkit-overflow-scrolling:touch;padding:.5rem 1.1rem 1.25rem}
.mnav-foot{flex-shrink:0;display:flex;align-items:center;justify-content:space-between;gap:1rem;padding:.9rem 1.1rem calc(.9rem + env(safe-area-inset-bottom));border-top:3px solid var(--ink)}
.mnav .lang a{color:var(--ink)}
.mnav .lang a.on{background:var(--surface)}
.mnav .hdr-cta{background:var(--surface)}
.m-link,.acc-btn{width:100%;display:flex;align-items:center;justify-content:space-between;padding:.85rem .2rem;font:700 clamp(1.45rem,7vw,2rem)/1.05 var(--font-head);letter-spacing:-.04em;text-transform:uppercase;text-align:left;color:var(--ink);background:none;border:0;border-bottom:3px solid var(--ink);cursor:pointer;text-decoration:none}
.m-link.active,.acc.active>.acc-btn{text-decoration:underline;text-decoration-thickness:4px;text-underline-offset:6px}
.acc-btn svg{width:22px;height:22px;flex-shrink:0;transition:transform .25s var(--ease)}
.acc.open>.acc-btn svg{transform:rotate(180deg)}
.acc-panel{display:grid;grid-template-rows:0fr;transition:grid-template-rows .3s var(--ease)}
.acc.open>.acc-panel{grid-template-rows:1fr}
.acc-inner{overflow:hidden}
.acc-inner .grp{font:700 .72rem/1 var(--font-mono);letter-spacing:.08em;text-transform:uppercase;padding:1rem .2rem .45rem}
.acc-inner a{display:flex;align-items:center;gap:.5rem;padding:.55rem .6rem;font:600 1rem/1.3 var(--font-body);color:var(--ink);text-decoration:none;border:2px solid transparent}
.acc-inner a:hover,.acc-inner a:active{background:var(--surface);border-color:var(--ink)}
.acc-inner a[aria-current]{text-decoration:underline;text-decoration-thickness:3px}
.acc-inner .grid2{display:grid;grid-template-columns:1fr 1fr}
.acc-inner .grid2 a{font-size:.9rem}
.acc-inner>.list:last-child,.acc-inner>.grid2:last-child{padding-bottom:.9rem}
@media (max-width:1099px){
  .desk-nav,.hdr-actions .hdr-cta,.hdr-actions .lang{display:none}
  .hdr-actions{margin-left:auto}
  .menu-btn{display:block}
  :root{--header-h:64px}
}
@media (min-width:1100px){.mnav{display:none}}
@media (max-width:380px){.acc-inner .grid2{grid-template-columns:1fr}}
/* Footer */
.site-footer{background:var(--violet);border-top:3px solid var(--ink);color:var(--ink);font-family:var(--font-body);padding:3.5rem 0 2rem;margin-top:0}
.ft-wrap{width:min(var(--maxw),100% - 2.5rem);margin-inline:auto}
.ft-grid{display:grid;grid-template-columns:1.5fr 1fr 1fr 1.2fr;gap:2rem}
.ft-brand p{margin:.9rem 0 1.2rem;max-width:340px;font-size:.95rem;line-height:1.55}
.site-footer h5{font:700 .75rem/1 var(--font-mono);letter-spacing:.08em;text-transform:uppercase;margin:0 0 1rem;padding-bottom:.5rem;border-bottom:3px solid var(--ink)}
.site-footer ul{list-style:none;margin:0;padding:0;display:grid;gap:.45rem;font-size:.93rem}
.site-footer ul a{color:var(--ink);text-decoration:none;font-weight:500}
.site-footer ul a:hover{text-decoration:underline;text-decoration-thickness:2px;text-underline-offset:3px}
.ft-bottom{margin-top:2.5rem;padding-top:1.25rem;border-top:3px solid var(--ink);display:grid;gap:.6rem;font-size:.8rem;line-height:1.5}
@media (max-width:900px){.ft-grid{grid-template-columns:1fr 1fr}}
@media (max-width:560px){.ft-grid{grid-template-columns:1fr}}
@media (prefers-reduced-motion:reduce){.site-header *,.mnav,.mnav *,.mega{transition:none!important}}
"""

# ---------------------------------------------------------------------------
# Layout-JS: header-schaduw, mega-menu, mobiel overlay, taalblokken (dashboards)
# ---------------------------------------------------------------------------
LAYOUT_JS = r"""
(function(){
  var root=document.documentElement;
  /* Dashboards bevatten een NL- en EN-header; kies de taal (?lang= > localStorage > nl) */
  var blocks=document.querySelectorAll('[data-lang-block]');
  if(blocks.length){
    var q=new URLSearchParams(location.search).get('lang'),lang='nl';
    try{lang=(q||localStorage.getItem('ds-lang')||'nl').toLowerCase();if(q)localStorage.setItem('ds-lang',lang);}catch(e){lang=(q||'nl').toLowerCase();}
    if(lang!=='en')lang='nl';
    blocks.forEach(function(b){if(b.getAttribute('data-lang-block')!==lang)b.parentNode.removeChild(b);else b.hidden=false;});
    root.lang=lang;
    var mt=document.querySelector('meta[name="ds-title-'+lang+'"]');if(mt)document.title=mt.content;
    if(lang==='en'&&window.DS_I18N)dsTranslate(window.DS_I18N);
    var content=document.querySelector('.ds-content');
    if(content){content.querySelectorAll('table').forEach(function(tb){
      for(var el=tb.parentElement;el&&el!==content;el=el.parentElement){var o=getComputedStyle(el).overflowX;if(o==='auto'||o==='scroll')return;}
      var w=document.createElement('div');w.className='ds-scroll';tb.parentNode.insertBefore(w,tb);w.appendChild(tb);});}
  }
  function dsTranslate(dict){
    var keys=Object.keys(dict).sort(function(a,b){return b.length-a.length;});
    function tr(s){var o=s;for(var i=0;i<keys.length;i++){if(o.indexOf(keys[i])>-1)o=o.split(keys[i]).join(dict[keys[i]]);}return o;}
    function walk(node){
      if(node.nodeType===3){var v=node.nodeValue;if(v&&v.trim()){var n=tr(v);if(n!==v)node.nodeValue=n;}return;}
      if(node.nodeType!==1)return;
      var tag=node.tagName;if(tag==='SCRIPT'||tag==='STYLE'||tag==='TBODY'||node.classList.contains('site-header')||node.classList.contains('site-footer')||node.classList.contains('mnav'))return;
      ['placeholder','title','aria-label'].forEach(function(a){var v=node.getAttribute&&node.getAttribute(a);if(v){var n=tr(v);if(n!==v)node.setAttribute(a,n);}});
      for(var c=node.firstChild;c;c=c.nextSibling)walk(c);
    }
    walk(document.body);
    var busy=false,mo=new MutationObserver(function(ms){if(busy)return;busy=true;ms.forEach(function(m){m.addedNodes.forEach(walk);if(m.type==='characterData')walk(m.target);});busy=false;});
    mo.observe(document.body,{childList:true,subtree:true,characterData:true});
  }
  var hdr=document.querySelector('.site-header');
  if(hdr){var onS=function(){hdr.classList.toggle('scrolled',window.scrollY>8);};addEventListener('scroll',onS,{passive:true});onS();}
  /* Desktop mega-menu: klik + hover (met korte vertraging) */
  var items=[].slice.call(document.querySelectorAll('.desk-item[data-key]'));
  function closeAll(except){items.forEach(function(it){if(it!==except){it.classList.remove('open');it.querySelector('.desk-trigger').setAttribute('aria-expanded','false');}});}
  items.forEach(function(it){
    var btn=it.querySelector('.desk-trigger'),t;
    function open(){clearTimeout(t);closeAll(it);it.classList.add('open');btn.setAttribute('aria-expanded','true');}
    btn.addEventListener('click',function(e){e.stopPropagation();it.classList.contains('open')?closeAll():open();});
    it.addEventListener('mouseenter',function(){if(matchMedia('(hover:hover)').matches)open();});
    it.addEventListener('mouseleave',function(){t=setTimeout(function(){it.classList.remove('open');btn.setAttribute('aria-expanded','false');},200);});
    it.addEventListener('focusout',function(e){if(!it.contains(e.relatedTarget)){it.classList.remove('open');btn.setAttribute('aria-expanded','false');}});
  });
  document.addEventListener('click',function(e){if(!e.target.closest||!e.target.closest('.desk-item'))closeAll();});
  /* Mobiel overlay-menu */
  var mnav=document.getElementById('mnav'),menuBtn=document.querySelector('.menu-btn');
  function setAcc(a,open){a.classList.toggle('open',open);a.querySelector('.acc-btn').setAttribute('aria-expanded',String(open));}
  function setNav(open){
    if(!mnav)return;root.classList.toggle('nav-open',open);mnav.setAttribute('aria-hidden',String(!open));
    if(menuBtn)menuBtn.setAttribute('aria-expanded',String(open));
    if(open){var act=mnav.querySelector('.acc.active');mnav.querySelectorAll('.acc').forEach(function(a){setAcc(a,a===act);});
      var c=mnav.querySelector('.mnav-close');if(c)setTimeout(function(){c.focus();},50);}
    else if(menuBtn&&mnav.contains(document.activeElement))menuBtn.focus();
  }
  if(menuBtn)menuBtn.addEventListener('click',function(){setNav(!root.classList.contains('nav-open'));});
  document.querySelectorAll('[data-close]').forEach(function(el){el.addEventListener('click',function(){setNav(false);});});
  if(mnav){
    mnav.querySelectorAll('.acc-btn').forEach(function(b){b.addEventListener('click',function(){
      var a=b.parentElement,open=!a.classList.contains('open');
      mnav.querySelectorAll('.acc').forEach(function(x){setAcc(x,false);});setAcc(a,open);
      if(open)setTimeout(function(){a.scrollIntoView({block:'nearest',behavior:'smooth'});},220);});});
    mnav.querySelectorAll('a').forEach(function(a){a.addEventListener('click',function(){setNav(false);});});
  }
  addEventListener('keydown',function(e){if(e.key==='Escape'){setNav(false);closeAll();}});
  matchMedia('(min-width: 1100px)').addEventListener('change',function(e){if(e.matches)setNav(false);});
})();
"""

# ---------------------------------------------------------------------------
# Kleur-conversie: donker (oud) -> licht neo-brutalist
# ---------------------------------------------------------------------------
BG_RGB = (243, 240, 232)
INK = '#111111'
MUTED = '#4a4a4a'
COLOR_RE = re.compile(r'#[0-9a-fA-F]{8}\b|#[0-9a-fA-F]{6}\b|#[0-9a-fA-F]{3}\b|rgba?\([^)]*\)|\bwhite\b|\bblack\b')


def parse_color(tok):
    t = tok.strip().lower()
    if t == 'white':
        return 255, 255, 255, 1.0
    if t == 'black':
        return 0, 0, 0, 1.0
    if t.startswith('#'):
        h = t[1:]
        if len(h) == 3:
            h = ''.join(c * 2 for c in h)
        a = int(h[6:8], 16) / 255 if len(h) == 8 else 1.0
        return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), a
    m = re.match(r'rgba?\(([^)]*)\)', t)
    if m:
        parts = [p for p in re.split(r'[,\s/]+', m.group(1)) if p]
        try:
            r, g, b = [float(p.rstrip('%')) for p in parts[:3]]
            a = float(parts[3].rstrip('%')) / (100 if parts[3].endswith('%') else 1) if len(parts) > 3 else 1.0
        except (ValueError, IndexError):
            return None
        return int(r), int(g), int(b), a
    return None


def _lum(r, g, b):
    f = lambda c: (c / 255) / 12.92 if c / 255 <= 0.03928 else ((c / 255 + 0.055) / 1.055) ** 2.4
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


def _contrast(c1, c2):
    a, b = _lum(*c1), _lum(*c2)
    return (max(a, b) + 0.05) / (min(a, b) + 0.05)


def _neutral(r, g, b):
    return (max(r, g, b) - min(r, g, b)) < 36


def _darken(r, g, b, target=4.6):
    h, l, s = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
    while l > 0.04:
        rgb = tuple(int(round(x * 255)) for x in colorsys.hls_to_rgb(h, l, s))
        if _contrast(rgb, BG_RGB) >= target:
            return '#{:02x}{:02x}{:02x}'.format(*rgb)
        l -= 0.02
    return INK


def conv_fg(tok):
    c = parse_color(tok)
    if not c or c[3] == 0:
        return tok
    r, g, b, a = c
    if _neutral(r, g, b):
        L = _lum(r, g, b)
        if L > 0.55:
            return INK if a >= 0.85 else MUTED
        return MUTED if L > 0.18 else tok
    return _darken(r, g, b) if _contrast((r, g, b), BG_RGB) < 4.5 else tok


def conv_bg(tok):
    c = parse_color(tok)
    if not c or c[3] == 0:
        return tok
    r, g, b, a = c
    L = _lum(r, g, b)
    if _neutral(r, g, b) and L > 0.8 and a < 1:
        return '#ffffff' if a <= 0.1 else '#e9e4d6'
    if L < 0.06 and a < 1:
        return '#ffffff'
    if L < 0.012:
        return 'var(--bg)'
    if L < 0.07:
        return '#ffffff'
    if _neutral(r, g, b) and 0.07 <= L < 0.3:   # mid-grey panels (#334155 e.d.)
        return '#e9e4d6'
    return tok


def conv_border(tok):
    c = parse_color(tok)
    if not c:
        return tok
    r, g, b, a = c
    if a < 1 or _neutral(r, g, b) or _lum(r, g, b) < 0.07 or _lum(r, g, b) > 0.75:
        return INK
    return _darken(r, g, b, 3.2) if _contrast((r, g, b), BG_RGB) < 3 else tok


def _map(v, fn):
    return COLOR_RE.sub(lambda m: fn(m.group(0)), v)


ACCENT_VARS = re.compile(r'var\(--(primary|primary-hover|accent|accent-color|accent-hover)\)')


def transform_decl(prop, v, ctx):
    p = prop.strip().lower()
    if p.startswith('--'):
        n = p[2:]
        if any(k in n for k in ('border', 'line', 'grid')):
            return _map(v, conv_border)
        if any(k in n for k in ('bg', 'background', 'surface', 'panel', 'paper', 'card')):
            return _map(v, conv_bg)
        return _map(v, conv_fg)
    if p in ('color', '-webkit-text-fill-color', 'caret-color'):
        if ctx.get('clip') and p == '-webkit-text-fill-color':
            return 'currentColor'
        if ctx.get('clip') and p == 'color':
            return 'var(--ink, #111)'
        return _map(v, conv_fg)
    if p in ('background', 'background-color', 'background-image'):
        if ctx.get('clip'):
            return 'var(--lime, #c6f432)'
        v = ACCENT_VARS.sub('var(--lime, #c6f432)', v)
        return _map(v, conv_bg)
    if p in ('-webkit-background-clip', 'background-clip') and 'text' in v:
        return 'border-box'
    if (p.startswith('border') and 'radius' not in p) or p in ('outline', 'outline-color'):
        return _map(v, conv_border)
    if p.endswith('radius'):
        return v if ('50%' in v or '100%' in v) else '0'
    if p == 'box-shadow':
        if re.fullmatch(r'\s*-?\d+px\s+-?\d+px\s+0(px)?\s+\S+\s*', v):
            return v
        return 'none'
    if p in ('text-shadow', 'backdrop-filter', '-webkit-backdrop-filter'):
        return 'none'
    if p == 'filter' and 'drop-shadow' in v:
        return 'none'
    return v


def _split(block):
    out, depth, cur = [], 0, []
    for ch in block:
        if ch == '(':
            depth += 1
        elif ch == ')':
            depth -= 1
        if ch == ';' and depth == 0:
            out.append(''.join(cur))
            cur = []
        else:
            cur.append(ch)
    out.append(''.join(cur))
    return out


def transform_block(block):
    decls = _split(block)
    ctx = {'clip': bool(re.search(r'background-clip\s*:\s*text', block))}
    out = []
    for d in decls:
        if ':' not in d:
            out.append(d)
            continue
        prop, val = d.split(':', 1)
        if not re.fullmatch(r'\s*-{0,2}[a-zA-Z][-a-zA-Z0-9]*\s*', prop) or '{' in val:
            out.append(d)
            continue
        imp = ''
        core = val
        if '!important' in core:
            core = core.replace('!important', '')
            imp = ' !important'
        trail = core[len(core.rstrip()):]
        lead = core[:len(core) - len(core.lstrip())]
        nv = transform_decl(prop, core.strip(), ctx)
        out.append(f'{prop}:{lead or " "}{nv}{imp}{trail}')
    res = ';'.join(out)
    if ctx['clip'] and 'padding' not in block:
        res = res.rstrip().rstrip(';') + '; padding: 0 .12em; box-decoration-break: clone; -webkit-box-decoration-break: clone; '
    return res


def transform_css(css):
    return re.sub(r'\{([^{}]*)\}', lambda m: '{' + transform_block(m.group(1)) + '}', css)


def transform_html_styles(html):
    html = re.sub(r'(<style[^>]*>)(.*?)(</style>)',
                  lambda m: m.group(1) + transform_css(m.group(2)) + m.group(3), html, flags=re.S | re.I)
    html = re.sub(r'(\sstyle=")([^"]*)(")', lambda m: m.group(1) + transform_block(m.group(2)) + m.group(3), html)
    html = re.sub(r"(\sstyle=')([^']*)(')", lambda m: m.group(1) + transform_block(m.group(2)) + m.group(3), html)
    return html


# ---------------------------------------------------------------------------
# Dashboard-thema
# ---------------------------------------------------------------------------
DASH_CSS = r"""
html{-webkit-text-size-adjust:100%}
body{font-family:var(--font-body)!important;background:var(--bg)!important;color:var(--ink)!important;margin:0!important;padding:0!important;max-width:none!important;min-height:100vh;display:flex!important;flex-direction:column!important;line-height:1.5}
.ds-content{box-sizing:border-box;flex:1 0 auto;width:100%;max-width:1680px;margin:0 auto;padding:clamp(1rem,3vw,2rem) clamp(.75rem,3vw,2rem) 3rem;display:flex;flex-direction:column;min-width:0}
.ds-intro{margin:0 0 1rem;color:var(--muted);max-width:900px}
.ds-kicker{align-self:flex-start;display:inline-block;font:700 .72rem/1 var(--font-mono);letter-spacing:.08em;text-transform:uppercase;background:var(--violet);color:var(--ink);padding:.3rem .55rem;margin-bottom:.6rem}
.ds-content h1{font-family:var(--font-head)!important;font-weight:700!important;text-transform:uppercase;letter-spacing:-.04em!important;line-height:1!important;font-size:clamp(1.6rem,4vw,2.6rem)!important;color:var(--ink)!important;-webkit-text-fill-color:currentColor!important;background:none!important;margin:0 0 .4rem!important;padding:0!important}
.ds-content>header,.ds-content header:not(.site-header){position:static!important;top:auto!important;background:var(--surface)!important;border:3px solid var(--ink)!important;box-shadow:var(--shadow)!important;padding:1rem 1.25rem!important;margin:0 0 1.5rem!important;display:flex!important;flex-wrap:wrap;gap:.75rem 1.5rem;align-items:center;justify-content:space-between}
.ds-content>header h1{font-size:clamp(1.3rem,3vw,1.9rem)!important;margin:0!important}
.ds-content main{padding:0!important;overflow:visible!important}
.ds-content p{max-width:900px}
.ds-content em{font-style:normal}
.meta-info{color:var(--ink)!important;flex-wrap:wrap;gap:.75rem 1rem!important;font-size:.85rem!important}
.meta-info .badge,#row-count{background:var(--ink)!important;color:var(--lime)!important;border-radius:0!important;font-family:var(--font-mono);font-weight:700!important;padding:.3rem .6rem!important}
.clear-btn{background:var(--coral)!important;color:var(--ink)!important;border:2px solid var(--ink)!important;border-radius:0!important;box-shadow:3px 3px 0 var(--ink);font-weight:700!important;text-transform:uppercase;font-family:var(--font-body)!important}
.clear-btn:hover{transform:translate(-1px,-1px);box-shadow:4px 4px 0 var(--ink)}
.table-container,.ds-scroll{background:var(--surface)!important;border:3px solid var(--ink)!important;border-radius:0!important;box-shadow:var(--shadow)!important;overflow:auto!important;max-height:calc(100vh - 150px);max-height:calc(100dvh - 150px);-webkit-overflow-scrolling:touch}
.ds-scroll{max-height:none}
.ds-scroll>table,.table-container>table{box-shadow:none!important;border:0!important;margin:0!important}
.ds-content table{border-collapse:collapse!important;width:100%;font-size:.86rem;font-variant-numeric:tabular-nums;background:var(--surface)!important}
.ds-content thead{background:var(--ink)!important}
.ds-content th{background:var(--ink)!important;color:var(--bg)!important;border-bottom:3px solid var(--ink)!important;text-transform:uppercase;font-size:.72rem!important;letter-spacing:.04em;font-weight:700!important;white-space:nowrap}
.ds-content th:hover{background:#2a2a2a!important}
.ds-content .col-title{color:var(--bg)!important}
.ds-content td{border-bottom:1.5px solid var(--ink)!important;color:var(--ink)}
.ds-content tbody tr:hover{background:var(--lime)!important}
.ds-content tr:nth-child(even){background:transparent}
.filter-input,.filter-select,.multi-select-btn{background:var(--surface)!important;color:var(--ink)!important;border:2px solid var(--ink)!important;border-radius:0!important;font-family:var(--font-body)!important}
.filter-input:focus,.filter-select:focus{box-shadow:3px 3px 0 var(--lime)!important;border-color:var(--ink)!important}
.multi-select-dropdown{background:var(--surface)!important;border:3px solid var(--ink)!important;border-radius:0!important;box-shadow:var(--shadow)!important}
.checkbox-item{color:var(--ink)!important;text-transform:none;letter-spacing:0;font-weight:500}
.checkbox-item:hover{background:var(--lime)}
tbody tr.near-20ma{background:#eef9d2!important}
tbody tr.near-20ma td{color:var(--ink)!important}
tbody tr.near-20ma td:first-child,tbody tr.near-20ma td.rank-cell{color:var(--pos)!important;font-weight:700}
tbody tr.under-50ma{background:#ffe7e1!important}
tbody tr.under-50ma td{color:var(--ink)!important}
tbody tr.under-50ma td:first-child,tbody tr.under-50ma td.rank-cell{color:var(--neg)!important;font-weight:700}
tbody tr.near-20ma:hover,tbody tr.under-50ma:hover{background:var(--lime)!important}
.rank-top{background:var(--lime)!important;color:var(--ink)!important;font-weight:700!important}
.trend-bullish,.delta-positive,.volatility-low,.sharpe-good{color:var(--pos)!important;font-weight:700}
.trend-bearish,.delta-negative,.volatility-high,.drawdown-deep{color:var(--neg)!important;font-weight:700}
.drawdown-safe{color:#1d4ed8!important}.value-good{color:var(--link)!important;font-weight:700}
.info-cards{gap:1rem!important}
.info-cards .card,.ds-content .card{background:var(--surface)!important;border:3px solid var(--ink)!important;border-radius:0!important;box-shadow:var(--shadow)!important}
.card-val{color:var(--ink)!important;font-family:var(--font-head)}
.card-label,.subtitle{color:var(--muted)!important}
.badge,.acc-badge,.dist-badge{border-radius:0!important;border:1.5px solid var(--ink)!important;color:var(--ink)!important}
.header-info{color:var(--muted)!important}
#no-results{color:var(--muted)!important}
.ds-legend{display:flex;flex-wrap:wrap;gap:.5rem 1rem;margin:0 0 1rem;font-size:.8rem}
.ds-legend span{display:inline-flex;align-items:center;gap:.4rem}
.ds-legend i{width:14px;height:14px;border:2px solid var(--ink);display:inline-block}
.plotly-graph-div{border:3px solid var(--ink);box-shadow:var(--shadow);background:#fff;max-width:100%}
::-webkit-scrollbar{width:10px;height:10px}::-webkit-scrollbar-track{background:var(--bg-2)}::-webkit-scrollbar-thumb{background:var(--ink);border-radius:0}
.site-footer{margin-top:2rem}
@media (max-width:640px){.ds-content td,.ds-content th{padding:.55rem .6rem!important}.table-container{max-height:calc(100dvh - 120px)}}
"""

# NL -> EN voor de UI-teksten van de dashboards (data blijft ongewijzigd)
DS_I18N = {
    'Filters wissen': 'Clear filters',
    'Laatste update': 'Last update',
    'Gegenereerd op': 'Generated on',
    "Geen ETF's gevonden die aan je filters voldoen.": 'No ETFs match your filters.',
    'Geen aandelen gevonden die aan je filters voldoen.': 'No stocks match your filters.',
    'Geen resultaten gevonden die aan je filters voldoen.': 'No results match your filters.',
    '(Alle selecteren)': '(Select all)',
    'geselecteerd': 'selected',
    'Alle...': 'All...',
    "Aantal ETF's": 'Number of ETFs',
    "ETF's": 'ETFs',
    'aandelen': 'stocks',
    'Aandelen': 'Stocks',
    'Naam ETF': 'ETF name',
    'Prijs': 'Price',
    'Volatiliteit': 'Volatility',
    'Rendement 1J': 'Return 1Y',
    'Land / Regio': 'Country / Region',
    'Groei 3j': 'Growth 3y',
    'Gefilterd op onderliggende waarde en wiskundig risico (1 jaar historie).': 'Filtered on underlying value and mathematical risk (1-year history).',
    'Gefilterd op kwaliteit, gevaarlijke yields (Value Traps / Covered Calls) zijn weggelaten, met sectorspreiding.': 'Filtered on quality; risky yields (value traps / covered-call ETFs) are excluded, with sector diversification.',
    'Groen': 'Green', 'Rood': 'Red',
    'Koers binnen ±0,5σ van de 20-daags gemiddelde (instapzone)': 'Price within ±0.5σ of the 20-day average (entry zone)',
    'Koers onder het 50-daags gemiddelde (zwak / verkopen)': 'Price below the 50-day average (weak / sell)',
    'Top 10 binnen de ranking': 'Top 10 in the ranking',
    'Klik op een kolomkop om te sorteren.': 'Click a column header to sort.',
}

DS_INTRO = {  # korte uitleg per dashboard (NL, EN)
    'momentum_seasonality': ("Historische prestaties van Momentum ETF's (Vanaf 2007)", "Historical performance of Momentum ETFs (Since 2007)"),
    'entry': ('Seizoensregime (60% jaarcyclus + 40% presidentscyclus) voor de komende OpEx-perioden, gecorrigeerd voor VIX, 200-daags gemiddelde en waardering.',
              'Seasonal regime (60% annual cycle + 40% presidential cycle) for the upcoming OpEx periods, adjusted for VIX, the 200-day average and valuation.'),
    'ib': ('Momentum-ranking van Amerikaanse aandelen. Filter en sorteer per kolom.',
           'Momentum ranking of US stocks. Filter and sort per column.'),
    'ib25': ('De 25 hoogst gerangschikte momentumaandelen, gespreid over sectoren.',
             'The 25 highest-ranked momentum stocks, diversified across sectors.'),
    'momentum': ('Momentum-ranking van het volledige ETF-universum. Filter en sorteer per kolom.',
                 'Momentum ranking of the full ETF universe. Filter and sort per column.'),
    'momentum30': ('Top 30 momentum-ETF’s met spreiding over landen en sectoren.',
                   'Top 30 momentum ETFs with diversification across countries and sectors.'),
    'dividend': ('Dividend-ranking van ETF’s op rendement, groei en kwaliteit.',
                 'Dividend ranking of ETFs by yield, growth and quality.'),
    'dividend30': ('Top 30 dividend-ETF’s, gefilterd op kwaliteit en sectorspreiding.',
                   'Top 30 dividend ETFs, filtered for quality and sector diversification.'),
    'fundamentals': ('ETF’s gerangschikt op fundamentele waarde en risico (volatiliteit, drawdown, Sharpe).',
                     'ETFs ranked by fundamental value and risk (volatility, drawdown, Sharpe).'),
    'fundamentals30': ('Top 30 ETF’s op basis van fundamentals en risico.',
                       'Top 30 ETFs based on fundamentals and risk.'),
}

LEGEND_KEYS = ('ib', 'ib25', 'momentum', 'momentum30', 'dividend')


def _legend(lang):
    if lang == 'nl':
        a, b, c = ('Koers binnen ±0,5σ van de 20-daags gemiddelde (instapzone)',
                   'Koers onder het 50-daags gemiddelde (zwak / verkopen)', 'Top 10 binnen de ranking')
    else:
        a, b, c = ('Price within ±0.5σ of the 20-day average (entry zone)',
                   'Price below the 50-day average (weak / sell)', 'Top 10 in the ranking')
    return (f'<div class="ds-legend" data-lang-block="{lang}"{" hidden" if lang == "en" else ""}>'
            f'<span><i style="background:#eef9d2"></i>{a}</span><span><i style="background:#ffe7e1"></i>{b}</span>'
            f'<span><i style="background:#c6f432"></i>{c}</span></div>')


# ---------------------------------------------------------------------------
# S&P 500 Entry-dashboard (Plotly): layout-fix, mobiel en Engelse vertaling
#   - Titel + 5 indicatoren gaan uit het Plotly-canvas naar responsieve HTML
#     (in de generator overlapten ze met de eerste grafiek).
#   - Herstelt yaxis2: de generator maakte van de as van rij 2 een overlay op
#     rij 1, waardoor de SPY/QQQ/SMH-staven bovenin terechtkwamen.
#   - Mobiel (<=700px): compacte assen, korte labels, geen scroll-zoom.
#   - ?lang=en (of opgeslagen taalkeuze): alle grafiekteksten in het Engels.
# ---------------------------------------------------------------------------
ENTRY_CSS = r"""
.ds-entry-head{margin:0 0 1.25rem}
.ds-entry-head h1 .em{font-style:normal}
.ds-entry-meta{margin:0 0 .2rem!important;font:400 .8rem/1.5 var(--font-mono);color:var(--muted)}
.ds-entry-meta span{color:inherit!important;font-size:inherit!important}
.ds-entry-advice{margin:.9rem 0 1rem;padding:.8rem 1rem;background:var(--surface);border:3px solid var(--ink);box-shadow:var(--shadow-sm);font-size:.95rem;line-height:1.5;max-width:none!important}
.ds-entry-advice span{color:var(--ink)!important;font-size:inherit!important}
.ds-kpis{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:.75rem}
.ds-kpi{min-width:0;padding:.75rem .9rem;background:var(--surface);border:3px solid var(--ink);box-shadow:var(--shadow-sm)}
.ds-kpi .k{font:700 .74rem/1.3 var(--font-mono);text-transform:uppercase;letter-spacing:.03em}
.ds-kpi .k span{display:block;margin-top:.15rem;font-size:.8rem!important;text-transform:none;letter-spacing:0}
.ds-kpi .v{margin-top:.35rem;font:700 clamp(1.5rem,3vw,2rem)/1.05 var(--font-head);font-variant-numeric:tabular-nums}
.ds-entry-plot{width:100%;min-width:0}
.ds-entry-plot .plotly-graph-div{width:auto!important;background:#0d1117!important}
@media (max-width:900px){.ds-kpis{grid-template-columns:repeat(3,minmax(0,1fr))}}
@media (max-width:560px){.ds-kpis{grid-template-columns:repeat(2,minmax(0,1fr));gap:.6rem}.ds-kpi{padding:.6rem .7rem}.ds-kpi:last-child:nth-child(odd){grid-column:1/-1}.ds-entry-advice{font-size:.88rem}}
"""

ENTRY_JS = r"""
(function(){
  var NL2EN=[
    [/SEIZOENSREGIME — Komende 10 Perioden/g,'SEASONAL REGIME — Next 10 Periods'],
    [/HISTORISCHE GEMIDDELDE RETURNS/g,'HISTORICAL AVERAGE RETURNS'],
    [/CUMULATIEVE VERWACHTING/g,'CUMULATIVE EXPECTATION'],
    [/HISTORISCHE VERDELING — Huidige & Volgende Periode/g,'HISTORICAL DISTRIBUTION — Current & Next Period'],
    [/Seizoens Entry Dashboard/g,'Seasonal Entry Dashboard'],
    [/Gegenereerd op/g,'Generated on'],
    [/Kortetermijn Actie/g,'Short-Term Action'],
    [/Zwakte verwacht\. Wacht op een dip\./g,'Weakness expected. Wait for a dip.'],
    [/Neutraal regime, maar betere tijden in aantocht\. Accumuleren\./g,'Neutral regime, but better times ahead. Accumulate.'],
    [/Neutraal regime\. Geen haast\./g,'Neutral regime. No rush.'],
    [/Seizoen in de rug\. Kopen bij kleine dips\./g,'Seasonal tailwind. Buy small dips.'],
    [/Markt is duur en HYG toont risk-off\. Wees conservatief met instappen\./g,'Market is expensive and HYG shows risk-off. Be conservative with entries.'],
    [/Markt is fundamenteel duur, agressief kopen is riskant\./g,'Market is fundamentally expensive; aggressive buying is risky.'],
    [/Let op: Credit markten \(HYG\) tonen lichte zwakte\./g,'Note: credit markets (HYG) show slight weakness.'],
    [/Marktomstandigheden en risico-indicatoren lijken gezond\./g,'Market conditions and risk indicators look healthy.'],
    [/HUIDIGE PERIODE/g,'CURRENT PERIOD'],
    [/Gecorrigeerde verwachting/g,'Adjusted expectation'],
    [/Cumulatief macro-gecorrigeerd/g,'Cumulative macro-adjusted'],
    [/Cumulatief gecorrigeerd/g,'Cumulative adjusted'],
    [/Cumulatief basis/g,'Cumulative base'],
    [/Basis avg per periode/g,'Base avg per period'],
    [/Basis verwachting/g,'Base expectation'],
    [/\bBasis\b/g,'Base'],
    [/Gecombineerd Regime/g,'Combined Regime'],
    [/\bGecombineerd\b/g,'Combined'],
    [/\bGecorrigeerd\b/g,'Adjusted'],
    [/Sterk Groen/g,'Strong Green'],[/Sterk Rood/g,'Strong Red'],
    [/\bGroen\b/g,'Green'],[/\bRood\b/g,'Red'],
    [/seizoensrendement verminderd/g,'seasonal return reduced'],
    [/licht versterkt/g,'slightly amplified'],[/sterk versterkt/g,'strongly amplified'],[/max versterkt/g,'max amplified'],
    [/drawdown minder ernstig/g,'drawdown less severe'],[/drawdown versterkt/g,'drawdown amplified'],
    [/gevaarzone actief/g,'danger zone active'],[/zware drawdown verwacht/g,'heavy drawdown expected'],
    [/bear versterkt/g,'bear amplified'],[/bear verzwakt/g,'bear weakened'],[/extra bounce kans/g,'extra bounce chance'],
    [/Erg Goedkoop/g,'Very Cheap'],[/Erg Duur/g,'Very Expensive'],[/\bGoedkoop\b/g,'Cheap'],
    [/\bGemiddeld\b/g,'Average'],[/\bPrijzig\b/g,'Pricey'],
    [/200d gem\b/g,'200d avg'],[/\bBoven\b/g,'Above'],[/\bOnder\b/g,'Below'],[/\bNabij\b/g,'Near'],
    [/Presidential Cyclus/g,'Presidential Cycle'],[/\bCyclus:/g,'Cycle:'],[/\bPeriode:/g,'Period:'],
    [/Verkiezingsjaar/g,'Election Year'],[/Post-Verkiezing/g,'Post-Election'],[/Pre-Verkiezing/g,'Pre-Election'],
    [/\bGem:/g,'Avg:'],[/\bBeste:/g,'Best:'],[/\bSlechtste:/g,'Worst:'],
    [/\bNeutraal\b/g,'Neutral'],[/\bneutraal\b/g,'neutral'],
    [/\bNormaal\b/g,'Normal'],[/\bnormaal\b/g,'normal'],
    [/\bVerhoogd\b/g,'Elevated'],[/\bverhoogd\b/g,'elevated'],
    [/\bLaag\b/g,'Low'],[/\bLAAG\b/g,'LOW'],[/\bHoog\b/g,'High'],[/\bHOOG\b/g,'HIGH'],
    [/\bExtreem\b/g,'Extreme'],[/\bEXTREEM\b/g,'EXTREME'],
    [/\bonbekend\b/g,'unknown'],[/geen data/g,'no data'],
    [/\(Huidig\)/g,'(Current)'],[/\(Volgend\)/g,'(Next)'],
    [/\bMrt\b/g,'Mar'],[/\bMei\b/g,'May'],[/\bOkt\b/g,'Oct'],
    [/\bNU\b/g,'NOW']
  ];
  var SKIP={bdata:1,dtype:1,shape:1,customdata:1};
  function pickLang(){var q=null,l='nl';try{q=new URLSearchParams(location.search).get('lang');l=(q||localStorage.getItem('ds-lang')||'nl').toLowerCase();}catch(e){l=(q||'nl').toLowerCase();}return l==='en'?'en':'nl';}
  function tr(s){for(var i=0;i<NL2EN.length;i++)s=s.replace(NL2EN[i][0],NL2EN[i][1]);return s;}
  function walk(o,key){
    if(typeof o==='string')return SKIP[key]?o:tr(o);
    if(Array.isArray(o))return o.map(function(v){return walk(v,key);});
    if(o&&typeof o==='object'){var r={};for(var k in o)r[k]=SKIP[k]?o[k]:walk(o[k],k);return r;}
    return o;
  }
  function clone(o){return JSON.parse(JSON.stringify(o));}
  function strip(s){return String(s).replace(/<[^>]*>/g,'').trim();}

  /* Structurele reparatie (los van schermbreedte) */
  function prepare(data,layout){
    var kpis=[],keep=[];
    data.forEach(function(t){(t.type==='indicator'?kpis:keep).push(t);});
    var title=(layout.title&&layout.title.text)||'';
    delete layout.title;
    var y2=layout.yaxis2||{},adjTitle=(y2.title&&y2.title.text)||'';
    if(y2.overlaying){delete y2.overlaying;delete y2.side;delete y2.title;y2.showgrid=true;y2.tickfont={size:9,color:'#8b949e'};}
    var hasOverlay=false;
    keep.forEach(function(t){if(t.type==='scatter'&&(t.xaxis||'x')==='x'&&(t.yaxis||'y')==='y'){t.yaxis='y5';hasOverlay=true;}});
    if(hasOverlay)layout.yaxis5={overlaying:'y',side:'right',anchor:'x',showgrid:false,zeroline:false,tickformat:'+.1f',ticksuffix:'%',
      tickfont:{color:'#ffd700',size:9},title:{text:adjTitle,font:{color:'#ffd700',size:9}}};
    layout.margin=Object.assign({},layout.margin||{},{t:48});
    return {data:keep,layout:layout,kpis:kpis,title:title};
  }

  function shortTick(s){var first=String(s).split(/<br\s*\/?>/i)[0];var cur=/&gt;&gt;&gt;|>>>/.test(first);return (cur?'\u25B6 ':'')+strip(first).replace(/^(&gt;|>)+\s*/,'');}

  /* Schermafhankelijke variant */
  function variant(base,mobile){
    var d=clone(base.data),l=clone(base.layout);
    l.hoverlabel={font:{size:mobile?10:11}};
    if(!mobile)return {d:d,l:l};
    l.margin={l:40,r:40,t:42,b:30};
    l.hovermode='closest';
    l.dragmode=false;
    l.legend=Object.assign({},l.legend||{},{font:{size:9},y:-0.025});
    ['x','x2','x3'].forEach(function(ax){
      var key=ax==='x'?'xaxis':'xaxis'+ax.slice(1),src=null;
      d.forEach(function(t){if(!src&&(t.xaxis||'x')===ax&&Array.isArray(t.x))src=t.x;});
      if(!src||!l[key])return;
      l[key].tickmode='array';l[key].tickvals=src;l[key].ticktext=src.map(shortTick);
      l[key].tickangle=-60;l[key].tickfont=Object.assign({},l[key].tickfont||{},{size:8});
    });
    if(l.xaxis4)l.xaxis4.showticklabels=false;
    ['yaxis','yaxis2','yaxis3','yaxis4','yaxis5'].forEach(function(k){if(l[k]){l[k].tickfont=Object.assign({},l[k].tickfont||{},{size:8});if(l[k].title)l[k].title.text='';}});
    (l.annotations||[]).forEach(function(a){
      if(a.xref==='paper'){a.font=Object.assign({},a.font||{},{size:10});return;}
      var m=/\(([+-]?\d)\)/.exec(strip(a.text||''));
      if(m&&!a.showarrow){a.text='<b>'+m[1]+'</b>';a.font=Object.assign({},a.font||{},{size:9});}
      else if(a.showarrow){a.font=Object.assign({},a.font||{},{size:11});}
    });
    d.forEach(function(t){
      if(t.type!=='bar')return;
      if((t.xaxis||'x')==='x'&&Array.isArray(t.text)){t.text=t.text.map(function(s){var p=String(s).split(/<br\s*\/?>/i);return p.length>1?p[1]:s;});t.textfont=Object.assign({},t.textfont||{},{size:8});}
      if(t.xaxis==='x2')t.textposition='none';
    });
    return {d:d,l:l};
  }

  function fmt(t){var v=Number(t.value),s=(t.number&&t.number.suffix)||'';if(!isFinite(v))return 'N/A';return (Number.isInteger(v)||Math.abs(v)>=1000?String(Math.round(v)):v.toFixed(1))+s;}

  function renderHead(gd,base){
    var wrap=gd.parentElement&&gd.parentElement.style.height?gd.parentElement:gd;
    var host=document.getElementById('ds-entry-head');
    if(!host){host=document.createElement('section');host.id='ds-entry-head';host.className='ds-entry-head';wrap.parentNode.insertBefore(host,wrap);}
    var lines=String(base.title).split(/<br\s*\/?>/i).filter(function(x){return strip(x);});
    var h='';
    if(lines.length){h+='<h1>'+strip(lines[0])+'</h1>';}
    lines.slice(1).forEach(function(x){
      if(/\uD83D\uDCA1|<b>/.test(x))h+='<div class="ds-entry-advice">'+x+'</div>';
      else h+='<p class="ds-entry-meta">'+x+'</p>';
    });
    if(base.kpis.length){
      h+='<div class="ds-kpis">'+base.kpis.map(function(t){
        var c=(t.number&&t.number.font&&t.number.font.color)||'inherit';
        var k=String((t.title&&t.title.text)||'').replace(/<br\s*\/?>/gi,'');
        return '<div class="ds-kpi"><div class="k">'+k+'</div><div class="v" style="color:'+c+'">'+fmt(t)+'</div></div>';
      }).join('')+'</div>';
    }
    host.innerHTML=h;
  }

  window.dsPlot=function(id,data,layout,config){
    var gd=typeof id==='string'?document.getElementById(id):id;
    if(!gd)return;
    if(pickLang()==='en'){data=walk(data,'');layout=walk(layout,'');}
    var base=prepare(data,layout);
    renderHead(gd,base);
    var wrap=gd.parentElement;
    if(wrap&&wrap.style.height){wrap.style.height='auto';wrap.classList.add('ds-entry-plot');}
    var cfg=Object.assign({},config||{},{scrollZoom:false,responsive:true});
    var mq=window.matchMedia('(max-width: 700px)');
    function draw(first){
      var m=mq.matches,v=variant(base,m),c=Object.assign({},cfg,{displayModeBar:!m});
      gd.style.height=(v.l.height||1380)+'px';
      return first?Plotly.newPlot(gd,v.d,v.l,c):Plotly.react(gd,v.d,v.l,c);
    }
    if(mq.addEventListener)mq.addEventListener('change',function(){draw(false);});
    else if(mq.addListener)mq.addListener(function(){draw(false);});
    /* Breedte volgen als de container verandert zonder window-resize (bv. scrollbalk na laden) */
    if(window.ResizeObserver){var lastW=0,raf=0;new ResizeObserver(function(){var w=gd.clientWidth;if(Math.abs(w-lastW)<2)return;lastW=w;cancelAnimationFrame(raf);
      raf=requestAnimationFrame(function(){if(gd._fullLayout)Plotly.Plots.resize(gd);});}).observe(gd);}
    return draw(true);
  };
})();
"""


def patch_entry(html):
    """Koppelt de Entry-dashboard-fix aan een (al dan niet al gethemede) Plotly-pagina.
    Idempotent; een eerder ingevoegde versie wordt vervangen door de actuele."""
    html = re.sub(r'<style data-ds-theme="entry">.*?</style><script data-ds-theme="entry">.*?</script>', '', html, flags=re.S)
    html = html.replace('.ds-content{flex:1 0 auto;width:100%;', '.ds-content{box-sizing:border-box;flex:1 0 auto;width:100%;')
    if 'Plotly.newPlot(' in html:
        html = html.replace('Plotly.newPlot(', 'window.dsPlot(', 1)
    if 'window.dsPlot(' not in html:
        return html
    inject = f'<style data-ds-theme="entry">{ENTRY_CSS}</style><script data-ds-theme="entry">{ENTRY_JS}</script>'
    return html.replace('</head>', inject + '</head>', 1)


def apply_theme(html, key):
    """Zet een gegenereerde dashboard-HTML om naar de DataSente-huisstijl (idempotent)."""
    if 'data-ds-theme' in html:
        return patch_entry(html) if key == 'entry' else html
    file_, t_nl, t_en, _ = DASHBOARDS[key]
    html = transform_html_styles(html)
    lang_hrefs = {'nl': f'{file_}?lang=nl', 'en': f'{file_}?lang=en'}
    head_add = (
        ('<meta name="viewport" content="width=device-width, initial-scale=1.0">' if 'name="viewport"' not in html else '')
        + f'<meta name="ds-title-nl" content="{_esc(t_nl)} · DataSente">'
        + f'<meta name="ds-title-en" content="{_esc(t_en)} · DataSente">'
        + '<meta name="theme-color" content="#f3f0e8">'
        + '<link rel="icon" href="favicon.svg" type="image/svg+xml">'
        + FONT_LINKS
        + f'<style data-ds-theme="layout">{LAYOUT_CSS}{DASH_CSS}</style>'
    )
    html = re.sub(r'<title>.*?</title>', f'<title>{_esc(t_nl)} · DataSente</title>', html, count=1, flags=re.S)
    html = re.sub(r'<link rel="icon"[^>]*>', '', html)
    html = html.replace('</head>', head_add + '</head>', 1)
    intro = ''.join(
        f'<p class="ds-intro" data-lang-block="{lg}"{" hidden" if lg == "en" else ""}>'
        f'{_esc(DS_INTRO[key][0 if lg == "nl" else 1])}</p>'
        for lg in ('nl', 'en'))
    if key in LEGEND_KEYS:
        intro += _legend('nl') + _legend('en')
    kicker = '<span class="ds-kicker">Dashboard · DataSente</span>'
    headers = ''.join(
        f'<div data-lang-block="{lg}"{" hidden" if lg == "en" else ""}>'
        f'{render_header(lg, active="dash", current=file_, tag="div", lang_hrefs=lang_hrefs)}</div>'
        for lg in ('nl', 'en'))
    footers = ''.join(
        f'<div data-lang-block="{lg}"{" hidden" if lg == "en" else ""}>{render_footer(lg, tag="div")}</div>'
        for lg in ('nl', 'en'))
    html = re.sub(r'<body([^>]*)>', lambda m: f'<body{m.group(1)} data-ds-theme="{key}">' + headers
                  + '<div class="ds-content">' + kicker, html, count=1)
    # uitleg + legenda direct onder de titel (na </header> als de h1 daarin staat, anders na </h1>)
    body_at = html.find('<div class="ds-content">')
    h1_end = html.find('</h1>', body_at)
    hdr_end = html.find('</header>', body_at)
    if hdr_end != -1 and h1_end != -1 and h1_end < hdr_end:
        pos = hdr_end + len('</header>')
    elif h1_end != -1:
        pos = h1_end + len('</h1>')
    else:
        pos = body_at + len('<div class="ds-content">') + len(kicker)
    html = html[:pos] + intro + html[pos:]
    i18n = f'<script>window.DS_I18N={json.dumps(DS_I18N, ensure_ascii=False)};</script>'
    idx = html.rfind('</body>')
    html = html[:idx] + '</div>' + footers + i18n + f'<script data-ds-theme="layout">{LAYOUT_JS}</script>' + html[idx:]
    if key == 'entry':
        html = patch_entry(html)
    return html
