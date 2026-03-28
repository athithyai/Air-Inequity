"""All Dash callbacks."""

import plotly.express as px
import plotly.graph_objects as go

from dash import Input, Output, State, callback, dcc

from data_loader import ANNUAL, DF, GEOJSON, POLLUTANTS

# ── Colour scales ──────────────────────────────────────────────────────────────
_CHOROPLETH_SCALES = {
    "Air_Inequity_Index": "RdYlGn_r",
    "Index":              "Oranges",
    "GDP_per_capita":     "Blues",
}

_METRIC_LABELS = {
    "Air_Inequity_Index": "Air Inequity Index",
    "Index":              "Pollution Index",
    "GDP_per_capita":     "GDP per Capita (€)",
}

_POLLUTANT_COLORS = {
    "PM25": "#E15759",
    "NO2":  "#F28E2B",
    "O3":   "#76B7B2",
    "SO2":  "#59A14F",
    "CO":   "#B07AA1",
    "HCHO": "#EDC948",
}


# ── 1. Store hovered region ────────────────────────────────────────────────────
@callback(
    Output("selected-nuts", "data"),
    Input("choropleth-map", "hoverData"),
)
def store_hover(hover_data):
    if hover_data and hover_data.get("points"):
        return hover_data["points"][0].get("location")
    return None


# ── 2. Choropleth map ──────────────────────────────────────────────────────────
@callback(
    Output("choropleth-map", "figure"),
    Input("year-select", "value"),
    Input("metric-select", "value"),
)
def update_map(year: int, metric: str):
    data = ANNUAL[ANNUAL["year"] == year]

    fig = px.choropleth(
        data,
        geojson=GEOJSON,
        locations="NUTS_ID",
        featureidkey="properties.NUTS_ID",
        color=metric,
        color_continuous_scale=_CHOROPLETH_SCALES[metric],
        hover_name="NUTS_ID",
        hover_data={
            "Air_Inequity_Index": ":.3f",
            "Index":              ":.3f",
            "GDP_per_capita":     ":,.0f",
        },
        labels={metric: _METRIC_LABELS[metric]},
    )

    fig.update_geos(
        fitbounds="locations",
        visible=False,
    )
    fig.update_layout(
        margin={"r": 0, "t": 0, "l": 0, "b": 0},
        coloraxis_colorbar={"title": _METRIC_LABELS[metric], "len": 0.7},
    )
    return fig


# ── 3. Index cards ─────────────────────────────────────────────────────────────
@callback(
    Output("card-aii",   "children"),
    Output("card-index", "children"),
    Output("card-gdp",   "children"),
    Input("selected-nuts", "data"),
    Input("year-select",   "value"),
)
def update_cards(nuts_id, year):
    if nuts_id is None:
        return "—", "—", "—"
    row = ANNUAL[(ANNUAL["NUTS_ID"] == nuts_id) & (ANNUAL["year"] == year)]
    if row.empty:
        return "—", "—", "—"
    r = row.iloc[0]
    return (
        f"{r['Air_Inequity_Index']:.3f}",
        f"{r['Index']:.3f}",
        f"€ {r['GDP_per_capita']:,.0f}",
    )


# ── 4. Time series ─────────────────────────────────────────────────────────────
@callback(
    Output("time-series", "figure"),
    Input("ts-region-select",   "value"),
    Input("ts-show-pollutants", "value"),
    Input("selected-nuts",      "data"),  # map hover overrides the dropdown
)
def update_time_series(selected_region, show_pollutants, hovered_nuts):
    # Map hover takes priority when user is hovering
    region = hovered_nuts if hovered_nuts else selected_region

    if region == "__all__" or region is None:
        subset = DF.groupby("date").agg(
            Air_Inequity_Index=("Air_Inequity_Index", "mean"),
            **{f"{p}_weighted_quality": (f"{p}_weighted_quality", "mean") for p in POLLUTANTS},
        ).reset_index()
        title = "Netherlands average"
    else:
        subset = DF[DF["NUTS_ID"] == region].sort_values("date")
        title = region

    fig = go.Figure()

    # ── Main AII line ──────────────────────────────────────────────────────────
    fig.add_trace(
        go.Scatter(
            x=subset["date"],
            y=subset["Air_Inequity_Index"],
            mode="lines+markers",
            name="Air Inequity Index",
            line={"color": "#2C5F8A", "width": 2.5},
            marker={"size": 4},
            hovertemplate="<b>%{x|%b %Y}</b><br>AII: %{y:.3f}<extra></extra>",
        )
    )

    # ── Optional: stacked area of weighted pollutant contributions ─────────────
    if "yes" in (show_pollutants or []):
        for pollutant in POLLUTANTS:
            col = f"{pollutant}_weighted_quality"
            fig.add_trace(
                go.Scatter(
                    x=subset["date"],
                    y=subset[col],
                    mode="lines",
                    name=pollutant,
                    stackgroup="pollutants",
                    line={"width": 0, "color": _POLLUTANT_COLORS[pollutant]},
                    hovertemplate=f"<b>%{{x|%b %Y}}</b><br>{pollutant}: %{{y:.3f}}<extra></extra>",
                    opacity=0.7,
                )
            )

    fig.update_layout(
        title={"text": f"<b>{title}</b>", "font": {"size": 13}},
        xaxis={
            "title": None,
            "rangeslider": {"visible": True, "thickness": 0.06},
            "rangeselector": {
                "buttons": [
                    {"count": 1, "label": "1Y", "step": "year",  "stepmode": "backward"},
                    {"count": 3, "label": "3Y", "step": "year",  "stepmode": "backward"},
                    {"step": "all", "label": "All"},
                ]
            },
        },
        yaxis={"title": "Air Inequity Index"},
        legend={"orientation": "h", "y": -0.25},
        hovermode="x unified",
        margin={"t": 40, "b": 60, "l": 50, "r": 20},
    )
    return fig


# ── 5. Pollutant box plot ──────────────────────────────────────────────────────
@callback(
    Output("box-plot", "figure"),
    Input("selected-nuts", "data"),
    Input("year-select",   "value"),
)
def update_boxplot(nuts_id, year):
    mask = DF["year"] == year
    if nuts_id:
        mask = mask & (DF["NUTS_ID"] == nuts_id)
    subset = DF[mask]

    fig = go.Figure()
    for p in POLLUTANTS:
        col = f"{p}_quality"
        fig.add_trace(
            go.Box(
                y=subset[col],
                name=p,
                marker_color=_POLLUTANT_COLORS[p],
                boxmean=True,
                hovertemplate=f"<b>{p}</b><br>Score: %{{y}}<extra></extra>",
            )
        )

    fig.update_layout(
        yaxis={
            "title": "Quality score (1 = best, 6 = worst)",
            "range": [0.5, 6.5],
            "dtick": 1,
        },
        showlegend=False,
        margin={"t": 10, "b": 30, "l": 50, "r": 20},
        hovermode="closest",
    )
    return fig


# ── 6. CSV download ────────────────────────────────────────────────────────────
@callback(
    Output("download-csv", "data"),
    Input("btn-download", "n_clicks"),
    prevent_initial_call=True,
)
def download_csv(_):
    export = DF.drop(columns=["date"])
    return dcc.send_data_frame(export.to_csv, "air_inequity_nl.csv", index=False)


# ── 7. Sync map-hover to time-series region dropdown ──────────────────────────
@callback(
    Output("ts-region-select", "value"),
    Input("selected-nuts",     "data"),
    State("ts-region-select",  "value"),
)
def sync_ts_dropdown(hovered_nuts, current):
    if hovered_nuts:
        return hovered_nuts
    return current
