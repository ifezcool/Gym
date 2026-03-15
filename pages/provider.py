import dash
from dash import dcc, html, register_page, callback, Output, Input
import dash_bootstrap_components as dbc

register_page(__name__, path='/wellness/provider', title='AVON HMO Provider Portal')

layout = html.Div([
    dcc.Location(id='provider-location', refresh=True),

    # Auth + data stores (session-persisted so login survives navigation)
    dcc.Store(id="auth-store", storage_type="session",
              data={"authenticated": False, "username": None, "providername": None}),
    dcc.Store(id="data-ready-store-ps", data=False),
    dcc.Store(id="store-q2",  data=None),
    dcc.Store(id="store-q3",  data=None),
    dcc.Store(id="store-q4",  data=None),
    dcc.Store(id="store-q5",  data=None),
    dcc.Store(id="services-view-store",           data="providers"),
    dcc.Store(id="services-state-filter",         data=None),
    dcc.Store(id="services-provider-name-filter", data=None),
    dcc.Store(id="services-plan-type-filter",     data=None),
    dcc.Store(id="services-client-name-filter",   data=None),

    # Logout redirect store — written by logout callback in combined.py
    dcc.Store(id="logout-redirect", data=None),

    # Main content — filled by render_ps_layout / show_ps_portal in combined.py
    html.Div(id='ps-main-content'),
])


@callback(
    Output('provider-location', 'href'),
    Input('logout-redirect',    'data'),
    prevent_initial_call=True,
)
def do_redirect(href):
    if href:
        return href
    return dash.no_update
