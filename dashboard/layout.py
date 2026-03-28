"""Dashboard layout definition."""

import dash_bootstrap_components as dbc
from dash import dcc, html

from data_loader import NUTS_IDS, YEARS


def create_layout() -> dbc.Container:
    year_options = [{"label": str(y), "value": y} for y in YEARS]
    region_options = [{"label": nid, "value": nid} for nid in NUTS_IDS]

    return dbc.Container(
        [
            # ── Header ────────────────────────────────────────────────────────
            dbc.Row(
                dbc.Col(
                    html.Div(
                        [
                            html.H2("Air Inequity Index", className="mb-0"),
                            html.P(
                                "Satellite air quality × economic vulnerability — Netherlands NUTS-3",
                                className="text-muted mb-0",
                            ),
                        ],
                        className="py-3 border-bottom",
                    )
                )
            ),

            # ── Controls ──────────────────────────────────────────────────────
            dbc.Row(
                [
                    dbc.Col(
                        [
                            html.Label("Year", className="fw-bold"),
                            dcc.Dropdown(
                                id="year-select",
                                options=year_options,
                                value=YEARS[-1],
                                clearable=False,
                            ),
                        ],
                        width=2,
                    ),
                    dbc.Col(
                        [
                            html.Label("Colour map metric", className="fw-bold"),
                            dcc.RadioItems(
                                id="metric-select",
                                options=[
                                    {"label": "Air Inequity Index", "value": "Air_Inequity_Index"},
                                    {"label": "Pollution Index",    "value": "Index"},
                                    {"label": "GDP per Capita",     "value": "GDP_per_capita"},
                                ],
                                value="Air_Inequity_Index",
                                inline=True,
                                className="mt-1",
                            ),
                        ],
                        width=7,
                    ),
                    dbc.Col(
                        dbc.Button(
                            "Download CSV",
                            id="btn-download",
                            color="secondary",
                            size="sm",
                            className="mt-4",
                        ),
                        width={"size": 2, "offset": 1},
                    ),
                ],
                className="mt-3 mb-2 align-items-end",
            ),

            # ── Map + Index cards ─────────────────────────────────────────────
            dbc.Row(
                [
                    dbc.Col(
                        dcc.Graph(
                            id="choropleth-map",
                            style={"height": "480px"},
                            config={"scrollZoom": True},
                        ),
                        width=8,
                    ),
                    dbc.Col(
                        [
                            _index_card("Air Inequity Index", "card-aii",   "primary"),
                            _index_card("Pollution Index",    "card-index",  "warning"),
                            _index_card("GDP per Capita (€)", "card-gdp",    "success"),
                            html.Small(
                                "Hover over a region to see its values",
                                className="text-muted d-block text-center mt-2",
                            ),
                        ],
                        width=4,
                        className="d-flex flex-column justify-content-center",
                    ),
                ],
                className="mb-3",
            ),

            # ── Time Series (main feature) ────────────────────────────────────
            dbc.Row(
                dbc.Col(
                    dbc.Card(
                        [
                            dbc.CardHeader(
                                dbc.Row(
                                    [
                                        dbc.Col(
                                            html.H6("Air Inequity Index — Monthly Time Series", className="mb-0"),
                                            width=6,
                                        ),
                                        dbc.Col(
                                            dcc.Dropdown(
                                                id="ts-region-select",
                                                options=[{"label": "All regions (average)", "value": "__all__"}]
                                                + region_options,
                                                value="__all__",
                                                clearable=False,
                                                placeholder="Select region…",
                                            ),
                                            width=3,
                                        ),
                                        dbc.Col(
                                            dcc.Checklist(
                                                id="ts-show-pollutants",
                                                options=[{"label": " Show pollutants", "value": "yes"}],
                                                value=[],
                                                inline=True,
                                            ),
                                            width=3,
                                            className="d-flex align-items-center",
                                        ),
                                    ],
                                    align="center",
                                )
                            ),
                            dbc.CardBody(
                                dcc.Graph(
                                    id="time-series",
                                    style={"height": "380px"},
                                    config={"displayModeBar": True},
                                )
                            ),
                        ]
                    )
                )
            ),

            # ── Pollutant box plot ────────────────────────────────────────────
            dbc.Row(
                dbc.Col(
                    dbc.Card(
                        [
                            dbc.CardHeader(
                                html.H6(
                                    "Pollutant Quality Score Distribution",
                                    className="mb-0",
                                )
                            ),
                            dbc.CardBody(
                                dcc.Graph(
                                    id="box-plot",
                                    style={"height": "300px"},
                                )
                            ),
                        ]
                    ),
                    className="mt-3 mb-4",
                )
            ),

            # ── Hidden stores & download ──────────────────────────────────────
            dcc.Store(id="selected-nuts", data=None),
            dcc.Download(id="download-csv"),
        ],
        fluid=True,
        className="px-4",
    )


def _index_card(title: str, value_id: str, color: str) -> dbc.Card:
    return dbc.Card(
        [
            dbc.CardHeader(title, className="py-1 small"),
            dbc.CardBody(
                html.H4("—", id=value_id, className="mb-0 text-center"),
                className="py-2",
            ),
        ],
        color=color,
        outline=True,
        className="mb-2",
    )
