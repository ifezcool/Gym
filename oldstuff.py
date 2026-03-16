import dash
from dash import dcc, html, Input, Output, State, callback_context
from dash_svg import Svg, Path
import dash_bootstrap_components as dbc
import pandas as pd
import numpy as np
import datetime as dt
import pyodbc
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
from dotenv import load_dotenv
import base64
import urllib.parse

load_dotenv('secrets.env')

app = dash.Dash(
    __name__,
    external_stylesheets=[
        dbc.themes.BOOTSTRAP,
        "https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Playfair+Display:wght@400;500;600;700&display=swap",
        "https://cdn.jsdelivr.net/npm/lucide-static@0.344.0/font/lucide.min.css"
    ],
    suppress_callback_exceptions=True
)
app.title = "AVON HMO Enrollee Annual Wellness Portal"

server = app.server

CUSTOM_CSS = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Playfair+Display:wght@400;500;600;700&display=swap');
    
    :root {
        --primary-color: #6B46C1;
        --secondary-color: #38B2AC;
        --primary-rgb: 107, 70, 193;
    }
    
    body {
        font-family: 'Inter', sans-serif;
    }
    
    h1, h2, h3, h4, h5, h6 {
        font-family: 'Playfair Display', serif;
    }
    
    .gradient-bg {
        background: linear-gradient(135deg, #faf5ff 0%, #ffffff 50%, #f0fdf4 100%);
    }
    
    .purple-skew {
        background: rgba(107, 70, 193, 0.05);
        transform: skewY(-3deg);
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        height: 250px;
        content: '';
    }
    
    .green-blob {
        position: absolute;
        bottom: 0;
        right: 0;
        width: 400px;
        height: 400px;
        background: rgba(56, 178, 172, 0.05);
        border-radius: 50%;
        filter: blur(60px);
        pointer-events: none;
    }
    
    .logo-container {
        width: 64px;
        height: 64px;
        background: linear-gradient(135deg, #6B46C1, #805AD5);
        border-radius: 16px;
        display: flex;
        align-items: center;
        justify-content: center;
        transform: rotate(3deg);
        box-shadow: 0 10px 25px rgba(107, 70, 193, 0.25);
        margin: 0 auto;
    }
    
    .card-glass {
        background: rgba(255, 255, 255, 0.9);
        backdrop-filter: blur(10px);
        border: 1px solid rgba(107, 70, 193, 0.1);
        box-shadow: 0 25px 50px -12px rgba(107, 70, 193, 0.08);
    }
    
    .form-input {
        height: 48px;
        border: 2px solid #E9D8FD;
        border-radius: 12px;
        transition: all 0.2s;
    }
    
    .form-input:focus {
        border-color: #6B46C1;
        box-shadow: 0 0 0 3px rgba(107, 70, 193, 0.1);
    }
    
    .btn-primary-custom {
        background: linear-gradient(135deg, #6B46C1, #805AD5);
        border: none;
        height: 48px;
        font-weight: 600;
        border-radius: 12px;
        box-shadow: 0 10px 25px rgba(107, 70, 193, 0.25);
        transition: all 0.2s;
    }
    
    .btn-primary-custom:hover {
        transform: translateY(-2px);
        box-shadow: 0 15px 30px rgba(107, 70, 193, 0.3);
    }
    
    .header-purple {
        background: linear-gradient(135deg, #6B46C1, #805AD5);
    }
    
    .border-left-accent {
        border-left: 4px solid #38B2AC;
    }
    
    .status-card {
        border-top: 8px solid #48BB78;
    }
    
    .validity-banner {
        background: #FFFBEB;
        border: 1px solid #FCD34D;
        border-radius: 8px;
    }
    
    .logo-icon {
        width: 32px;
        height: 32px;
    }
    
    .wellness-card {
        background: rgba(255, 255, 255, 0.9);
        backdrop-filter: blur(10px);
        border: 1px solid rgba(107, 70, 193, 0.1);
        box-shadow: 0 25px 50px -12px rgba(107, 70, 193, 0.08);
        border-radius: 24px;
    }
    
    .questionnaire-section {
        background: rgba(255, 255, 255, 0.7);
        border-radius: 16px;
        padding: 20px;
        margin-bottom: 15px;
        border: 1px solid rgba(107, 70, 193, 0.08);
    }
    
    .questionnaire-section h5 {
        color: #44337A;
        margin-bottom: 15px;
    }
    
    .question-label {
        font-weight: 500;
        color: #4A5568;
        margin-bottom: 8px;
    }
    
    .section-divider {
        border-top: 2px solid #E9D8FD;
        margin: 25px 0;
    }
    
    .booking-header {
        background: linear-gradient(135deg, #6B46C1, #805AD5);
        padding: 30px 0;
        margin-bottom: 30px;
    }
    
    .detail-label {
        color: #718096;
        font-size: 0.875rem;
    }
    
    .detail-value {
        font-weight: 600;
        color: #2D3748;
    }
    
    .already-booked-card {
        background: rgba(255, 255, 255, 0.95);
        border-radius: 16px;
        border-left: 4px solid #3182CE;
        box-shadow: 0 10px 25px rgba(0, 0, 0, 0.1);
    }
    
    .consent-banner {
        background: linear-gradient(135deg, #FEFCBF, #F6E05E);
        border: 1px solid #D69E2E;
        border-radius: 12px;
    }
    
    .custom-select .Select-control {
        height: 48px;
        border: 2px solid #E9D8FD;
        border-radius: 12px;
    }
    
    .custom-select .Select-control:focus {
        border-color: #6B46C1;
        box-shadow: 0 0 0 3px rgba(107, 70, 193, 0.1);
    }
    
    .custom-radio .custom-control-inline {
        margin-right: 20px;
    }
    
    .date-picker-custom .DateInput {
        height: 48px;
        border: 2px solid #E9D8FD;
        border-radius: 12px;
    }
    
    .date-picker-custom .DateInput_focus {
        border-color: #6B46C1;
        box-shadow: 0 0 0 3px rgba(107, 70, 193, 0.1);
    }
</style>
"""

app.index_string = f'''
<!DOCTYPE html>
<html>
    <head>
        {{%metas%}}
        <title>{app.title}</title>
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
        {CUSTOM_CSS}
    </body>
</html>
'''

server = os.environ.get('server_name')
database = os.environ.get('db_name')
username = os.environ.get('db_username')
password = os.environ.get('db_password')

sterling_bank_enrollees = ['100552', '101401', '45492', '45509', '45537', '45704', '45711', '45712', '45747', '45748', '67106', '67113', '67132', '67133', '80701', '105096', '45532']

conn = pyodbc.connect(
    'DRIVER={ODBC Driver 17 for SQL Server};SERVER='
    + server
    +';DATABASE='
    + database
    +';UID='
    + username
    +';PWD='
    + password
)

def load_all_data():
    global wellness_df, wellness_providers, loyalty_enrollees, filled_wellness_df
    query1 = "SELECT * from vw_new_wellness_enrollee_portal_update"
    query2 = 'select MemberNo, MemberName, Client, email, state, selected_provider, Wellness_benefits, selected_date, selected_session, date_submitted from demo_tbl_annual_wellness_enrollee_data a where a.PolicyEndDate = (select max(PolicyEndDate) from demo_tbl_annual_wellness_enrollee_data b where a.MemberNo = b.MemberNo)'
    query3 = "select a.CODE, a.STATE, PROVIDER_NAME, a.ADDRESS,Provider_Name + ' - ' + Location as ProviderLoc, PROVIDER, name from Updated_Wellness_Providers a join tbl_Providerlist_stg b on a.CODE = b.code"
    query4 = 'select * from vw_loyaltybeneficiaries'
    
    wellness_df = pd.read_sql(query1, conn)
    wellness_providers = pd.read_sql(query3, conn)
    loyalty_enrollees = pd.read_sql(query4, conn)
    filled_wellness_df = pd.read_sql(query2, conn)
    
    wellness_df['memberno'] = wellness_df['memberno'].astype(int).astype(str)
    filled_wellness_df['MemberNo'] = filled_wellness_df['MemberNo'].astype(str)
    loyalty_enrollees['MemberNo'] = loyalty_enrollees['MemberNo'].astype(str)

load_all_data()

ladol_special = pd.read_csv('Ladol Special Wellness.csv')

image_filename = 'wellness_image_1.png'
encoded_image = base64.b64encode(open(image_filename, 'rb').read()).decode()

initial_user_data = {
    'email': '', 'mobile_num': '', 'state': 'ABIA',
    'selected_provider': 'ROSEVINE HOSPITAL  -  73 ABA OWERRI ROAD, ABA',
    'job_type': 'Mainly Desk Work', 'gender': 'Male',
}
for i in list('abcdefghijk'):
    initial_user_data[f'resp_1_{i}'] = 'Grand Parent(s)'
for i in list('abcdefghi'):
    initial_user_data[f'resp_2_{i}'] = 'Yes'
for i in list('abcdef'):
    initial_user_data[f'resp_3_{i}'] = 'Yes'
for i in list('abcdefghijklmnopqrst'):
    initial_user_data[f'resp_4_{i}'] = 'Never'

app.layout = html.Div([
    dcc.Location(id='url', refresh=True),
    dcc.Store(id='user-data-store', data=initial_user_data),
    dcc.Store(id='enrollee-data-store', data={}),
    dcc.Store(id='submission-trigger', data=0),
    dcc.Store(id='questionnaire-responses', data={}),
    dcc.Store(id='session-store', data=''),
    
    html.Div([
        dcc.Location(id="url-welcome", refresh=True),
        
        html.Div(className="purple-skew"),
        html.Div(className="green-blob"),
        
        html.Div(
            className="position-relative w-100",
            style={"maxWidth": "520px", "zIndex": "10", "margin": "0 auto"},
            children=[
                html.Div([
                    html.Div(className="logo-container mb-4", children=[
                        Svg(
                            width="32", height="32", viewBox="0 0 24 24",
                            fill="none", stroke="white",
                            style={"strokeWidth": "2", "strokeLinecap": "round", "strokeLinejoin": "round"},
                            children=[
                                Path(d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"),
                                Path(d="m9 12 2 2 4-4")
                            ]
                        )
                    ]),
                    html.H1("Wellness Portal", className="text-4xl fw-bold mb-2", style={"color": "#44337A", "fontSize": "2rem"}),
                    html.P("AVON HMO Enrollee Annual Wellness Portal. Check your eligibility and book your annual wellness checkup.",
                           className="text-lg mb-4", style={"color": "#718096"}),
                ], className="text-center mb-5"),

                dbc.Card([
                    dbc.CardBody([
                        html.Div([
                            html.Label("Member Number / Policy ID", className="fw-medium mb-2", style={"color": "#44337A"}),
                            dcc.Input(
                                id='enrollee-id-input',
                                type='text',
                                placeholder='Enter your Member ID',
                                className='form-control form-input mb-3',
                                style={"fontSize": "18px"}
                            ),
                            html.Div(id='eligibility-message'),
                            
                            dbc.Button([
                                html.Span("Check Eligibility ", className="me-2"),
                                html.Span("→")
                            ], id='member-id-submit-btn', color="primary",
                               className="w-100 btn-primary-custom d-flex align-items-center justify-content-center",
                               style={"color": "white"}),
                            
                            html.Small("Enter your Member ID from URL (?member=12345) or manually", 
                                      className="d-block text-center mt-3", style={"color": "rgba(113, 128, 150, 0.6)"})
                        ], className="p-2")
                    ])
                ], className="card-glass border-0", style={"borderRadius": "24px"}),

                html.Div([
                    dbc.Row([
                        dbc.Col(id='already-booked-section', width=12)
                    ]),
                    
                    dbc.Row([
                        dbc.Col(id='enrollment-form-section', width=12)
                    ]),
                ], className="mt-4"),

                html.P(f"© {dt.datetime.now().year} AVON HMO. All rights reserved.",
                       className="text-center mt-4 small", style={"color": "rgba(113, 128, 150, 0.6)"})
            ]
        )
    ], className="gradient-bg min-vh-100 d-flex align-items-center justify-content-center p-4 position-relative overflow-hidden"),
    
    dbc.Modal([
        dbc.ModalHeader("Submission Successful", style={"fontFamily": "Playfair Display, serif", "color": "#44337A"}),
        dbc.ModalBody(id='submission-message'),
        dbc.ModalFooter(dbc.Button("Close", id="close-modal", className="btn-primary-custom", style={"color": "white"}))
    ], id="success-modal", is_open=False, size="lg", centered=True),
])


@app.callback(
    [Output('eligibility-message', 'children'),
     Output('already-booked-section', 'children'),
     Output('enrollment-form-section', 'children'),
     Output('enrollee-data-store', 'data'),
     Output('enrollee-id-input', 'value')],
    [Input('url', 'search'),
     Input('member-id-submit-btn', 'n_clicks'),
     Input('enrollee-id-input', 'n_submit')],
    [State('enrollee-id-input', 'value'),
     State('enrollee-data-store', 'data')]
)
def check_eligibility(url_search, n_clicks, n_submit, enrollee_id, stored_data):
    # Check if triggered by URL, button or enter key
    ctx = callback_context
    triggered_id = ctx.triggered[0]['prop_id'].split('.')[0] if ctx.triggered else None
    
    # Reload filled data
    global filled_wellness_df
    query2 = 'select MemberNo, MemberName, Client, email, state, selected_provider, Wellness_benefits, selected_date, selected_session, date_submitted from demo_tbl_annual_wellness_enrollee_data a where a.PolicyEndDate = (select max(PolicyEndDate) from demo_tbl_annual_wellness_enrollee_data b where a.MemberNo = b.MemberNo)'
    filled_wellness_df = pd.read_sql(query2, conn)
    filled_wellness_df['MemberNo'] = filled_wellness_df['MemberNo'].astype(str)
    
    if triggered_id == 'url' or not enrollee_id:
        parsed = urllib.parse.parse_qs(urllib.parse.urlparse(url_search).query)
        url_member = parsed.get('member', [None])[0]
        if url_member:
            enrollee_id = url_member
    
    if not enrollee_id:
        return "", "", "", {}, ""
    
    enrollee_id = str(enrollee_id).strip()
    
    if enrollee_id in filled_wellness_df['MemberNo'].values:
        row = filled_wellness_df[filled_wellness_df['MemberNo'] == enrollee_id].iloc[0]
        member_name = row['MemberName']
        submitted_date = str(row['date_submitted'])[:10]
        final_submit_date = dt.datetime.strptime(submitted_date, "%Y-%m-%d").date()
        policystart = wellness_df.loc[wellness_df['memberno'] == enrollee_id, 'PolicyStartDate'].values[0]
        policyend = wellness_df.loc[wellness_df['memberno'] == enrollee_id, 'PolicyEndDate'].values[0]
        
        if policystart <= final_submit_date <= policyend:
            member_name = row['MemberName']
            clientname = row['Client']
            package = row['Wellness_benefits']
            member_email = row['email']
            provider = row['selected_provider']
            app_date = row['selected_date']
            app_session = row['selected_session']
            
            six_weeks = dt.datetime.strptime(submitted_date, "%Y-%m-%d").date() + dt.timedelta(weeks=6)
            six_weeks_str = six_weeks.strftime('%A, %d %B %Y')
            
            msg = dbc.Alert([
                html.H5(f"Dear {member_name}."),
                html.P(f"Please note that you have already booked your wellness appointment on {submitted_date} and your booking confirmation has been sent to {member_email} as provided"),
                html.P(f"Wellness Facility: {provider}"),
                html.P(f"Wellness Benefits: {package}"),
                html.P(f"Appointment Date: {app_date} - {app_session}"),
                html.P("Kindly note that your wellness result will only be available two (2) weeks after your visit to the provider for your wellness test."),
                html.P("Kindly contact your Client Manager if you wish change your booking appointment/wellness center."),
                html.Hr(),
                html.P(f"Note that your annual wellness is only valid till {six_weeks_str}", className='font-weight-bold')
            ], color="info", className='already-booked-card p-4')
            
            enrollee_data = {
                'member_name': member_name, 'client': clientname, 'policy': '',
                'policystart': str(policystart), 'policyend': str(policyend),
                'already_booked': True
            }
            return msg, "", "", enrollee_data, enrollee_id
    
    if enrollee_id in wellness_df['memberno'].values:
        enrollee_data = {
            'already_booked': False,
            'policystart': str(wellness_df.loc[wellness_df['memberno'] == enrollee_id, 'PolicyStartDate'].values[0]),
            'policyend': str(wellness_df.loc[wellness_df['memberno'] == enrollee_id, 'PolicyEndDate'].values[0]),
            'member_name': str(wellness_df.loc[wellness_df['memberno'] == enrollee_id, 'membername'].values[0]),
            'client': str(wellness_df.loc[wellness_df['memberno'] == enrollee_id, 'Client'].values[0]),
            'policy': str(wellness_df.loc[wellness_df['memberno'] == enrollee_id, 'PolicyName'].values[0]),
            'package': str(wellness_df.loc[wellness_df['memberno'] == enrollee_id, 'WellnessPackage'].values[0]),
            'age': int(wellness_df.loc[wellness_df['memberno'] == enrollee_id, 'Age'].values[0]),
            'relation': str(wellness_df.loc[wellness_df['memberno'] == enrollee_id, 'Relation'].values[0]),
            'gender': str(wellness_df.loc[wellness_df['memberno'] == enrollee_id, 'sex'].values[0]) if 'sex' in wellness_df.columns else 'Male'
        }
        
        six_week_dt = dt.date.today() + dt.timedelta(weeks=6)
        six_weeks = six_week_dt.strftime('%A, %d %B %Y')
        
        consent_msg = dbc.Alert([
            html.H5(f"Dear {enrollee_data['member_name']}."),
            html.P([
                html.B("Kindly confirm that your enrollment details match the info displayed below."),
                html.Br(), html.Br(),
                "Also note that by proceeding to fill this form, you consent to the collection and processing of your data for the purpose of this wellness screening exercise.",
                "You understand that your results may be shared with the HMO for claims management and care coordination, ",
                "and that your data will be handled in accordance with Avon HMO's Privacy Policy."
            ]),
            html.Hr(),
            html.P(f"Company: {enrollee_data['client']}. Policy: {enrollee_data['policy']}. Policy End Date: {enrollee_data['policyend']}.", className='font-weight-bold'),
            html.P("Please contact your Client Manager if this information does not match your enrollment details.", className='text-danger'),
            html.Hr(),
            html.P(f"Please note that once you complete this form, you only have till {six_weeks} to complete your wellness check.", className='font-weight-bold text-primary')
        ], color="warning", className="consent-banner mb-4")
        
        form = build_enrollment_form(enrollee_data)
        return "", "", [consent_msg, form], enrollee_data, enrollee_id
    
    not_eligible = dbc.Alert("You are not eligible to participate, please contact your HR or Client Manager", color="info", className="alert alert-danger mb-3", style={"backgroundColor": "#FED7D7", "border": "1px solid #FEB2B2", "color": "#C53030"})
    return not_eligible, "", "", {}, enrollee_id


def build_enrollment_form(enrollee_data):
    client = enrollee_data['client']
    policy = enrollee_data['policy']
    age = enrollee_data['age']
    relation = enrollee_data['relation']
    
    current_date = dt.date.today()
    max_date = dt.date(2027, 12, 31)
    
    if client == 'PIVOT GIS LIMITED' or client == 'PIVOT   GIS LIMITED':
        max_date = dt.date(2024, 12, 31)
    elif client == 'UNITED BANK FOR AFRICA':
        max_date = dt.date(2028, 2, 1)
    
    form = dbc.Card([
        dbc.CardBody([
            html.H4("Kindly fill all the fields below to proceed", className='mb-4', style={"color": "#44337A"}),
            
            dbc.Row([
                dbc.Col([
                    html.Label("Input a Valid Email Address", className="small fw-medium", style={"color": "#44337A"}),
                    dcc.Input(id='email-input', type='email', placeholder='you@company.com', 
                             className='form-control form-input', style={"fontSize": "16px"})
                ], width=12, md=6, className="mb-3"),
                dbc.Col([
                    html.Label("Input a Valid Mobile Number", className="small fw-medium", style={"color": "#44337A"}),
                    dcc.Input(id='mobile-input', type='text', placeholder='080...', 
                             className='form-control form-input', style={"fontSize": "16px"})
                ], width=12, md=6, className="mb-3")
            ]),
            
            dbc.Row([
                dbc.Col([
                    html.Label("Gender", className="small fw-medium d-block mb-2", style={"color": "#44337A"}),
                    dbc.RadioItems(
                        id='gender-radio',
                        options=[{'label': ' Male ', 'value': 'Male'}, {'label': ' Female ', 'value': 'Female'}],
                        value='Male',
                        inline=True,
                        className="mb-3"
                    )
                ], width=12)
            ]),
            
            dbc.Row([
                dbc.Col([
                    html.Label("Nature of Work / Occupation Type", className="small fw-medium", style={"color": "#44337A"}),
                    dcc.Dropdown(
                        id='job-type-select',
                        options=get_job_options(client, policy),
                        value='',
                        placeholder='Select Work Category',
                        className="mb-3"
                    )
                ], width=12)
            ]),
            
            html.Hr(className="my-4"),
            
            dbc.Row([
                dbc.Col([
                    html.Label("Your Current Location", className="small fw-medium", style={"color": "#44337A"}),
                    dcc.Dropdown(
                        id='state-select',
                        options=get_state_options(client),
                        value='',
                        placeholder='Pick your Current State of Residence',
                        className="mb-3"
                    )
                ], width=12)
            ]),
            
            dbc.Row([
                dbc.Col([
                    html.Label("Pick your Preferred Wellness Facility", className="small fw-medium", style={"color": "#44337A"}),
                    dcc.Dropdown(
                        id='provider-select',
                        options=[],
                        value='',
                        placeholder='Select a Provider',
                        className="mb-3"
                    )
                ], width=12)
            ]),
            
            dbc.Row([
                dbc.Col([
                    html.Label("Select Your Preferred Appointment Date", className="small fw-medium", style={"color": "#44337A"}),
                    dcc.DatePickerSingle(
                        id='date-picker',
                        min_date_allowed=current_date,
                        max_date_allowed=max_date,
                        initial_visible_month=current_date,
                        date=None,
                        className="mb-3"
                    )
                ], width=12)
            ], className="mb-3", id='date-picker-row'),
            
            dbc.Row([
                dbc.Col(id='session-radio-container', width=12)
            ], className='mb-3'),
            
            dbc.Alert("Fill the questionnaire below to complete your wellness booking", 
                     color="info", id='booking-info-alert',
                     style={"backgroundColor": "#EBF8FF", "border": "1px solid #4299E1", "color": "#2C5282"}),
            
            html.Hr(className="my-4"),
            
            build_health_questionnaire(),
            
            html.Hr(className="my-4"),
            
            dbc.Button([
                html.Span("Submit Booking ", className="me-2"),
                html.Span("✓")
            ], id='submit-form-btn', color='primary', size='lg', 
               className="w-100 btn-primary-custom d-flex align-items-center justify-content-center", style={"color": "white"})
            
        ])
    ], className="card-glass border-0", style={"borderRadius": "24px"})
    
    return html.Div([form], className="px-3")


def get_job_options(client, policy):
    if policy == 'TOTAL ENERGIES MANAGED CARE PLAN':
        return [
            {'label': 'Offshore Personnel', 'value': 'Offshore Personnel'},
            {'label': 'Fire Team', 'value': 'Fire Team'},
            {'label': 'MERT', 'value': 'MERT'},
            {'label': 'Lab Personnel', 'value': 'Lab Personnel'},
            {'label': 'Admin and Others', 'value': 'Admin and Others'}
        ]
    return [
        {'label': 'Mainly Desk Work', 'value': 'Mainly Desk Work'},
        {'label': 'Mainly Field Work', 'value': 'Mainly Field Work'},
        {'label': 'Desk and Field Work', 'value': 'Desk and Field Work'},
        {'label': 'Physical Outdoor Work', 'value': 'Physical Outdoor Work'},
        {'label': 'Physical Indoor Work', 'value': 'Physical Indoor Work'}
    ]


def get_state_options(client):
    excluded_state = 'HQ'
    available_states = list(wellness_providers['STATE'].unique())
    available_states = [s for s in available_states if s != excluded_state]
    
    state_map = {
        'UNITED BANK FOR AFRICA': [s for s in available_states if s != 'HQ'],
        'VERTEVILLE ENERGY': ['LAGOS', 'BORNO', 'DELTA', 'RIVERS'],
        'PETROSTUFF NIGERIA LIMITED': ['LAGOS', 'ABUJA', 'RIVERS'],
        'TRANSCORP HILTON HOTEL ABUJA': ['ABUJA'],
        'REX INSURANCE LTD': ['LAGOS', 'RIVERS', 'DELTA', 'OYO', 'KADUNA', 'KANO']
    }
    return [{'label': s, 'value': s} for s in state_map.get(client, [s for s in available_states if s != 'HQ'])]


def build_health_questionnaire():
    family_questions = [
        ('a. HYPERTENSION (HIGH BLOOD PRESSURE)', 'resp_1_a'),
        ('b. DIABETES', 'resp_1_b'),
        ('c. CANCER (ANY TYPE)', 'resp_1_c'),
        ('d. ASTHMA', 'resp_1_d'),
        ('e. ARTHRITIS', 'resp_1_e'),
        ('f. HIGH CHOLESTEROL', 'resp_1_f'),
        ('g. HEART ATTACK', 'resp_1_g'),
        ('h. EPILEPSY', 'resp_1_h'),
        ('i. TUBERCLOSIS', 'resp_1_i'),
        ('j. SUBSTANCE DEPENDENCY', 'resp_1_j'),
        ('k. MENTAL ILLNESS', 'resp_1_k'),
    ]
    
    personal_questions = [
        ('i. HYPERTENSION (HIGH BLOOD PRESSURE)', 'resp_2_a'),
        ('ii. DIABETES', 'resp_2_b'),
        ('iii. CANCER (ANY TYPE)', 'resp_2_c'),
        ('iv. ASTHMA', 'resp_2_d'),
        ('v. ULCER', 'resp_2_e'),
        ('vi. POOR VISION', 'resp_2_f'),
        ('vii. ALLERGY', 'resp_2_g'),
        ('viii. ARTHRITIS/LOW BACK PAIN', 'resp_2_h'),
        ('ix. ANXIETY/DEPRESSION', 'resp_2_i'),
    ]
    
    surgical_questions = [
        ('i. CEASAREAN SECTION', 'resp_3_a'),
        ('ii. FRACTURE REPAIR', 'resp_3_b'),
        ('iii. HERNIA', 'resp_3_c'),
        ('iv. LUMP REMOVAL', 'resp_3_d'),
        ('v. APPENDICETOMY', 'resp_3_e'),
        ('vi. SPINE SURGERY', 'resp_3_f'),
    ]
    
    wellness_questions = [
        ('a. I avoid eating foods that are high in fat', 'resp_4_a'),
        ('b. I have been avoiding the use or minimise my exposure to alcohol', 'resp_4_b'),
        ('c. I have been avoiding the use of tobacco products', 'resp_4_c'),
        ('d. I am physically fit and exercise at least 30 minutes every day', 'resp_4_d'),
        ('e. I have been eating vegetables and fruits at least 3 times weekly', 'resp_4_e'),
        ('f. I drink 6-8 glasses of water a day', 'resp_4_f'),
        ('g. I maintain my weight within the recommendation for my weight, age and height', 'resp_4_g'),
        ('h. My blood pressure is within normal range without the use of drugs', 'resp_4_h'),
        ('i. My cholesterol level is within the normal range', 'resp_4_i'),
        ('j. I easily make decisions without worry', 'resp_4_j'),
        ('k. I enjoy more than 5 hours of sleep at night', 'resp_4_k'),
        ('l. I enjoy my work and life', 'resp_4_l'),
        ('m. I enjoy the support from friends and family', 'resp_4_m'),
        ('n. I feel bad about myself or that I am a failure or have let myself or my family down', 'resp_4_n'),
        ('o. I have poor appetite or I am over-eating', 'resp_4_o'),
        ('p. I feel down, depressed, hopeless, tired or have little energy', 'resp_4_p'),
        ('q. I have trouble falling asleep, staying asleep, or sleeping too much', 'resp_4_q'),
        ('r. I have no interest or pleasure in doing things', 'resp_4_r'),
        ('s. I have trouble concentrating on things, such as reading the newspaper, or watching TV', 'resp_4_s'),
        ('t. I think I would be better off dead or better off hurting myself in some way', 'resp_4_t'),
    ]
    
    sections = []
    
    sections.append(html.Div(className="questionnaire-section", children=[
        html.H5("1. Family Medical History", className="fw-semibold"),
        html.P("Have any of your family members experienced any of the following conditions?", className="text-muted small mb-3")
    ]))
    
    for q, qid in family_questions:
        sections.append(html.Div(className="mb-3", children=[
            html.P(q, className='question-label mb-2'),
            dbc.RadioItems(
                id=f'radio-{qid}',
                options=[
                    {'label': ' Grand Parent(s) ', 'value': 'Grand Parent(s)'},
                    {'label': ' Parent(s) ', 'value': 'Parent(s)'},
                    {'label': ' Uncle/Aunty ', 'value': 'Uncle/Aunty'},
                    {'label': ' Nobody ', 'value': 'Nobody'}
                ],
                value='Grand Parent(s)',
                inline=True,
                className="custom-radio"
            )
        ]))
    
    sections.append(html.Hr(className="section-divider"))
    sections.append(html.Div(className="questionnaire-section", children=[
        html.H5("2. Personal Medical History", className="fw-semibold"),
        html.P("Do you have any of the following condition(s) that you are managing?", className="text-muted small mb-3")
    ]))
    
    for q, qid in personal_questions:
        sections.append(html.Div(className="mb-3", children=[
            html.P(q, className='question-label mb-2'),
            dbc.RadioItems(
                id=f'radio-{qid}',
                options=[
                    {'label': ' Yes ', 'value': 'Yes'},
                    {'label': ' No ', 'value': 'No'},
                    {'label': ' Yes, but not on Medication ', 'value': 'Yes, but not on Medication'}
                ],
                value='Yes',
                inline=True,
                className="custom-radio"
            )
        ]))
    
    sections.append(html.Hr(className="section-divider"))
    sections.append(html.Div(className="questionnaire-section", children=[
        html.H5("3. Personal Surgical History", className="fw-semibold"),
        html.P("Have you ever had surgery for any of the following?", className="text-muted small mb-3")
    ]))
    
    for q, qid in surgical_questions:
        sections.append(html.Div(className="mb-3", children=[
            html.P(q, className='question-label mb-2'),
            dbc.RadioItems(
                id=f'radio-{qid}',
                options=[
                    {'label': ' Yes ', 'value': 'Yes'},
                    {'label': ' No ', 'value': 'No'}
                ],
                value='Yes',
                inline=True,
                className="custom-radio"
            )
        ]))
    
    sections.append(html.Hr(className="section-divider"))
    sections.append(html.Div(className="questionnaire-section", children=[
        html.H5("4. Health Survey Questionnaire", className="fw-semibold"),
        html.P("Kindly provide valid responses to the following questions", className="text-muted small mb-3")
    ]))
    
    for q, qid in wellness_questions:
        sections.append(html.Div(className="mb-3", children=[
            html.P(q, className='question-label mb-2'),
            dbc.RadioItems(
                id=f'radio-{qid}',
                options=[
                    {'label': ' Never ', 'value': 'Never'},
                    {'label': ' Occasional ', 'value': 'Occasional'},
                    {'label': ' Always ', 'value': 'Always'},
                    {'label': ' I Do Not Know ', 'value': 'I Do Not Know'}
                ],
                value='Never',
                inline=True,
                className="custom-radio"
            )
        ]))
    
    return html.Div(sections)


@app.callback(
    Output('questionnaire-responses', 'data'),
    [Input('radio-resp_1_a', 'value'),
     Input('radio-resp_1_b', 'value'),
     Input('radio-resp_1_c', 'value'),
     Input('radio-resp_1_d', 'value'),
     Input('radio-resp_1_e', 'value'),
     Input('radio-resp_1_f', 'value'),
     Input('radio-resp_1_g', 'value'),
     Input('radio-resp_1_h', 'value'),
     Input('radio-resp_1_i', 'value'),
     Input('radio-resp_1_j', 'value'),
     Input('radio-resp_1_k', 'value'),
     Input('radio-resp_2_a', 'value'),
     Input('radio-resp_2_b', 'value'),
     Input('radio-resp_2_c', 'value'),
     Input('radio-resp_2_d', 'value'),
     Input('radio-resp_2_e', 'value'),
     Input('radio-resp_2_f', 'value'),
     Input('radio-resp_2_g', 'value'),
     Input('radio-resp_2_h', 'value'),
     Input('radio-resp_2_i', 'value'),
     Input('radio-resp_3_a', 'value'),
     Input('radio-resp_3_b', 'value'),
     Input('radio-resp_3_c', 'value'),
     Input('radio-resp_3_d', 'value'),
     Input('radio-resp_3_e', 'value'),
     Input('radio-resp_3_f', 'value'),
     Input('radio-resp_4_a', 'value'),
     Input('radio-resp_4_b', 'value'),
     Input('radio-resp_4_c', 'value'),
     Input('radio-resp_4_d', 'value'),
     Input('radio-resp_4_e', 'value'),
     Input('radio-resp_4_f', 'value'),
     Input('radio-resp_4_g', 'value'),
     Input('radio-resp_4_h', 'value'),
     Input('radio-resp_4_i', 'value'),
     Input('radio-resp_4_j', 'value'),
     Input('radio-resp_4_k', 'value'),
     Input('radio-resp_4_l', 'value'),
     Input('radio-resp_4_m', 'value'),
     Input('radio-resp_4_n', 'value'),
     Input('radio-resp_4_o', 'value'),
     Input('radio-resp_4_p', 'value'),
     Input('radio-resp_4_q', 'value'),
     Input('radio-resp_4_r', 'value'),
     Input('radio-resp_4_s', 'value'),
     Input('radio-resp_4_t', 'value')]
)
def update_questionnaire_responses(r1a, r1b, r1c, r1d, r1e, r1f, r1g, r1h, r1i, r1j, r1k,
                                    r2a, r2b, r2c, r2d, r2e, r2f, r2g, r2h, r2i,
                                    r3a, r3b, r3c, r3d, r3e, r3f,
                                    r4a, r4b, r4c, r4d, r4e, r4f, r4g, r4h, r4i, r4j, r4k, r4l, r4m, r4n, r4o, r4p, r4q, r4r, r4s, r4t):
    return {
        'resp_1_a': r1a, 'resp_1_b': r1b, 'resp_1_c': r1c, 'resp_1_d': r1d, 'resp_1_e': r1e,
        'resp_1_f': r1f, 'resp_1_g': r1g, 'resp_1_h': r1h, 'resp_1_i': r1i, 'resp_1_j': r1j, 'resp_1_k': r1k,
        'resp_2_a': r2a, 'resp_2_b': r2b, 'resp_2_c': r2c, 'resp_2_d': r2d, 'resp_2_e': r2e,
        'resp_2_f': r2f, 'resp_2_g': r2g, 'resp_2_h': r2h, 'resp_2_i': r2i,
        'resp_3_a': r3a, 'resp_3_b': r3b, 'resp_3_c': r3c, 'resp_3_d': r3d, 'resp_3_e': r3e, 'resp_3_f': r3f,
        'resp_4_a': r4a, 'resp_4_b': r4b, 'resp_4_c': r4c, 'resp_4_d': r4d, 'resp_4_e': r4e,
        'resp_4_f': r4f, 'resp_4_g': r4g, 'resp_4_h': r4h, 'resp_4_i': r4i, 'resp_4_j': r4j,
        'resp_4_k': r4k, 'resp_4_l': r4l, 'resp_4_m': r4m, 'resp_4_n': r4n, 'resp_4_o': r4o,
        'resp_4_p': r4p, 'resp_4_q': r4q, 'resp_4_r': r4r, 'resp_4_s': r4s, 'resp_4_t': r4t
    }


@app.callback(
    Output('provider-select', 'options'),
    [Input('state-select', 'value')],
    [State('enrollee-id-input', 'value')]
)
def update_providers(state, enrollee_id):
    if not enrollee_id or not state:
        return []
    
    enrollee_id = str(enrollee_id).strip()
    if enrollee_id not in wellness_df['memberno'].values:
        return []
    
    client = wellness_df.loc[wellness_df['memberno'] == enrollee_id, 'Client'].values[0]
    
    providers = get_providers_for_client_state(client, state, enrollee_id)
    return [{'label': p, 'value': p} for p in providers]


def get_providers_for_client_state(client, state, enrollee_id=None):
    if client == 'UNITED BANK FOR AFRICA':
        if state == 'UBA HQ':
            return ['UBA Head Office (CERBA Onsite) - Marina, Lagos Island']
        elif state == 'RIVERS':
            return [
                'PONYX HOSPITALS LTD - Plot 26,presidential estate, GRA phase iii, opp. NDDC H/Qrts, port- harcourt/ Aba expressway',
                'UNION DIAGNOSTICS - Finima Street, PortHarcourt, Rivers'
            ]
    
    if client == 'STANDARD CHARTERED BANK NIGERIA LIMITED':
        base_providers = list(wellness_providers.loc[wellness_providers['STATE'] == state, 'PROVIDER'].unique())
        if state == 'LAGOS':
            return base_providers + ['Onsite - SCB Head Office - 142, Ahmadu Bello Way, Victoria Island']
        elif state == 'RIVERS' or state == 'RIVERS ':
            return base_providers + ['Onsite - SCB Office, 143, Port Harcourt Aba Express Road (F-0)']
        elif state == 'FCT':
            return base_providers + ['Onsite - SCB Office, 374 Ademola Adetokunbo Crescent Wuse II, Beside Visa/Airtel Building']
    
    if client == 'TRANSCORP POWER UGHELLI' and state == 'DELTA':
        return list(wellness_providers.loc[wellness_providers['STATE'] == state, 'PROVIDER'].unique()) + ['AVON MEDICAL SITE CLINIC, Ughelli']
    
    if client == 'TRANS AFAM POWER PLANT LIMITED' and state == 'RIVERS':
        return list(wellness_providers.loc[wellness_providers['STATE'] == state, 'PROVIDER'].unique()) + ['AVON MEDICAL SITE CLINIC, Afam']
    
    if client == 'TULIP COCOA PROCESSING' and state == 'OGUN':
        return list(wellness_providers.loc[wellness_providers['STATE'] == state, 'PROVIDER'].unique()) + ['AMAZING GRACE HOSPITAL - 7, Iloro Street, Ijebu-Ode, Ogun State']
    
    if client in ['HEIRS HOLDINGS', 'TRANSCORP PLC', 'TONY ELUMELU FOUNDATION'] and state == 'LAGOS':
        relation = wellness_df.loc[wellness_df['memberno'] == enrollee_id, 'Relation'].values[0]
        if relation in ['MEMBER', 'FEMALE MEMBER', 'MALE MEMBER']:
            return ['AVON Medical - Onsite']
        return list(wellness_providers.loc[wellness_providers['STATE'] == state, 'ProviderLoc'].unique())
    
    if client == 'AFRILAND PROPERTIES PLC' and state == 'LAGOS':
        return list(wellness_providers.loc[wellness_providers['STATE'] == state, 'PROVIDER'].unique()) + ['AVON Medical - Onsite']
    
    if client == 'TRANSCORP HOTELS ABUJA' and state == 'FCT':
        return list(wellness_providers.loc[wellness_providers['STATE'] == state, 'PROVIDER'].unique()) + ['AVON Medical - Onsite']
    
    if client == 'PIVOT GIS LIMITED' and state == 'LAGOS':
        return list(wellness_providers.loc[wellness_providers['STATE'] == state, 'PROVIDER'].unique()) + [
            'MECURE HEALTHCARE, OSHODI - Debo Industrial Cmpd, Plot 6, Block H, Oshodi Industrial Scheme',
            'MECURE HEALTHCARE, LEKKI - Niyi Okunubi Street, Off Admiralty way. Lekki phase 1',
            'CLINIX HEALTHCARE, ILUPEJU - Plot B, BLKXII, Alhaji Adejumo Avenue, Ilupeju, Lagos',
            'CLINIX HEALTHCARE, FESTAC - Dele Orisabiyi Street, Amuwo Odofin, Lagos'
        ]
    
    if client == 'VERTEVILLE ENERGY':
        if state == 'LAGOS':
            return ['Union Diagnostics, V/I - 5 Eletu Ogabi Street, Off Adeola Odeku, Victoria Island, Lagos', 
                    'CERBA Lancet, V/I - 3 Babatunde Jose Street, Adetokunbo Ademola']
        elif state == 'DELTA':
            return ['Union Diagnostics and Clinical Services - Onsite']
        elif state == 'BORNO':
            return ['Kanem Hospital and Maternity - 152 Tafewa Balewa road, Opp Lamisula Police station, Mafoni ward, Maiduguri.']
        elif state == 'RIVERS':
            return ['Union Diagnostic - Port-Harcourt: 2, Finima Street, Old GRA, Opp. Leventis bus-stop)']
    
    if client == 'PETROSTUFF NIGERIA LIMITED':
        if state == 'LAGOS':
            return ['BEACON HEALTH - No 70, Fatai Arobieke Street, Lekki Phase 1, Lagos',
                    'AFRIGLOBAL MEDICARE DIAGNOSTIC CENTRE - 8 Mobolaji Bank Anthony Way Ikeja',
                    'UNION DIAGNOSTICS - 5,Eletu Ogabi street off Adeola odeku V.I']
        elif state == 'ABUJA':
            return ['BODY AFFAIRS DIAGNOSTICS - 1349, Ahmadu Bello Way, Garki 2, Abuja']
        elif state == 'RIVERS':
            return ['PONYX HOSPITALS LTD - Plot 26, Presidential Estate, GRA Phase III, opp. NDDC H/Qrts, Port-Harcourt/Aba Expressway']
    
    if client == 'TRANSCORP HILTON HOTEL ABUJA' and state == 'ABUJA':
        return ['TRANSCORP/E-CLINIC WELLNESS']
    
    if client == 'REX INSURANCE LTD':
        if state == 'LAGOS':
            return ['AFRIGLOBAL MEDICARE DIAGNOSTIC CENTRE - Plot 1192A Kasumu Ekemode St, Victoria Island, Lagos',
                    'CLINIX HEALTHCARE - Plot B, BLKXII, Alhaji Adejumo Avenue, Ilupeju, Lagos']
        elif state == 'RIVERS':
            return ['PONYX HOSPITALS LTD - Plot 26, Presidential Estate, GRA Phase III, opp. NDDC H/Qrts, Port-Harcourt/Aba Expressway']
        elif state == 'DELTA':
            return ['ECHOLAB - 375B Nnebisi Road, Umuagu, Asaba, Delta']
        elif state == 'OYO':
            return ['BEACONHEALTH - 1, C.S Ola Street, Opposite Boldlink Ltd, Henry Tee Bus Stop, Ring Road, Ibadan']
        elif state == 'KADUNA':
            return ['HARMONY HOSPITAL LTD - 74, Narayi Road, Barnawa, Kaduna']
        elif state == 'KANO':
            return ['RAYSCAN DIAGNOSTICS LTD - Plot 4 Gyadi Court Road, Kano']
    
    return list(wellness_providers.loc[wellness_providers['STATE'] == state, 'ProviderLoc'].unique())


@app.callback(
    [Output('session-radio-container', 'children'),
     Output('date-picker-row', 'style'),
     Output('session-store', 'data')],
    [Input('state-select', 'value'),
     Input('provider-select', 'value'),
     Input('date-picker', 'date'),
     Input('session-radio', 'value')],
    [State('enrollee-id-input', 'value'),
     State('session-store', 'data')]
)
def update_sessions(state, provider, selected_date, session_radio_value, enrollee_id, current_session):
    if not enrollee_id:
        return html.Div(), {'display': 'none'}, ''
    
    enrollee_id = str(enrollee_id).strip()
    if enrollee_id not in wellness_df['memberno'].values:
        return html.Div(), {'display': 'none'}, ''
    
    client = wellness_df.loc[wellness_df['memberno'] == enrollee_id, 'Client'].values[0]
    
    if client == 'PIVOT GIS LIMITED' or client == 'PIVOT   GIS LIMITED':
        return html.Div(), {'display': 'block'}, ''
    
    if (state == 'LAGOS' or state == 'UBA HQ') and provider:
        if 'UBA Head Office' in provider:
            return dbc.Alert("The date for your Wellness Exercise will be communicated to you by your HR. Kindly fill the questionaire below to complete your wellness booking", color="info"), {'display': 'none'}, ''
        
        if ('CERBA LANCET' in provider) or ('CERBA LANCET NIGERIA' in provider):
            if not selected_date:
                return dbc.Alert("Please select a date first", color="warning"), {'display': 'block'}, current_session
            
            # Reload filled data
            global filled_wellness_df
            query2 = 'select MemberNo, MemberName, Client, email, state, selected_provider, Wellness_benefits, selected_date, selected_session, date_submitted from demo_tbl_annual_wellness_enrollee_data a where a.PolicyEndDate = (select max(PolicyEndDate) from demo_tbl_annual_wellness_enrollee_data b where a.MemberNo = b.MemberNo)'
            filled_wellness_df = pd.read_sql(query2, conn)
            filled_wellness_df['MemberNo'] = filled_wellness_df['MemberNo'].astype(str)
            
            selected_date_str = dt.datetime.strptime(selected_date, '%Y-%m-%d').strftime('%Y-%m-%d')
            
            booked_sessions = filled_wellness_df.loc[
                (filled_wellness_df['selected_date'] == selected_date_str) &
                (filled_wellness_df['selected_provider'] == provider),
                'selected_session'
            ].values.tolist()
            
            available_sessions = ['08:00 AM - 09:00 AM', '09:00 AM - 10:00 AM', '10:00 AM - 11:00 AM', '11:00 AM - 12:00 PM',
                                   '12:00 PM - 01:00 PM', '01:00 PM - 02:00 PM', '02:00 PM - 03:00 PM', '03:00 PM - 04:00 PM']
            
            session_bookings_count = {s: booked_sessions.count(s) for s in available_sessions}
            available_sessions = [s for s in available_sessions if session_bookings_count[s] < 3]
            
            if not available_sessions:
                return dbc.Alert("All sessions for the selected date at this facility are fully booked. Please select another date or facility.", color="danger"), {'display': 'block'}, current_session
            
            return [dbc.Alert("Please note that the Facilities are opened between the 8:00 am and 5:00 pm, Monday - Friday and 8:00 am - 2:00 pm on Saturdays.", color="info"),
                    dbc.RadioItems(
                        id='session-radio',
                        options=[{'label': s, 'value': s} for s in available_sessions],
                        value=session_radio_value if session_radio_value in available_sessions else None,
                        inline=True
                    )], {'display': 'block'}, session_radio_value if session_radio_value else current_session
    
    return html.Div(), {'display': 'block'}, ''


@app.callback(
    [Output('success-modal', 'is_open'),
     Output('submission-message', 'children')],
    [Input('submit-form-btn', 'n_clicks'),
     Input('close-modal', 'n_clicks')],
    [State('enrollee-id-input', 'value'),
     State('email-input', 'value'),
     State('mobile-input', 'value'),
     State('gender-radio', 'value'),
     State('job-type-select', 'value'),
     State('state-select', 'value'),
     State('provider-select', 'value'),
     State('date-picker', 'date'),
     State('session-store', 'data'),
     State('enrollee-data-store', 'data'),
     State('questionnaire-responses', 'data')],
    prevent_initial_call=True
)
def submit_form(submit_clicks, close_clicks, enrollee_id, email, mobile, gender, job_type, state, provider, selected_date, session, enrollee_data, questionnaire_responses):
    if not questionnaire_responses:
        questionnaire_responses = {}
    
    if not submit_clicks or submit_clicks == 0:
        return False, ""
    
    ctx = callback_context
    if not ctx.triggered:
        return False, ""
    
    trigger_id = ctx.triggered[0]['prop_id'].split('.')[0]
    
    if trigger_id == 'close-modal':
        return False, ""
    
    missing = []
    if not email:
        missing.append('Email')
    if not mobile:
        missing.append('Mobile Number')
    if not state:
        missing.append('Your Current Location')
    if not provider:
        missing.append('Preferred Wellness Facility')
    
    if missing:
        return True, dbc.Alert(f"The following field(s) are required: {', '.join(missing)}", color="danger")
    
    selected_date_str = ''
    date_communicated = False
    if selected_date:
        selected_date_str = dt.datetime.strptime(selected_date, '%Y-%m-%d').strftime('%Y-%m-%d')
    
    if not session:
        session = ''
    
    client = enrollee_data.get('client', '')
    policy = enrollee_data.get('policy', '')
    age = enrollee_data.get('age', 0)
    member_gender = gender
    
    if client == 'UNITED BANK FOR AFRICA':
        if 'UBA Head Office' in provider:
            selected_date_str = 'To be Communicated by the HR'
            date_communicated = True
        if age >= 30 and member_gender == 'Female':
            benefits = 'Physical Exam, Blood Pressure Check, Fasting Blood Sugar, BMI, Urinalysis, Cholesterol, Genotype, Chest X-Ray, Cholesterol, Liver Function Test, Electrolyte,Urea and Creatinine Test(E/U/Cr), Packed Cell Volume(PCV), ECG, Visual Acuity, Mantoux Test, Cervical Smear, Mammogram'
        elif age >= 40 and member_gender == 'Male':
            benefits = 'Physical Exam, Blood Pressure Check, Fasting Blood Sugar, BMI, Urinalysis, Cholesterol, Genotype, Chest X-Ray, Cholesterol, Liver Function Test, Electrolyte,Urea and Creatinine Test(E/U/Cr), Packed Cell Volume(PCV), ECG, Visual Acuity, Mantoux Test, Prostrate Specific Antigen'
        else:
            benefits = 'Physical Exam, Blood Pressure Check, Fasting Blood Sugar, BMI, Urinalysis, Cholesterol, Genotype, Chest X-Ray, Cholesterol, Liver Function Test, Electrolyte,Urea and Creatinine Test(E/U/Cr), Packed Cell Volume(PCV), ECG, Visual Acuity, Mantoux Test'
    elif enrollee_id in sterling_bank_enrollees:
        benefits = 'Physical Exam, BP, Blood Sugar, Urinalysis, Chest X-Ray, Stool Microscopy, Cholesterol, Prostate Specific Antigen(PSA)'
    elif enrollee_id in loyalty_enrollees['MemberNo'].values:
        benefits = (loyalty_enrollees.loc[loyalty_enrollees['MemberNo'] == enrollee_id, 'Eligible Services'].values[0] 
                    + "\nAdditional Test: " 
                    + loyalty_enrollees.loc[loyalty_enrollees['MemberNo'] == enrollee_id, 'Additional Services'].values[0])
    elif policy == 'TOTAL ENERGIES MANAGED CARE PLAN':
        if job_type == 'Offshore Personnel':
            benefits = 'Complete physical examination, Urinalysis, Fasting Blood Sugar, FBC, Lipid Profile, E/U/Cr, CRP, Liver Function test, Resting ECG, Audiometry, Chest X-ray indicated only at examiners request'
        elif job_type in ('Fire Team', 'MERT', 'Lab Personnel'):
            benefits = 'Complete physical examination, Urinalysis, Fasting Blood Sugar, FBC, Lipid Profile, E/U/Cr, CRP, Liver Function test, Resting ECG, Spirometry, Chest X-ray indicated only at examiners request'
        else:
            benefits = 'Complete physical examination, Urinalysis, Fasting Blood Sugar, FBC, Lipid Profile, E/U/Cr, CRP, Liver Function test, Resting ECG'
    elif client == 'ETRANZACT':
        if policy not in ('PLUS PLAN 2019', 'ETRANZACT PLUS PLAN NEW'):
            if age > 40 and member_gender == 'Male':
                benefits = 'Physical Examination, Blood Pressure Check, Fasting Blood Sugar, Stool Microscopy, BMI, Urinalysis, Cholesterol, Genotype, Packed Cell Volume, Chest X-Ray, ECG, Liver Function Test, E/U/Cr, PSA'
            elif age > 40 and member_gender == 'Female':
                benefits = 'Physical Examination, Blood Pressure Check, Fasting Blood Sugar, Stool Microscopy, BMI, Urinalysis, Cholesterol, Genotype, Packed Cell Volume, Chest X-Ray, ECG, Liver Function Test, E/U/Cr, Mamogram every 2 Years'
            elif 30 < age <= 40 and member_gender == 'Female':
                benefits = 'Physical Examination, Blood Pressure Check, Fasting Blood Sugar, Stool Microscopy, BMI, Urinalysis, Cholesterol, Genotype, Packed Cell Volume, Chest X-Ray, ECG, Liver Function Test, E/U/Cr, Breast Scan every 2 Years'
            else:
                benefits = 'Physical Examination, Blood Pressure Check, Fasting Blood Sugar, Stool Microscopy, BMI, Urinalysis, Cholesterol, Genotype, Packed Cell Volume, Chest X-Ray, ECG, Liver Function Test, E/U/Cr'
        else:
            benefits = enrollee_data.get('package', '')
    elif client == 'LADOL' and enrollee_id in ladol_special['MemberNo'].astype(str).values:
        benefits = ladol_special.loc[ladol_special['MemberNo'].astype(str) == enrollee_id, 'Eligible Tests'].values[0]
    else:
        benefits = enrollee_data.get('package', '')
    
    six_week_dt = dt.date.today() + dt.timedelta(weeks=6)
    six_weeks = six_week_dt.strftime('%A, %d %B %Y')
    
    cursor = conn.cursor()
    
    try:
        insert_query = """
        INSERT INTO [dbo].[demo_tbl_annual_wellness_enrollee_data] (MemberNo, MemberName, client, policy,policystartdate, policyenddate, email, mobile_num, job_type, age, state, selected_provider,
        sex, wellness_benefits, selected_date, selected_session,
        [HIGH BLOOD PRESSURE - Family],[Diabetes - Family],[Cancer - Family],[Asthma - Family],[Arthritis - Family]
        ,[High Cholesterol],[Heart Attack - Family],[Epilepsy - Family],[Tuberclosis - Family],[Substance Dependency - Family]
        ,[Mental Illness - Family],[HIGH BLOOD PRESSURE - Personal],[Diabetes - Personal],[Cancer - Personal],[Asthma - Personal]
        ,[Ulcer - Personal],[Poor Vision - Personal],[Allergy - Personal],[Arthritis/Low Back Pain - Personal],[Anxiety/Depression - Personal]
        ,[CEASAREAN SECTION],[FRACTURE REPAIR],[HERNIA],[LUMP REMOVAL] ,[APPENDICETOMY],[SPINE SURGERY],[I AVOID EATING FOODS THAT ARE HIGH IN FAT]
        ,[I AVOID THE USE OR MINIMISE MY EXPOSURE TO ALCOHOL],[I AVOID THE USE OF TOBACCO PRODUCTS],[I AM PHYSICALLY FIT AND EXERCISE AT LEAST 30 MINUTES EVERY DAY]
        ,[I EAT VEGETABLES AND FRUITS AT LEAST 3 TIMES WEEKLY],[I DRINK 6-8 GLASSES OF WATER A DAY],[I MAINTAIN MY WEIGHT WITHIN THE RECOMMENDATION FOR MY WEIGHT, AGE AND HEIGHT]
        ,[MY BLOOD PRESSURE IS WITHIN NORMAL RANGE WITHOUT THE USE OF DRUGS],[MY CHOLESTEROL LEVEL IS WITHIN THE NORMAL RANGE]
        ,[I EASILY MAKE DECISIONS WITHOUT WORRY],[I ENJOY MORE THAN 5 HOURS OF SLEEP AT NIGHT],[I ENJOY MY WORK AND LIFE]
        ,[I ENJOY THE SUPPORT FROM FRIENDS AND FAMILY],[I FEEL BAD ABOUT MYSELF OR THAT I AM A FAILURE OR HAVE LET MYSELF OR MY FAMILY DOWN]
        ,[I HAVE POOR APPETITE OR I AM OVER-EATING],[I FEEL DOWN, DEPRESSED, HOPELESS, TIRED OR HAVE LITTLE ENERGY]
        ,[I HAVE TROUBLE FALLING ASLEEP, STAYING ASLEEP, OR SLEEPING TOO MUCH],[I HAVE NO INTEREST OR PLEASURE IN DOING THINGS]
        ,[I HAVE TROUBLE CONCENTRATING ON THINGS, SUCH AS READING THE NEWSPAPER, OR WATCHING TV]
        ,[THOUGHT THAT I WOULD BE BETTER OFF DEAD OR BETTER OFF HURTING MYSELF IN SOME WAY],
        date_submitted)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """
        
        cursor.execute(insert_query, (
            enrollee_id, enrollee_data['member_name'], client, policy,
            enrollee_data['policystart'], enrollee_data['policyend'], email, mobile, job_type,
            age, state, provider, member_gender, benefits, selected_date_str, session,
            questionnaire_responses.get('resp_1_a', 'Grand Parent(s)'), questionnaire_responses.get('resp_1_b', 'Grand Parent(s)'),
            questionnaire_responses.get('resp_1_c', 'Grand Parent(s)'), questionnaire_responses.get('resp_1_d', 'Grand Parent(s)'),
            questionnaire_responses.get('resp_1_e', 'Grand Parent(s)'), questionnaire_responses.get('resp_1_f', 'Grand Parent(s)'),
            questionnaire_responses.get('resp_1_g', 'Grand Parent(s)'), questionnaire_responses.get('resp_1_h', 'Grand Parent(s)'),
            questionnaire_responses.get('resp_1_i', 'Grand Parent(s)'), questionnaire_responses.get('resp_1_j', 'Grand Parent(s)'),
            questionnaire_responses.get('resp_1_k', 'Grand Parent(s)'), questionnaire_responses.get('resp_2_a', 'Yes'),
            questionnaire_responses.get('resp_2_b', 'Yes'), questionnaire_responses.get('resp_2_c', 'Yes'),
            questionnaire_responses.get('resp_2_d', 'Yes'), questionnaire_responses.get('resp_2_e', 'Yes'),
            questionnaire_responses.get('resp_2_f', 'Yes'), questionnaire_responses.get('resp_2_g', 'Yes'),
            questionnaire_responses.get('resp_2_h', 'Yes'), questionnaire_responses.get('resp_2_i', 'Yes'),
            questionnaire_responses.get('resp_3_a', 'Yes'), questionnaire_responses.get('resp_3_b', 'Yes'),
            questionnaire_responses.get('resp_3_c', 'Yes'), questionnaire_responses.get('resp_3_d', 'Yes'),
            questionnaire_responses.get('resp_3_e', 'Yes'), questionnaire_responses.get('resp_3_f', 'Yes'),
            questionnaire_responses.get('resp_4_a', 'Never'), questionnaire_responses.get('resp_4_b', 'Never'),
            questionnaire_responses.get('resp_4_c', 'Never'), questionnaire_responses.get('resp_4_d', 'Never'),
            questionnaire_responses.get('resp_4_e', 'Never'), questionnaire_responses.get('resp_4_f', 'Never'),
            questionnaire_responses.get('resp_4_g', 'Never'), questionnaire_responses.get('resp_4_h', 'Never'),
            questionnaire_responses.get('resp_4_i', 'Never'), questionnaire_responses.get('resp_4_j', 'Never'),
            questionnaire_responses.get('resp_4_k', 'Never'), questionnaire_responses.get('resp_4_l', 'Never'),
            questionnaire_responses.get('resp_4_m', 'Never'), questionnaire_responses.get('resp_4_n', 'Never'),
            questionnaire_responses.get('resp_4_o', 'Never'), questionnaire_responses.get('resp_4_p', 'Never'),
            questionnaire_responses.get('resp_4_q', 'Never'), questionnaire_responses.get('resp_4_r', 'Never'),
            questionnaire_responses.get('resp_4_s', 'Never'), questionnaire_responses.get('resp_4_t', 'Never'),
            dt.datetime.now()
        ))
        
        conn.commit()
        
        email_sent, email_error = send_confirmation_email(enrollee_id, enrollee_data['member_name'], email, provider, benefits, selected_date_str, session, enrollee_data['client'], date_communicated)
        
        success_msg = dbc.Alert([
            html.H5(f"Thank you {enrollee_data['member_name']}."),
            html.P("Your annual wellness has been successfully booked."),
            html.Hr(),
            html.P(f"Please note that you have from now till {six_weeks} to complete your annual wellness exercise.", className='font-weight-bold'),
            html.Hr(),
            html.P("A confirmation Email has been sent to your provided email. Kindly note that your wellness result will only be available two (2) weeks after your visit to the provider for your wellness check.")
        ], color="success", className="mb-0")
        
        if not email_sent:
            success_msg = dbc.Alert([
                html.H5(f"Thank you {enrollee_data['member_name']}."),
                html.P("Your annual wellness has been successfully booked."),
                html.Hr(),
                html.P(f"Please note that you have from now till {six_weeks} to complete your annual wellness exercise.", className='font-weight-bold'),
                html.Hr(),
                html.P("However, the confirmation email could not be sent. Please contact support if you don't receive your confirmation.", className='text-warning'),
                html.Small(f"Error: {email_error}", className='text-muted')
            ], color="warning", className="mb-0")
        
    except Exception as e:
        success_msg = dbc.Alert(f"An error occurred: {str(e)}", color="danger")
        return True, success_msg
    finally:
        cursor.close()
    
    return True, success_msg


def send_confirmation_email(enrollee_id, member_name, email, provider, benefits, selected_date, session, client, date_communicated=False):
    myemail = 'noreply@avonhealthcare.com'
    password = os.environ.get('email_password')
    
    msg_befor_table = f'''
    Dear {member_name},<br><br>
    We hope you are staying safe.<br><br>
    You have been scheduled for a wellness screening at your selected provider, see the below table for details.<br><br>
    '''
    
    wellness_table = {
        "Appointment Date": [selected_date + ' - ' + session] if session and not date_communicated else [selected_date],
        "Wellness Facility": [provider],
        "Wellness Benefits": [benefits]
    }
    
    wellness_table_html = pd.DataFrame(wellness_table).to_html(index=False, escape=False)
    
    table_html = f"""
    <style>
    table {{
            border: 1px solid #1C6EA4;
            background-color: #EEEEEE;
            width: 100%;
            text-align: left;
            border-collapse: collapse;
            }}
            table td, table th {{
            border: 1px solid #AAAAAA;
            padding: 3px 2px;
            }}
            table tbody td {{
            font-size: 13px;
            }}
            table thead {{
            background: #59058D;
            border-bottom: 2px solid #444444;
            }}
            table thead th {{
            font-size: 15px;
            font-weight: bold;
            color: #FFFFFF;
            border-left: 2px solid #D0E4F5;
            }}
            table thead th:first-child {{
            border-left: none;
            }}
    </style>
    <table>
    {wellness_table_html}
    </table>
    """
    
    text_after_table = f'''
    <br>Kindly note the following requirements for your wellness exercise:<br><br>
    -Present at the hospital with your Avon member ID number ({enrollee_id})/ Ecard.<br>
    -Provide the facility with your valid email address to mail your result.<br>
    -Visit your designated centers between the hours of 8 am - 11 am any day of the week from the scheduled date communicated.<br>
    -Arrive at the facility fasting i.e. last meals should be before 9 pm the previous night and nothing should be eaten that morning before the test.
    You are allowed to drink up to two cups of water.<br><br>
    For the best results of your screening, it is advisable for blood tests to be done on or before 10 am.<br><br>
    Your results will be strictly confidential and will be sent to you directly via your email. You are advised to review
    your results with your primary care provider for relevant medical advice.<br><br>
    <b>Kindly note that your wellness result will only be available two (2) weeks after your visit to the provider for your wellness check.</b><br><br>
    Should you require assistance at any time or wish to make any complaint about the service at any of the facilities, 
    please contact our Call-Center at 0700-277-9800  or send us a chat on WhatsApp at 0912-603-9532. 
    You can also send us an email at callcentre@avonhealthcare.com. Please be assured that an agent would always be on standby to assist you.<br><br>
    Thank you for choosing Avon HMO,<br><br>
    Medical Services.<br>
    '''
    
    text_after_table1 = f'''
    <br>Kindly note that wellness exercise at your selected facility is strictly by appointment and
    and you are expected to be available at the facility on the appointment date as selected by you.<br><br>
    Also, note that you will be required to:<br><br>
    -Present at the facility with your Avon member ID number ({enrollee_id})/ Ecard.<br>
    -Provide the facility with your valid email address to mail your result.<br>
    -You are advised to be present at your selected facility 15 mins before your scheduled time.<br><br>
    Your results will be strictly confidential and will be sent to you directly via your email. You are advised to review
    your results with your primary care provider for relevant medical advice.<br><br>
    <b>Kindly note that your wellness result will only be available two (2) weeks after your visit to the provider for your wellness check.</b><br><br>
    Should you require assistance at any time or wish to make any complaint about the service at any of the facilities, 
    please contact our Call-Center at 0700-277-9800  or send us a chat on WhatsApp at 0912-603-9532. 
    You can also send us an email at callcentre@avonhealthcare.com. Please be assured that an agent would always be on standby to assist you.<br><br>
    Thank you for choosing Avon HMO,<br><br>
    Medical Services.<br>
    '''
    
    head_office_msg = f'''
    Dear {member_name},<br><br>
    We hope you are staying safe.<br><br>
    You have been scheduled for a wellness screening at {provider}.<br><br>
    Find listed below your wellness benefits:<br><br><b>{benefits}</b>.<br><br>
    Kindly note the following regarding your wellness appointment:<br><br>
    - HR will reach out to you with a scheduled date and time for your annual wellness.<br><br>
    - Once scheduled, you are to present your Avon HMO ID card or member ID - {enrollee_id} at the point of accessing your annual wellness check.<br><br>
    - The wellness exercise will take place at the designated floor which will be communicated to you by the HR between 9 am and 4 pm from Monday – Friday. <br><br>
    - For the most accurate fasting blood sugar test results, it is advisable for blood tests to be done before 10am. <br><br>
    - Staff results will be sent to the email addresses provided by them to the wellness providers.<br><br>
    - There will be consultation with a physician to review immediate test results on-site while other test results that are not readily available will be reviewed by a physician at your Primary Care Provider.<br><br>
    Should you require assistance at any time or wish to make any complaint about the service rendered during this wellness exercise,
    please contact our Call-Center at 0700-277-9800 or send us a chat on WhatsApp at 0912-603-9532.
    You can also send us an email at callcentre@avonhealthcare.com. Please be assured that an agent would always be on standby to assist you.<br><br>
    Thank you for choosing Avon HMO.<br><br>
    Medical Services.<br>
    '''
    
    pivotgis_msg = f'''
    <br>Kindly note that this wellness activation is only valid till the 31st of December, 2024.<br><br>
    Also, note that you will be required to:<br><br>
    -Present at the hospital with your Avon member ID number ({enrollee_id})/ Ecard.<br>
    -Provide the facility with your valid email address to mail your result.<br>
    -You are advised to be present at your selected facility 15 mins before your scheduled time.<br><br>
    Your results will be strictly confidential and will be sent to you directly via your email. You are advised to review
    your results with your primary care provider for relevant medical advice.<br><br>
    <b>Kindly note that your wellness result will only be available two (2) weeks after your visit to the provider for your wellness check.</b><br><br>
    Should you require assistance at any time or wish to make any complaint about the service at any of the facilities, 
    please contact our Call-Center at 0700-277-9800  or send us a chat on WhatsApp at 0912-603-9532. 
    You can also send us an email at callcentre@avonhealthcare.com. Please be assured that an agent would always be on standby to assist you.<br><br>
    Thank you for choosing Avon HMO,<br><br>
    Medical Services.<br>
    '''
    
    email_sent = False
    email_error = ''
    
    if client == 'UNITED BANK FOR AFRICA':
        if 'UBA Head Office' in provider:
            full_message = msg_befor_table + table_html + head_office_msg
        elif 'CERBA LANCET' in provider or 'CERBA LANCET NIGERIA' in provider:
            full_message = msg_befor_table + table_html + text_after_table1
        else:
            full_message = msg_befor_table + table_html + text_after_table
    elif client == 'PIVOT GIS LIMITED' or client == 'PIVOT   GIS LIMITED':
        full_message = msg_befor_table + table_html + pivotgis_msg
    else:
        full_message = msg_befor_table + table_html + text_after_table
    
    bcc_email_list = ['ifeoluwa.adeniyi@avonhealthcare.com', 'ifeoluwa.adeniyi@avonhealthcare.com']
    
    if provider in ['ECHOLAB - Opposite mararaba medical centre, Tipper Garage, Mararaba',
                    'TOBIS CLINIC - Chief Melford Okilo Road Opposite Sobaz Filling Station, Akenfa –Epie',
                    'ECHOLAB - 375B Nnebisi Road, Umuagu, Asaba']:
        bcc_email_list.extend(['ifeoluwa.adeniyi@avonhealthcare.com', 'ifeoluwa.adeniyi@avonhealthcare.com'])
    
    try:
        server = smtplib.SMTP('smtp.office365.com', 587)
        server.starttls()
        server.login(myemail, password)
        
        msg = MIMEMultipart()
        msg['From'] = 'AVON HMO Client Services'
        msg['To'] = email
        msg['Bcc'] = ', '.join(bcc_email_list)
        msg['Subject'] = 'AVON ENROLLEE WELLNESS APPOINTMENT CONFIRMATION'
        msg.attach(MIMEText(full_message, 'html'))
        
        server.sendmail(myemail, [email] + bcc_email_list, msg.as_string())
        server.quit()
        email_sent = True
    except Exception as e:
        email_error = str(e)
        print(f"Email error: {e}")
    
    return email_sent, email_error


if __name__ == '__main__':
    app.run(debug=True, port=8050)
