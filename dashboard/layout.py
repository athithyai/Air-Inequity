"""Dashboard layout — tabbed, Tailwind-styled."""

from dash import dcc, html

from data_loader import NUTS_IDS, YEARS, NAME_MAP, HAS_EXTENDED, HAS_GEMEENTE

_REGION_OPTIONS = [{"label": "All regions (average)", "value": "__all__"}] + [
    {"label": f"{NAME_MAP.get(n, n)}  ({n})", "value": n} for n in NUTS_IDS
]
_REGION_OPTIONS_NO_ALL = [
    {"label": f"{NAME_MAP.get(n, n)}  ({n})", "value": n} for n in NUTS_IDS
]

_YEAR_OPTIONS = [{"label": str(y), "value": y} for y in YEARS]

_METRIC_OPTIONS = [
    {"label": "Air Inequity Index", "value": "Air_Inequity_Index"},
    {"label": "Pollution Index",    "value": "Index"},
    {"label": "GDP per Capita",     "value": "GDP_per_capita"},
]
if HAS_EXTENDED:
    _METRIC_OPTIONS += [
        {"label": "Health Burden Index (HBI)", "value": "HBI"},
        {"label": "Env. Justice Score (EJS)",  "value": "EJS"},
        {"label": "Green Space Deficit (GSD)", "value": "GSD"},
    ]


def _dd(id_, options, value, width="180px"):
    return dcc.Dropdown(
        id=id_, options=options, value=value, clearable=False,
        className="dropdown-light",
        style={"minWidth": width, "fontSize": "13px"},
    )


def _card(children, extra_cls=""):
    return html.Div(
        children,
        className=f"bg-white rounded-2xl shadow-sm overflow-hidden {extra_cls}",
    )


def _card_header(title, controls=None):
    return html.Div(
        className="flex items-center justify-between px-5 pt-4 pb-2 flex-wrap gap-2",
        children=[
            html.Span(title, className="text-sm font-semibold text-slate-700"),
            html.Div(controls or [], className="flex items-center gap-2 flex-wrap"),
        ],
    )


def create_layout(_df=None):
    return html.Div(
        className="min-h-screen bg-slate-100",
        style={"fontFamily": "Inter, system-ui, sans-serif"},
        children=[

            # ── Stores ────────────────────────────────────────────────────────
            dcc.Store(id="selected-nuts", storage_type="memory"),
            dcc.Download(id="download-csv"),

            # ── HEADER ────────────────────────────────────────────────────────
            html.Header(
                className="bg-slate-900 shadow-lg sticky top-0 z-50",
                children=html.Div(
                    className="max-w-screen-xl mx-auto px-6 py-4 flex items-center justify-between",
                    children=[
                        html.Div(className="flex items-center gap-3", children=[
                            html.Span("🌍", className="text-2xl select-none"),
                            html.Div([
                                html.H1("Air Inequity NL",
                                        className="text-lg font-bold text-white leading-tight"),
                                html.P("Satellite pollution × economic vulnerability — Netherlands NUTS-3",
                                       className="text-xs text-slate-400 leading-tight"),
                            ]),
                        ]),
                        html.Div(className="flex items-end gap-4", children=[
                            html.Div([
                                html.Label("Year", className="text-xs text-slate-400 mb-1 block font-medium"),
                                dcc.Dropdown(
                                    id="year-select", options=_YEAR_OPTIONS, value=YEARS[-1],
                                    clearable=False, className="dropdown-dark",
                                    style={"width": "90px"},
                                ),
                            ]),
                            html.Button(
                                "Export CSV", id="btn-download",
                                className="text-xs bg-slate-700 hover:bg-slate-600 text-slate-200 "
                                          "px-3 py-2 rounded-lg border border-slate-600 cursor-pointer "
                                          "transition-colors whitespace-nowrap",
                            ),
                        ]),
                    ],
                ),
            ),

            # ── KPI STRIP ─────────────────────────────────────────────────────
            html.Div(
                className="bg-white border-b border-slate-200",
                children=html.Div(
                    className="max-w-screen-xl mx-auto px-6 py-3 flex gap-6 items-center flex-wrap",
                    children=[
                        html.Span("Hover a region →",
                                  className="text-slate-400 text-xs uppercase tracking-wide font-semibold"),
                        _kpi("card-region", "Region",            "text-slate-700"),
                        _kpi("card-aii",    "Air Inequity Index", "text-red-500"),
                        _kpi("card-index",  "Pollution Index",    "text-orange-500"),
                        _kpi("card-gdp",    "GDP / capita",       "text-blue-600"),
                        _kpi("card-hbi",    "Health Burden",      "text-purple-600"),
                        _kpi("card-ejs",    "Env Justice Score",  "text-emerald-600"),
                    ],
                ),
            ),

            # ── TABS ──────────────────────────────────────────────────────────
            html.Div(
                className="max-w-screen-xl mx-auto px-4 py-4",
                children=dcc.Tabs(
                    id="main-tabs",
                    value="tab-overview",
                    colors={"border": "#e2e8f0", "primary": "#3b82f6", "background": "#f1f5f9"},
                    children=[

                        # ══ TAB 1: OVERVIEW ═══════════════════════════════════
                        dcc.Tab(label="Overview", value="tab-overview",
                                className="custom-tab", selected_className="custom-tab--selected",
                                children=html.Div(
                                    className="grid grid-cols-12 gap-4 pt-4",
                                    children=[

                                        # Choropleth
                                        html.Div(className="col-span-12 lg:col-span-7", children=[
                                            _card([
                                                _card_header("Regional Map", [
                                                    _dd("metric-select", _METRIC_OPTIONS,
                                                        "Air_Inequity_Index", "220px"),
                                                    dcc.RadioItems(
                                                        id="boundary-select",
                                                        options=[
                                                            {"label": " NUTS-3 (40)",    "value": "nuts3"},
                                                            {"label": " Gemeente (342)", "value": "gemeente",
                                                             "disabled": not HAS_GEMEENTE},
                                                        ],
                                                        value="nuts3",
                                                        inline=True,
                                                        labelClassName="text-slate-500 text-xs cursor-pointer mr-3",
                                                        inputClassName="mr-1 accent-blue-500",
                                                    ),
                                                ]),
                                                dcc.Graph(id="choropleth-map", style={"height": "500px"},
                                                          config={"scrollZoom": True, "displayModeBar": False}),
                                            ]),
                                        ]),

                                        # Right column
                                        html.Div(className="col-span-12 lg:col-span-5 flex flex-col gap-4", children=[
                                            _card([
                                                _card_header("Monthly Trend", [
                                                    _dd("ts-region-select", _REGION_OPTIONS, "__all__", "200px"),
                                                    dcc.Checklist(
                                                        id="ts-show-pollutants",
                                                        options=[{"label": " Breakdown", "value": "yes"}],
                                                        value=[],
                                                        className="text-xs text-slate-500",
                                                    ),
                                                ]),
                                                dcc.Graph(id="time-series", style={"height": "240px"},
                                                          config={"displayModeBar": False}),
                                            ]),
                                            _card([
                                                _card_header("Pollutant Quality Scores"),
                                                dcc.Graph(id="box-plot", style={"height": "220px"},
                                                          config={"displayModeBar": False}),
                                            ]),
                                        ]),
                                    ],
                                )),

                        # ══ TAB 2: JUSTICE ════════════════════════════════════
                        dcc.Tab(label="Environmental Justice", value="tab-justice",
                                className="custom-tab", selected_className="custom-tab--selected",
                                children=html.Div(
                                    className="grid grid-cols-12 gap-4 pt-4",
                                    children=[
                                        # GDP vs AII scatter
                                        html.Div(className="col-span-12 lg:col-span-6", children=[
                                            _card([
                                                _card_header("Wealth vs Air Inequity", [
                                                    _dd("scatter-year-select", _YEAR_OPTIONS, YEARS[-1], "90px"),
                                                ]),
                                                dcc.Graph(id="scatter-gdp-aii", style={"height": "360px"},
                                                          config={"displayModeBar": False}),
                                            ]),
                                        ]),
                                        # Green space vs pollution
                                        html.Div(className="col-span-12 lg:col-span-6", children=[
                                            _card([
                                                _card_header("Green Space vs Pollution Index", [
                                                    _dd("green-year-select", _YEAR_OPTIONS, YEARS[-1], "90px"),
                                                ]),
                                                dcc.Graph(id="scatter-green-poll", style={"height": "360px"},
                                                          config={"displayModeBar": False}),
                                            ]),
                                        ]),
                                        # COVID bar
                                        html.Div(className="col-span-12", children=[
                                            _card([
                                                _card_header("COVID-19 Lockdown Air Quality Signal"),
                                                html.P(
                                                    "% change in Pollution Index — Spring 2020 vs 2018/19 baseline. "
                                                    "Negative = cleaner air during lockdown.",
                                                    className="px-5 pb-1 text-xs text-slate-400",
                                                ),
                                                dcc.Graph(id="covid-bar", style={"height": "260px"},
                                                          config={"displayModeBar": False}),
                                            ]),
                                        ]),
                                    ],
                                )),

                        # ══ TAB 3: TIME ═══════════════════════════════════════
                        dcc.Tab(label="Time Analysis", value="tab-time",
                                className="custom-tab", selected_className="custom-tab--selected",
                                children=html.Div(
                                    className="grid grid-cols-12 gap-4 pt-4",
                                    children=[
                                        # Calendar heatmap
                                        html.Div(className="col-span-12 lg:col-span-8", children=[
                                            _card([
                                                _card_header("Monthly AII Heatmap (year × month)", [
                                                    _dd("heatmap-region-select", _REGION_OPTIONS,
                                                        NUTS_IDS[0] if NUTS_IDS else "__all__", "200px"),
                                                ]),
                                                dcc.Graph(id="calendar-heatmap", style={"height": "320px"},
                                                          config={"displayModeBar": False}),
                                            ]),
                                        ]),
                                        # Seasonal breakdown
                                        html.Div(className="col-span-12 lg:col-span-4", children=[
                                            _card([
                                                _card_header("Seasonal Breakdown", [
                                                    _dd("seasonal-region-select", _REGION_OPTIONS, "__all__", "180px"),
                                                ]),
                                                dcc.Graph(id="seasonal-bar", style={"height": "320px"},
                                                          config={"displayModeBar": False}),
                                            ]),
                                        ]),
                                        # Top/bottom year-over-year
                                        html.Div(className="col-span-12", children=[
                                            _card([
                                                _card_header("Year-over-Year: Best vs Worst 5 Regions"),
                                                dcc.Graph(id="yoy-lines", style={"height": "280px"},
                                                          config={"displayModeBar": False}),
                                            ]),
                                        ]),
                                    ],
                                )),

                        # ══ TAB 4: RANKINGS ════════════════════════════════════
                        dcc.Tab(label="Region Rankings", value="tab-regions",
                                className="custom-tab", selected_className="custom-tab--selected",
                                children=html.Div(
                                    className="grid grid-cols-12 gap-4 pt-4",
                                    children=[
                                        # Ranking table
                                        html.Div(className="col-span-12 lg:col-span-7", children=[
                                            _card([
                                                _card_header("Rankings by Air Inequity Index", [
                                                    _dd("rank-year-select", _YEAR_OPTIONS, YEARS[-1], "90px"),
                                                ]),
                                                html.Div(id="ranking-table",
                                                         className="overflow-x-auto px-2 pb-4"),
                                            ]),
                                        ]),
                                        # Radar chart
                                        html.Div(className="col-span-12 lg:col-span-5", children=[
                                            _card([
                                                _card_header("Region Profile", [
                                                    _dd("radar-region-select",
                                                        _REGION_OPTIONS_NO_ALL,
                                                        NUTS_IDS[0] if NUTS_IDS else None, "200px"),
                                                ]),
                                                dcc.Graph(id="radar-chart", style={"height": "380px"},
                                                          config={"displayModeBar": False}),
                                            ]),
                                        ]),
                                    ],
                                )),
                    ],
                ),
            ),

            # ── FOOTER ────────────────────────────────────────────────────────
            html.Footer(
                className="bg-slate-900 mt-8",
                children=html.Div(
                    className="max-w-screen-xl mx-auto px-6 py-5",
                    children=html.P(
                        className="text-slate-500 text-xs text-center",
                        children=[
                            "Data: Sentinel-5P TROPOMI · CAMS EAC4 · Eurostat · CBS StatLine  ·  ",
                            html.A("GitHub", href="https://github.com/athithyai/Air-Inequity",
                                   target="_blank", className="text-blue-400 hover:text-blue-300"),
                            "  ·  Built for EU Big Data Hackathon 2025",
                        ],
                    ),
                ),
            ),
        ],
    )


def _kpi(id_, label, color_cls):
    return html.Div(className="flex flex-col", children=[
        html.Span(label, className="text-xs text-slate-400 uppercase tracking-wide"),
        html.Span("—", id=id_, className=f"text-xl font-bold {color_cls} leading-tight tabular-nums"),
    ])
