"""All Dash callbacks."""

import plotly.express as px
import plotly.graph_objects as go

from dash import Input, Output, State, callback, dcc

from data_loader import ANNUAL, DF, GEOJSON, NAME_MAP, NUTS_IDS, POLLUTANTS

# ── Shared chart style ────────────────────────────────────────────────────────
_FONT = dict(family="Inter, system-ui, sans-serif", size=12, color="#334155")
_CHART_BASE = dict(
    paper_bgcolor="white",
    plot_bgcolor="white",
    font=_FONT,
    hoverlabel=dict(bgcolor="white", bordercolor="#e2e8f0", font=_FONT),
)

# ── Colour scales ─────────────────────────────────────────────────────────────
_CHOROPLETH_SCALES = {
    "Air_Inequity_Index": "RdYlGn_r",
    "Index":              "OrRd",
    "GDP_per_capita":     "Blues",
}
_METRIC_LABELS = {
    "Air_Inequity_Index": "Air Inequity Index",
    "Index":              "Pollution Index",
    "GDP_per_capita":     "GDP per Capita (€)",
}
_POLLUTANT_COLORS = {
    "PM25": "#E15759", "NO2": "#F28E2B", "O3": "#76B7B2",
    "SO2":  "#59A14F", "CO": "#B07AA1",  "HCHO": "#EDC948",
}


# ── 1. Store hovered NUTS_ID ──────────────────────────────────────────────────
@callback(
    Output("selected-nuts", "data"),
    Input("choropleth-map", "hoverData"),
)
def store_hover(hover_data):
    if hover_data and hover_data.get("points"):
        return hover_data["points"][0].get("location")
    return None


# ── 2. Choropleth map (flat tiled, carto-positron) ────────────────────────────
@callback(
    Output("choropleth-map", "figure"),
    Input("year-select",  "value"),
    Input("metric-select", "value"),
)
def update_map(year: int, metric: str):
    data = ANNUAL[ANNUAL["year"] == year].copy()

    fig = px.choropleth_mapbox(
        data,
        geojson=GEOJSON,
        locations="NUTS_ID",
        featureidkey="properties.NUTS_ID",
        color=metric,
        color_continuous_scale=_CHOROPLETH_SCALES[metric],
        mapbox_style="carto-positron",
        zoom=6.4,
        center={"lat": 52.35, "lon": 5.25},
        opacity=0.75,
        custom_data=["region_name", "Air_Inequity_Index", "Index", "GDP_per_capita"],
    )

    fig.update_traces(
        hovertemplate=(
            "<b>%{customdata[0]}</b>"
            "<span style='color:#94a3b8'> · %{location}</span><br>"
            "<br>"
            "Air Inequity Index&nbsp;&nbsp;<b>%{customdata[1]:.3f}</b><br>"
            "Pollution Index&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<b>%{customdata[2]:.3f}</b><br>"
            "GDP per Capita&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<b>€%{customdata[3]:,.0f}</b>"
            "<extra></extra>"
        ),
        marker_line_width=0.5,
        marker_line_color="white",
    )

    fig.update_layout(
        coloraxis_colorbar=dict(
            title=_METRIC_LABELS[metric],
            title_side="right",
            thickness=12,
            len=0.6,
            tickfont=dict(size=11),
        ),
        margin=dict(r=0, t=0, l=0, b=0),
        paper_bgcolor="white",
        font=_FONT,
    )
    return fig


# ── 3. KPI cards (hover → region values) ──────────────────────────────────────
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


# ── 4. Sync dropdown → map hover (so dropdown label stays in sync) ─────────────
@callback(
    Output("ts-region-select", "value"),
    Input("selected-nuts",     "data"),
    State("ts-region-select",  "value"),
)
def sync_ts_dropdown(hovered_nuts, current):
    return hovered_nuts if hovered_nuts else current


# ── 5. Time series (driven by dropdown, which is synced to hover above) ────────
@callback(
    Output("time-series", "figure"),
    Input("ts-region-select",   "value"),
    Input("ts-show-pollutants", "value"),
)
def update_time_series(region, show_pollutants):
    if region == "__all__" or region is None:
        subset = (
            DF.groupby("date")
            .agg(
                Air_Inequity_Index=("Air_Inequity_Index", "mean"),
                **{f"{p}_weighted_quality": (f"{p}_weighted_quality", "mean") for p in POLLUTANTS},
            )
            .reset_index()
        )
        title = "Netherlands — all regions (average)"
    else:
        subset = DF[DF["NUTS_ID"] == region].sort_values("date")
        name   = NAME_MAP.get(region, region)
        title  = f"{name} ({region})"

    fig = go.Figure()

    # Stacked pollutant area (optional, rendered beneath the AII line)
    if "yes" in (show_pollutants or []):
        for p in POLLUTANTS:
            col = f"{p}_weighted_quality"
            fig.add_trace(go.Scatter(
                x=subset["date"], y=subset[col],
                name=p, mode="lines",
                stackgroup="pollutants",
                line=dict(width=0, color=_POLLUTANT_COLORS[p]),
                hovertemplate=f"<b>{p}</b>: %{{y:.3f}}<extra></extra>",
                opacity=0.7,
            ))

    # Main AII line
    fig.add_trace(go.Scatter(
        x=subset["date"], y=subset["Air_Inequity_Index"],
        mode="lines+markers",
        name="Air Inequity Index",
        line=dict(color="#3b82f6", width=2.5),
        marker=dict(size=4, color="#3b82f6"),
        hovertemplate="<b>%{x|%b %Y}</b>  AII: <b>%{y:.3f}</b><extra></extra>",
    ))

    fig.update_layout(
        **_CHART_BASE,
        title=dict(text=f"<b>{title}</b>", font=dict(size=13, color="#0f172a"), x=0.01),
        xaxis=dict(
            title=None,
            showgrid=True, gridcolor="#f1f5f9",
            rangeslider=dict(visible=True, thickness=0.05),
            rangeselector=dict(
                buttons=[
                    dict(count=1, label="1Y", step="year",  stepmode="backward"),
                    dict(count=3, label="3Y", step="year",  stepmode="backward"),
                    dict(step="all", label="All"),
                ],
                bgcolor="white", bordercolor="#e2e8f0", borderwidth=1,
                font=dict(size=11),
            ),
        ),
        yaxis=dict(title="Air Inequity Index", showgrid=True, gridcolor="#f1f5f9"),
        legend=dict(orientation="h", y=-0.28, font=dict(size=11)),
        hovermode="x unified",
        margin=dict(t=40, b=70, l=50, r=16),
    )
    return fig


# ── 6. Pollutant box plot ──────────────────────────────────────────────────────
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

    name = NAME_MAP.get(nuts_id, nuts_id) if nuts_id else "All regions"

    fig = go.Figure()
    for p in POLLUTANTS:
        fig.add_trace(go.Box(
            y=subset[f"{p}_quality"],
            name=p,
            marker_color=_POLLUTANT_COLORS[p],
            boxmean=True,
            hovertemplate=f"<b>{p}</b><br>Score: %{{y}}<extra></extra>",
            line_width=1.5,
        ))

    fig.update_layout(
        **_CHART_BASE,
        title=dict(text=f"<b>{name} · {year}</b>", font=dict(size=13, color="#0f172a"), x=0.01),
        yaxis=dict(
            title="Quality score (1 = cleanest, 6 = worst)",
            range=[0.5, 6.5], dtick=1,
            showgrid=True, gridcolor="#f1f5f9",
        ),
        showlegend=False,
        hovermode="closest",
        margin=dict(t=40, b=30, l=60, r=16),
    )
    return fig


# ── 7. CSV download ────────────────────────────────────────────────────────────
@callback(
    Output("download-csv", "data"),
    Input("btn-download", "n_clicks"),
    prevent_initial_call=True,
)
def download_csv(_):
    export = DF.drop(columns=["date", "region_name"], errors="ignore")
    return dcc.send_data_frame(export.to_csv, "air_inequity_nl.csv", index=False)
