"""Air Inequity Index — Netherlands Dashboard."""

import dash
import dash_bootstrap_components as dbc

from data_loader import DF
from layout import create_layout

app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.FLATLY],
    title="Air Inequity Index — NL",
    suppress_callback_exceptions=True,
)

app.layout = create_layout()

# Import callbacks after app is created (avoids circular import)
import callbacks  # noqa: F401, E402

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=8050)
