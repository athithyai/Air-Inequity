"""All Dash callbacks — Overview, Justice, Time, Rankings tabs."""

import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from dash import Input, Output, State, callback, dash_table, dcc, html

from data_loader import ANNUAL, DF, GEOJSON, NAME_MAP, NUTS_IDS, POLLUTANTS, REGION_STATIC, YEARS

# ── Shared style ──────────────────────────────────────────────────────────────
_FONT = dict(family="Inter, system-ui, sans-serif", size=12, color="#334155")
_CHART_BASE = dict(
    paper_bgcolor="white",
    plot_bgcolor="white",
    font=_FONT,
    hoverlabel=dict(bgcolor="white", bordercolor="#e2e8f0", font=_FONT),
)

_CHOROPLETH_SCALES = {
    "Air_Inequity_Index": "RdYlGn_r",
    "Index":              "OrRd",
    "GDP_per_capita":     "Blues",
    "HBI":                "YlOrRd",
    "EJS":                "Reds",
    "GSD":                "RdYlGn",
}
_METRIC_LABELS = {
    "Air_Inequity_Index": "Air Inequity Index",
    "Index":              "Pollution Index",
    "GDP_per_capita":     "GDP per Capita (€)",
    "HBI":                "Health Burden Index",
    "EJS":                "Environmental Justice Score",
    "GSD":                "Green Space Deficit",
}
_POLLUTANT_COLORS = {
    "PM25": "#E15759", "NO2": "#F28E2B", "O3": "#76B7B2",
    "SO2":  "#59A14F", "CO": "#B07AA1",  "HCHO": "#EDC948",
}
_SEASON_COLORS = {"Winter": "#60a5fa", "Spring": "#34d399", "Summer": "#f97316", "Autumn": "#a78bfa"}


# ═══════════════════════════════════════════════════════════════════════════════
# 1. Store hovered NUTS_ID
# ═══════════════════════════════════════════════════════════════════════════════
@callback(
    Output("selected-nuts", "data"),
    Input("choropleth-map", "hoverData"),
)
def store_hover(hover_data):
    if hover_data and hover_data.get("points"):
        return hover_data["points"][0].get("location")
    return None


# ═══════════════════════════════════════════════════════════════════════════════
# 2. Choropleth map
# ═══════════════════════════════════════════════════════════════════════════════
@callback(
    Output("choropleth-map", "figure"),
    Input("year-select",   "value"),
    Input("metric-select", "value"),
)
def update_map(year, metric):
    data = ANNUAL[ANNUAL["year"] == year].copy()
    if metric not in data.columns:
        metric = "Air_Inequity_Index"

    fig = px.choropleth_mapbox(
        data,
        geojson=GEOJSON,
        locations="NUTS_ID",
        featureidkey="properties.NUTS_ID",
        color=metric,
        color_continuous_scale=_CHOROPLETH_SCALES.get(metric, "RdYlGn_r"),
        mapbox_style="carto-positron",
        zoom=6.4,
        center={"lat": 52.35, "lon": 5.25},
        opacity=0.75,
        custom_data=["region_name", "Air_Inequity_Index", "Index", "GDP_per_capita"],
    )
    fig.update_traces(
        hovertemplate=(
            "<b>%{customdata[0]}</b>"
            "<span style='color:#94a3b8'> · %{location}</span><br><br>"
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
            title=_METRIC_LABELS.get(metric, metric),
            title_side="right", thickness=12, len=0.6,
            tickfont=dict(size=11),
        ),
        margin=dict(r=0, t=0, l=0, b=0),
        paper_bgcolor="white",
        font=_FONT,
    )
    return fig


# ═══════════════════════════════════════════════════════════════════════════════
# 3. KPI cards
# ═══════════════════════════════════════════════════════════════════════════════
@callback(
    Output("card-region", "children"),
    Output("card-aii",    "children"),
    Output("card-index",  "children"),
    Output("card-gdp",    "children"),
    Output("card-hbi",    "children"),
    Output("card-ejs",    "children"),
    Input("selected-nuts", "data"),
    Input("year-select",   "value"),
)
def update_cards(nuts_id, year):
    if nuts_id is None:
        return "—", "—", "—", "—", "—", "—"
    row = ANNUAL[(ANNUAL["NUTS_ID"] == nuts_id) & (ANNUAL["year"] == year)]
    if row.empty:
        return NAME_MAP.get(nuts_id, nuts_id), "—", "—", "—", "—", "—"
    r = row.iloc[0]
    region_name = NAME_MAP.get(nuts_id, nuts_id)
    hbi = f"{r['HBI']:.3f}" if "HBI" in r.index and not np.isnan(r.get("HBI", float("nan"))) else "—"
    ejs = f"{r['EJS']:.3f}" if "EJS" in r.index and not np.isnan(r.get("EJS", float("nan"))) else "—"
    return (
        region_name,
        f"{r['Air_Inequity_Index']:.3f}",
        f"{r['Index']:.3f}",
        f"€ {r['GDP_per_capita']:,.0f}",
        hbi, ejs,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# 4. Sync hover → ts-region-select dropdown
# ═══════════════════════════════════════════════════════════════════════════════
@callback(
    Output("ts-region-select", "value"),
    Input("selected-nuts",     "data"),
    State("ts-region-select",  "value"),
)
def sync_ts_dropdown(hovered, current):
    return hovered if hovered else current


# ═══════════════════════════════════════════════════════════════════════════════
# 5. Time series
# ═══════════════════════════════════════════════════════════════════════════════
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
        title  = f"{NAME_MAP.get(region, region)} ({region})"

    fig = go.Figure()

    if "yes" in (show_pollutants or []):
        for p in POLLUTANTS:
            col = f"{p}_weighted_quality"
            if col not in subset.columns:
                continue
            fig.add_trace(go.Scatter(
                x=subset["date"], y=subset[col],
                name=p, mode="lines", stackgroup="pollutants",
                line=dict(width=0, color=_POLLUTANT_COLORS[p]),
                hovertemplate=f"<b>{p}</b>: %{{y:.3f}}<extra></extra>",
                opacity=0.7,
            ))

    fig.add_trace(go.Scatter(
        x=subset["date"], y=subset["Air_Inequity_Index"],
        mode="lines+markers", name="Air Inequity Index",
        line=dict(color="#3b82f6", width=2.5),
        marker=dict(size=4, color="#3b82f6"),
        hovertemplate="<b>%{x|%b %Y}</b>  AII: <b>%{y:.3f}</b><extra></extra>",
    ))

    fig.update_layout(
        **_CHART_BASE,
        title=dict(text=f"<b>{title}</b>", font=dict(size=13, color="#0f172a"), x=0.01),
        xaxis=dict(
            title=None, showgrid=True, gridcolor="#f1f5f9",
            rangeslider=dict(visible=True, thickness=0.05),
            rangeselector=dict(
                buttons=[
                    dict(count=1, label="1Y", step="year", stepmode="backward"),
                    dict(count=3, label="3Y", step="year", stepmode="backward"),
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


# ═══════════════════════════════════════════════════════════════════════════════
# 6. Box plot
# ═══════════════════════════════════════════════════════════════════════════════
@callback(
    Output("box-plot", "figure"),
    Input("selected-nuts", "data"),
    Input("year-select",   "value"),
)
def update_boxplot(nuts_id, year):
    mask   = DF["year"] == year
    if nuts_id:
        mask = mask & (DF["NUTS_ID"] == nuts_id)
    subset = DF[mask]
    name   = NAME_MAP.get(nuts_id, nuts_id) if nuts_id else "All regions"

    fig = go.Figure()
    for p in POLLUTANTS:
        col = f"{p}_quality"
        if col not in subset.columns:
            continue
        fig.add_trace(go.Box(
            y=subset[col], name=p,
            marker_color=_POLLUTANT_COLORS[p],
            boxmean=True, line_width=1.5,
            hovertemplate=f"<b>{p}</b><br>Score: %{{y}}<extra></extra>",
        ))

    fig.update_layout(
        **_CHART_BASE,
        title=dict(text=f"<b>{name} · {year}</b>", font=dict(size=13, color="#0f172a"), x=0.01),
        yaxis=dict(title="Quality (1=clean, 6=worst)", range=[0.5, 6.5], dtick=1,
                   showgrid=True, gridcolor="#f1f5f9"),
        showlegend=False,
        hovermode="closest",
        margin=dict(t=40, b=30, l=60, r=16),
    )
    return fig


# ═══════════════════════════════════════════════════════════════════════════════
# 7. CSV download
# ═══════════════════════════════════════════════════════════════════════════════
@callback(
    Output("download-csv", "data"),
    Input("btn-download", "n_clicks"),
    prevent_initial_call=True,
)
def download_csv(_):
    export = DF.drop(columns=["date", "region_name"], errors="ignore")
    return dcc.send_data_frame(export.to_csv, "air_inequity_nl.csv", index=False)


# ═══════════════════════════════════════════════════════════════════════════════
# 8. Scatter — GDP vs AII
# ═══════════════════════════════════════════════════════════════════════════════
@callback(
    Output("scatter-gdp-aii", "figure"),
    Input("scatter-year-select", "value"),
)
def scatter_gdp_aii(year):
    data = ANNUAL[ANNUAL["year"] == year].copy()
    data["label"] = data["NUTS_ID"].map(NAME_MAP)

    fig = px.scatter(
        data, x="GDP_per_capita", y="Air_Inequity_Index",
        text="NUTS_ID",
        color="Air_Inequity_Index",
        color_continuous_scale="RdYlGn_r",
        hover_data={"label": True, "NUTS_ID": False,
                    "GDP_per_capita": ":,.0f",
                    "Air_Inequity_Index": ":.3f"},
        labels={"GDP_per_capita": "GDP per Capita (€)",
                "Air_Inequity_Index": "Air Inequity Index"},
    )
    fig.update_traces(
        textposition="top center",
        textfont_size=9,
        marker=dict(size=10, opacity=0.8, line=dict(width=0.5, color="white")),
    )
    # Trend line
    x = data["GDP_per_capita"].dropna()
    y = data["Air_Inequity_Index"].dropna()
    if len(x) > 2:
        idx = x.index.intersection(y.index)
        m, b = np.polyfit(x[idx], y[idx], 1)
        xr = np.linspace(x.min(), x.max(), 100)
        fig.add_trace(go.Scatter(
            x=xr, y=m * xr + b,
            mode="lines",
            line=dict(color="#94a3b8", width=1.5, dash="dot"),
            name="Trend",
            hoverinfo="skip",
        ))

    fig.update_layout(
        **_CHART_BASE,
        xaxis=dict(title="GDP per Capita (€)", showgrid=True, gridcolor="#f1f5f9",
                   tickformat=",.0f"),
        yaxis=dict(title="Air Inequity Index", showgrid=True, gridcolor="#f1f5f9"),
        coloraxis_showscale=False,
        showlegend=False,
        margin=dict(t=20, b=50, l=60, r=20),
    )
    return fig


# ═══════════════════════════════════════════════════════════════════════════════
# 9. Scatter — Green Space vs Pollution
# ═══════════════════════════════════════════════════════════════════════════════
@callback(
    Output("scatter-green-poll", "figure"),
    Input("green-year-select", "value"),
)
def scatter_green_poll(year):
    data = ANNUAL[ANNUAL["year"] == year].copy()
    data["label"] = data["NUTS_ID"].map(NAME_MAP)

    if "green_pct" not in data.columns or data["green_pct"].isna().all():
        fig = go.Figure()
        fig.add_annotation(text="Green space data unavailable",
                           xref="paper", yref="paper", x=0.5, y=0.5,
                           showarrow=False, font=dict(size=14, color="#94a3b8"))
        fig.update_layout(**_CHART_BASE, margin=dict(t=20, b=50, l=60, r=20))
        return fig

    fig = px.scatter(
        data.dropna(subset=["green_pct", "Index"]),
        x="green_pct", y="Index",
        text="NUTS_ID",
        color="Index",
        color_continuous_scale="OrRd",
        hover_data={"label": True, "NUTS_ID": False,
                    "green_pct": ":.1f",
                    "Index": ":.3f"},
        labels={"green_pct": "Green Space %", "Index": "Pollution Index"},
    )
    fig.update_traces(
        textposition="top center",
        textfont_size=9,
        marker=dict(size=10, opacity=0.8, line=dict(width=0.5, color="white")),
    )
    # Trend line
    sub = data.dropna(subset=["green_pct", "Index"])
    if len(sub) > 2:
        m, b = np.polyfit(sub["green_pct"], sub["Index"], 1)
        xr = np.linspace(sub["green_pct"].min(), sub["green_pct"].max(), 100)
        fig.add_trace(go.Scatter(
            x=xr, y=m * xr + b, mode="lines",
            line=dict(color="#94a3b8", width=1.5, dash="dot"),
            name="Trend", hoverinfo="skip",
        ))

    fig.update_layout(
        **_CHART_BASE,
        xaxis=dict(title="Green Space %", showgrid=True, gridcolor="#f1f5f9"),
        yaxis=dict(title="Pollution Index", showgrid=True, gridcolor="#f1f5f9"),
        coloraxis_showscale=False, showlegend=False,
        margin=dict(t=20, b=50, l=60, r=20),
    )
    return fig


# ═══════════════════════════════════════════════════════════════════════════════
# 10. COVID lockdown signal bar chart
# ═══════════════════════════════════════════════════════════════════════════════
@callback(
    Output("covid-bar", "figure"),
    Input("main-tabs", "value"),
)
def covid_bar(_tab):
    if "covid_signal" not in REGION_STATIC.columns:
        fig = go.Figure()
        fig.add_annotation(text="COVID signal not available",
                           xref="paper", yref="paper", x=0.5, y=0.5,
                           showarrow=False, font=dict(size=14, color="#94a3b8"))
        fig.update_layout(**_CHART_BASE, margin=dict(t=20, b=50, l=80, r=20))
        return fig

    d = REGION_STATIC[["NUTS_ID", "region_name", "covid_signal"]].dropna()
    d = d.sort_values("covid_signal")
    d["label"] = d["region_name"].fillna(d["NUTS_ID"])
    d["pct"] = (d["covid_signal"] * 100).round(1)
    d["color"] = d["pct"].apply(lambda v: "#22c55e" if v < 0 else "#ef4444")

    fig = go.Figure(go.Bar(
        y=d["label"],
        x=d["pct"],
        orientation="h",
        marker_color=d["color"],
        text=d["pct"].apply(lambda v: f"{v:+.1f}%"),
        textposition="outside",
        hovertemplate="<b>%{y}</b><br>Change: <b>%{x:+.1f}%</b><extra></extra>",
    ))
    fig.update_layout(
        **_CHART_BASE,
        xaxis=dict(title="% change in Pollution Index", showgrid=True, gridcolor="#f1f5f9",
                   zeroline=True, zerolinecolor="#94a3b8", zerolinewidth=1.5),
        yaxis=dict(title=None, automargin=True),
        margin=dict(t=10, b=40, l=180, r=60),
    )
    return fig


# ═══════════════════════════════════════════════════════════════════════════════
# 11. Calendar heatmap (year × month)
# ═══════════════════════════════════════════════════════════════════════════════
@callback(
    Output("calendar-heatmap", "figure"),
    Input("heatmap-region-select", "value"),
)
def calendar_heatmap(region):
    if region == "__all__" or region is None:
        sub = DF.groupby(["year", "month"])["Air_Inequity_Index"].mean().reset_index()
        title = "All regions"
    else:
        sub = DF[DF["NUTS_ID"] == region][["year", "month", "Air_Inequity_Index"]]
        title = NAME_MAP.get(region, region)

    pivot = sub.pivot_table(index="year", columns="month", values="Air_Inequity_Index")
    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
              "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

    fig = go.Figure(go.Heatmap(
        z=pivot.values,
        x=[months[m - 1] for m in pivot.columns],
        y=[str(y) for y in pivot.index],
        colorscale="RdYlGn_r",
        text=[[f"{v:.3f}" if not np.isnan(v) else "" for v in row] for row in pivot.values],
        texttemplate="%{text}",
        textfont_size=9,
        hovertemplate="<b>%{y} %{x}</b><br>AII: <b>%{z:.3f}</b><extra></extra>",
        colorbar=dict(title="AII", thickness=10, len=0.8),
    ))
    fig.update_layout(
        **_CHART_BASE,
        title=dict(text=f"<b>{title}</b>", font=dict(size=12, color="#0f172a"), x=0.01),
        xaxis=dict(title=None, side="top"),
        yaxis=dict(title=None, autorange="reversed"),
        margin=dict(t=60, b=20, l=60, r=60),
    )
    return fig


# ═══════════════════════════════════════════════════════════════════════════════
# 12. Seasonal breakdown bar
# ═══════════════════════════════════════════════════════════════════════════════
@callback(
    Output("seasonal-bar", "figure"),
    Input("seasonal-region-select", "value"),
)
def seasonal_bar(region):
    if region == "__all__" or region is None:
        sub = DF.copy()
        title = "All regions"
    else:
        sub = DF[DF["NUTS_ID"] == region].copy()
        title = NAME_MAP.get(region, region)

    if "season" not in sub.columns:
        fig = go.Figure()
        fig.update_layout(**_CHART_BASE, margin=dict(t=20, b=50, l=60, r=20))
        return fig

    agg = sub.groupby(["year", "season"])["Air_Inequity_Index"].mean().reset_index()
    seasons = ["Winter", "Spring", "Summer", "Autumn"]
    agg["season"] = pd.Categorical(agg["season"], categories=seasons, ordered=True)
    agg = agg.sort_values(["year", "season"])

    fig = go.Figure()
    for season in seasons:
        s = agg[agg["season"] == season]
        fig.add_trace(go.Bar(
            x=s["year"].astype(str), y=s["Air_Inequity_Index"],
            name=season, marker_color=_SEASON_COLORS.get(season, "#94a3b8"),
        ))

    fig.update_layout(
        **_CHART_BASE,
        title=dict(text=f"<b>{title}</b>", font=dict(size=12, color="#0f172a"), x=0.01),
        barmode="group",
        xaxis=dict(title=None),
        yaxis=dict(title="Avg AII", showgrid=True, gridcolor="#f1f5f9"),
        legend=dict(orientation="h", y=-0.2, font=dict(size=10)),
        margin=dict(t=40, b=60, l=50, r=16),
    )
    return fig


# ═══════════════════════════════════════════════════════════════════════════════
# 13. Year-over-year lines (top/bottom 5)
# ═══════════════════════════════════════════════════════════════════════════════
@callback(
    Output("yoy-lines", "figure"),
    Input("main-tabs", "value"),
)
def yoy_lines(_tab):
    yearly = (
        DF.groupby(["NUTS_ID", "year"])["Air_Inequity_Index"]
        .mean()
        .reset_index()
    )
    last_yr = yearly["year"].max()
    last_vals = yearly[yearly["year"] == last_yr].set_index("NUTS_ID")["Air_Inequity_Index"]
    top5    = last_vals.nlargest(5).index.tolist()
    bottom5 = last_vals.nsmallest(5).index.tolist()
    selected = top5 + bottom5

    fig = go.Figure()
    for nuts_id in selected:
        sub = yearly[yearly["NUTS_ID"] == nuts_id].sort_values("year")
        is_top = nuts_id in top5
        fig.add_trace(go.Scatter(
            x=sub["year"], y=sub["Air_Inequity_Index"],
            mode="lines+markers",
            name=NAME_MAP.get(nuts_id, nuts_id),
            line=dict(
                color="#ef4444" if is_top else "#22c55e",
                width=2 if is_top else 1.5,
                dash="solid" if is_top else "dot",
            ),
            marker=dict(size=5),
            hovertemplate=f"<b>{NAME_MAP.get(nuts_id, nuts_id)}</b><br>%{{x}}: <b>%{{y:.3f}}</b><extra></extra>",
        ))

    fig.update_layout(
        **_CHART_BASE,
        xaxis=dict(title=None, dtick=1, showgrid=True, gridcolor="#f1f5f9"),
        yaxis=dict(title="Air Inequity Index", showgrid=True, gridcolor="#f1f5f9"),
        legend=dict(orientation="h", y=-0.25, font=dict(size=10)),
        hovermode="x unified",
        margin=dict(t=20, b=70, l=60, r=16),
    )
    # Annotations
    fig.add_annotation(text="Top 5 (worst)", xref="paper", yref="paper",
                       x=0.01, y=1.04, showarrow=False,
                       font=dict(size=11, color="#ef4444"), xanchor="left")
    fig.add_annotation(text="Bottom 5 (best)", xref="paper", yref="paper",
                       x=0.25, y=1.04, showarrow=False,
                       font=dict(size=11, color="#22c55e"), xanchor="left")
    return fig


# ═══════════════════════════════════════════════════════════════════════════════
# 14. Ranking table
# ═══════════════════════════════════════════════════════════════════════════════
@callback(
    Output("ranking-table", "children"),
    Input("rank-year-select", "value"),
)
def ranking_table(year):
    data = ANNUAL[ANNUAL["year"] == year].copy()
    data["region_name"] = data["NUTS_ID"].map(NAME_MAP)
    data = data.sort_values("Air_Inequity_Index", ascending=False).reset_index(drop=True)
    data["rank"] = data.index + 1

    cols_show = ["rank", "NUTS_ID", "region_name", "Air_Inequity_Index", "Index", "GDP_per_capita"]
    extra = [c for c in ["HBI", "EJS", "GSD", "green_pct", "industrial_pct"] if c in data.columns]
    cols_show += extra
    data = data[cols_show]

    col_defs = [
        {"name": "#",         "id": "rank",                "type": "numeric"},
        {"name": "NUTS-3",    "id": "NUTS_ID"},
        {"name": "Region",    "id": "region_name"},
        {"name": "AII",       "id": "Air_Inequity_Index",   "type": "numeric",
         "format": dash_table.Format.Format(precision=3, scheme=dash_table.Format.Scheme.fixed)},
        {"name": "Poll.Idx",  "id": "Index",               "type": "numeric",
         "format": dash_table.Format.Format(precision=3, scheme=dash_table.Format.Scheme.fixed)},
        {"name": "GDP/cap €", "id": "GDP_per_capita",      "type": "numeric",
         "format": dash_table.Format.Format(precision=0, scheme=dash_table.Format.Scheme.fixed,
                                            group=dash_table.Format.Group.yes)},
    ]
    for col in extra:
        fmt = dash_table.Format.Format(precision=2, scheme=dash_table.Format.Scheme.fixed)
        col_defs.append({"name": col, "id": col, "type": "numeric", "format": fmt})

    return dash_table.DataTable(
        data=data.to_dict("records"),
        columns=col_defs,
        sort_action="native",
        filter_action="native",
        page_size=20,
        style_table={"overflowX": "auto"},
        style_header={
            "backgroundColor": "#f8fafc",
            "fontWeight": "600",
            "fontSize": "12px",
            "color": "#475569",
            "borderBottom": "2px solid #e2e8f0",
            "padding": "10px 12px",
        },
        style_cell={
            "fontSize": "12px",
            "padding": "8px 12px",
            "border": "none",
            "borderBottom": "1px solid #f1f5f9",
            "fontFamily": "Inter, system-ui, sans-serif",
            "color": "#334155",
            "textAlign": "left",
        },
        style_data_conditional=[
            {"if": {"row_index": "odd"}, "backgroundColor": "#fafafa"},
            {"if": {"filter_query": "{rank} = 1"},
             "backgroundColor": "#fef2f2", "color": "#b91c1c", "fontWeight": "600"},
            {"if": {"column_id": "Air_Inequity_Index",
                    "filter_query": "{Air_Inequity_Index} > 0.5"},
             "color": "#dc2626", "fontWeight": "600"},
        ],
        style_filter={"fontSize": "11px"},
    )


# ═══════════════════════════════════════════════════════════════════════════════
# 15. Radar chart
# ═══════════════════════════════════════════════════════════════════════════════
@callback(
    Output("radar-chart", "figure"),
    Input("radar-region-select", "value"),
    Input("year-select", "value"),
)
def radar_chart(region, year):
    if region is None:
        return go.Figure()

    row_q = ANNUAL[(ANNUAL["NUTS_ID"] == region) & (ANNUAL["year"] == year)]
    row_r = REGION_STATIC[REGION_STATIC["NUTS_ID"] == region]

    if row_q.empty:
        return go.Figure()

    r = row_q.iloc[0]
    r2 = row_r.iloc[0] if not row_r.empty else {}

    # Normalize all dimensions to 0-1 (1 = worst) relative to all regions this year
    nl_all = ANNUAL[ANNUAL["year"] == year]

    def _norm(col, invert=False):
        if col not in nl_all.columns:
            return 0.5
        vals = nl_all[col].dropna()
        vmin, vmax = vals.min(), vals.max()
        # Value for this region
        region_vals = nl_all[nl_all["NUTS_ID"] == region][col]
        if region_vals.empty or region_vals.isna().all():
            if not row_r.empty and col in row_r.columns:
                v = row_r.iloc[0][col]
            else:
                return 0.5
        else:
            v = float(region_vals.iloc[0])
        if vmax == vmin:
            return 0.5
        norm = (v - vmin) / (vmax - vmin)
        return 1 - norm if invert else norm

    dim_labels = ["Pollution", "Inequity", "GDP (low=poor)",
                  "Health Burden", "Green Space Deficit", "Industrial Exp."]
    dim_values = [
        _norm("Index"),
        _norm("Air_Inequity_Index"),
        _norm("GDP_per_capita", invert=True),
        _norm("HBI"),
        _norm("GSD"),
        _norm("industrial_pct"),
    ]
    labels = dim_labels + [dim_labels[0]]
    values = dim_values + [dim_values[0]]

    fig = go.Figure(go.Scatterpolar(
        r=values, theta=labels,
        fill="toself",
        fillcolor="rgba(59,130,246,0.2)",
        line=dict(color="#3b82f6", width=2),
        hovertemplate="%{theta}: <b>%{r:.2f}</b><extra></extra>",
    ))

    avg_vals = [0.5] * len(labels)
    fig.add_trace(go.Scatterpolar(
        r=avg_vals, theta=labels,
        mode="lines",
        line=dict(color="#94a3b8", width=1.5, dash="dot"),
        name="NL midpoint",
        hoverinfo="skip",
    ))

    region_name = NAME_MAP.get(region, region)
    fig.update_layout(
        **_CHART_BASE,
        title=dict(text=f"<b>{region_name} — {year}</b>",
                   font=dict(size=13, color="#0f172a"), x=0.5, xanchor="center"),
        polar=dict(
            radialaxis=dict(visible=True, range=[0, 1], tickfont=dict(size=9),
                            gridcolor="#e2e8f0"),
            angularaxis=dict(tickfont=dict(size=10), gridcolor="#e2e8f0"),
        ),
        showlegend=False,
        margin=dict(t=60, b=30, l=50, r=50),
    )
    return fig


import pandas as pd  # noqa: E402  (needed by seasonal_bar)
