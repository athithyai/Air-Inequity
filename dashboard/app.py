"""Air Inequity Index — Netherlands Dashboard."""

import sys
from pathlib import Path

# Ensure dashboard/ imports work when launched via gunicorn from repo root
sys.path.insert(0, str(Path(__file__).parent))

import dash
from layout import create_layout

app = dash.Dash(
    __name__,
    title="Air Inequity Index — NL",
    suppress_callback_exceptions=True,
)

# Expose server for Gunicorn / Render
server = app.server

# Inject Tailwind + Inter font via CDN
app.index_string = """<!DOCTYPE html>
<html lang="en">
  <head>
    {%metas%}
    <title>{%title%}</title>
    {%favicon%}
    {%css%}
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
  </head>
  <body>
    {%app_entry%}
    <footer>
      {%config%}
      {%scripts%}
      {%renderer%}
    </footer>
  </body>
</html>"""

app.layout = create_layout(None)

# Import callbacks after app is created (avoids circular import)
import callbacks  # noqa: F401, E402

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=8050)
