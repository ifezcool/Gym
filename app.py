import dash
from dash import Dash, html, dcc
import dash_bootstrap_components as dbc

app = Dash(
    __name__,
    use_pages=True,
    external_stylesheets=[
        dbc.themes.BOOTSTRAP,
        "https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Playfair+Display:wght@400;500;600;700&display=swap",
    ],
    suppress_callback_exceptions=True
)

app.title = "AVON HMO Portal"

WELLNESS_CSS = """
<style>
    body { font-family: 'Inter', sans-serif; }
    h1,h2,h3,h4,h5,h6 { font-family: 'Playfair Display', serif; }
    .gradient-bg { background: linear-gradient(135deg, #faf5ff 0%, #ffffff 50%, #f0fdf4 100%); }
    .purple-skew { background: rgba(107,70,193,0.05); transform: skewY(-3deg); position: absolute; top:0; left:0; right:0; height:250px; }
    .green-blob  { position:absolute; bottom:0; right:0; width:400px; height:400px; background:rgba(56,178,172,0.05); border-radius:50%; filter:blur(60px); pointer-events:none; }
    .logo-container { width:64px; height:64px; background:linear-gradient(135deg,#6B46C1,#805AD5); border-radius:16px; display:flex; align-items:center; justify-content:center; transform:rotate(3deg); box-shadow:0 10px 25px rgba(107,70,193,0.25); margin:0 auto; }
    .card-glass { background:rgba(255,255,255,0.9); backdrop-filter:blur(10px); border:1px solid rgba(107,70,193,0.1); box-shadow:0 25px 50px -12px rgba(107,70,193,0.08); }
    .form-input  { height:48px; border:2px solid #E9D8FD; border-radius:12px; transition:all 0.2s; }
    .form-input:focus { border-color:#6B46C1; box-shadow:0 0 0 3px rgba(107,70,193,0.1); }
    .btn-primary-custom { background:linear-gradient(135deg,#6B46C1,#805AD5); border:none; height:48px; font-weight:600; border-radius:12px; box-shadow:0 10px 25px rgba(107,70,193,0.25); transition:all 0.2s; }
    .btn-primary-custom:hover { transform:translateY(-2px); box-shadow:0 15px 30px rgba(107,70,193,0.3); }
    .questionnaire-section { background:rgba(255,255,255,0.7); border-radius:16px; padding:20px; margin-bottom:15px; border:1px solid rgba(107,70,193,0.08); }
    .questionnaire-section h5 { color:#44337A; margin-bottom:15px; }
    .question-label { font-weight:500; color:#4A5568; margin-bottom:8px; }
    .section-divider { border-top:2px solid #E9D8FD; margin:25px 0; }
    .provider-portal-btn { position:fixed; top:18px; right:24px; z-index:9999; background:linear-gradient(135deg,#59058d,#800cbf); color:white !important; border:none; border-radius:10px; padding:8px 18px; font-weight:600; font-size:14px; box-shadow:0 4px 14px rgba(89,5,141,0.35); cursor:pointer; text-decoration:none; display:inline-flex; align-items:center; gap:6px; transition:all 0.2s; }
    .provider-portal-btn:hover { transform:translateY(-1px); box-shadow:0 6px 20px rgba(89,5,141,0.45); color:white !important; }
    .already-booked-card { background:rgba(255,255,255,0.95); border-radius:16px; border-left:4px solid #3182CE; box-shadow:0 10px 25px rgba(0,0,0,0.1); }
    .consent-banner { background:linear-gradient(135deg,#FEFCBF,#F6E05E); border:1px solid #D69E2E; border-radius:12px; }
</style>
"""

app.index_string = f'''
<!DOCTYPE html>
<html>
    <head>
        {{%metas%}}
        <title>{{%title%}}</title>
        {{%favicon%}}
        {{%css%}}
    </head>
    <body>
        {{%app_entry%}}
        <footer>
            {{%config%}}
            {{%scripts%}}
            {{%renderer%}}
        </footer>
        {WELLNESS_CSS}
    </body>
</html>
'''

app.layout = html.Div([
    dcc.Location(id='url', refresh=False),
    dash.page_container
])
# Expose Flask server for gunicorn: gunicorn app:server
server = app.server
if __name__ == '__main__':
    app.run(debug=True, port=8050)