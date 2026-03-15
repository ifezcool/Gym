import dash
from dash import dcc, html, Input, Output, State, callback, register_page
import dash_bootstrap_components as dbc
import pandas as pd
import pyodbc
from PIL import Image
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
import random
import os
import pytz
import base64
from io import BytesIO
import plotly.graph_objects as go
from dotenv import load_dotenv
import time

register_page(__name__, path='/gym-portal', title='Gym Portal')

load_dotenv('secrets.env')

# Database connection setup
server = os.environ.get('server_name')
database = os.environ.get('db_name')
username = os.environ.get('db_username')
password = os.environ.get('db_password')
email_username = os.environ.get('email_username')
email_password = os.environ.get('email_password')

def get_db_connection():
    if not all([server, database, username, password]):
        missing_vars = []
        if not server: missing_vars.append('server_name')
        if not database: missing_vars.append('db_name')
        if not username: missing_vars.append('db_username')
        if not password: missing_vars.append('db_password')
        raise Exception(f"Missing environment variables: {', '.join(missing_vars)}")
    
    return pyodbc.connect(
        'DRIVER={ODBC Driver 17 for SQL Server};SERVER='
        + server
        + ';DATABASE='
        + database
        + ';UID='
        + username
        + ';PWD='
        + password
    )

# Helper functions
def generate_reference_id():
    random_digits = ''.join([str(random.randint(0, 9)) for _ in range(6)])
    return f"AV/{random_digits}"

def check_reference_id_exists(reference_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        query = "SELECT COUNT(*) FROM tbl_GymAccess_Log WHERE Refid = ?"
        cursor.execute(query, reference_id)
        count = cursor.fetchone()[0]
        conn.close()
        return count > 0
    except Exception as e:
        print(f"Error checking reference ID: {str(e)}")
        return True

def generate_unique_reference_id():
    while True:
        reference_id = generate_reference_id()
        if not check_reference_id_exists(reference_id):
            return reference_id

def check_access_availability(memberno, access_limit, access_type):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        if access_type.lower() == 'weekly':
            period_query = """
                SELECT COUNT(*) as period_count
                FROM tbl_GymAccess_Log
                WHERE Memberno = ?
                AND AccessDate >= DATEADD(day, 
                    -(DATEPART(WEEKDAY, GETDATE()) - 1), 
                    CAST(GETDATE() AS DATE))
                AND AccessDate < DATEADD(day, 
                    8 - DATEPART(WEEKDAY, GETDATE()), 
                    CAST(GETDATE() AS DATE))
            """
        elif access_type.lower() == 'monthly':
            period_query = """
                SELECT COUNT(*) as period_count
                FROM tbl_GymAccess_Log
                WHERE Memberno = ?
                AND AccessDate >= DATEADD(month, DATEDIFF(month, 0, GETDATE()), 0)
                AND AccessDate < DATEADD(month, DATEDIFF(month, 0, GETDATE()) + 1, 0)
            """
        else:
            raise ValueError(f"Unsupported access type: {access_type}")
        
        cursor.execute(period_query, memberno)
        period_count = cursor.fetchone()[0]
        conn.close()
        
        if period_count >= access_limit:
            return False, period_count
        return True, period_count
        
    except Exception as e:
        print(f"Error checking access availability: {str(e)}")
        return False, 0

def log_gym_access(memberno, name, gym_provider, reference_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        count_query = """
            SELECT COUNT(*) as access_count 
            FROM tbl_GymAccess_Log 
            WHERE Memberno = ?
        """
        cursor.execute(count_query, memberno)
        current_count = cursor.fetchone()[0] + 1
        
        insert_query = """
            INSERT INTO tbl_GymAccess_Log (Memberno, Name, AccessDate, AccessCount, Gym, Refid)
            VALUES (?, ?, GETDATE(), ?, ?, ?)
        """
        cursor.execute(insert_query, (memberno, name, current_count, gym_provider, reference_id))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Failed to log gym access: {str(e)}")
        return False

def send_email(enrollee_id, gym, state, enrollee_email, client, reference_id, timestamp, enrollee_name):
    try:
        sender_email = email_username
        sender_password = email_password
        receiver_email = "ifeoluwa.adeniyi@avonhealthcare.com"
        
        message = MIMEMultipart()
        message["From"] = sender_email
        message["To"] = receiver_email
        message["Cc"] = enrollee_email
        message["Subject"] = f"GYM ACCESS REQUEST - {enrollee_id}"
        
        formatted_timestamp = timestamp.strftime('%d-%b-%Y %I:%M:%S %p')
        
        body = f"""
            <p>Dear Contact Centre,</p>
            <p>This is to notify you that one of our esteemed enrollees has successfully booked a gym session. Below are the details:</p>
            <div style="background-color: #f0f0f0; padding: 15px; border-left: 5px solid purple; border-radius: 5px;">
                <p><strong>Member ID:</strong> {enrollee_id}</p>
                <p><strong>Name:</strong> {enrollee_name}</p>
                <p><strong>Client:</strong> {client}</p>
                <p><strong>State:</strong> {state}</p>
                <p><strong>Gym Provider:</strong> {gym}</p>
                <p><strong>Reference ID:</strong> {reference_id}</p>
                <p><strong>Booking Date/Time:</strong> {formatted_timestamp}</p>
            </div>
            <p>Best regards,<br>Gym Access Portal</p>
        """
        
        message.attach(MIMEText(body, "html"))
        
        server = smtplib.SMTP("smtp.office365.com", 587)
        server.starttls()
        server.login(sender_email, sender_password)
        recipients = [receiver_email, enrollee_email]
        server.send_message(message)
        server.quit()
        return True
    except Exception as e:
        print(f"Failed to send email: {str(e)}")
        return False

def get_image_src(image_path):
    try:
        img = Image.open(image_path)
        buffered = BytesIO()
        img.save(buffered, format="PNG")
        img_str = base64.b64encode(buffered.getvalue()).decode()
        return f"data:image/png;base64,{img_str}"
    except:
        return ""

# Layout
layout = html.Div([
    # Back to Home Button
    html.Div([
        dcc.Link(
            dbc.Button(
                "← Back to Home",
                style={
                    'padding': '10px 20px',
                    'fontSize': '1rem',
                    'fontWeight': '500',
                    'borderRadius': '10px',
                    'background': 'linear-gradient(135deg, #7a6b8a 0%, #5a4470 100%)',
                    'border': 'none',
                    'color': '#fff',
                    'cursor': 'pointer'
                }
            ),
            href="/"
        )
    ], style={'padding': '20px'}),
    
    # Header Section
    html.Div([
        html.Div([
            html.Img(src=get_image_src('GymPortal.png'), 
                    style={
                        'width': '100%', 
                        'maxWidth': '800px',
                        'display': 'block',
                        'margin': '0 auto'
                    })
        ], style={'marginBottom': '30px'}),
        
        html.H1("AVON HMO Gym Access Portal", 
               style={
                   'textAlign': 'center',
                   'color': '#5a4470',
                   'fontSize': '2.5rem',
                   'fontWeight': '600',
                   'marginBottom': '10px',
                   'textShadow': '2px 2px 4px rgba(0,0,0,0.1)'
               }),
        html.P("Your gateway to wellness and fitness",
              style={
                  'textAlign': 'center',
                  'color': '#7a6b8a',
                  'fontSize': '1.2rem',
                  'marginBottom': '30px'
              })
    ], style={
        'background': 'linear-gradient(135deg, #e8e0f0 0%, #d4c4e0 100%)',
        'padding': '40px 20px',
        'borderRadius': '0 0 30px 30px',
        'boxShadow': '0 10px 30px rgba(0,0,0,0.1)'
    }),
    
    # Main Content Area
    html.Div([
        html.Div([
            # Eligibility Check Section
            html.Div([
                html.H3("Check Your Eligibility", 
                       style={
                           'color': '#5a4470',
                           'marginBottom': '20px',
                           'fontSize': '1.8rem',
                           'fontWeight': '600'
                       }),
                html.Div([
                    dbc.Input(
                        id="member-id-input",
                        placeholder="Enter your Member ID",
                        type="text",
                        style={
                            'padding': '15px',
                            'fontSize': '1.1rem',
                            'borderRadius': '10px',
                            'border': '2px solid #d4c4e0',
                            'marginBottom': '20px'
                        }
                    ),
                    dbc.Button(
                        "Check Eligibility",
                        id="check-btn",
                        n_clicks=0,
                        style={
                            'width': '100%',
                            'padding': '15px',
                            'fontSize': '1.2rem',
                            'fontWeight': '600',
                            'borderRadius': '12px',
                            'background': 'linear-gradient(135deg, #9d7cb8 0%, #7a6b8a 100%)',
                            'border': 'none',
                            'color': '#fff',
                            'boxShadow': '0 6px 20px rgba(122, 107, 138, 0.4)',
                            'transition': 'all 0.3s ease',
                            'cursor': 'pointer',
                            'marginBottom': '20px'
                        }
                    ),
                    dcc.Loading(
                        id="loading-eligibility",
                        type="default",
                        color="#9d7cb8",
                        children=html.Div(id='eligibility-result', children=[])
                    ),
                    
                    # State and Provider Selection - controlled by callbacks
                    html.Div(id='state-selection-container', children=[]),
                    html.Div(id='provider-selection-container', children=[])
                ])
            ], style={
                'backgroundColor': '#fff',
                'padding': '30px',
                'borderRadius': '15px',
                'boxShadow': '0 8px 25px rgba(0,0,0,0.1)',
                'marginBottom': '30px'
            }),
            
            # Hidden store for eligibility data
            dcc.Store(id='eligibility-store')
            
        ], style={
            'maxWidth': '700px',
            'margin': '0 auto'
        })
    ], style={
        'padding': '40px 20px',
        'minHeight': '50vh'
    }),
    
    # Footer
    html.Div([
        html.P("© 2026 AVON HMO - Your Health, Our Priority",
               style={
                   'textAlign': 'center',
                   'color': '#7a6b8a',
                   'fontSize': '0.9rem',
                   'padding': '20px'
               })
    ])
    
], style={
    'backgroundColor': '#d4c4e0',
    'minHeight': '100vh',
    'fontFamily': '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif'
})

# Callbacks
@callback(
    [Output('eligibility-result', 'children'),
     Output('eligibility-store', 'data')],
    [Input('check-btn', 'n_clicks')],
    [State('member-id-input', 'value')],
    prevent_initial_call=True
)
def check_eligibility(n_clicks, member_id):
    if not member_id:
        error_msg = html.Div([
            html.Div([
                html.H4("⚠️ Input Required", style={'color': '#c44569', 'marginBottom': '10px'}),
                html.P("Please enter your Member ID to check eligibility.",
                      style={'color': '#555'})
            ], style={
                'backgroundColor': '#ffe5e5',
                'padding': '20px',
                'borderRadius': '12px',
                'border': '2px solid #ffcccc'
            })
        ])
        return error_msg, {'is_eligible': False}
    
    try:
        conn = get_db_connection()
        query = """
            SELECT DISTINCT
                [Client Policy ID Number],
                [Client Name],
                [Plan Type],
                [Gym Access],
                [MemberNo],
                [MemberType],
                [Name],
                MAX(EMAIL) as EMAIL,
                MAX(AccessLimit) as AccessLimit,
                MAX(AccessType) as AccessType
            FROM vw_GymAccess 
            WHERE MemberNo = ?
            GROUP BY 
                [Client Policy ID Number],
                [Client Name],
                [Plan Type],
                [Gym Access],
                [MemberNo],
                [MemberType],
                [Name]
        """
        df = pd.read_sql(query, conn, params=[member_id])
        conn.close()
        
        if df.empty:
            error_msg = html.Div([
                html.Div([
                    html.H4("❌ Not Found", style={'color': '#c44569', 'marginBottom': '10px'}),
                    html.P(f"Member ID '{member_id}' not found in our records.",
                          style={'color': '#555'})
                ], style={
                    'backgroundColor': '#ffe5e5',
                    'padding': '25px',
                    'borderRadius': '12px',
                    'border': '2px solid #ffcccc'
                })
            ])
            return error_msg, {'is_eligible': False}
        
        row = df.iloc[0]
        access_limit = row['AccessLimit']
        access_type = row['AccessType']
        
        is_available, current_count = check_access_availability(member_id, access_limit, access_type)
        
        if not is_available:
            error_msg = html.Div([
                html.Div([
                    html.H4("⚠️ Limit Reached", style={'color': '#c44569', 'marginBottom': '15px'}),
                    html.P(f"Hello {row['Name']},",
                          style={'color': '#555', 'marginBottom': '10px'}),
                    html.P(f"You have reached your {access_type.lower()} gym access limit of {access_limit} visit(s).",
                          style={'color': '#555', 'marginBottom': '10px'}),
                    html.P(f"Current usage: {current_count}/{access_limit}",
                          style={'color': '#888', 'fontSize': '0.95rem'})
                ], style={
                    'backgroundColor': '#fff3cd',
                    'padding': '25px',
                    'borderRadius': '12px',
                    'border': '2px solid #ffc107'
                })
            ])
            return error_msg, {'is_eligible': False}
        
        success_msg = html.Div([
            html.H4("✅ Eligible!", 
                   style={
                       'color': '#4a9d5f',
                       'marginBottom': '15px',
                       'fontSize': '1.5rem',
                       'fontWeight': '600'
                   }),
            html.P(f"Welcome, {row['Name']}!",
                  style={
                      'color': '#555',
                      'fontSize': '1.1rem',
                      'marginBottom': '20px',
                      'fontWeight': '500'
                  }),
            html.Div([
                html.P([
                    html.Strong("Client: "),
                    html.Span(row['Client Name'])
                ], style={'marginBottom': '8px', 'color': '#666'}),
                html.P([
                    html.Strong("Access Type: "),
                    html.Span(f"{access_type.title()} - {access_limit} visit(s)")
                ], style={'marginBottom': '8px', 'color': '#666'}),
                html.P([
                    html.Strong("Current Usage: "),
                    html.Span(f"{current_count}/{access_limit}")
                ], style={'marginBottom': '8px', 'color': '#666'})
            ], style={
                'background': '#f8f9fa',
                'padding': '15px',
                'borderRadius': '8px',
                'marginTop': '15px'
            })
        ], style={
            'backgroundColor': '#e8f5e9',
            'padding': '25px',
            'borderRadius': '12px',
            'border': '2px solid #a5d6a7',
            'marginBottom': '20px'
        })
        
        eligibility_data = {
            'is_eligible': True,
            'member_id': member_id,
            'enrollee_name': row['Name'],
            'enrollee_email': row['EMAIL'],
            'client_name': row['Client Name'],
            'access_limit': access_limit,
            'access_type': access_type,
            'current_count': current_count
        }
        
        return success_msg, eligibility_data
        
    except Exception as e:
        error_msg = html.Div([
            html.Div([
                html.H4("❌ Error", style={'color': '#c44569', 'marginBottom': '15px'}),
                html.P(f"An error occurred: {str(e)}",
                      style={'color': '#555'})
            ], style={
                'backgroundColor': '#ffe5e5',
                'padding': '25px',
                'borderRadius': '12px',
                'border': '2px solid #ffcccc',
                'maxWidth': '600px',
                'margin': '0 auto'
            })
        ])
        return error_msg, {'is_eligible': False}

@callback(
    Output('state-selection-container', 'children'),
    [Input('eligibility-store', 'data')]
)
def show_state_selector(eligibility_data):
    if eligibility_data and eligibility_data.get('is_eligible'):
        try:
            conn = get_db_connection()
            state_query = "SELECT DISTINCT State FROM tblGymlist"
            states_df = pd.read_sql(state_query, conn)
            conn.close()
            state_list = states_df['State'].dropna().unique().tolist()
            
            return html.Div([
                html.H5("Select Your State", 
                       style={
                           'color': '#5a4470',
                           'marginTop': '30px',
                           'marginBottom': '12px',
                           'fontSize': '1.2rem',
                           'fontWeight': '600'
                       }),
                dbc.Select(
                    id='state-select',
                    options=[{'label': state, 'value': state} for state in state_list],
                    style={
                        'padding': '10px',
                        'fontSize': '1rem',
                        'borderRadius': '10px',
                        'border': '2px solid #d4c4e0',
                        'marginBottom': '20px'
                    }
                )
            ], style={
                'backgroundColor': '#fff',
                'padding': '25px',
                'borderRadius': '12px',
                'boxShadow': '0 4px 15px rgba(0,0,0,0.08)',
                'marginBottom': '20px'
            })
        except Exception as e:
            return html.Div([
                html.P(f"Error loading states: {str(e)}", 
                      style={'color': '#c44569', 'textAlign': 'center'})
            ])
    
    return ""

@callback(
    Output('provider-selection-container', 'children'),
    [Input('state-select', 'value')],
    [State('eligibility-store', 'data')]
)
def update_providers(selected_state, eligibility_data):
    if selected_state and eligibility_data.get('is_eligible'):
        try:
            conn = get_db_connection()
            provider_query = "SELECT DISTINCT Provider_Name FROM tblGymlist WHERE State = ?"
            providers_df = pd.read_sql(provider_query, conn, params=[selected_state])
            conn.close()
            provider_list = providers_df['Provider_Name'].dropna().unique().tolist()
            
            return html.Div([
                html.H5("Select Your Gym Provider", 
                       style={
                           'color': '#5a4470',
                           'marginTop': '20px',
                           'marginBottom': '12px',
                           'fontSize': '1.2rem',
                           'fontWeight': '600'
                       }),
                dbc.Select(
                    id='provider-select',
                    options=[{'label': provider, 'value': provider} for provider in provider_list],
                    style={
                        'padding': '10px',
                        'fontSize': '1rem',
                        'borderRadius': '10px',
                        'border': '2px solid #d4c4e0',
                        'marginBottom': '20px'
                    }
                ),
                dbc.Button(
                    "🏋️ Book GYM Session",
                    id="book-gym-btn",
                    n_clicks=0,
                    style={
                        'width': '100%',
                        'padding': '15px',
                        'fontSize': '1.2rem',
                        'fontWeight': '600',
                        'borderRadius': '12px',
                        'background': 'linear-gradient(135deg, #4a9d5f 0%, #3d8350 100%)',
                        'border': 'none',
                        'color': '#fff',
                        'boxShadow': '0 6px 20px rgba(74, 157, 95, 0.4)',
                        'transition': 'all 0.3s ease',
                        'cursor': 'pointer',
                        'marginBottom': '20px'
                    }
                ),
                dcc.Loading(
                    id="loading-booking",
                    type="default",
                    color="#4a9d5f",
                    children=html.Div(id='booking-result')
                )
            ], style={
                'backgroundColor': '#fff',
                'padding': '25px',
                'borderRadius': '12px',
                'boxShadow': '0 4px 15px rgba(0,0,0,0.08)'
            })
        except Exception as e:
            return html.Div([
                html.P(f"Error loading providers: {str(e)}", 
                      style={'color': '#c44569', 'textAlign': 'center'})
            ])
    
    return ""

@callback(
    Output('booking-result', 'children'),
    [Input('book-gym-btn', 'n_clicks')],
    [State('provider-select', 'value'),
     State('state-select', 'value'),
     State('eligibility-store', 'data')],
    prevent_initial_call=True
)
def book_gym_session(n_clicks, selected_provider, selected_state, eligibility_data):
    if not selected_provider or not selected_state or not eligibility_data.get('is_eligible'):
        return ""
        
    time.sleep(2)
    
    is_still_available, _ = check_access_availability(
        eligibility_data['member_id'], 
        eligibility_data['access_limit'],
        eligibility_data['access_type']
    )
    
    if not is_still_available:
        return html.Div([
            html.Div([
                html.H4("⚠️ Access Limit Reached", style={'color': '#c44569', 'marginBottom': '15px'}),
                html.P(f"You have reached your maximum gym access limit.",
                      style={'color': '#555'})
            ], style={
                'backgroundColor': '#ffe5e5',
                'padding': '25px',
                'borderRadius': '12px',
                'border': '2px solid #ffcccc',
                'marginTop': '20px'
            })
        ])
    
    reference_id = generate_unique_reference_id()
    wat_timezone = pytz.timezone('Africa/Lagos')
    current_timestamp = datetime.now(wat_timezone)
    
    email_sent = send_email(
        eligibility_data['member_id'], 
        selected_provider, 
        selected_state, 
        "ifeoluwa.adeniyi@avonhealthcare.com",
        eligibility_data['client_name'], 
        reference_id, 
        current_timestamp,
        eligibility_data['enrollee_name']
    )
    
    if email_sent:
        log_gym_access(
            eligibility_data['member_id'],
            eligibility_data['enrollee_name'],
            selected_provider,
            reference_id
        )
        
        formatted_time = current_timestamp.strftime('%d-%b-%Y %I:%M:%S %p')
        
        return html.Div([
            html.Div([
                html.H3("🎉 Booking Successful!", 
                       style={
                           'color': '#4a9d5f',
                           'textAlign': 'center',
                           'marginBottom': '20px',
                           'fontSize': '2rem',
                           'fontWeight': '600'
                       }),
                html.P(f"Your gym session at {selected_provider} has been booked successfully!",
                      style={
                          'textAlign': 'center',
                          'color': '#555',
                          'fontSize': '1.1rem',
                          'marginBottom': '25px'
                      }),
                
                # Reference ID Card
                html.Div([
                    html.P("Reference ID", 
                          style={
                              'color': '#888',
                              'fontSize': '0.9rem',
                              'marginBottom': '5px',
                              'textAlign': 'center'
                          }),
                    html.H2(reference_id, 
                           style={
                               'color': '#7a6b8a',
                               'textAlign': 'center',
                               'fontWeight': 'bold',
                               'letterSpacing': '2px',
                               'marginBottom': '10px'
                           }),
                    html.P(f"Booked: {formatted_time}",
                          style={
                              'color': '#888',
                              'fontSize': '0.9rem',
                              'textAlign': 'center'
                          })
                ], style={
                    'background': 'linear-gradient(135deg, #e8e0f0 0%, #d4c4e0 100%)',
                    'padding': '25px',
                    'borderRadius': '12px',
                    'marginBottom': '20px'
                }),
                
                html.P("📧 Check your email for further instructions. Show this reference ID to gym staff.",
                      style={
                          'textAlign': 'center',
                          'color': '#666',
                          'fontSize': '0.95rem',
                          'fontStyle': 'italic'
                      })
            ], style={
                'backgroundColor': '#e8f5e9',
                'padding': '35px',
                'borderRadius': '15px',
                'border': '2px solid #a5d6a7',
                'marginTop': '20px',
                'boxShadow': '0 8px 20px rgba(74, 157, 95, 0.2)'
            })
        ])
    else:
        return html.Div([
            html.Div([
                html.H4("❌ Booking Failed", style={'color': '#c44569', 'marginBottom': '15px'}),
                html.P("There was an error processing your booking. Please try again.",
                      style={'color': '#555'})
            ], style={
                'backgroundColor': '#ffe5e5',
                'padding': '25px',
                'borderRadius': '12px',
                'border': '2px solid #ffcccc',
                'marginTop': '20px'
            })
        ])