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
  /* ─── DESIGN TOKENS ─── */
  :root {
    --purple-900: #2D1B69;
    --purple-700: #5B21B6;
    --purple-600: #7C3AED;
    --purple-500: #8B5CF6;
    --purple-100: #EDE9FE;
    --purple-50:  #F5F3FF;

    --green-600:  #059669;
    --green-500:  #10B981;
    --green-100:  #D1FAE5;

    --red-600:    #DC2626;
    --red-100:    #FEE2E2;

    --amber-500:  #F59E0B;
    --amber-100:  #FEF3C7;

    --blue-600:   #2563EB;
    --blue-100:   #DBEAFE;

    --gray-900:   #111827;
    --gray-700:   #374151;
    --gray-500:   #6B7280;
    --gray-300:   #D1D5DB;
    --gray-100:   #F3F4F6;
    --gray-50:    #F9FAFB;

    --shadow-sm:  0 1px 3px rgba(0,0,0,0.10), 0 1px 2px rgba(0,0,0,0.06);
    --shadow-md:  0 4px 6px rgba(0,0,0,0.07), 0 2px 4px rgba(0,0,0,0.05);
    --shadow-lg:  0 10px 15px rgba(0,0,0,0.10), 0 4px 6px rgba(0,0,0,0.05);
    --shadow-xl:  0 20px 25px rgba(0,0,0,0.10), 0 10px 10px rgba(0,0,0,0.04);

    --radius-sm:  6px;
    --radius-md:  10px;
    --radius-lg:  14px;
    --radius-xl:  20px;
    --radius-2xl: 28px;

    --transition: all 0.18s cubic-bezier(0.4, 0, 0.2, 1);
  }

  /* ─── BASE ─── */
  *, *::before, *::after { box-sizing: border-box; }
  
  html { scroll-behavior: smooth; }
  
  body {
    font-family: 'Inter', system-ui, -apple-system, sans-serif;
    background-color: var(--gray-50);
    color: var(--gray-900);
    margin: 0;
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
  }

  h1, h2, h3, h4, h5, h6 {
    font-family: 'Inter', system-ui, sans-serif;
    font-weight: 600;
    line-height: 1.3;
    color: var(--gray-900);
    margin: 0 0 0.5em;
  }

  /* ─── PAGE LAYOUT ─── */
  .page-wrapper {
    min-height: 100vh;
    background: var(--gray-50);
  }

  /* ─── TOP NAV / HEADER BAR ─── */
  .avon-topbar {
    position: sticky;
    top: 0;
    z-index: 1000;
    background: rgba(255,255,255,0.85);
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    border-bottom: 1px solid var(--gray-100);
    padding: 0 32px;
    height: 60px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    box-shadow: var(--shadow-sm);
  }

  .avon-topbar-brand {
    display: flex;
    align-items: center;
    gap: 10px;
    font-weight: 700;
    font-size: 1rem;
    color: var(--purple-700);
    text-decoration: none;
  }

  .avon-topbar-brand:hover { color: var(--purple-600); }

  /* ─── AUTH PILL ─── */
  .avon-auth-pill {
    display: flex;
    align-items: center;
    gap: 4px;
    background: var(--gray-100);
    border: 1px solid var(--gray-200);
    border-radius: var(--radius-full);
    padding: 4px 6px 4px 14px;
    font-size: 0.8125rem;
    font-weight: 500;
    color: var(--gray-700);
    white-space: nowrap;
  }

  .avon-auth-pill .btn {
    border-radius: 6px !important;
    font-size: 0.75rem !important;
    padding: 3px 10px !important;
    height: auto !important;
    line-height: 1.5 !important;
  }

  .avon-logo-mark {
    width: 36px;
    height: 36px;
    background: linear-gradient(135deg, var(--purple-700), var(--purple-500));
    border-radius: var(--radius-md);
    display: flex;
    align-items: center;
    justify-content: center;
    box-shadow: 0 2px 8px rgba(91,33,182,0.3);
  }

  /* ─── CARDS ─── */
  .avon-card {
    background: #fff;
    border-radius: var(--radius-xl);
    border: 1px solid var(--gray-100);
    box-shadow: var(--shadow-sm);
    transition: var(--transition);
    overflow: hidden;
  }

  .avon-card:hover { box-shadow: var(--shadow-md); }

  .avon-card-elevated {
    background: #fff;
    border-radius: var(--radius-xl);
    border: 1px solid var(--gray-100);
    box-shadow: var(--shadow-lg);
  }

  /* ─── FORMS ─── */
  .avon-input {
    width: 100%;
    height: 44px;
    padding: 0 14px;
    font-size: 0.9375rem;
    font-family: 'Inter', sans-serif;
    color: var(--gray-900);
    background: #fff;
    border: 1.5px solid var(--gray-300);
    border-radius: var(--radius-md);
    outline: none;
    transition: var(--transition);
    appearance: none;
  }

  .avon-input:focus {
    border-color: var(--purple-500);
    box-shadow: 0 0 0 3px rgba(139,92,246,0.12);
  }

  .avon-input::placeholder { color: var(--gray-500); }

  .avon-label {
    display: block;
    font-size: 0.875rem;
    font-weight: 500;
    color: var(--gray-700);
    margin-bottom: 6px;
  }

  .form-control, .form-select {
    height: 44px !important;
    border: 1.5px solid var(--gray-300) !important;
    border-radius: var(--radius-md) !important;
    font-size: 0.9375rem !important;
    color: var(--gray-900) !important;
    transition: var(--transition) !important;
    box-shadow: none !important;
  }

  .form-control:focus, .form-select:focus {
    border-color: var(--purple-500) !important;
    box-shadow: 0 0 0 3px rgba(139,92,246,0.12) !important;
  }

  /* Dash dcc.Input override */
  input.dash-input {
    height: 44px;
    padding: 0 14px;
    border: 1.5px solid var(--gray-300);
    border-radius: var(--radius-md);
    font-family: 'Inter', sans-serif;
    font-size: 0.9375rem;
    transition: var(--transition);
    width: 100%;
  }

  input.dash-input:focus {
    border-color: var(--purple-500);
    box-shadow: 0 0 0 3px rgba(139,92,246,0.12);
    outline: none;
  }

  /* Dropdown */
  .Select-control, .VirtualizedSelectFocusedOption {
    border-radius: var(--radius-md) !important;
    border: 1.5px solid var(--gray-300) !important;
  }

  .Select--multi .Select-value {
    background: var(--purple-100) !important;
    border-color: var(--purple-200) !important;
    color: var(--purple-700) !important;
    border-radius: 4px !important;
  }

  .Select-option.is-focused {
    background: var(--purple-50) !important;
  }

  .Select-option.is-selected {
    background: var(--purple-600) !important;
  }

  /* ─── BUTTONS ─── */
  .avon-btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    height: 44px;
    padding: 0 20px;
    font-size: 0.9375rem;
    font-weight: 600;
    font-family: 'Inter', sans-serif;
    border: none;
    border-radius: var(--radius-md);
    cursor: pointer;
    transition: var(--transition);
    text-decoration: none;
    white-space: nowrap;
  }

  .avon-btn-primary {
    background: linear-gradient(135deg, var(--purple-700), var(--purple-600));
    color: #fff;
    box-shadow: 0 2px 8px rgba(91,33,182,0.30);
  }

  .avon-btn-primary:hover {
    transform: translateY(-1px);
    box-shadow: 0 4px 14px rgba(91,33,182,0.40);
    color: #fff;
  }

  .avon-btn-primary:active { transform: translateY(0); }

  .avon-btn-secondary {
    background: #fff;
    color: var(--purple-700);
    border: 1.5px solid var(--gray-300);
    box-shadow: var(--shadow-xs);
  }

  .avon-btn-secondary:hover {
    background: var(--purple-50);
    border-color: var(--purple-300);
    color: var(--purple-700);
  }

  .avon-btn-danger {
    background: var(--red-600);
    color: #fff;
    box-shadow: 0 2px 8px rgba(220,38,38,0.25);
  }

  .avon-btn-danger:hover {
    background: #B91C1C;
    transform: translateY(-1px);
    color: #fff;
  }

  .avon-btn-success {
    background: var(--green-600);
    color: #fff;
    box-shadow: 0 2px 8px rgba(5,150,105,0.25);
  }

  .avon-btn-success:hover {
    background: #047857;
    transform: translateY(-1px);
    color: #fff;
  }

  .avon-btn-full { width: 100%; }

  /* Override dbc.Button styles to match above — by adding className */
  .btn-avon-primary {
    background: linear-gradient(135deg, #5B21B6, #7C3AED) !important;
    border: none !important;
    border-radius: 10px !important;
    font-weight: 600 !important;
    box-shadow: 0 2px 8px rgba(91,33,182,0.30) !important;
    transition: all 0.18s cubic-bezier(0.4,0,0.2,1) !important;
    color: #fff !important;
  }
  .btn-avon-primary:hover {
    transform: translateY(-1px) !important;
    box-shadow: 0 4px 14px rgba(91,33,182,0.40) !important;
  }

  /* ─── PROVIDER PORTAL BUTTON (fixed top-right) ─── */
  .provider-portal-btn {
    position: fixed;
    top: 14px;
    right: 24px;
    z-index: 9999;
    background: linear-gradient(135deg, var(--purple-700), var(--purple-600));
    color: #fff !important;
    border: none;
    border-radius: var(--radius-md);
    padding: 8px 16px;
    font-weight: 600;
    font-size: 0.8125rem;
    box-shadow: 0 2px 8px rgba(91,33,182,0.35);
    cursor: pointer;
    text-decoration: none;
    display: inline-flex;
    align-items: center;
    gap: 6px;
    transition: var(--transition);
  }

  .provider-portal-btn:hover {
    transform: translateY(-1px);
    box-shadow: 0 4px 14px rgba(91,33,182,0.45);
    color: #fff !important;
  }

  /* ─── STAT / SUMMARY CARDS ─── */
  .avon-stat-card {
    background: #fff;
    border: 1px solid var(--gray-100);
    border-radius: var(--radius-lg);
    padding: 20px 24px;
    box-shadow: var(--shadow-sm);
    text-align: center;
  }

  .avon-stat-number {
    font-size: 2.25rem;
    font-weight: 700;
    line-height: 1;
    margin-bottom: 4px;
  }

  .avon-stat-label {
    font-size: 0.8125rem;
    font-weight: 500;
    color: var(--gray-500);
    letter-spacing: 0.025em;
    text-transform: uppercase;
  }

  .avon-stat-purple .avon-stat-number { color: var(--purple-700); }
  .avon-stat-green  .avon-stat-number { color: var(--green-600); }
  .avon-stat-red    .avon-stat-number { color: var(--red-600); }

  /* ─── ALERTS / BANNERS ─── */
  .avon-alert {
    border-radius: var(--radius-lg);
    padding: 16px 20px;
    border: 1px solid transparent;
    font-size: 0.9375rem;
    line-height: 1.6;
  }

  .avon-alert-info {
    background: var(--blue-100);
    border-color: #BFDBFE;
    color: #1E40AF;
  }

  .avon-alert-success {
    background: var(--green-100);
    border-color: #A7F3D0;
    color: #065F46;
  }

  .avon-alert-warning {
    background: var(--amber-100);
    border-color: #FDE68A;
    color: #92400E;
  }

  .avon-alert-danger {
    background: var(--red-100);
    border-color: #FECACA;
    color: #991B1B;
  }

  /* Override Bootstrap alerts */
  .alert {
    border-radius: var(--radius-lg) !important;
    border-width: 1px !important;
    box-shadow: none !important;
    font-size: 0.9375rem !important;
  }

  /* ─── DATA TABLES ─── */
  .dash-spreadsheet-container {
    border-radius: var(--radius-lg) !important;
    overflow: hidden;
    border: 1px solid var(--gray-200) !important;
    box-shadow: var(--shadow-sm);
  }

  .dash-spreadsheet .dash-header {
    background: #5B21B6 !important;
    color: #fff !important;
    font-size: 0.8125rem !important;
    font-weight: 600 !important;
    letter-spacing: 0.02em !important;
    text-transform: uppercase !important;
    padding: 12px 10px !important;
    border: none !important;
  }

  .dash-spreadsheet .dash-cell {
    font-size: 0.875rem !important;
    padding: 10px !important;
    border-color: var(--gray-100) !important;
    color: var(--gray-700) !important;
  }

  .dash-spreadsheet tr:nth-child(odd) .dash-cell {
    background: var(--purple-50) !important;
  }

  .dash-spreadsheet tr:hover .dash-cell {
    background: var(--purple-100) !important;
  }

  /* ─── MODAL ─── */
  .modal-content {
    border-radius: var(--radius-xl) !important;
    border: none !important;
    box-shadow: var(--shadow-xl) !important;
  }

  .modal-header {
    border-bottom: 1px solid var(--gray-100) !important;
    padding: 20px 24px !important;
  }

  .modal-footer {
    border-top: 1px solid var(--gray-100) !important;
    padding: 16px 24px !important;
  }

  .modal-body { padding: 24px !important; }

  /* ─── WELLNESS PAGE SPECIFICS ─── */
  .wellness-hero {
    background: linear-gradient(135deg, #F5F3FF 0%, #FFFFFF 50%, #F0FDF4 100%);
    padding: 48px 24px 40px;
    text-align: center;
    position: relative;
    overflow: hidden;
  }

  .wellness-hero::before {
    content: '';
    position: absolute;
    top: -60px; left: -60px;
    width: 240px; height: 240px;
    background: radial-gradient(circle, rgba(139,92,246,0.08) 0%, transparent 70%);
    border-radius: 50%;
  }

  .wellness-hero::after {
    content: '';
    position: absolute;
    bottom: -40px; right: -40px;
    width: 200px; height: 200px;
    background: radial-gradient(circle, rgba(16,185,129,0.07) 0%, transparent 70%);
    border-radius: 50%;
  }

  .logo-container {
    width: 56px;
    height: 56px;
    background: linear-gradient(135deg, var(--purple-700), var(--purple-500));
    border-radius: var(--radius-lg);
    display: flex;
    align-items: center;
    justify-content: center;
    box-shadow: 0 4px 14px rgba(91,33,182,0.30);
    margin: 0 auto 20px;
  }

  .wellness-card {
    background: rgba(255,255,255,0.95);
    backdrop-filter: blur(10px);
    border: 1px solid rgba(91,33,182,0.08);
    border-radius: var(--radius-2xl);
    box-shadow: var(--shadow-xl);
  }

  .questionnaire-section {
    background: var(--gray-50);
    border: 1px solid var(--gray-100);
    border-radius: var(--radius-lg);
    padding: 20px 24px;
    margin-bottom: 12px;
  }

  .questionnaire-section h5 {
    font-size: 0.9375rem;
    font-weight: 600;
    color: var(--purple-700);
    margin-bottom: 16px;
  }

  .question-label {
    font-size: 0.875rem;
    font-weight: 500;
    color: var(--gray-700);
    margin-bottom: 8px;
    line-height: 1.5;
  }

  .section-divider {
    border: none;
    border-top: 1px solid var(--gray-200);
    margin: 24px 0;
  }

  .consent-banner {
    background: #FFFBEB;
    border: 1px solid #FDE68A;
    border-left: 4px solid var(--amber-500);
    border-radius: var(--radius-lg);
    padding: 16px 20px;
  }

  .already-booked-card {
    background: #fff;
    border: 1px solid var(--blue-100);
    border-left: 4px solid var(--blue-600);
    border-radius: var(--radius-lg);
    box-shadow: var(--shadow-md);
  }

  /* DatePicker */
  .SingleDatePicker, .DateInput {
    border-radius: var(--radius-md) !important;
  }

  .DateInput_input {
    border-bottom: none !important;
    border: 1.5px solid var(--gray-300) !important;
    border-radius: var(--radius-md) !important;
    font-size: 0.9375rem !important;
    padding: 10px 12px !important;
    height: 44px !important;
    font-family: 'Inter', sans-serif !important;
  }

  .DateInput_input__focused {
    border-color: var(--purple-500) !important;
    box-shadow: 0 0 0 3px rgba(139,92,246,0.12) !important;
  }

  .CalendarDay__selected, .CalendarDay__selected:active, .CalendarDay__selected:hover {
    background: var(--purple-600) !important;
    border-color: var(--purple-600) !important;
  }

  /* RadioItems */
  .custom-radio .form-check-input:checked {
    background-color: var(--purple-600) !important;
    border-color: var(--purple-600) !important;
  }

  .form-check-input:focus {
    box-shadow: 0 0 0 3px rgba(139,92,246,0.15) !important;
    border-color: var(--purple-500) !important;
  }

  /* ─── PROVIDER PORTAL ─── */
  .provider-sidebar-card {
    background: #fff;
    border: 1px solid var(--gray-100);
    border-radius: var(--radius-xl);
    box-shadow: var(--shadow-sm);
    overflow: hidden;
  }

  .provider-nav-btn {
    display: block;
    width: 100%;
    text-align: left;
    padding: 10px 14px;
    border-radius: var(--radius-md);
    font-size: 0.875rem;
    font-weight: 500;
    border: none;
    cursor: pointer;
    transition: var(--transition);
    background: transparent;
    color: var(--gray-700);
    margin-bottom: 4px;
  }

  .provider-nav-btn:hover {
    background: var(--purple-50);
    color: var(--purple-700);
  }

  .provider-nav-btn-active {
    background: var(--purple-100);
    color: var(--purple-700);
    font-weight: 600;
  }

  /* ─── LOADING SCREEN ─── */
  .avon-loading-screen {
    min-height: 100vh;
    display: flex;
    align-items: center;
    justify-content: center;
    background: linear-gradient(135deg, var(--purple-50) 0%, #fff 50%, #F0FDF4 100%);
  }

  /* ─── GYM PORTAL ─── */
  .gym-hero {
    background: linear-gradient(135deg, var(--purple-50) 0%, #fff 100%);
    padding: 48px 24px;
    border-bottom: 1px solid var(--gray-100);
    text-align: center;
  }

  .gym-eligibility-card {
    background: #fff;
    border: 1px solid var(--gray-100);
    border-radius: var(--radius-xl);
    box-shadow: var(--shadow-lg);
    padding: 32px;
  }

  /* ─── BADGE / PILL ─── */
  .avon-badge {
    display: inline-flex;
    align-items: center;
    padding: 2px 10px;
    border-radius: var(--radius-full);
    font-size: 0.75rem;
    font-weight: 600;
  }

  .avon-badge-purple { background: var(--purple-100); color: var(--purple-700); }
  .avon-badge-green  { background: var(--green-100);  color: var(--green-600); }
  .avon-badge-red    { background: var(--red-100);    color: var(--red-600); }
  .avon-badge-amber  { background: var(--amber-100);  color: #92400E; }

  /* ─── SPINNER / LOADING ─── */
  ._dash-loading {
    visibility: hidden;
  }

  /* ─── SCROLLBAR ─── */
  ::-webkit-scrollbar { width: 6px; height: 6px; }
  ::-webkit-scrollbar-track { background: transparent; }
  ::-webkit-scrollbar-thumb {
    background: var(--gray-300);
    border-radius: 99px;
  }
  ::-webkit-scrollbar-thumb:hover { background: var(--gray-500); }

  /* ─── FOOTER ─── */
  .avon-footer {
    text-align: center;
    padding: 24px;
    font-size: 0.75rem;
    color: var(--gray-500);
    border-top: 1px solid var(--gray-100);
    margin-top: 48px;
  }

  /* ─── RESPONSIVE ─── */
  @media (max-width: 768px) {
    .wellness-hero { padding: 32px 16px 28px; }
    .gym-hero { padding: 32px 16px; }
    .provider-portal-btn { top: 10px; right: 12px; font-size: 0.75rem; padding: 7px 12px; }
  }
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