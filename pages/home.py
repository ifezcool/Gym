import dash
from dash import dcc, html, register_page
import dash_bootstrap_components as dbc

register_page(__name__, path='/', title='Home')

# Layout for the home page
layout = html.Div([
    # Header Section
    html.Div([
        html.H1("Welcome to AVON HMO Portal", 
               style={
                   'textAlign': 'center',
                   'color': '#5a4470',
                   'fontSize': '3rem',
                   'fontWeight': '600',
                   'marginBottom': '20px',
                   'textShadow': '2px 2px 4px rgba(0,0,0,0.1)'
               }),
        html.P("Choose your destination below",
               style={
                   'textAlign': 'center',
                   'color': '#7a6b8a',
                   'fontSize': '1.2rem',
                   'marginBottom': '50px'
               })
    ], style={
        'background': 'linear-gradient(135deg, #e8e0f0 0%, #d4c4e0 100%)',
        'padding': '60px 20px',
        'borderRadius': '0 0 30px 30px',
        'boxShadow': '0 10px 30px rgba(0,0,0,0.1)'
    }),
    
    # Navigation Cards Section
    html.Div([
        html.Div([
            dbc.Row([
                # Gym Portal Card
                dbc.Col([
                    dbc.Card([
                        dbc.CardBody([
                            html.H3("🏋️ Gym Portal", 
                                   className="card-title",
                                   style={
                                       'color': '#5a4470',
                                       'fontSize': '1.8rem',
                                       'fontWeight': '600',
                                       'marginBottom': '15px',
                                       'textAlign': 'center'
                                   }),
                            html.P("Access gym facilities, book sessions, and track your fitness journey.",
                                   className="card-text",
                                   style={
                                       'color': '#666',
                                       'fontSize': '1rem',
                                       'marginBottom': '25px',
                                       'textAlign': 'center'
                                   }),
                            html.Div([
                                dcc.Link(
                                    dbc.Button(
                                        "Go to Gym Portal",
                                        style={
                                            'width': '100%',
                                            'padding': '12px',
                                            'fontSize': '1.1rem',
                                            'fontWeight': '600',
                                            'borderRadius': '10px',
                                            'background': 'linear-gradient(135deg, #9d7cb8 0%, #7a6b8a 100%)',
                                            'border': 'none',
                                            'boxShadow': '0 4px 15px rgba(122, 107, 138, 0.3)',
                                            'transition': 'all 0.3s ease',
                                            'cursor': 'pointer'
                                        }
                                    ),
                                    href="/gym-portal"
                                )
                            ])
                        ])
                    ], style={
                        'borderRadius': '15px',
                        'boxShadow': '0 10px 30px rgba(0,0,0,0.1), 0 6px 10px rgba(0,0,0,0.08)',
                        'border': 'none',
                        'height': '100%',
                        'transition': 'transform 0.3s ease'
                    })
                ], width=6),
                
                # Wellness Portal Card
                dbc.Col([
                    dbc.Card([
                        dbc.CardBody([
                            html.H3("🧘 Wellness Portal", 
                                   className="card-title",
                                   style={
                                       'color': '#5a4470',
                                       'fontSize': '1.8rem',
                                       'fontWeight': '600',
                                       'marginBottom': '15px',
                                       'textAlign': 'center'
                                   }),
                            html.P("Coming soon! Access wellness resources, mental health support, and holistic care.",
                                   className="card-text",
                                   style={
                                       'color': '#666',
                                       'fontSize': '1rem',
                                       'marginBottom': '25px',
                                       'textAlign': 'center'
                                   }),
                            html.Div([
                                dbc.Button(
                                    "Coming Soon",
                                    disabled=True,
                                    style={
                                        'width': '100%',
                                        'padding': '12px',
                                        'fontSize': '1.1rem',
                                        'fontWeight': '600',
                                        'borderRadius': '10px',
                                        'background': '#ccc',
                                        'border': 'none',
                                        'cursor': 'not-allowed'
                                    }
                                )
                            ])
                        ])
                    ], style={
                        'borderRadius': '15px',
                        'boxShadow': '0 10px 30px rgba(0,0,0,0.1), 0 6px 10px rgba(0,0,0,0.08)',
                        'border': 'none',
                        'height': '100%',
                        'opacity': '0.8'
                    })
                ], width=6)
            ], style={'gap': '30px'})
        ], style={
            'maxWidth': '1000px',
            'margin': '0 auto',
            'padding': '20px'
        })
    ]),
    
    # Footer
    html.Div([
        html.P("© 2026 AVON HMO - Your Health, Our Priority",
               style={
                   'textAlign': 'center',
                   'color': '#7a6b8a',
                   'fontSize': '0.9rem',
                   'padding': '20px'
               })
    ], style={
        'marginTop': '50px'
    })
    
], style={
    'backgroundColor': '#d4c4e0',
    'minHeight': '100vh',
    'fontFamily': '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif'
})