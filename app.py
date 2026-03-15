import dash
from dash import Dash, html, dcc
import dash_bootstrap_components as dbc

# Initialize the app with multi-page support
app = Dash(
    __name__,
    use_pages=True,
    external_stylesheets=[dbc.themes.BOOTSTRAP],
    suppress_callback_exceptions=True
)

# Set the app title
app.title = "AVON HMO Portal"

# Main app layout
app.layout = html.Div([
    dcc.Location(id='url', refresh=False),
    dash.page_container
])

if __name__ == '__main__':
    app.run(debug=True, port=8050)