"""Dashboard layout — Tailwind CSS."""

from dash import dcc, html

from data_loader import NUTS_IDS, YEARS


# ── Helper components ──────────────────────────────────────────────────────────

def _kpi_card(label: str, value_id: str, accent: str) -> html.Div:
    """Large-number metric card with a coloured left border."""
    borders = {"red": "border-red-500", "orange": "border-orange-400", "green": "border-emerald-500"}
    values  = {"red": "text-red-500",   "orange": "text-orange-400",   "green": "text-emerald-500"}
    return html.Div(
        [
            html.P(label, className="text-xs font-semibold uppercase tracking-widest text-slate-400 mb-2"),
            html.P("—", id=value_id, className=f"text-4xl font-bold tabular-nums {values[accent]}"),
        ],
        className=f"bg-white rounded-xl p-5 border-l-4 {borders[accent]} shadow-sm flex-1 min-w-0",
    )


def _section_header(title: str, subtitle: str = "") -> html.Div:
    return html.Div(
        [
            html.H2(title, className="text-sm font-semibold text-slate-700"),
            html.P(subtitle, className="text-xs text-slate-400") if subtitle else None,
        ],
        className="px-5 pt-4 pb-2",
    )


# ── Main layout ────────────────────────────────────────────────────────────────

def create_layout() -> html.Div:
    year_opts   = [{"label": str(y), "value": y} for y in YEARS]
    region_opts = [{"label": nid, "value": nid} for nid in NUTS_IDS]

    return html.Div(
        [
            # ── HEADER ────────────────────────────────────────────────────────
            html.Header(
                html.Div(
                    [
                        # Title
                        html.Div(
                            [
                                html.Span("🌍", className="text-2xl mr-3 select-none"),
                                html.Div(
                                    [
                                        html.H1(
                                            "Air Inequity Index",
                                            className="text-lg font-bold text-white leading-tight",
                                        ),
                                        html.P(
                                            "Satellite pollution × economic vulnerability — Netherlands NUTS-3",
                                            className="text-xs text-slate-400 leading-tight",
                                        ),
                                    ]
                                ),
                            ],
                            className="flex items-center",
                        ),

                        # Controls
                        html.Div(
                            [
                                # Year dropdown
                                html.Div(
                                    [
                                        html.Label(
                                            "Year",
                                            className="text-xs text-slate-400 mb-1 block font-medium",
                                        ),
                                        dcc.Dropdown(
                                            id="year-select",
                                            options=year_opts,
                                            value=YEARS[-1],
                                            clearable=False,
                                            className="dropdown-dark",
                                            style={"width": "90px"},
                                        ),
                                    ]
                                ),

                                # Metric radio
                                html.Div(
                                    [
                                        html.Label(
                                            "Colour map by",
                                            className="text-xs text-slate-400 mb-1 block font-medium",
                                        ),
                                        dcc.RadioItems(
                                            id="metric-select",
                                            options=[
                                                {"label": " Inequity",  "value": "Air_Inequity_Index"},
                                                {"label": " Pollution", "value": "Index"},
                                                {"label": " GDP/cap",   "value": "GDP_per_capita"},
                                            ],
                                            value="Air_Inequity_Index",
                                            inline=True,
                                            labelClassName="text-slate-300 text-sm mr-4 cursor-pointer",
                                            inputClassName="mr-1 accent-blue-500",
                                        ),
                                    ]
                                ),

                                # Download
                                html.Button(
                                    "↓ Export CSV",
                                    id="btn-download",
                                    className=(
                                        "text-xs bg-slate-700 hover:bg-slate-600 text-slate-200 "
                                        "px-3 py-2 rounded-lg border border-slate-600 cursor-pointer "
                                        "transition-colors whitespace-nowrap"
                                    ),
                                ),
                            ],
                            className="flex items-end gap-6",
                        ),
                    ],
                    className="max-w-screen-xl mx-auto px-6 py-4 flex items-center justify-between",
                ),
                className="bg-slate-900 shadow-lg sticky top-0 z-50",
            ),

            # ── KPI STRIP ─────────────────────────────────────────────────────
            html.Div(
                html.Div(
                    [
                        _kpi_card("Air Inequity Index", "card-aii",   "red"),
                        _kpi_card("Pollution Index",    "card-index", "orange"),
                        _kpi_card("GDP per Capita (€)", "card-gdp",   "green"),
                        html.Div(
                            [
                                html.P(
                                    "Hover over a region",
                                    className="text-slate-400 text-sm font-medium",
                                ),
                                html.P(
                                    "on the map to explore its metrics",
                                    className="text-slate-500 text-xs",
                                ),
                                html.Div(
                                    className="w-8 h-0.5 bg-blue-500 rounded-full mt-3"
                                ),
                            ],
                            className="flex-1 flex flex-col justify-center pl-4 border-l border-slate-200",
                        ),
                    ],
                    className="max-w-screen-xl mx-auto px-6 py-4 flex gap-4",
                ),
                className="bg-slate-50 border-b border-slate-200",
            ),

            # ── MAIN ──────────────────────────────────────────────────────────
            html.Main(
                html.Div(
                    [
                        # Choropleth map
                        html.Div(
                            dcc.Graph(
                                id="choropleth-map",
                                style={"height": "500px"},
                                config={"scrollZoom": True, "displayModeBar": False},
                            ),
                            className="bg-white rounded-2xl shadow-sm overflow-hidden",
                        ),

                        # Time series
                        html.Div(
                            [
                                html.Div(
                                    [
                                        html.H2(
                                            "Monthly Trend",
                                            className="text-sm font-semibold text-slate-700",
                                        ),
                                        html.Div(
                                            [
                                                dcc.Dropdown(
                                                    id="ts-region-select",
                                                    options=[
                                                        {"label": "All regions (average)", "value": "__all__"}
                                                    ] + region_opts,
                                                    value="__all__",
                                                    clearable=False,
                                                    placeholder="Select region…",
                                                    className="dropdown-light",
                                                    style={"width": "220px", "fontSize": "13px"},
                                                ),
                                                dcc.Checklist(
                                                    id="ts-show-pollutants",
                                                    options=[{"label": " Show pollutant breakdown", "value": "yes"}],
                                                    value=[],
                                                    inline=True,
                                                    labelClassName="text-slate-500 text-sm cursor-pointer",
                                                    inputClassName="mr-1 accent-blue-500",
                                                    className="ml-4",
                                                ),
                                            ],
                                            className="flex items-center",
                                        ),
                                    ],
                                    className="flex items-center justify-between px-5 pt-4 pb-1",
                                ),
                                dcc.Graph(
                                    id="time-series",
                                    style={"height": "340px"},
                                    config={"displayModeBar": True, "displaylogo": False},
                                ),
                            ],
                            className="bg-white rounded-2xl shadow-sm mt-4 overflow-hidden",
                        ),

                        # Box plot
                        html.Div(
                            [
                                _section_header(
                                    "Pollutant Quality Scores",
                                    "Score 1 = cleanest · 6 = most polluted · filtered by selected year & region",
                                ),
                                dcc.Graph(
                                    id="box-plot",
                                    style={"height": "280px"},
                                    config={"displayModeBar": False},
                                ),
                            ],
                            className="bg-white rounded-2xl shadow-sm mt-4 overflow-hidden",
                        ),
                    ],
                    className="max-w-screen-xl mx-auto px-6 py-6",
                )
            ),

            # ── FOOTER ────────────────────────────────────────────────────────
            html.Footer(
                html.Div(
                    html.P(
                        [
                            "Data: Sentinel-5P TROPOMI · CAMS EAC4 · Eurostat NUTS-3  ·  ",
                            html.A(
                                "View on GitHub",
                                href="https://github.com/athithyai/Air-Inequity",
                                target="_blank",
                                className="text-blue-400 hover:text-blue-300 transition-colors",
                            ),
                            "  ·  Remake of the ",
                            html.A(
                                "EU Big Data Hackathon 2025 NSI_NL",
                                href="https://github.com/eurostat/eubd2025_results/tree/main/NSI_NL",
                                target="_blank",
                                className="text-blue-400 hover:text-blue-300 transition-colors",
                            ),
                        ],
                        className="text-slate-500 text-xs text-center",
                    ),
                    className="max-w-screen-xl mx-auto px-6 py-5",
                ),
                className="bg-slate-900 mt-8",
            ),

            # Hidden stores & download component
            dcc.Store(id="selected-nuts", data=None),
            dcc.Download(id="download-csv"),
        ],
        className="min-h-screen bg-slate-100",
        style={"fontFamily": "Inter, system-ui, sans-serif"},
    )
