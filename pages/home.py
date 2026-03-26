import dash
from dash import dcc, html, register_page
from dash_svg import Svg, Path
import dash_bootstrap_components as dbc
import datetime as dt

register_page(__name__, path='/', title='Home')

topbar = html.Header(className="avon-topbar", children=[
    html.A(className="avon-topbar-brand", href="/", children=[
        html.Div(className="avon-logo-mark", children=[
            Svg(width="18", height="18", viewBox="0 0 24 24", fill="none", stroke="white",
                style={"strokeWidth": "2.5"},
                children=[
                    Path(d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"),
                    Path(d="m9 12 2 2 4-4")
                ])
        ]),
        html.Span("AVON HMO")
    ]),
    html.Span("Your Health, Our Priority",
              style={"fontSize": "0.8125rem", "color": "#6B7280"})
])

hero = html.Section(style={
    "background": "linear-gradient(135deg, #F5F3FF 0%, #FFFFFF 60%, #F0FDF4 100%)",
    "padding": "72px 24px 56px",
    "textAlign": "center",
    "position": "relative",
    "overflow": "hidden",
    "borderBottom": "1px solid #F3F4F6",
}, children=[
    html.Div(style={
        "position": "absolute", "top": "-80px", "left": "-80px",
        "width": "320px", "height": "320px",
        "background": "radial-gradient(circle, rgba(139,92,246,0.07) 0%, transparent 70%)",
        "borderRadius": "50%", "pointerEvents": "none"
    }),
    html.Div(style={
        "position": "absolute", "bottom": "-60px", "right": "-60px",
        "width": "280px", "height": "280px",
        "background": "radial-gradient(circle, rgba(16,185,129,0.06) 0%, transparent 70%)",
        "borderRadius": "50%", "pointerEvents": "none"
    }),

    html.Div(style={"position": "relative", "zIndex": "1"}, children=[
        html.Div(className="logo-container", style={"marginBottom": "24px"}),

        html.Span("Member Portal", style={
            "display": "inline-block",
            "background": "#EDE9FE",
            "color": "#5B21B6",
            "fontSize": "0.75rem",
            "fontWeight": "600",
            "letterSpacing": "0.06em",
            "textTransform": "uppercase",
            "padding": "4px 12px",
            "borderRadius": "9999px",
            "marginBottom": "16px"
        }),

        html.H1("Welcome to AVON HMO Portal", style={
            "fontSize": "clamp(1.75rem, 4vw, 2.75rem)",
            "fontWeight": "700",
            "color": "#111827",
            "marginBottom": "12px",
            "maxWidth": "600px",
            "margin": "0 auto 12px",
        }),

        html.P("Choose a portal to get started with your health and wellness journey.", style={
            "fontSize": "1.0625rem",
            "color": "#6B7280",
            "maxWidth": "480px",
            "margin": "0 auto",
            "lineHeight": "1.6",
        })
    ])
])

cards_section = html.Section(style={
    "maxWidth": "960px",
    "margin": "0 auto",
    "padding": "48px 24px 80px",
}, children=[
    dbc.Row([
        dbc.Col([
            html.A(href="/gym-portal", style={"textDecoration": "none"}, children=[
                html.Div(className="avon-card", style={
                    "padding": "32px",
                    "cursor": "pointer",
                    "borderTop": "3px solid #5B21B6",
                }, children=[
                    html.Div("🏋️", style={"fontSize": "2.5rem", "marginBottom": "16px"}),
                    html.H3("Gym Portal", style={
                        "color": "#111827", "fontSize": "1.25rem",
                        "fontWeight": "700", "marginBottom": "10px"
                    }),
                    html.P("Book gym sessions, track usage, and access fitness facilities across Nigeria.",
                           style={"color": "#6B7280", "fontSize": "0.9375rem",
                                  "lineHeight": "1.6", "marginBottom": "24px"}),
                    html.Div(style={
                        "display": "inline-flex", "alignItems": "center", "gap": "6px",
                        "color": "#5B21B6", "fontWeight": "600", "fontSize": "0.875rem"
                    }, children=["Go to Gym Portal ", html.Span("→")])
                ])
            ])
        ], xs=12, md=6, className="mb-4"),

        dbc.Col([
            html.A(href="/wellness", style={"textDecoration": "none"}, children=[
                html.Div(className="avon-card", style={
                    "padding": "32px",
                    "cursor": "pointer",
                    "borderTop": "3px solid #059669",
                }, children=[
                    html.Div("🧘", style={"fontSize": "2.5rem", "marginBottom": "16px"}),
                    html.H3("Wellness Portal", style={
                        "color": "#111827", "fontSize": "1.25rem",
                        "fontWeight": "700", "marginBottom": "10px"
                    }),
                    html.P("Check eligibility, book your annual wellness checkup, and access health resources.",
                           style={"color": "#6B7280", "fontSize": "0.9375rem",
                                  "lineHeight": "1.6", "marginBottom": "24px"}),
                    html.Div(style={
                        "display": "inline-flex", "alignItems": "center", "gap": "6px",
                        "color": "#059669", "fontWeight": "600", "fontSize": "0.875rem"
                    }, children=["Go to Wellness Portal ", html.Span("→")])
                ])
            ])
        ], xs=12, md=6, className="mb-4"),
    ])
])

footer = html.Footer(className="avon-footer", children=[
    f"© {dt.datetime.now().year} AVON HMO. All rights reserved."
])

layout = html.Div(style={"background": "#F9FAFB", "minHeight": "100vh"}, children=[
    topbar,
    hero,
    cards_section,
    footer,
])