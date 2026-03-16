import dash
from dash import dcc, html, Input, Output, State, callback, callback_context, register_page
from dash_svg import Svg, Path
from dash import dash_table
import dash_bootstrap_components as dbc
import pandas as pd
import numpy as np
import datetime as dt
from sqlalchemy import create_engine, text
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import os
import time
import base64
import threading
import urllib.parse
import json
from dotenv import load_dotenv
from azure.storage.blob import BlobServiceClient
from datetime import datetime

register_page(__name__, path='/wellness', title='AVON HMO Wellness Portal')

# ── Styles ────────────────────────────────────────────────────────────────────
PURPLE_TABLE_STYLE = {
    "style_header": {
        "backgroundColor": "#59058d",
        "color": "white",
        "fontWeight": "bold",
        "textAlign": "center",
    },
    "style_cell": {
        "textAlign": "left",
        "padding": "8px",
        "fontSize": "13px",
        "overflow": "hidden",
        "textOverflow": "ellipsis",
        "maxWidth": "200px",
    },
    "style_data_conditional": [
        {"if": {"row_index": "odd"}, "backgroundColor": "rgb(248, 240, 255)"},
    ],
}

load_dotenv('secrets.env')

_server    = os.environ.get('server_name')
_database  = os.environ.get('db_name')
_username  = os.environ.get('db_username')
_password  = os.environ.get('db_password')
conn_str   = os.environ.get('conn_str')


def get_engine():
    params = urllib.parse.quote_plus(
        f"DRIVER={{ODBC Driver 17 for SQL Server}};"
        f"SERVER={_server};"
        f"DATABASE={_database};"
        f"UID={_username};"
        f"PWD={_password};"
        "Encrypt=yes;"
        "TrustServerCertificate=yes;"
        "Connection Timeout=30;"
    )
    return create_engine(f"mssql+pyodbc:///?odbc_connect={params}")


engine = get_engine()


def _log_audit(conn, table_name, operation, record_key, changed_by, old_values, new_values):
    try:
        cursor = conn.cursor()
        old_json = json.dumps(old_values, default=str) if old_values else None
        new_json = json.dumps(new_values, default=str) if new_values else None
        cursor.execute("""
            INSERT INTO tbl_wellness_audit_log (table_name, operation, record_key, changed_by, old_values, new_values)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (table_name, operation, record_key, changed_by, old_json, new_json))
        cursor.close()
    except Exception as e:
        pass


# =============================================================================
# SQL QUERIES  — Wellness Dashboard
# =============================================================================
query1  = "SELECT * from vw_new_wellness_enrollee_portal_update"
query2w = ('SELECT a.MemberNo,a.MemberName,a.Client,a.email,a.state,a.selected_provider,'
           'a.Wellness_benefits,a.selected_date,a.selected_session,a.date_submitted '
           'FROM demo_tbl_annual_wellness_enrollee_data a '
           'INNER JOIN (SELECT MemberNo, MAX(PolicyEndDate) AS max_end_date '
           'FROM demo_tbl_annual_wellness_enrollee_data GROUP BY MemberNo) latest '
           'ON  a.MemberNo = latest.MemberNo AND a.PolicyEndDate = latest.max_end_date;')
query3w = ("select a.CODE, a.STATE, PROVIDER_NAME, a.ADDRESS,"
           "Provider_Name + ' - ' + Location as ProviderLoc, PROVIDER, name "
           "from Updated_Wellness_Providers a join tbl_Providerlist_stg b on a.CODE = b.code")
query4w = 'select * from vw_loyaltybeneficiaries'

# =============================================================================
# SQL QUERIES  — Provider Submission Portal
# =============================================================================
query_ps_q2 = (
    "select MemberNo, MemberName, Client, PolicyStartDate, PolicyEndDate, email, state, selected_provider, "
    "Wellness_benefits, selected_date, selected_session, date_submitted, "
    "IssuedPACode, PA_Tests, PA_Provider, PAIssueDate "
    "FROM demo_tbl_annual_wellness_enrollee_data "
    "WHERE PolicyEndDate >= DATEADD(MONTH, -3, GETDATE())"
)
query_ps_q3 = (
    "select a.*, name as ProviderName "
    "from demo_Updated_Wellness_Providers a "
    "left join [dbo].[tbl_ProviderList_stg] b on a.code = b.code"
)
query_ps_q4 = (
    "SELECT r.* "
    "FROM demo_tbl_enrollee_wellness_result_data r "
    "INNER JOIN demo_tbl_annual_wellness_enrollee_data a ON r.memberno = a.memberno "
    "WHERE r.date_submitted < a.PolicyStartDate OR r.date_submitted > a.PolicyEndDate"
)
query_ps_q5 = "SELECT * FROM demo_Wellness_Plans_and_Benefits"


# =============================================================================
# SHARED CACHE  (thread-safe, 5-min TTL)
# =============================================================================
_cache      = {}
_cache_lock = threading.Lock()
_CACHE_TTL  = 300


def cached_read_sql(query, ttl=_CACHE_TTL):
    now = time.time()
    with _cache_lock:
        if query in _cache:
            df, ts = _cache[query]
            if now - ts < ttl:
                return df.copy()
    with engine.connect() as conn:
        df = pd.read_sql(query, conn)
    with _cache_lock:
        _cache[query] = (df, now)
    return df.copy()


def invalidate_cache():
    with _cache_lock:
        _cache.clear()


def log_audit_trail(conn, module_name, modified_by, field_name, previous_value=None, new_value=None):
    try:
        conn.execute(
            text("INSERT INTO WellnessPortalAuditTrail (ModuleName, ModifiedBy, FieldChangedName, PreviousValue, NewValue) VALUES (:module_name, :modified_by, :field_name, :previous_value, :new_value)"),
            {"module_name": module_name, "modified_by": modified_by, "field_name": field_name, 
             "previous_value": previous_value, "new_value": new_value}
        )
    except Exception:
        pass


# =============================================================================
# WELLNESS DASHBOARD GLOBALS + PRE-WARM
# =============================================================================
sterling_bank_enrollees = [
    '100552','101401','45492','45509','45537','45704','45711','45712',
    '45747','45748','67106','67113','67132','67133','80701','105096','45532'
]

wellness_df        = None
wellness_providers = None
loyalty_enrollees  = None
filled_wellness_df = None


def load_all_data():
    global wellness_providers, loyalty_enrollees, filled_wellness_df
    print("[LOADING] Loading wellness providers data...")
    wellness_providers = cached_read_sql(query3w)
    print("[COMPLETE] Wellness providers data loaded!")
    print("[LOADING] Loading loyalty enrollees data...")
    loyalty_enrollees = cached_read_sql(query4w)
    print("[COMPLETE] Loyalty enrollees data loaded!")
    print("[LOADING] Loading filled wellness data...")
    filled_wellness_df = cached_read_sql(query2w)
    print("[COMPLETE] Filled wellness data loaded!")
    filled_wellness_df['MemberNo'] = filled_wellness_df['MemberNo'].astype(str)
    loyalty_enrollees['MemberNo']  = loyalty_enrollees['MemberNo'].astype(str)
    print("[ALL COMPLETE] All startup data loaded successfully!")


def _prewarm_wellness():
    try:
        load_all_data()
        print("[cache] Wellness pre-warm complete.")
    except Exception as e:
        print(f"[cache] Wellness pre-warm warning: {e}")


threading.Thread(target=_prewarm_wellness, daemon=True).start()


def load_wellness_df():
    global wellness_df
    print("[LOADING] Loading wellness_df...")
    wellness_df = cached_read_sql(query1)
    wellness_df['memberno'] = wellness_df['memberno'].astype(int).astype(str)
    print("[COMPLETE] wellness_df loaded!")


ladol_special   = pd.read_csv('Ladol Special Wellness.csv')
image_filename  = 'wellness_image_1.png'
encoded_image   = base64.b64encode(open(image_filename, 'rb').read()).decode()

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

data_loaded = False


# =============================================================================
# PROVIDER SUBMISSION HELPERS
# =============================================================================
PA_TESTS_OPTIONS = [
    {'label': v, 'value': v} for v in [
        'Physical Exam','Urinalysis','PCV','Blood Sugar','BP','Genotype','BMI','ECG',
        'Visual Acuity','Chest X-Ray','Cholesterol','Liver Function Test',
        'Electrolyte, Urea and Creatinine Test(E/U/Cr)','Stool Microscopy','Mammogram',
        'Prostrate Specific Antigen(PSA)','Cervical Smear','Stress ECG','Hepatitis B',
        'Lipid Profile Test','Breast Scan','Prostrate Cancer Screening','Lung Function',
        'Cardiac Risk Assessment','Hearing Test','Mantoux Test',
        'Full Blood Count(FBC)','Hemoglobulin Test',
    ]
]


def login_user(username_val, password_val):
    with engine.connect() as conn:
        result = conn.execute(
            text("SELECT * FROM tbl_provider_wellness_submission_portal_users WHERE code = :code AND password = :password"),
            {"code": username_val, "password": password_val}
        )
        user = result.fetchone()
    if user:
        return user[0], user[1], user[2]
    return None, None, None


def display_member_results(conn_str_val, container_name, selected_provider,
                           selected_client, selected_member, policy_end_date):
    try:
        bsc = BlobServiceClient.from_connection_string(conn_str_val)
        cc  = bsc.get_container_client(container_name)
        pf  = selected_provider.replace(" ", "").lower()
        cf  = selected_client.replace(" ", "").lower()
        ped = policy_end_date.strftime("%Y-%m-%d") if hasattr(policy_end_date, 'strftime') else str(policy_end_date)
        prefix = f"{pf}/{cf}/{ped}/{selected_member.strip()}"
        links = [
            html.A(b.name.split("/")[-1],
                   href=f"https://{bsc.account_name}.blob.core.windows.net/{container_name}/{b.name}",
                   target="_blank")
            for b in cc.list_blobs(name_starts_with=prefix)
        ]
        return html.Div(links) if links else html.Div("No test results found.", style={'color': 'orange'})
    except Exception as e:
        return html.Div(f"Error: {e}", style={'color': 'red'})


def send_email_with_attachment(recipient_email, enrollee_name, provider_name,
                               test_date, subject, uploaded_files,
                               selected_date=None, selected_provider=None, wellness_benefits=None,
                               bcc_email='ifeoluwa.adeniyi@avonhealthcare.com'):
    sender_email   = 'noreply@avonhealthcare.com'
    email_password = os.environ.get('email_password')
    recipient_email = 'ifeoluwa.adeniyi@avonhealthcare.com'

    if selected_date and selected_provider and wellness_benefits:
        body = f"""
            Dear {enrollee_name},<br><br>
            We hope you are staying safe.<br><br>
            You have been scheduled for a wellness screening at your selected provider, see the below table for details:<br><br>
            <table border="1" cellpadding="5" cellspacing="0" style="border-collapse: collapse;">
                <tr>
                    <th style="background-color: #f2f2f2;">Appointment Date</th>
                    <th style="background-color: #f2f2f2;">Wellness Facility</th>
                    <th style="background-color: #f2f2f2;">Wellness Benefits</th>
                </tr>
                <tr>
                    <td>{selected_date}</td>
                    <td>{selected_provider}</td>
                    <td>{wellness_benefits}</td>
                </tr>
            </table>
        """
    else:
        body = f"""
            Dear {enrollee_name},<br><br>
            Trust this message meets you well.<br><br>
            Following your recent wellness test at {provider_name} on {test_date},
            please find attached the results of the wellness tests conducted on you.<br><br>
            You are advised to review the results and consult with your primary healthcare
            provider for further advice.<br><br>
            Best Regards,<br>AVON HMO Medical Services
        """
    try:
        s = smtplib.SMTP('smtp.office365.com', 587)
        s.starttls()
        s.login(sender_email, email_password)
        msg = MIMEMultipart()
        msg['From']    = 'AVON HMO Medical Services'
        msg['To']      = recipient_email
        msg['Bcc']     = bcc_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'html'))
        for fn, fd in uploaded_files:
            p = MIMEBase('application', 'octet-stream')
            p.set_payload(fd)
            encoders.encode_base64(p)
            p.add_header('Content-Disposition', f'attachment; filename={fn}')
            msg.attach(p)
        s.sendmail(sender_email, [recipient_email], msg.as_string())
        s.quit()
        return True, "Email sent successfully."
    except Exception as e:
        return False, f"Email error: {e}"


def send_pa_code_email(recipient_email, enrollee_name, selected_date, selected_provider,
                       wellness_benefits,
                       bcc_email='ifeoluwa.adeniyi@avonhealthcare.com'):
    sender_email   = 'noreply@avonhealthcare.com'
    email_password = os.environ.get('email_password')
    recipient_email = 'ifeoluwa.adeniyi@avonhealthcare.com'
    body = f"""
        Dear {enrollee_name},<br><br>
        We hope you are staying safe.<br><br>
        You have been scheduled for a wellness screening at your selected provider, see the below table for details:<br><br>
        <table style="border-collapse: collapse; width: 100%; max-width: 500px;">
            <tr style="background-color: #f2f2f2;">
                <th style="border: 1px solid #ddd; padding: 8px; text-align: left;">Appointment Date</th>
                <th style="border: 1px solid #ddd; padding: 8px; text-align: left;">Wellness Facility</th>
                <th style="border: 1px solid #ddd; padding: 8px; text-align: left;">Wellness Benefits</th>
            </tr>
            <tr>
                <td style="border: 1px solid #ddd; padding: 8px;">{selected_date}</td>
                <td style="border: 1px solid #ddd; padding: 8px;">{selected_provider}</td>
                <td style="border: 1px solid #ddd; padding: 8px;">{wellness_benefits}</td>
            </tr>
        </table><br><br>
        Kindly note the following requirements for your wellness exercise:<br><br>
        -Present at the hospital with your Avon member ID number/ Ecard.<br>
        -Provide the facility with your valid email address to mail your result.<br>
        -Visit your designated centers between the hours of 8 am - 11 am any day of the week from the scheduled date communicated.<br>
        -Arrive at the facility fasting i.e. last meals should be before 9 pm the previous night and nothing should be eaten that morning before the test. You are allowed to drink up to two cups of water.<br><br>
        For the best results of your screening, it is advisable for blood tests to be done on or before 10 am.<br><br>
        Your results will be strictly confidential and will be sent to you directly via your email.<br><br>
        Kindly note that your wellness result will only be available two (2) weeks after your visit to the provider for your wellness check.<br><br>
        Should you require assistance at any time or wish to make any complaint about the service at any of the facilities,
        please contact our Call-Center at 0700-277-9800 or send us a chat on WhatsApp at 0912-603-9532.
        You can also send us an email at callcentre@avonhealthcare.com.<br><br>
        Thank you for choosing Avon HMO,<br><br>
        Medical Services.
    """
    try:
        s = smtplib.SMTP('smtp.office365.com', 587)
        s.starttls()
        s.login(sender_email, email_password)
        msg = MIMEMultipart()
        msg['From']    = 'AVON HMO Medical Services'
        msg['To']      = recipient_email
        msg['Bcc']     = bcc_email
        msg['Subject'] = 'Wellness Screening PA Code Confirmation'
        msg.attach(MIMEText(body, 'html'))
        s.sendmail(sender_email, [recipient_email], msg.as_string())
        s.quit()
        return True, "Email sent successfully."
    except Exception as e:
        return False, f"Email error: {e}"


# =============================================================================
# WELLNESS DASHBOARD HELPERS
# =============================================================================
def get_job_options(client, policy):
    if policy == 'TOTAL ENERGIES MANAGED CARE PLAN':
        return [
            {'label': 'Offshore Personnel', 'value': 'Offshore Personnel'},
            {'label': 'Fire Team',           'value': 'Fire Team'},
            {'label': 'MERT',                'value': 'MERT'},
            {'label': 'Lab Personnel',       'value': 'Lab Personnel'},
            {'label': 'Admin and Others',    'value': 'Admin and Others'}
        ]
    return [
        {'label': 'Mainly Desk Work',       'value': 'Mainly Desk Work'},
        {'label': 'Mainly Field Work',      'value': 'Mainly Field Work'},
        {'label': 'Desk and Field Work',    'value': 'Desk and Field Work'},
        {'label': 'Physical Outdoor Work',  'value': 'Physical Outdoor Work'},
        {'label': 'Physical Indoor Work',   'value': 'Physical Indoor Work'}
    ]


def get_state_options(client):
    excluded_state    = 'HQ'
    available_states  = list(wellness_providers['STATE'].unique())
    available_states  = [s for s in available_states if s != excluded_state]

    state_map = {
        'UNITED BANK FOR AFRICA':          [s for s in available_states if s != 'HQ'],
        'VERTEVILLE ENERGY':               ['LAGOS', 'BORNO', 'DELTA', 'RIVERS'],
        'PETROSTUFF NIGERIA LIMITED':      ['LAGOS', 'ABUJA', 'RIVERS'],
        'TRANSCORP HILTON HOTEL ABUJA':    ['ABUJA'],
        'REX INSURANCE LTD':               ['LAGOS', 'RIVERS', 'DELTA', 'OYO', 'KADUNA', 'KANO']
    }
    return [{'label': s, 'value': s} for s in state_map.get(client, [s for s in available_states if s != 'HQ'])]


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
        elif state in ('RIVERS', 'RIVERS '):
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

    if client in ('PIVOT GIS LIMITED', 'PIVOT   GIS LIMITED') and state == 'LAGOS':
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


def build_health_questionnaire():
    family_questions = [
        ('a. HYPERTENSION (HIGH BLOOD PRESSURE)', 'resp_1_a'),
        ('b. DIABETES',                           'resp_1_b'),
        ('c. CANCER (ANY TYPE)',                  'resp_1_c'),
        ('d. ASTHMA',                             'resp_1_d'),
        ('e. ARTHRITIS',                          'resp_1_e'),
        ('f. HIGH CHOLESTEROL',                   'resp_1_f'),
        ('g. HEART ATTACK',                       'resp_1_g'),
        ('h. EPILEPSY',                           'resp_1_h'),
        ('i. TUBERCLOSIS',                        'resp_1_i'),
        ('j. SUBSTANCE DEPENDENCY',               'resp_1_j'),
        ('k. MENTAL ILLNESS',                     'resp_1_k'),
    ]
    personal_questions = [
        ('i. HYPERTENSION (HIGH BLOOD PRESSURE)', 'resp_2_a'),
        ('ii. DIABETES',                          'resp_2_b'),
        ('iii. CANCER (ANY TYPE)',                'resp_2_c'),
        ('iv. ASTHMA',                            'resp_2_d'),
        ('v. ULCER',                              'resp_2_e'),
        ('vi. POOR VISION',                       'resp_2_f'),
        ('vii. ALLERGY',                          'resp_2_g'),
        ('viii. ARTHRITIS/LOW BACK PAIN',         'resp_2_h'),
        ('ix. ANXIETY/DEPRESSION',                'resp_2_i'),
    ]
    surgical_questions = [
        ('i. CEASAREAN SECTION', 'resp_3_a'),
        ('ii. FRACTURE REPAIR',  'resp_3_b'),
        ('iii. HERNIA',          'resp_3_c'),
        ('iv. LUMP REMOVAL',     'resp_3_d'),
        ('v. APPENDICETOMY',     'resp_3_e'),
        ('vi. SPINE SURGERY',    'resp_3_f'),
    ]
    wellness_questions = [
        ('a. I avoid eating foods that are high in fat',                                                         'resp_4_a'),
        ('b. I have been avoiding the use or minimise my exposure to alcohol',                                   'resp_4_b'),
        ('c. I have been avoiding the use of tobacco products',                                                  'resp_4_c'),
        ('d. I am physically fit and exercise at least 30 minutes every day',                                    'resp_4_d'),
        ('e. I have been eating vegetables and fruits at least 3 times weekly',                                  'resp_4_e'),
        ('f. I drink 6-8 glasses of water a day',                                                               'resp_4_f'),
        ('g. I maintain my weight within the recommendation for my weight, age and height',                     'resp_4_g'),
        ('h. My blood pressure is within normal range without the use of drugs',                                'resp_4_h'),
        ('i. My cholesterol level is within the normal range',                                                  'resp_4_i'),
        ('j. I easily make decisions without worry',                                                            'resp_4_j'),
        ('k. I enjoy more than 5 hours of sleep at night',                                                      'resp_4_k'),
        ('l. I enjoy my work and life',                                                                         'resp_4_l'),
        ('m. I enjoy the support from friends and family',                                                      'resp_4_m'),
        ('n. I feel bad about myself or that I am a failure or have let myself or my family down',              'resp_4_n'),
        ('o. I have poor appetite or I am over-eating',                                                         'resp_4_o'),
        ('p. I feel down, depressed, hopeless, tired or have little energy',                                    'resp_4_p'),
        ('q. I have trouble falling asleep, staying asleep, or sleeping too much',                              'resp_4_q'),
        ('r. I have no interest or pleasure in doing things',                                                   'resp_4_r'),
        ('s. I have trouble concentrating on things, such as reading the newspaper, or watching TV',            'resp_4_s'),
        ('t. I think I would be better off dead or better off hurting myself in some way',                      'resp_4_t'),
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
                    {'label': ' Parent(s) ',       'value': 'Parent(s)'},
                    {'label': ' Uncle/Aunty ',     'value': 'Uncle/Aunty'},
                    {'label': ' Nobody ',          'value': 'Nobody'}
                ],
                value='Nobody',
                inline=True, className="custom-radio"
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
                    {'label': ' Yes ',                      'value': 'Yes'},
                    {'label': ' No ',                       'value': 'No'},
                    {'label': ' Yes, but not on Medication ', 'value': 'Yes, but not on Medication'}
                ],
                value='No',
                inline=True, className="custom-radio"
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
                options=[{'label': ' Yes ', 'value': 'Yes'}, {'label': ' No ', 'value': 'No'}],
                value='No',
                inline=True, className="custom-radio"
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
                    {'label': ' Never ',        'value': 'Never'},
                    {'label': ' Occasional ',   'value': 'Occasional'},
                    {'label': ' Always ',       'value': 'Always'},
                    {'label': ' I Do Not Know ','value': 'I Do Not Know'}
                ],
                value='Never',
                inline=True, className="custom-radio"
            )
        ]))

    return html.Div(sections)


def build_enrollment_form(enrollee_data):
    client   = enrollee_data['client']
    policy   = enrollee_data['policy']

    current_date = dt.date.today()
    max_date     = dt.date(2027, 12, 31)

    if client in ('PIVOT GIS LIMITED', 'PIVOT   GIS LIMITED'):
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
                        value='Male', inline=True, className="mb-3"
                    )
                ], width=12)
            ]),

            dbc.Row([
                dbc.Col([
                    html.Label("Nature of Work / Occupation Type", className="small fw-medium", style={"color": "#44337A"}),
                    dcc.Dropdown(
                        id='job-type-select',
                        options=get_job_options(client, policy),
                        value='', placeholder='Select Work Category', className="mb-3"
                    )
                ], width=12)
            ]),

            html.Hr(className="my-4"),

            dbc.Row([
                dbc.Col([
                    html.Label("Your Current Location", className="small fw-medium", style={"color": "#44337A"}),
                    dcc.Dropdown(
                        id='state-select', options=get_state_options(client),
                        value='', placeholder='Pick your Current State of Residence', className="mb-3"
                    )
                ], width=12)
            ]),

            dbc.Row([
                dbc.Col([
                    html.Label("Pick your Preferred Wellness Facility", className="small fw-medium", style={"color": "#44337A"}),
                    dcc.Dropdown(
                        id='provider-select', options=[], value='',
                        placeholder='Select a Provider', className="mb-3"
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
                        date=None, className="mb-3"
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
               className="w-100 btn-primary-custom d-flex align-items-center justify-content-center",
               style={"color": "white"})
        ])
    ], className="card-glass border-0", style={"borderRadius": "24px"})

    return html.Div([form], className="px-3")


def send_confirmation_email(enrollee_id, member_name, email, provider, benefits,
                            selected_date, session, client, date_communicated=False):
    myemail  = 'noreply@avonhealthcare.com'
    pwd      = os.environ.get('email_password')

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
    table {{border: 1px solid #1C6EA4; background-color: #EEEEEE; width: 100%; text-align: left; border-collapse: collapse;}}
    table td, table th {{border: 1px solid #AAAAAA; padding: 3px 2px;}}
    table tbody td {{font-size: 13px;}}
    table thead {{background: #59058D; border-bottom: 2px solid #444444;}}
    table thead th {{font-size: 15px; font-weight: bold; color: #FFFFFF; border-left: 2px solid #D0E4F5;}}
    table thead th:first-child {{border-left: none;}}
    </style>
    <table>{wellness_table_html}</table>
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
    You can also send us an email at callcentre@avonhealthcare.com.<br><br>
    Thank you for choosing Avon HMO,<br><br>
    Medical Services.<br>
    '''

    text_after_table1 = f'''
    <br>Kindly note that wellness exercise at your selected facility is strictly by appointment and
    you are expected to be available at the facility on the appointment date as selected by you.<br><br>
    Also, note that you will be required to:<br><br>
    -Present at the facility with your Avon member ID number ({enrollee_id})/ Ecard.<br>
    -Provide the facility with your valid email address to mail your result.<br>
    -You are advised to be present at your selected facility 15 mins before your scheduled time.<br><br>
    Your results will be strictly confidential and will be sent to you directly via your email. You are advised to review
    your results with your primary care provider for relevant medical advice.<br><br>
    <b>Kindly note that your wellness result will only be available two (2) weeks after your visit to the provider for your wellness check.</b><br><br>
    Should you require assistance at any time or wish to make any complaint about the service at any of the facilities,
    please contact our Call-Center at 0700-277-9800  or send us a chat on WhatsApp at 0912-603-9532.
    You can also send us an email at callcentre@avonhealthcare.com.<br><br>
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
    - The wellness exercise will take place at the designated floor which will be communicated to you by the HR between 9 am and 4 pm from Monday - Friday.<br><br>
    - For the most accurate fasting blood sugar test results, it is advisable for blood tests to be done before 10am.<br><br>
    - Staff results will be sent to the email addresses provided by them to the wellness providers.<br><br>
    - There will be consultation with a physician to review immediate test results on-site while other test results that are not readily available will be reviewed by a physician at your Primary Care Provider.<br><br>
    Should you require assistance at any time or wish to make any complaint about the service rendered during this wellness exercise,
    please contact our Call-Center at 0700-277-9800 or send us a chat on WhatsApp at 0912-603-9532.
    You can also send us an email at callcentre@avonhealthcare.com.<br><br>
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
    You can also send us an email at callcentre@avonhealthcare.com.<br><br>
    Thank you for choosing Avon HMO,<br><br>
    Medical Services.<br>
    '''

    email_sent  = False
    email_error = ''

    if client == 'UNITED BANK FOR AFRICA':
        if 'UBA Head Office' in provider:
            full_message = msg_befor_table + table_html + head_office_msg
        elif 'CERBA LANCET' in provider or 'CERBA LANCET NIGERIA' in provider:
            full_message = msg_befor_table + table_html + text_after_table1
        else:
            full_message = msg_befor_table + table_html + text_after_table
    elif client in ('PIVOT GIS LIMITED', 'PIVOT   GIS LIMITED'):
        full_message = msg_befor_table + table_html + pivotgis_msg
    else:
        full_message = msg_befor_table + table_html + text_after_table

    bcc_email_list = ['ifeoluwa.adeniyi@avonhealthcare.com', 'ifeoluwa.adeniyi@avonhealthcare.com']

    if provider in ['ECHOLAB - Opposite mararaba medical centre, Tipper Garage, Mararaba',
                    'TOBIS CLINIC - Chief Melford Okilo Road Opposite Sobaz Filling Station, Akenfa-Epie',
                    'ECHOLAB - 375B Nnebisi Road, Umuagu, Asaba']:
        bcc_email_list.extend(['ifeoluwa.adeniyi@avonhealthcare.com', 'ifeoluwa.adeniyi@avonhealthcare.com'])

    try:
        srv = smtplib.SMTP('smtp.office365.com', 587)
        srv.starttls()
        srv.login(myemail, pwd)
        msg = MIMEMultipart()
        msg['From']    = 'AVON HMO Client Services'
        msg['To']      = email
        msg['Bcc']     = ', '.join(bcc_email_list)
        msg['Subject'] = 'AVON ENROLLEE WELLNESS APPOINTMENT CONFIRMATION'
        msg.attach(MIMEText(full_message, 'html'))
        srv.sendmail(myemail, [email] + bcc_email_list, msg.as_string())
        srv.quit()
        email_sent = True
    except Exception as e:
        email_error = str(e)
        print(f"Email error: {e}")

    return email_sent, email_error


# =============================================================================
# PROVIDER SUBMISSION — LAYOUTS
# =============================================================================
def _nav_card(body_children):
    return dbc.Card([dbc.CardHeader("Navigation"), dbc.CardBody(body_children)], className="mb-3")


ps_login_layout = dbc.Container([
    html.Div(
        html.A("← Back to Wellness Portal", href="/wellness",
               style={"color": "#59058d", "fontWeight": "600", "textDecoration": "none", "fontSize": "14px"}),
        style={"padding": "16px 24px"}
    ),
    dbc.Row([
        dbc.Col([
            html.Br(), html.Br(), html.Br(),
            dbc.Card([
                dbc.CardBody([
                    html.H2("Provider Wellness Result Submission Portal", className="text-center mb-4"),
                    html.P("Login with your username and password to access the portal.", className="text-center text-muted"),
                    html.Br(),
                    dbc.Label("Username"),
                    dbc.Input(id="login-username", type="text", placeholder="Enter username"),
                    html.Br(),
                    dbc.Label("Password"),
                    dbc.Input(id="login-password", type="password", placeholder="Enter password"),
                    html.Br(),
                    dbc.Button("Login", id="login-button", color="primary", className="w-100",
                               style={"backgroundColor": "#59058d", "borderColor": "#59058d"}),
                    html.Br(),
                    html.Div(id="login-error", className="text-danger text-center")
                ])
            ], className="shadow-lg")
        ], width={"size": 6, "offset": 3})
    ])
], fluid=True, style={"backgroundColor": "#f8f9fa", "minHeight": "100vh"})

ps_provider_layout = dbc.Container([
    dbc.Row([dbc.Col([
        html.H2("Provider Wellness Result Submission Portal", className="mt-3"),
    ], width=9),
    dbc.Col([
        html.Div([
            html.Span(id="provider-welcome", className="me-3", style={"fontWeight": "bold", "color": "purple"}),
            dbc.Button("Logout", id="logout-btn", color="danger", size="sm"),
        ], className="d-flex align-items-center justify-content-end", style={"marginTop": "20px"}),
    ], width=3)
    ]),
    dbc.Row([
        dbc.Col([_nav_card([
            html.P("Welcome to the Provider Wellness Result Submission Portal"),
            dbc.RadioItems(
                id="provider-nav-option",
                options=[
                    {"label": "View Wellness Enrollees and Benefits", "value": "view"},
                    {"label": "Submit Wellness Results",              "value": "submit"}
                ],
                value="view", inline=True
            ),
        ])], width=3),
        dbc.Col([html.Div(id="provider-content")], width=9)
    ])
], fluid=True)

ps_claims_layout = dbc.Container([
    dbc.Row([dbc.Col([
        html.H2("Provider Wellness Result Review Portal", className="mt-3 text-center", style={"color": "purple"}),
    ], width=9),
    dbc.Col([
        html.Div([
            html.Span(id="claims-welcome", className="me-3", style={"fontWeight": "bold", "color": "purple"}),
            dbc.Button("Logout", id="logout-btn", color="danger", size="sm"),
        ], className="d-flex align-items-center justify-content-end", style={"marginTop": "20px"}),
    ], width=3)
    ]),
    dbc.Row([
        dbc.Col([_nav_card([
            html.P("Please select a Provider to view Submitted Wellness Results"),
            dbc.Label("Select Provider", style={"color": "purple"}),
            dcc.Dropdown(id="claims-provider-select", placeholder="Select Provider"),
            html.Br(),
            dbc.Label("Select Member", style={"color": "purple"}),
            dcc.Dropdown(id="claims-member-select", placeholder="Select Member"),
            html.Br(),
            dbc.Label("Select Policy Period", style={"color": "purple"}),
            dcc.Dropdown(id="claims-policy-period-select", placeholder="Select Policy Period"),
        ])], width=3),
        dbc.Col([html.Div(id="claims-content")], width=9)
    ])
], fluid=True)

ps_contact_layout = dbc.Container([
    dbc.Row([dbc.Col([
        html.H2("Wellness PA Code Authorisation and Results Review Portal", className="mt-3", style={"color": "purple"}),
    ], width=9),
    dbc.Col([
        html.Div([
            html.Span(id="contact-welcome", className="me-3", style={"fontWeight": "bold", "color": "purple"}),
            dbc.Button("Logout", id="logout-btn", color="danger", size="sm"),
        ], className="d-flex align-items-center justify-content-end", style={"marginTop": "20px"}),
    ], width=3)
    ]),
    dbc.Row([
        dbc.Col([_nav_card([
            html.P("Welcome to the Wellness PA Code Authorisation and Results Review Portal"),
            html.P("Kindly input Member ID to check Eligibility and Booking Status:", style={"color": "purple"}),
            dbc.Input(id="contact-enrollee-id", type="text", placeholder="Enter Member ID here"),
            html.Br(),
            dbc.Button("Search", id="contact-search-button", color="primary"),
        ])], width=3),
        dbc.Col([dcc.Loading(type="default", children=html.Div(id="contact-content"))], width=9)
    ])
], fluid=True)

ps_services_layout = dbc.Container([
    dbc.Row([dbc.Col([
        html.H2("Wellness Services Management Portal", className="mt-3", style={"color": "purple"}),
    ], width=9),
    dbc.Col([
        html.Div([
            html.Span(id="services-welcome", className="me-3", style={"fontWeight": "bold", "color": "purple"}),
            dbc.Button("Logout", id="logout-btn", color="danger", size="sm"),
        ], className="d-flex align-items-center justify-content-end", style={"marginTop": "20px"}),
    ], width=3)
    ]),
    dbc.Row([
        dbc.Col([dcc.Loading(type="default", children=html.Div(id="services-content"))], width=12),
    ])
], fluid=True)



# =============================================================================
# WELLNESS PORTAL — LOADING SCREEN
# =============================================================================
def wellness_loading_screen():
    return html.Div([
        html.Div(className="purple-skew"),
        html.Div(className="green-blob"),
        html.Div([
            html.Div(className="logo-container mb-4", children=[
                Svg(width="64", height="64", viewBox="0 0 24 24", fill="none", stroke="white",
                    style={"strokeWidth": "2", "strokeLinecap": "round", "strokeLinejoin": "round"},
                    children=[
                        Path(d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"),
                        Path(d="m9 12 2 2 4-4")
                    ])
            ]),
            html.H3("Loading portal data...", className="mb-3", style={"color": "#44337A"}),
            dbc.Spinner(size="lg", color="primary"),
            html.P("Please wait while we load the wellness portal", className="mt-3", style={"color": "#718096"})
        ], className="text-center")
    ], className="gradient-bg min-vh-100 d-flex align-items-center justify-content-center p-4 position-relative overflow-hidden")


# =============================================================================
# WELLNESS PORTAL — MAIN PORTAL LAYOUT
# =============================================================================
def wellness_portal_layout():
    return html.Div([
        html.A(
            [html.Span("⚕", style={"fontSize": "16px"}), " Provider Portal"],
            href="/wellness/provider",
            className="provider-portal-btn",
            id="go-to-provider-btn"
        ),

        dcc.Location(id='url-welcome', refresh=False),
        html.Div(className="purple-skew"),
        html.Div(className="green-blob"),

        html.Div(
            className="position-relative w-100",
            style={"maxWidth": "520px", "zIndex": "10", "margin": "0 auto"},
            children=[
                html.Div([
                    html.Div(className="logo-container mb-4", children=[
                        Svg(width="32", height="32", viewBox="0 0 24 24", fill="none", stroke="white",
                            style={"strokeWidth": "2", "strokeLinecap": "round", "strokeLinejoin": "round"},
                            children=[
                                Path(d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"),
                                Path(d="m9 12 2 2 4-4")
                            ])
                    ]),
                    html.H1("Wellness Portal", className="text-4xl fw-bold mb-2",
                            style={"color": "#44337A", "fontSize": "2rem"}),
                    html.P("AVON HMO Enrollee Annual Wellness Portal. Check your eligibility and book your annual wellness checkup.",
                           className="text-lg mb-4", style={"color": "#718096"}),
                    # Back to home link
                    html.Div([
                        dcc.Link("← Back to Home", href="/",
                                 style={"color": "#6B46C1", "fontWeight": "600", "textDecoration": "none", "fontSize": "14px"})
                    ], className="mb-3")
                ], className="text-center mb-5"),

                dbc.Card([
                    dbc.CardBody([
                        html.Div([
                            html.Label("Member Number / Policy ID", className="fw-medium mb-2", style={"color": "#44337A"}),
                            dcc.Input(
                                id='enrollee-id-input', type='text',
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
                            html.Small("Double check that your Member ID is correct. If you have any issues, please contact our support team.",
                                      className="d-block text-center mt-3",
                                      style={"color": "rgba(113, 128, 150, 0.6)"})
                        ], className="p-2")
                    ])
                ], className="card-glass border-0", style={"borderRadius": "24px"}),

                html.Div([
                    dbc.Row([dbc.Col(id='already-booked-section', width=12)]),
                    dbc.Row([dbc.Col(id='enrollment-form-section', width=12)]),
                ], className="mt-4"),

                html.P(f"© {dt.datetime.now().year} AVON HMO. All rights reserved.",
                       className="text-center mt-4 small",
                       style={"color": "rgba(113, 128, 150, 0.6)"})
            ]
        )
    ], className="gradient-bg min-vh-100 d-flex align-items-center justify-content-center p-4 position-relative overflow-hidden")


# =============================================================================
# PAGE LAYOUT  — multi-page entry point
# =============================================================================
layout = html.Div([
    # Stores
    dcc.Store(id='data-ready-store-wellness', data=False),
    dcc.Interval(id='data-check-interval', interval=500, n_intervals=0),
    dcc.Store(id='user-data-store',         data=initial_user_data),
    dcc.Store(id='enrollee-data-store',     data={}),
    dcc.Store(id='submission-trigger',      data=0),
    dcc.Store(id='questionnaire-responses', data={}),
    dcc.Store(id='session-store',           data=''),
    dcc.Store(id="auth-store",              storage_type="session",
              data={"authenticated": False, "username": None, "providername": None}),
    dcc.Store(id="data-ready-store-ps",     data=False),
    dcc.Store(id="store-q2",  data=None),
    dcc.Store(id="store-q3",  data=None),
    dcc.Store(id="store-q4",  data=None),
    dcc.Store(id="store-q5",  data=None),
    dcc.Store(id="services-view-store",           data="providers"),
    dcc.Store(id="services-state-filter",         data=None),
    dcc.Store(id="services-provider-name-filter", data=None),
    dcc.Store(id="services-plan-type-filter",     data=None),
    dcc.Store(id="services-client-name-filter",   data=None),

    # Sub-page content
    html.Div(id='wellness-page-content'),

    # Success modal
    dbc.Modal([
        dbc.ModalHeader("Submission Successful",
                        style={"fontFamily": "Playfair Display, serif", "color": "#44337A"}),
        dbc.ModalBody(id='submission-message'),
        dbc.ModalFooter(dbc.Button("Close", id="close-modal",
                                   className="btn-primary-custom", style={"color": "white"}))
    ], id="success-modal", is_open=False, size="lg", centered=True),
])


# =============================================================================
# WELLNESS PAGE CONTENT  (loading screen then portal once data is ready)
# =============================================================================
@callback(
    Output('wellness-page-content', 'children'),
    Output('data-check-interval',   'disabled'),
    Input('data-ready-store-wellness', 'data'),
)
def route_wellness_page(wellness_ready):
    if not wellness_ready:
        return wellness_loading_screen(), False
    return dcc.Loading(
        id="loading",
        type="circle",
        fullscreen=False,
        color="#6B46C1",
        children=wellness_portal_layout()
    ), True


# =============================================================================
# DATA READINESS CHECK
# =============================================================================
@callback(
    Output('data-ready-store-wellness', 'data'),
    Input('data-check-interval', 'n_intervals'),
    prevent_initial_call=False
)
def check_wellness_data_loaded(n):
    if filled_wellness_df is not None and loyalty_enrollees is not None and wellness_providers is not None:
        return True
    return False


# =============================================================================
# ELIGIBILITY CHECK
# =============================================================================
@callback(
    Output('eligibility-message',      'children'),
    Output('already-booked-section',   'children'),
    Output('enrollment-form-section',  'children'),
    Output('enrollee-data-store',      'data'),
    Output('enrollee-id-input',        'value'),
    Input('_pages_location',           'search'),
    Input('member-id-submit-btn',      'n_clicks'),
    Input('enrollee-id-input',         'n_submit'),
    State('enrollee-id-input',         'value'),
    State('enrollee-data-store',       'data'),
    prevent_initial_call=True
)
def check_eligibility(url_search, n_clicks, n_submit, enrollee_id, stored_data):
    global wellness_df
    if wellness_df is None:
        load_wellness_df()

    ctx = callback_context
    triggered_id = ctx.triggered[0]['prop_id'].split('.')[0] if ctx.triggered else None

    if triggered_id == '_pages_location' or not enrollee_id:
        parsed     = urllib.parse.parse_qs(urllib.parse.urlparse(url_search or '').query)
        url_member = parsed.get('member', [None])[0]
        if url_member:
            enrollee_id = url_member

    if not enrollee_id:
        return "", "", "", {}, ""

    enrollee_id = str(enrollee_id).strip()

    if enrollee_id in filled_wellness_df['MemberNo'].values:
        row = filled_wellness_df[filled_wellness_df['MemberNo'] == enrollee_id].iloc[0]
        member_name    = row['MemberName']
        submitted_date = str(row['date_submitted'])[:10]
        final_submit_date = dt.datetime.strptime(submitted_date, "%Y-%m-%d").date()
        policystart = wellness_df.loc[wellness_df['memberno'] == enrollee_id, 'PolicyStartDate'].values[0]
        policyend   = wellness_df.loc[wellness_df['memberno'] == enrollee_id, 'PolicyEndDate'].values[0]

        if policystart <= final_submit_date <= policyend:
            clientname   = row['Client']
            package      = row['Wellness_benefits']
            member_email = row['email']
            provider     = row['selected_provider']
            app_date     = row['selected_date']
            app_session  = row['selected_session']
            six_weeks    = (dt.datetime.strptime(submitted_date, "%Y-%m-%d").date() + dt.timedelta(weeks=6)).strftime('%A, %d %B %Y')

            msg = dbc.Alert([
                html.H5(f"Dear {member_name}."),
                html.P(f"Please note that you have already booked your wellness appointment on {submitted_date} and your booking confirmation has been sent to {member_email} as provided"),
                html.P(f"Wellness Facility: {provider}"),
                html.P(f"Wellness Benefits: {package}"),
                html.P(f"Appointment Date: {app_date} - {app_session}"),
                html.P("Kindly note that your wellness result will only be available two (2) weeks after your visit to the provider for your wellness test."),
                html.P("Kindly contact your Client Manager if you wish change your booking appointment/wellness center."),
                html.Hr(),
                html.P(f"Note that your annual wellness is only valid till {six_weeks}", className='font-weight-bold')
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
            'policystart':  str(wellness_df.loc[wellness_df['memberno'] == enrollee_id, 'PolicyStartDate'].values[0]),
            'policyend':    str(wellness_df.loc[wellness_df['memberno'] == enrollee_id, 'PolicyEndDate'].values[0]),
            'member_name':  str(wellness_df.loc[wellness_df['memberno'] == enrollee_id, 'membername'].values[0]),
            'client':       str(wellness_df.loc[wellness_df['memberno'] == enrollee_id, 'Client'].values[0]),
            'policy':       str(wellness_df.loc[wellness_df['memberno'] == enrollee_id, 'PolicyName'].values[0]),
            'package':      str(wellness_df.loc[wellness_df['memberno'] == enrollee_id, 'WellnessPackage'].values[0]),
            'age':          int(wellness_df.loc[wellness_df['memberno'] == enrollee_id, 'Age'].values[0]),
            'relation':     str(wellness_df.loc[wellness_df['memberno'] == enrollee_id, 'Relation'].values[0]),
            'gender':       str(wellness_df.loc[wellness_df['memberno'] == enrollee_id, 'sex'].values[0]) if 'sex' in wellness_df.columns else 'Male'
        }

        six_weeks = (dt.date.today() + dt.timedelta(weeks=6)).strftime('%A, %d %B %Y')

        consent_msg = dbc.Alert([
            html.H5(f"Dear {enrollee_data['member_name']}."),
            html.P([
                html.B("Kindly confirm that your enrollment details match the info displayed below."),
                html.Br(), html.Br(),
                "Also note that by proceeding to fill this form, you consent to the collection and processing of your data for the purpose of this wellness screening exercise. "
                "You understand that your results may be shared with the HMO for claims management and care coordination, "
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

    not_eligible = dbc.Alert(
        "You are not eligible to participate, please contact your HR or Client Manager",
        color="info", className="alert alert-danger mb-3",
        style={"backgroundColor": "#FED7D7", "border": "1px solid #FEB2B2", "color": "#C53030"}
    )
    return not_eligible, "", "", {}, enrollee_id


# =============================================================================
# QUESTIONNAIRE RESPONSES
# =============================================================================
@callback(
    Output('questionnaire-responses', 'data'),
    Input('radio-resp_1_a', 'value'), Input('radio-resp_1_b', 'value'), Input('radio-resp_1_c', 'value'),
    Input('radio-resp_1_d', 'value'), Input('radio-resp_1_e', 'value'), Input('radio-resp_1_f', 'value'),
    Input('radio-resp_1_g', 'value'), Input('radio-resp_1_h', 'value'), Input('radio-resp_1_i', 'value'),
    Input('radio-resp_1_j', 'value'), Input('radio-resp_1_k', 'value'),
    Input('radio-resp_2_a', 'value'), Input('radio-resp_2_b', 'value'), Input('radio-resp_2_c', 'value'),
    Input('radio-resp_2_d', 'value'), Input('radio-resp_2_e', 'value'), Input('radio-resp_2_f', 'value'),
    Input('radio-resp_2_g', 'value'), Input('radio-resp_2_h', 'value'), Input('radio-resp_2_i', 'value'),
    Input('radio-resp_3_a', 'value'), Input('radio-resp_3_b', 'value'), Input('radio-resp_3_c', 'value'),
    Input('radio-resp_3_d', 'value'), Input('radio-resp_3_e', 'value'), Input('radio-resp_3_f', 'value'),
    Input('radio-resp_4_a', 'value'), Input('radio-resp_4_b', 'value'), Input('radio-resp_4_c', 'value'),
    Input('radio-resp_4_d', 'value'), Input('radio-resp_4_e', 'value'), Input('radio-resp_4_f', 'value'),
    Input('radio-resp_4_g', 'value'), Input('radio-resp_4_h', 'value'), Input('radio-resp_4_i', 'value'),
    Input('radio-resp_4_j', 'value'), Input('radio-resp_4_k', 'value'), Input('radio-resp_4_l', 'value'),
    Input('radio-resp_4_m', 'value'), Input('radio-resp_4_n', 'value'), Input('radio-resp_4_o', 'value'),
    Input('radio-resp_4_p', 'value'), Input('radio-resp_4_q', 'value'), Input('radio-resp_4_r', 'value'),
    Input('radio-resp_4_s', 'value'), Input('radio-resp_4_t', 'value'),
)
def update_questionnaire_responses(
        r1a, r1b, r1c, r1d, r1e, r1f, r1g, r1h, r1i, r1j, r1k,
        r2a, r2b, r2c, r2d, r2e, r2f, r2g, r2h, r2i,
        r3a, r3b, r3c, r3d, r3e, r3f,
        r4a, r4b, r4c, r4d, r4e, r4f, r4g, r4h, r4i, r4j, r4k,
        r4l, r4m, r4n, r4o, r4p, r4q, r4r, r4s, r4t):
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


# =============================================================================
# PROVIDER OPTIONS
# =============================================================================
@callback(
    Output('provider-select', 'options'),
    Input('state-select', 'value'),
    State('enrollee-id-input', 'value'),
)
def update_providers(state, enrollee_id):
    if not enrollee_id or not state:
        return []
    global wellness_df
    if wellness_df is None:
        load_wellness_df()
    enrollee_id = str(enrollee_id).strip()
    if enrollee_id not in wellness_df['memberno'].values:
        return []
    client    = wellness_df.loc[wellness_df['memberno'] == enrollee_id, 'Client'].values[0]
    providers = get_providers_for_client_state(client, state, enrollee_id)
    return [{'label': p, 'value': p} for p in providers]


# =============================================================================
# SESSION UPDATE
# =============================================================================
@callback(
    Output('session-radio-container', 'children'),
    Output('date-picker-row',         'style'),
    Output('session-store',           'data'),
    Input('state-select',    'value'),
    Input('provider-select', 'value'),
    Input('date-picker',     'date'),
    State('enrollee-id-input', 'value'),
    State('session-store',     'data'),
)
def update_sessions(state, provider, selected_date, enrollee_id, current_session):
    if not enrollee_id:
        return html.Div(), {'display': 'none'}, ''
    global wellness_df
    if wellness_df is None:
        load_wellness_df()
    enrollee_id = str(enrollee_id).strip()
    if enrollee_id not in wellness_df['memberno'].values:
        return html.Div(), {'display': 'none'}, ''

    client = wellness_df.loc[wellness_df['memberno'] == enrollee_id, 'Client'].values[0]

    if client in ('PIVOT GIS LIMITED', 'PIVOT   GIS LIMITED'):
        return html.Div(), {'display': 'block'}, ''

    if (state in ('LAGOS', 'UBA HQ')) and provider:
        if 'UBA Head Office' in provider:
            return dbc.Alert(
                "The date for your Wellness Exercise will be communicated to you by your HR. Kindly fill the questionnaire below to complete your wellness booking",
                color="info"), {'display': 'none'}, ''

        if ('CERBA LANCET' in provider) or ('CERBA LANCET NIGERIA' in provider):
            if not selected_date:
                return dbc.Alert("Please select a date first", color="warning"), {'display': 'block'}, current_session

            global filled_wellness_df
            _q2_fresh = 'select MemberNo, MemberName, Client, email, state, selected_provider, Wellness_benefits, selected_date, selected_session, date_submitted from demo_tbl_annual_wellness_enrollee_data a where a.PolicyEndDate = (select max(PolicyEndDate) from demo_tbl_annual_wellness_enrollee_data b where a.MemberNo = b.MemberNo)'
            with engine.connect() as conn:
                filled_wellness_df = pd.read_sql(_q2_fresh, conn)
            filled_wellness_df['MemberNo'] = filled_wellness_df['MemberNo'].astype(str)

            selected_date_str = dt.datetime.strptime(selected_date, '%Y-%m-%d').strftime('%Y-%m-%d')
            booked_sessions = filled_wellness_df.loc[
                (filled_wellness_df['selected_date'] == selected_date_str) &
                (filled_wellness_df['selected_provider'] == provider),
                'selected_session'
            ].values.tolist()

            available_sessions = [
                '08:00 AM - 09:00 AM', '09:00 AM - 10:00 AM', '10:00 AM - 11:00 AM',
                '11:00 AM - 12:00 PM', '12:00 PM - 01:00 PM', '01:00 PM - 02:00 PM',
                '02:00 PM - 03:00 PM', '03:00 PM - 04:00 PM'
            ]
            session_counts     = {s: booked_sessions.count(s) for s in available_sessions}
            available_sessions = [s for s in available_sessions if session_counts[s] < 3]

            if not available_sessions:
                return dbc.Alert(
                    "All sessions for the selected date at this facility are fully booked. Please select another date or facility.",
                    color="danger"), {'display': 'block'}, current_session

            return [
                dbc.Alert("Please note that the Facilities are opened between the 8:00 am and 5:00 pm, Monday - Friday and 8:00 am - 2:00 pm on Saturdays.", color="info"),
                dbc.RadioItems(
                    id='session-radio',
                    options=[{'label': s, 'value': s} for s in available_sessions],
                    value=current_session if current_session in available_sessions else None,
                    inline=True
                )
            ], {'display': 'block'}, current_session if current_session else ''

    return html.Div(), {'display': 'block'}, ''


@callback(
    Output('session-store', 'data', allow_duplicate=True),
    Input('session-radio', 'value'),
    prevent_initial_call=True
)
def update_session_store(session_value):
    return session_value if session_value else ''


# =============================================================================
# FORM SUBMISSION
# =============================================================================
@callback(
    Output('success-modal',      'is_open'),
    Output('submission-message', 'children'),
    Input('submit-form-btn',  'n_clicks'),
    Input('close-modal',      'n_clicks'),
    State('enrollee-id-input',       'value'),
    State('email-input',             'value'),
    State('mobile-input',            'value'),
    State('gender-radio',            'value'),
    State('job-type-select',         'value'),
    State('state-select',            'value'),
    State('provider-select',         'value'),
    State('date-picker',             'date'),
    State('session-store',           'data'),
    State('enrollee-data-store',     'data'),
    State('questionnaire-responses', 'data'),
    prevent_initial_call=True
)
def submit_form(submit_clicks, close_clicks, enrollee_id, email, mobile, gender,
                job_type, state, provider, selected_date, session,
                enrollee_data, questionnaire_responses):
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
    if not email:    missing.append('Email')
    if not mobile:   missing.append('Mobile Number')
    if not state:    missing.append('Your Current Location')
    if not provider: missing.append('Preferred Wellness Facility')

    if missing:
        return True, dbc.Alert(f"The following field(s) are required: {', '.join(missing)}", color="danger")

    selected_date_str = ''
    date_communicated = False
    if selected_date:
        selected_date_str = dt.datetime.strptime(selected_date, '%Y-%m-%d').strftime('%Y-%m-%d')
    if not session:
        session = ''

    client        = enrollee_data.get('client', '')
    policy        = enrollee_data.get('policy', '')
    age           = enrollee_data.get('age', 0)
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
    six_weeks   = six_week_dt.strftime('%A, %d %B %Y')

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
        with engine.connect() as conn:
            cursor = conn.connection.cursor()
            cursor.execute(insert_query, (
                enrollee_id, enrollee_data['member_name'], client, policy,
                enrollee_data['policystart'], enrollee_data['policyend'], email, mobile, job_type,
                age, state, provider, member_gender, benefits, selected_date_str, session,
                questionnaire_responses.get('resp_1_a') or 'Grand Parent(s)', questionnaire_responses.get('resp_1_b') or 'Grand Parent(s)',
                questionnaire_responses.get('resp_1_c') or 'Grand Parent(s)', questionnaire_responses.get('resp_1_d') or 'Grand Parent(s)',
                questionnaire_responses.get('resp_1_e') or 'Grand Parent(s)', questionnaire_responses.get('resp_1_f') or 'Grand Parent(s)',
                questionnaire_responses.get('resp_1_g') or 'Grand Parent(s)', questionnaire_responses.get('resp_1_h') or 'Grand Parent(s)',
                questionnaire_responses.get('resp_1_i') or 'Grand Parent(s)', questionnaire_responses.get('resp_1_j') or 'Grand Parent(s)',
                questionnaire_responses.get('resp_1_k') or 'Grand Parent(s)', questionnaire_responses.get('resp_2_a') or 'Yes',
                questionnaire_responses.get('resp_2_b') or 'Yes', questionnaire_responses.get('resp_2_c') or 'Yes',
                questionnaire_responses.get('resp_2_d') or 'Yes', questionnaire_responses.get('resp_2_e') or 'Yes',
                questionnaire_responses.get('resp_2_f') or 'Yes', questionnaire_responses.get('resp_2_g') or 'Yes',
                questionnaire_responses.get('resp_2_h') or 'Yes', questionnaire_responses.get('resp_2_i') or 'Yes',
                questionnaire_responses.get('resp_3_a') or 'Yes', questionnaire_responses.get('resp_3_b') or 'Yes',
                questionnaire_responses.get('resp_3_c') or 'Yes', questionnaire_responses.get('resp_3_d') or 'Yes',
                questionnaire_responses.get('resp_3_e') or 'Yes', questionnaire_responses.get('resp_3_f') or 'Yes',
                questionnaire_responses.get('resp_4_a') or 'Never', questionnaire_responses.get('resp_4_b') or 'Never',
                questionnaire_responses.get('resp_4_c') or 'Never', questionnaire_responses.get('resp_4_d') or 'Never',
                questionnaire_responses.get('resp_4_e') or 'Never', questionnaire_responses.get('resp_4_f') or 'Never',
                questionnaire_responses.get('resp_4_g') or 'Never', questionnaire_responses.get('resp_4_h') or 'Never',
                questionnaire_responses.get('resp_4_i') or 'Never', questionnaire_responses.get('resp_4_j') or 'Never',
                questionnaire_responses.get('resp_4_k') or 'Never', questionnaire_responses.get('resp_4_l') or 'Never',
                questionnaire_responses.get('resp_4_m') or 'Never', questionnaire_responses.get('resp_4_n') or 'Never',
                questionnaire_responses.get('resp_4_o') or 'Never', questionnaire_responses.get('resp_4_p') or 'Never',
                questionnaire_responses.get('resp_4_q') or 'Never', questionnaire_responses.get('resp_4_r') or 'Never',
                questionnaire_responses.get('resp_4_s') or 'Never', questionnaire_responses.get('resp_4_t') or 'Never',
                dt.datetime.now()
            ))
            conn.connection.commit()

        success_msg = dbc.Alert([
            html.H5(f"Thank you {enrollee_data['member_name']}."),
            html.P("Your annual wellness has been successfully booked."),
            html.Hr(),
            html.P(f"Please note that you have from now till {six_weeks} to complete your annual wellness exercise.", className='font-weight-bold'),
            html.Hr(),
            html.P("You will receive a confirmation email once the Contact Center has issued your PA code.")
        ], color="success", className="mb-0")

    except Exception as e:
        return True, dbc.Alert(f"An error occurred: {str(e)}", color="danger")

    return True, success_msg


# =============================================================================
# PROVIDER PORTAL — RENDER based on auth
# =============================================================================
@callback(
    Output("ps-main-content",    "children"),
    Input("auth-store",          "data"),
    prevent_initial_call=False,
)
def render_ps_layout(auth_data):
    if not auth_data or not auth_data.get("authenticated", False):
        return ps_login_layout

    u = auth_data.get("username", "")
    if u.startswith("234"):
        title = "Provider Wellness Result Submission Portal"
    elif u.startswith("claim"):
        title = "Provider Wellness Result Review Portal"
    elif u.startswith("contact"):
        title = "Wellness PA Code Authorisation and Results Review Portal"
    elif u in ["ClientServices", "MedicalServices"]:
        title = "Wellness Services Management Portal"
    else:
        return ps_login_layout

    return dbc.Container([
        dbc.Row([dbc.Col([
            html.Br(), html.Br(),
            html.H4(title, className="text-center", style={"color": "purple"}),
            html.Br(),
            dbc.Spinner(size="lg", color="primary", children=html.Div(style={"height": "60px"})),
            html.P("Loading portal data, please wait…", className="text-center text-muted mt-3"),
        ], width={"size": 4, "offset": 4})])
    ], fluid=True, style={"minHeight": "60vh", "paddingTop": "15vh"})


@callback(
    Output("auth-store",   "data"),
    Output("login-error",  "children"),
    Input("login-button",  "n_clicks"),
    State("login-username","value"),
    State("login-password","value"),
    prevent_initial_call=True,
)
def login(n_clicks, username_val, password_val):
    if n_clicks and username_val and password_val:
        user_name, providername, login_password = login_user(username_val, password_val)
        if user_name == username_val and password_val == login_password:
            return {"authenticated": True, "username": username_val, "providername": providername}, ""
        return dash.no_update, "Username/password is incorrect"
    return dash.no_update, ""


@callback(
    Output("store-q2",           "data"),
    Output("store-q3",           "data"),
    Output("store-q4",           "data"),
    Output("store-q5",           "data"),
    Output("data-ready-store-ps","data"),
    Input("auth-store",          "data"),
    prevent_initial_call=True,
)
def load_portal_data(auth_data):
    if not auth_data or not auth_data.get("authenticated"):
        return None, None, None, None, False
    q2 = cached_read_sql(query_ps_q2).to_dict('records')
    q3 = cached_read_sql(query_ps_q3).to_dict('records')
    q4 = cached_read_sql(query_ps_q4).to_dict('records')
    q5 = cached_read_sql(query_ps_q5).to_dict('records')
    return q2, q3, q4, q5, True


@callback(
    Output("ps-main-content",     "children", allow_duplicate=True),
    Output("services-view-store", "data",     allow_duplicate=True),
    Input("data-ready-store-ps",  "data"),
    State("auth-store",           "data"),
    prevent_initial_call=True,
)
def show_ps_portal(ready, auth_data):
    if not ready or not auth_data or not auth_data.get("authenticated"):
        return dash.no_update, dash.no_update
    u = auth_data.get("username", "")
    if u.startswith("234"):
        return ps_provider_layout, dash.no_update
    elif u.startswith("claim"):
        return ps_claims_layout, dash.no_update
    elif u.startswith("contact"):
        return ps_contact_layout, dash.no_update
    elif u == "ClientServices":
        return ps_services_layout, "plans"
    elif u == "MedicalServices":
        return ps_services_layout, "providers"
    return ps_login_layout, dash.no_update


@callback(
    Output("auth-store",    "data", allow_duplicate=True),
    Output("logout-redirect","data", allow_duplicate=True),
    Input("logout-btn",  "n_clicks"),
    prevent_initial_call=True,
)
def logout(n_clicks):
    if n_clicks:
        invalidate_cache()
        return {"authenticated": False, "username": None, "providername": None}, "/wellness/provider"
    return dash.no_update, dash.no_update


@callback(Output("provider-welcome", "children"), Input("auth-store", "data"), prevent_initial_call=False)
def update_provider_welcome(d):
    if not d or not d.get("authenticated"):
        return ""
    username = d.get("username", "")
    if username.startswith("234"):
        return f"Logged in as {d.get('providername','')}"
    return ""

@callback(Output("claims-welcome",  "children"), Input("auth-store", "data"), prevent_initial_call=False)
def update_claims_welcome(d):
    if not d or not d.get("authenticated"):
        return ""
    username = d.get("username", "")
    if username.startswith("claim"):
        return f"Logged in as {d.get('providername','')}"
    return ""

@callback(Output("contact-welcome", "children"), Input("auth-store", "data"), prevent_initial_call=False)
def update_contact_welcome(d):
    if not d or not d.get("authenticated"):
        return ""
    username = d.get("username", "")
    if username.startswith("contact"):
        return f"Logged in as Contact Center"
    return ""

@callback(Output("services-welcome","children"), Input("auth-store", "data"), prevent_initial_call=False)
def update_services_welcome(d):
    if not d or not d.get("authenticated"):
        return ""
    username = d.get("username", "")
    if username == "ClientServices":
        return "Logged in as Client Services"
    elif username == "MedicalServices":
        return "Logged in as Medical Services"
    return f"Logged in as {username}"


@callback(
    Output("provider-content",   "children"),
    Input("provider-nav-option", "value"),
    State("store-q2",  "data"),
    State("store-q4",  "data"),
    State("auth-store","data"),
)
def update_provider_content(option, q2_data, q4_data, auth_data):
    if not auth_data or not q2_data or not auth_data.get("username", "").startswith("234"):
        return ""
    filled_df = pd.DataFrame(q2_data)
    filled_df['ProviderName'] = filled_df['PA_Provider'].str.split('-').str[0].str.strip()
    filled_df['MemberNo']     = filled_df['MemberNo'].astype(str)
    result_df = pd.DataFrame(q4_data) if q4_data else pd.DataFrame(columns=['memberno'])
    if not result_df.empty:
        result_df['memberno'] = result_df['memberno'].astype(str)

    pn = auth_data.get("providername", "")
    if pn == 'CLINA LANCET LABOURATORIES':
        mask = filled_df['ProviderName'].str.contains('CERBA|UBA Head|CLINA', regex=True)
    elif 'ABACHA' in pn or 'DAMATURU' in pn:
        mask = filled_df['ProviderName'].str.contains('ABACHA')
    elif pn == 'ASHMED SPECIALIST':
        mask = filled_df['ProviderName'].str.contains('ASHMED', regex=False)
    else:
        mask = filled_df['ProviderName'] == pn

    pdf = filled_df[mask][['MemberNo', 'MemberName', 'IssuedPACode', 'PA_Tests']].copy()
    pdf['SubmissionStatus'] = pdf['MemberNo'].apply(
        lambda x: 'Submitted' if x in result_df['memberno'].values else 'Not Submitted'
    )
    pdf = pdf.sort_values('SubmissionStatus').reset_index(drop=True)

    if option == "view":
        submitted_count = (pdf['SubmissionStatus'] == 'Submitted').sum()
        not_submitted_count = (pdf['SubmissionStatus'] == 'Not Submitted').sum()
        return html.Div([
            html.H3("View Wellness Enrollees and Benefits"),
            dbc.Row([
                dbc.Col([dbc.Card([dbc.CardBody([
                    html.H5(f"{submitted_count}", className="card-title text-center", style={"fontSize": "36px", "color": "green"}),
                    html.P("Submitted", className="card-text text-center", style={"color": "green"})
                ])], style={"boxShadow": "0 4px 8px rgba(0,0,0,0.1)", "borderTop": "4px solid green"})], width=6),
                dbc.Col([dbc.Card([dbc.CardBody([
                    html.H5(f"{not_submitted_count}", className="card-title text-center", style={"fontSize": "36px", "color": "red"}),
                    html.P("Not Submitted", className="card-text text-center", style={"color": "red"})
                ])], style={"boxShadow": "0 4px 8px rgba(0,0,0,0.1)", "borderTop": "4px solid red"})], width=6),
            ], className="mb-3"),
            dash_table.DataTable(
                data=pdf.to_dict('records'),
                columns=[{"name": i, "id": i} for i in pdf.columns],
                style_header=PURPLE_TABLE_STYLE["style_header"],
                style_cell={**PURPLE_TABLE_STYLE["style_cell"], "fontFamily": "Arial"},
                style_data_conditional=PURPLE_TABLE_STYLE["style_data_conditional"] + [
                    {"if": {"filter_query": '{SubmissionStatus} = "Submitted"',     "column_id": "SubmissionStatus"}, "backgroundColor": "green", "color": "white"},
                    {"if": {"filter_query": '{SubmissionStatus} = "Not Submitted"', "column_id": "SubmissionStatus"}, "backgroundColor": "red",   "color": "white"},
                ],
                style_table={"overflowX": "auto"}, page_size=20,
            )
        ])
    else:
        ns = pdf[pdf['SubmissionStatus'] == 'Not Submitted'].copy()
        ns['member'] = ns['MemberNo'].str.cat(ns['MemberName'], sep=' - ')
        return html.Div([
            html.H3("Submit Wellness Results"),
            html.P("Please select the enrollee you would like to submit wellness results for"),
            dbc.Label("Select Enrollee"),
            dcc.Dropdown(id="member-select", options=ns['member'].unique().tolist(), placeholder="Select Enrollee"),
            html.Br(),
            html.Div(id="submission-form")
        ])


@callback(
    Output("submission-form", "children"),
    Input("member-select",    "value"),
    State("store-q2",         "data"),
    prevent_initial_call=True,
)
def show_submission_form(member, q2_data):
    if not member or not q2_data:
        return ""
    member_no = member.split(' - ')[0]
    df  = pd.DataFrame(q2_data)
    df['MemberNo'] = df['MemberNo'].astype(str)
    row = df[df['MemberNo'] == member_no].iloc[0]
    return html.Div([
        html.Br(),
        html.P(f"Submitting results for: {row['MemberName']}"),
        html.P(f"Policy End Date: {row['PolicyEndDate']}"),
        html.P("Please enter the PACode issued for the Enrollee Wellness Test"),
        dbc.Input(id="pa-code-input", type="text", placeholder="Enter PACode"),
        html.Br(),
        html.P("Please Select the Tests Conducted on the Enrollee"),
        dcc.Dropdown(id="tests-conducted", options=PA_TESTS_OPTIONS, multi=True, placeholder="Select all Tests Conducted"),
        html.Br(),
        html.P("Please Enter the Date the Tests were Conducted"),
        dcc.DatePickerSingle(id="test-date-picker", placeholder="Enter Test Date"),
        html.Br(),
        html.P("Upload Test Results"),
        dcc.Upload(
            id="upload-results",
            children=html.Div(['Drag and Drop or ', html.A('Select Files')]),
            style={'width': '100%', 'height': '60px', 'lineHeight': '60px', 'borderWidth': '1px',
                   'borderStyle': 'dashed', 'borderRadius': '5px', 'textAlign': 'center', 'margin': '10px'},
            multiple=True
        ),
        html.Br(),
        dbc.Button("Submit Results", id="submit-results-btn", color="success"),
        html.Div(id="ps-submission-message")
    ])


@callback(
    Output("ps-submission-message", "children"),
    Input("submit-results-btn",     "n_clicks"),
    State("member-select",          "value"),
    State("pa-code-input",          "value"),
    State("tests-conducted",        "value"),
    State("test-date-picker",       "date"),
    State("upload-results",         "filename"),
    State("upload-results",         "contents"),
    State("store-q2",               "data"),
    State("auth-store",             "data"),
    prevent_initial_call=True,
)
def submit_results(n_clicks, member, pa_code, tests_conducted, test_date,
                   uploaded_filenames, uploaded_contents, q2_data, auth_data):
    if not n_clicks or not member:
        return ""
    missing = [f for f, v in [('PA Code', pa_code), ('Tests Conducted', tests_conducted),
                               ('Test Date', test_date), ('Uploaded File', uploaded_filenames)] if not v]
    if missing:
        return dbc.Alert(f"Compulsory fields missing: {', '.join(missing)}", color="danger")

    member_no = member.split(' - ')[0]
    df = pd.DataFrame(q2_data)
    df['MemberNo'] = df['MemberNo'].astype(str)
    row    = df[df['MemberNo'] == member_no].iloc[0]
    ped    = row['PolicyEndDate']
    ped_str = ped.strftime("%Y-%m-%d") if hasattr(ped, 'strftime') else str(ped)
    pname  = auth_data.get("providername", "").replace(" ", "").lower()
    cname  = row['Client'].replace(" ", "").lower()
    folder = f"{pname}/{cname}/{ped_str}/{member_no}"

    bsc  = BlobServiceClient.from_connection_string(conn_str)
    cont = 'annual-wellness-results'
    uploaded_files = []
    for fn, fc in zip(uploaded_filenames or [], uploaded_contents or []):
        content_type, content_b64 = fc.split(',', 1)
        file_bytes = base64.b64decode(content_b64)
        blob_path  = f"{folder}/{member_no}_{fn}"
        bsc.get_blob_client(container=cont, blob=blob_path).upload_blob(file_bytes, overwrite=True)
        uploaded_files.append((fn, file_bytes))

    with engine.connect() as conn:
        conn.execute(
            text("""
                INSERT INTO demo_tbl_enrollee_wellness_result_data
                (memberno, membername, providername, pacode, tests_conducted, test_date, test_result_link, date_submitted)
                VALUES (:memberno, :membername, :providername, :pacode, :tests_conducted, :test_date, :test_result_link, GETDATE())
            """),
            {
                "memberno":        member_no,
                "membername":      row['MemberName'],
                "providername":    auth_data.get("providername", ""),
                "pacode":          pa_code,
                "tests_conducted": ', '.join(tests_conducted),
                "test_date":       test_date,
                "test_result_link": f"https://{bsc.account_name}.blob.core.windows.net/{cont}/{folder}"
            }
        )
        conn.commit()
    invalidate_cache()

    selected_date_str = row['selected_date'].strftime("%Y-%m-%d") if hasattr(row.get('selected_date'), 'strftime') else str(row.get('selected_date', ''))
    ok, msg = send_email_with_attachment(
        row['email'], row['MemberName'], auth_data.get("providername", ""),
        test_date, 'AVON HMO ANNUAL TEST RESULTS', uploaded_files,
        selected_date=selected_date_str,
        selected_provider=row.get('selected_provider'),
        wellness_benefits=row.get('Wellness_benefits')
    )
    return dbc.Alert("Results submitted. Email sent to enrollee.", color="success") \
           if ok else dbc.Alert(msg, color="danger")


@callback(
    Output("claims-provider-select", "options"),
    Input("data-ready-store-ps",     "data"),
    Input("auth-store",               "data"),
    State("store-q2",                "data"),
    prevent_initial_call=False,
)
def load_claims_providers(ready, auth_data, q2_data):
    if not ready or not q2_data:
        return []
    df = pd.DataFrame(q2_data)
    if 'selected_provider' not in df.columns:
        return []
    providers = df['selected_provider'].dropna().unique()
    return [{"label": p, "value": p} for p in sorted(providers)]


@callback(
    Output("claims-member-select", "options"),
    Input("claims-provider-select","value"),
    Input("data-ready-store-ps",   "data"),
    State("store-q2",              "data"),
    prevent_initial_call=False,
)
def load_claims_members(provider, ready, q2_data):
    if not q2_data:
        return []
    df = pd.DataFrame(q2_data)
    if 'selected_provider' not in df.columns or 'MemberNo' not in df.columns or 'MemberName' not in df.columns:
        return []
    df['MemberNo'] = df['MemberNo'].astype(str)
    df['member'] = df['MemberNo'].str.cat(df['MemberName'].astype(str), sep=' - ')
    if provider:
        filtered = df[df['selected_provider'] == provider]
    else:
        filtered = df
    return [{"label": m, "value": m} for m in filtered['member'].unique()]


@callback(
    Output("claims-policy-period-select", "options"),
    Input("claims-member-select",       "value"),
    Input("claims-provider-select",    "value"),
    Input("data-ready-store-ps",        "data"),
    State("store-q2",                   "data"),
    prevent_initial_call=False,
)
def load_claims_policy_periods(member, provider, ready, q2_data):
    if not q2_data:
        return []
    df = pd.DataFrame(q2_data)
    if 'PolicyStartDate' not in df.columns or 'PolicyEndDate' not in df.columns:
        return []
    df['MemberNo'] = df['MemberNo'].astype(str)
    if provider:
        df = df[df['selected_provider'] == provider]
    if member:
        member_id = member.split(' - ')[0]
        df = df[df['MemberNo'] == member_id]
    df = df.dropna(subset=['PolicyStartDate', 'PolicyEndDate'])
    if df.empty:
        return []
    periods = []
    for _, row in df.iterrows():
        start = row['PolicyStartDate']
        end = row['PolicyEndDate']
        if isinstance(start, str):
            start = pd.to_datetime(start, errors='coerce')
        if isinstance(end, str):
            end = pd.to_datetime(end, errors='coerce')
        if pd.notna(start) and pd.notna(end):
            label = f"{start.strftime('%Y-%m-%d')} to {end.strftime('%Y-%m-%d')}"
            value = f"{start.strftime('%Y-%m-%d')}|{end.strftime('%Y-%m-%d')}"
            periods.append({"label": label, "value": value})
    unique_periods = {p['value']: p for p in periods}.values()
    return sorted(unique_periods, key=lambda x: x['value'], reverse=True)


@callback(
    Output("claims-content",      "children"),
    Input("claims-member-select",       "value"),
    Input("claims-policy-period-select","value"),
    State("claims-provider-select",    "value"),
    State("store-q2",                  "data"),
    prevent_initial_call=True,
)
def show_claims_content(member, policy_period, provider, q2_data):
    if not member or not provider or not q2_data:
        return ""
    member_id = member.split(' - ')[0]
    df  = pd.DataFrame(q2_data)
    df['MemberNo'] = df['MemberNo'].astype(str)
    df = df[df['MemberNo'] == member_id]
    if policy_period:
        start_date, end_date = policy_period.split('|')
        df['PolicyStartDate'] = pd.to_datetime(df['PolicyStartDate'], errors='coerce')
        df['PolicyEndDate'] = pd.to_datetime(df['PolicyEndDate'], errors='coerce')
        df = df[(df['PolicyStartDate'].dt.strftime('%Y-%m-%d') == start_date) & 
                (df['PolicyEndDate'].dt.strftime('%Y-%m-%d') == end_date)]
    if df.empty:
        return html.Div("No records found for the selected criteria.", style={"color": "red"})
    row = df.sort_values('date_submitted', ascending=False).iloc[0]
    return html.Div([
        html.H3(f"Test Results for {member}", style={"color": "green"}),
        html.H4(f"Client: {row['Client']}",                                  style={"color": "purple"}),
        html.H4(f"PA Code Issued to Provider: {row['IssuedPACode']}",        style={"color": "purple"}),
        html.H4(f"Wellness Tests PA Code was Issued for: {row['PA_Tests']}", style={"color": "purple"}),
        html.Hr(),
        html.H4("Results:"),
        display_member_results(conn_str, 'annual-wellness-results',
                               provider, row['Client'], member_id, row['PolicyEndDate'])
    ])


@callback(
    Output("contact-content",      "children"),
    Input("contact-search-button", "n_clicks"),
    Input("data-ready-store-ps",   "data"),
    State("auth-store",            "data"),
    State("contact-enrollee-id",   "value"),
    State("store-q2",  "data"),
    State("store-q3",  "data"),
    State("store-q4",  "data"),
    prevent_initial_call=False,
)
def search_enrollee(n_clicks, data_ready, auth_data, enrollee_id, q2_data, q3_data, q4_data):
    if not auth_data or not auth_data.get("authenticated"):
        return ""
    if not auth_data.get("username", "").startswith("contact"):
        return ""
    if not data_ready or not q2_data:
        return ""

    filled_df = pd.DataFrame(q2_data)
    filled_df['MemberNo'] = filled_df['MemberNo'].astype(str)
    filled_df['selected_provider'] = filled_df['selected_provider'].fillna('')
    filled_df['IssuedPACode'] = filled_df['IssuedPACode'].fillna('')
    filled_df['PAIssueDate'] = filled_df['PAIssueDate'].fillna('')
    
    table_df = filled_df[['MemberName', 'MemberNo', 'Client', 'selected_provider', 'date_submitted', 'IssuedPACode', 'PAIssueDate']].copy()
    table_df = table_df.sort_values('IssuedPACode', ascending=True).reset_index(drop=True)
    table_df['date_submitted'] = pd.to_datetime(table_df['date_submitted'], format='mixed', errors='coerce').dt.strftime('%Y-%m-%d')
    table_df['PAIssueDate'] = table_df['PAIssueDate'].apply(lambda x: pd.to_datetime(x, format='mixed', errors='coerce').strftime('%Y-%m-%d') if pd.notna(x) and x else '')
    
    total_records = len(filled_df)
    records_with_pa = (filled_df['IssuedPACode'] != '').sum()
    records_without_pa = (filled_df['IssuedPACode'] == '').sum()

    cards_html = html.Div([
        html.H4("Wellness Enrollee Overview", style={"color": "#59058d", "marginBottom": "20px"}),
        dbc.Row([
            dbc.Col([dbc.Card([dbc.CardBody([
                html.H5(f"{total_records}", className="card-title text-center", style={"fontSize": "36px", "color": "#59058d"}),
                html.P("Total Enrollee Records", className="card-text text-center", style={"color": "#59058d"})
            ])], style={"boxShadow": "0 4px 8px rgba(0,0,0,0.1)", "borderTop": "4px solid #59058d"})], width=4),
            dbc.Col([dbc.Card([dbc.CardBody([
                html.H5(f"{records_with_pa}", className="card-title text-center", style={"fontSize": "36px", "color": "green"}),
                html.P("Records with PA Code", className="card-text text-center", style={"color": "green"})
            ])], style={"boxShadow": "0 4px 8px rgba(0,0,0,0.1)", "borderTop": "4px solid green"})], width=4),
            dbc.Col([dbc.Card([dbc.CardBody([
                html.H5(f"{records_without_pa}", className="card-title text-center", style={"fontSize": "36px", "color": "red"}),
                html.P("Records without PA Code", className="card-text text-center", style={"color": "red"})
            ])], style={"boxShadow": "0 4px 8px rgba(0,0,0,0.1)", "borderTop": "4px solid red"})], width=4),
        ], className="mb-4"),
        html.H5("All Enrollees", style={"color": "#59058d", "marginBottom": "10px"}),
        dash_table.DataTable(
            data=table_df.to_dict('records'),
            columns=[{"name": "Member Name", "id": "MemberName"}, {"name": "Member No", "id": "MemberNo"}, 
                     {"name": "Client Name", "id": "Client"}, {"name": "Provider", "id": "selected_provider"},
                     {"name": "Submitted Date", "id": "date_submitted"}, {"name": "Avon PA Code", "id": "IssuedPACode"},
                     {"name": "PA Issue Date", "id": "PAIssueDate"}],
            style_header=PURPLE_TABLE_STYLE["style_header"],
            style_cell=PURPLE_TABLE_STYLE["style_cell"],
            style_data_conditional=PURPLE_TABLE_STYLE["style_data_conditional"] + [
                {"if": {"filter_query": '{Avon PA Code} = ""', "column_id": "IssuedPACode"}, "backgroundColor": "#ffcccc", "color": "red"},
            ],
            style_table={"overflowX": "auto"}, page_size=20,
        )
    ])
    
    if not n_clicks or not enrollee_id:
        return cards_html

    enrollee_id = enrollee_id.strip()
    filled_df['ProviderName'] = filled_df['PA_Provider'].str.split('-').str[0].str.strip()
    filled_df['MemberNo']     = filled_df['MemberNo'].astype(str)

    result_df = pd.DataFrame(q4_data) if q4_data else pd.DataFrame(columns=['memberno'])
    if not result_df.empty:
        result_df['memberno'] = result_df['memberno'].astype(str)

    if enrollee_id in filled_df['MemberNo'].values:
        member_df = filled_df[filled_df['MemberNo'] == enrollee_id].copy()

        def get_policy_year(row):
            try:
                start = pd.to_datetime(row['PolicyStartDate'])
                end   = pd.to_datetime(row['PolicyEndDate'])
                return f"{start.strftime('%b/%Y')} - {end.strftime('%b/%Y')}"
            except:
                return "Unknown"

        member_df['policy_year'] = member_df.apply(get_policy_year, axis=1)
        policy_years = member_df['policy_year'].unique().tolist()
        policy_years_sorted = sorted(policy_years, key=lambda x: (x.split(' - ')[1] if ' - ' in x else '', x), reverse=True)

        current_year_options = [{'label': 'Current Policy Year', 'value': 'current'}] + \
                               [{'label': py, 'value': py} for py in policy_years_sorted]
        row = member_df[member_df['policy_year'] == policy_years_sorted[0]].iloc[0] if policy_years_sorted else member_df.iloc[0]

        res_row    = result_df[result_df['memberno'] == enrollee_id]
        has_result = not res_row.empty

        booking = member_df.loc[
            member_df['MemberNo'] == enrollee_id,
            ['MemberNo', 'MemberName', 'Client', 'Wellness_benefits', 'selected_provider',
             'date_submitted', 'IssuedPACode', 'PA_Tests', 'PA_Provider', 'PAIssueDate',
             'PolicyStartDate', 'PolicyEndDate']
        ].reset_index(drop=True).transpose()

        providers_df = pd.DataFrame(q3_data) if q3_data else pd.DataFrame(columns=['ProviderName'])
        prov_list    = sorted(set(
            providers_df['ProviderName'].dropna().unique().tolist() +
            ['MECURE HEALTHCARE, OSHODI', 'MECURE HEALTHCARE, LEKKI',
             'CLINIX HEALTHCARE', 'TEEKAY HOSPITAL LIMITED', 'KANEM HOSPITAL AND MATERNITY']
        ))

        table_rows = [
            html.Tr([html.Td(idx, style={'fontWeight': 'bold'}), html.Td(str(v[0]))])
            for idx, v in booking.iterrows()
        ]
        result_alert = (
            dbc.Alert(
                f"Wellness Results for {row['MemberName']} done by "
                f"{res_row['providername'].values[0]} submitted and sent to "
                f"{row['email']} on {res_row['date_submitted'].values[0]}",
                color="success"
            ) if has_result else
            dbc.Alert(
                f"Wellness Results for {row['MemberName']} not yet submitted. "
                "Please follow up with the provider.", color="danger"
            )
        )

        return html.Div([
            html.H4(f"Wellness Booking Details for {row['MemberName']}", style={"color": "purple"}),
            html.Label("Select Policy Year", style={"fontWeight": "bold", "color": "purple"}),
            dcc.Dropdown(id="contact-policy-year", options=current_year_options, value='current', clearable=False),
            html.Br(),
            html.H5("Booking Details", style={"color": "purple"}),
            html.Table(table_rows, style={'width': '100%', 'borderCollapse': 'collapse'}),
            html.Hr(),
            html.H4("Kindly Update Details of PA Code Issued to Provider for the Enrollee", style={"color": "purple"}),
            dbc.Label("Input the Generated PA Code"),
            dbc.Input(id="contact-pacode", type="text", placeholder="Enter PA Code", value=row.get('IssuedPACode', '')),
            html.Br(),
            dbc.Label("Select the Tests Conducted"),
            dcc.Dropdown(id="contact-pa-tests", options=PA_TESTS_OPTIONS, multi=True,
                         value=row.get('PA_Tests', '').split(',') if row.get('PA_Tests') else []),
            html.Br(),
            dbc.Label("Select the Wellness Provider"),
            dcc.Dropdown(id="contact-pa-provider",
                         options=[{'label': p, 'value': p} for p in prov_list],
                         placeholder="Select Provider", value=row.get('PA_Provider', '')),
            html.Br(),
            dbc.Label("Select the Date the PA was Issued"),
            dcc.DatePickerSingle(id="contact-pa-issue-date", placeholder="Select Date", date=row.get('PAIssueDate', None)),
            html.Br(),
            dbc.Button("PROCEED", id="contact-proceed-btn", color="primary"),
            html.Div(id="contact-pa-message"),
            html.Hr(),
            result_alert
        ])

    return dbc.Alert("Invalid Member ID or Enrollee not eligible for Wellness Test.", color="danger")


@callback(
    Output("contact-pacode",        "value"),
    Output("contact-pa-tests",      "value"),
    Output("contact-pa-provider",   "value"),
    Output("contact-pa-issue-date", "date"),
    Input("contact-policy-year",    "value"),
    State("contact-enrollee-id",    "value"),
    State("store-q2",               "data"),
    prevent_initial_call=True,
)
def update_form_on_policy_year(policy_year, enrollee_id, q2_data):
    if not enrollee_id or not q2_data or not policy_year:
        return dash.no_update, dash.no_update, dash.no_update, dash.no_update

    df = pd.DataFrame(q2_data)
    df['MemberNo'] = df['MemberNo'].astype(str)

    def get_py_str(row):
        try:
            return f"{pd.to_datetime(row['PolicyStartDate']).strftime('%b/%Y')} - {pd.to_datetime(row['PolicyEndDate']).strftime('%b/%Y')}"
        except:
            return "Unknown"

    df['policy_year_str'] = df.apply(get_py_str, axis=1)
    member_df = df[df['MemberNo'] == enrollee_id]

    if policy_year == 'current':
        target_df = member_df.sort_values('date_submitted', ascending=False).head(1)
    else:
        target_df = member_df[member_df['policy_year_str'] == policy_year]

    if target_df.empty:
        return "", [], "", None

    row = target_df.iloc[0]
    pa_tests_value = [t.strip() for t in row.get('PA_Tests', '').split(',') if t.strip()] if row.get('PA_Tests') else []
    return (row.get('IssuedPACode', ''), pa_tests_value, row.get('PA_Provider', ''), row.get('PAIssueDate', None))


@callback(
    Output("contact-pa-message",   "children"),
    Input("contact-proceed-btn",   "n_clicks"),
    State("contact-enrollee-id",   "value"),
    State("contact-policy-year",   "value"),
    State("contact-pacode",        "value"),
    State("contact-pa-tests",      "value"),
    State("contact-pa-provider",   "value"),
    State("contact-pa-issue-date", "date"),
    State("store-q2",              "data"),
    State("auth-store",            "data"),
    prevent_initial_call=True,
)
def update_pa_code(n_clicks, enrollee_id, policy_year, pacode, pa_tests, pa_provider,
                   pa_issue_date, q2_data, auth_data):
    if not auth_data or not auth_data.get("authenticated"):
        return ""
    if not auth_data.get("username", "").startswith("contact") or not n_clicks:
        return ""
    missing = [f for f, v in [('PA Code', pacode), ('Tests Conducted', pa_tests), ('Provider', pa_provider)] if not v]
    if missing:
        return dbc.Alert(f"Please fill: {', '.join(missing)}", color="danger")

    df = pd.DataFrame(q2_data) if q2_data else pd.DataFrame()
    df['MemberNo'] = df['MemberNo'].astype(str)

    def get_py_str(row):
        try:
            return f"{pd.to_datetime(row['PolicyStartDate']).strftime('%b/%Y')} - {pd.to_datetime(row['PolicyEndDate']).strftime('%b/%Y')}"
        except:
            return "Unknown"

    df['policy_year_str'] = df.apply(get_py_str, axis=1)
    member_df  = df[df['MemberNo'] == enrollee_id]
    target_row = (member_df.sort_values('date_submitted', ascending=False).iloc[0]
                  if policy_year == 'current'
                  else member_df[member_df['policy_year_str'] == policy_year].iloc[0])

    date_submitted = target_row['date_submitted']
    try:
        if isinstance(date_submitted, dt.datetime):
            date_submitted = date_submitted
        elif isinstance(date_submitted, pd.Timestamp):
            date_submitted = date_submitted.to_pydatetime()
        elif isinstance(date_submitted, str):
            date_submitted = pd.to_datetime(date_submitted).to_pydatetime()
    except Exception as e:
        return dbc.Alert(f"Error parsing date: {e}", color="danger")
    
    conn = engine.raw_connection()
    try:
        cursor = conn.cursor()
        if pa_issue_date:
            cursor.execute("""
                UPDATE demo_tbl_annual_wellness_enrollee_data
                SET IssuedPACode = ?, PA_Tests = ?, PA_Provider = ?, PAIssueDate = ?
                WHERE MemberNo = ? AND date_submitted = ?
            """, (pacode, ','.join(pa_tests) if isinstance(pa_tests, list) else pa_tests, pa_provider, pa_issue_date, enrollee_id, date_submitted))
        else:
            cursor.execute("""
                UPDATE demo_tbl_annual_wellness_enrollee_data
                SET IssuedPACode = ?, PA_Tests = ?, PA_Provider = ?, PAIssueDate = NULL
                WHERE MemberNo = ? AND date_submitted = ?
            """, (pacode, ','.join(pa_tests) if isinstance(pa_tests, list) else pa_tests, pa_provider, enrollee_id, date_submitted))
        conn.commit()
        cursor.close()
    finally:
        conn.close()
    
    invalidate_cache()

    if policy_year == 'current':
        ok, msg = send_pa_code_email(
            target_row.get('email', ''), target_row.get('MemberName', ''),
            target_row.get('selected_date', ''), target_row.get('selected_provider', ''),
            target_row.get('Wellness_benefits', '')
        )
        if ok:
            return dbc.Alert("PA Code successfully updated for the enrollee. Scheduling email sent.", color="success")
        else:
            return dbc.Alert(f"PA Code updated but email failed: {msg}", color="warning")
    else:
        return dbc.Alert(f"PA Code successfully updated for the enrollee for policy year {policy_year}.", color="success")


@callback(
    Output("services-view-store", "data"),
    Input("services-view-providers-btn", "n_clicks"),
    Input("services-view-plans-btn",     "n_clicks"),
    prevent_initial_call=True,
)
def services_navigation(providers_clicks, plans_clicks):
    ctx = dash.callback_context
    if not ctx.triggered:
        return dash.no_update
    btn = ctx.triggered[0]['prop_id'].split('.')[0]
    return "plans" if btn == "services-view-plans-btn" else "providers"


@callback(
    Output("services-sidebar",   "children"),
    Input("services-view-store", "data"),
    State("auth-store",          "data"),
    prevent_initial_call=True,
)
def render_services_sidebar(view, auth_data):
    return html.Div()  # No sidebar for ClientServices and MedicalServices


@callback(
    Output("services-state-dropdown","options"),
    Input("data-ready-store-ps",     "data"),
    State("store-q3",                "data"),
    prevent_initial_call=True,
)
def populate_state_filter(ready, q3_data):
    if not ready or not q3_data:
        return []
    df = pd.DataFrame(q3_data)
    if 'STATE' not in df.columns:
        return []
    return [{"label": s, "value": s} for s in sorted(df['STATE'].dropna().unique())]


@callback(
    Output("services-state", "options"),
    Input("services-view-store", "data"),
    State("store-q3", "data"),
)
def populate_services_state_dropdown(view, q3_data):
    if not q3_data:
        return []
    df = pd.DataFrame(q3_data)
    if 'STATE' not in df.columns:
        return []
    return [{"label": s, "value": s} for s in sorted(df['STATE'].dropna().unique())]


@callback(Output("services-state-filter",         "data"), Input("services-state-dropdown",     "value"), prevent_initial_call=True)
def update_state_filter(v):         return v

@callback(Output("services-provider-name-filter", "data"), Input("services-provider-name-input","value"), prevent_initial_call=True)
def update_provider_name_filter(v): return v if v else None

@callback(Output("services-plan-type-filter",     "data"), Input("services-plan-type-dropdown",  "value"), prevent_initial_call=True)
def update_plan_type_filter(v):     return v

@callback(Output("services-client-name-filter",   "data"), Input("services-client-name-input",   "value"), prevent_initial_call=True)
def update_client_name_filter(v):   return v if v else None


@callback(
    Output("services-content",             "children"),
    Input("services-view-store",           "data"),
    Input("data-ready-store-ps",           "data"),
    Input("services-state-filter",         "data"),
    Input("services-provider-name-filter", "data"),
    Input("services-plan-type-filter",     "data"),
    Input("services-client-name-filter",   "data"),
    State("store-q3",  "data"),
    State("store-q5",  "data"),
    State("auth-store","data"),
    prevent_initial_call=True,
)
def view_providers(view, ready, state_filter, provider_name_filter, plan_type_filter,
                   client_name_filter, q3_data, q5_data, auth_data):
    if not auth_data or not auth_data.get("authenticated"):
        return ""
    username = auth_data.get("username", "")
    if username == "MedicalServices":
        view = "providers"
    elif username == "ClientServices":
        view = "plans"
    else:
        return ""
    if not ready:
        return ""
    if not view:
        view = "providers"

    if view == "plans":
        if not q5_data:
            return dbc.Alert("No plan data available.", color="warning")
        df = pd.DataFrame(q5_data)
        if plan_type_filter:
            df = df[df['CLIENT_PLAN'] == plan_type_filter]
        if client_name_filter:
            df = df[df['CLIENT_NAME'].str.contains(client_name_filter, case=False, na=False)]
        
        return html.Div([
            html.H4("Wellness Plans & Benefits", style={"color": "purple"}),
            html.P(f"Showing {len(df)} plan(s)", style={"color": "gray"}),
            html.Div([
                html.Div([
                    html.Label("Plan Type", style={"fontWeight": "bold", "display": "block"}),
                    dcc.Dropdown(id="services-plan-type-dropdown",
                        options=[{"label": p, "value": p} for p in sorted(pd.DataFrame(q5_data)['CLIENT_PLAN'].dropna().unique())] if q5_data else [],
                        value=plan_type_filter, placeholder="Select Plan Type", clearable=True, style={"width": "200px"}),
                ], style={"display": "inline-block", "marginRight": "20px", "verticalAlign": "top"}),
                html.Div([
                    html.Label("Client Name", style={"fontWeight": "bold", "display": "block"}),
                    dcc.Input(id="services-client-name-input", type="text", placeholder="Search Client Name...",
                              value=client_name_filter or "", debounce=True, style={"width": "200px"}),
                ], style={"display": "inline-block", "verticalAlign": "top"}),
            ], style={"marginBottom": "20px"}),
            html.Div([
                dbc.Button("Add Plan", id="plans-add-btn", color="success", className="me-2"),
                dbc.Button("Edit Selected", id="plans-edit-btn", color="warning", className="me-2"),
                dbc.Button("Delete Selected", id="plans-delete-btn", color="danger", className="me-2"),
            ], className="mb-2"),
            html.Div(id="plans-delete-message"),
            html.Div(id="plans-save-message"),
            dash_table.DataTable(
                data=df.to_dict('records'),
                columns=[{"name": i, "id": i} for i in df.columns],
                style_header=PURPLE_TABLE_STYLE["style_header"],
                style_cell=PURPLE_TABLE_STYLE["style_cell"],
                style_data_conditional=PURPLE_TABLE_STYLE["style_data_conditional"],
                style_table={"overflowX": "auto"}, page_size=20,
                id="services-plans-table", row_selectable="single"
            ),
            dbc.Modal([
                dbc.ModalHeader("Add New Wellness Plan"),
                dbc.ModalBody([
                    dbc.Row([dbc.Col([dbc.Label("Client Name"), dbc.Input(id="plans-client-name", type="text", placeholder="Enter Client Name")])]),
                    dbc.Row([dbc.Col([dbc.Label("Policy No"), dbc.Input(id="plans-policy-no", type="text", placeholder="Enter Policy No")])]),
                    dbc.Row([dbc.Col([dbc.Label("Client Plan"), dbc.Input(id="plans-client-plan", type="text", placeholder="Enter Client Plan")])]),
                    dbc.Row([dbc.Col([dbc.Label("Customization"), dbc.Input(id="plans-customization", type="text", placeholder="Enter Customization")])]),
                    dbc.Row([dbc.Col([dbc.Label("Wellness Benefits"), dbc.Textarea(id="plans-wellness-benefits", placeholder="Enter Wellness Benefits", style={"minHeight": "100px"})])]),
                ]),
                dbc.ModalFooter([
                    dbc.Button("Submit", id="plans-submit-btn", color="primary"),
                    dbc.Button("Close", id="plans-close-btn", color="secondary", className="ms-2"),
                ]),
            ], id="plans-modal", is_open=False),
            dbc.Modal([
                dbc.ModalHeader("Edit Wellness Plan"),
                dbc.ModalBody([
                    dbc.Row([dbc.Col([dbc.Label("Policy No (Read-only)"), dbc.Input(id="plans-edit-policy-no", type="text", disabled=True)])]),
                    dbc.Row([dbc.Col([dbc.Label("Client Name"), dbc.Input(id="plans-edit-client-name", type="text", placeholder="Enter Client Name")])]),
                    dbc.Row([dbc.Col([dbc.Label("Client Plan"), dbc.Input(id="plans-edit-client-plan", type="text", placeholder="Enter Client Plan")])]),
                    dbc.Row([dbc.Col([dbc.Label("Customization"), dbc.Input(id="plans-edit-customization", type="text", placeholder="Enter Customization")])]),
                    dbc.Row([dbc.Col([dbc.Label("Wellness Benefits"), dbc.Textarea(id="plans-edit-wellness-benefits", placeholder="Enter Wellness Benefits", style={"minHeight": "100px"})])]),
                ]),
                dbc.ModalFooter([
                    dbc.Button("Save", id="plans-edit-save-btn", color="primary"),
                    dbc.Button("Close", id="plans-edit-close-btn", color="secondary", className="ms-2"),
                ]),
            ], id="plans-edit-modal", is_open=False),
            html.Div(id="plans-edit-message"),
            html.Div(id="plans-add-message"),
        ])
    else:
        if not q3_data:
            return dbc.Alert("No provider data available.", color="warning")
        df = pd.DataFrame(q3_data)
        if state_filter:
            df = df[df['STATE'] == state_filter]
        if provider_name_filter:
            df = df[df['PROVIDER_NAME'].str.contains(provider_name_filter, case=False, na=False)]
        
        return html.Div([
            html.H4("Wellness Providers", style={"color": "purple"}),
            html.P(f"Showing {len(df)} provider(s)" + (f" in {state_filter}" if state_filter else ""), style={"color": "gray"}),
            html.Div([
                html.Div([
                    html.Label("State", style={"fontWeight": "bold", "display": "block"}),
                    dcc.Dropdown(id="services-state-dropdown",
                        options=[{"label": s, "value": s} for s in sorted(pd.DataFrame(q3_data)['STATE'].dropna().unique())] if q3_data else [],
                        value=state_filter, placeholder="Select State", clearable=True, style={"width": "200px"}),
                ], style={"display": "inline-block", "marginRight": "20px", "verticalAlign": "top"}),
                html.Div([
                    html.Label("Provider Name", style={"fontWeight": "bold", "display": "block"}),
                    dcc.Input(id="services-provider-name-input", type="text", placeholder="Search Provider Name...",
                              value=provider_name_filter or "", debounce=True, style={"width": "200px"}),
                ], style={"display": "inline-block", "verticalAlign": "top"}),
            ], style={"marginBottom": "20px"}),
            html.Div([
                dbc.Button("Add Provider", id="services-add-btn", color="success", className="me-2"),
                dbc.Button("Edit Selected", id="services-edit-btn", color="warning", className="me-2"),
                dbc.Button("Delete Selected", id="services-delete-btn", color="danger", className="me-2"),
            ], className="mb-2"),
            html.Div(id="services-delete-message"),
            html.Div(id="services-save-message"),
            dash_table.DataTable(
                data=df.to_dict('records'),
                columns=[{"name": i, "id": i} for i in df.columns],
                style_header=PURPLE_TABLE_STYLE["style_header"],
                style_cell=PURPLE_TABLE_STYLE["style_cell"],
                style_data_conditional=PURPLE_TABLE_STYLE["style_data_conditional"],
                style_table={"overflowX": "auto"}, page_size=20,
                id="services-providers-table", row_selectable="single"
            ),
            dbc.Modal([
                dbc.ModalHeader("Add New Provider"),
                dbc.ModalBody([
                    dbc.Row([dbc.Col([dbc.Label("Code"), dbc.Input(id="services-code", type="text", placeholder="Enter Code")])]),
                    dbc.Row([dbc.Col([dbc.Label("State"), dcc.Dropdown(id="services-state", options=[{"label": s, "value": s} for s in sorted(pd.DataFrame(q3_data)['STATE'].dropna().unique())] if q3_data else [], placeholder="Select State")])]),
                    dbc.Row([dbc.Col([dbc.Label("Provider Name"), dbc.Input(id="services-provider-name", type="text", placeholder="Enter Provider Name")])]),
                    dbc.Row([dbc.Col([dbc.Label("Address"), dbc.Input(id="services-address", type="text", placeholder="Enter Address")])]),
                    dbc.Row([dbc.Col([dbc.Label("Location"), dbc.Input(id="services-location", type="text", placeholder="Enter Location")])]),
                    dbc.Row([dbc.Col([dbc.Label("Provider (Auto-filled)"), dbc.Input(id="services-provider", type="text", placeholder="Auto-filled from Name + Location", disabled=True)])]),
                ]),
                dbc.ModalFooter([
                    dbc.Button("Submit", id="services-submit-btn", color="primary"),
                    dbc.Button("Close", id="services-close-btn", color="secondary", className="ms-2"),
                ]),
            ], id="services-modal", is_open=False),
            dbc.Modal([
                dbc.ModalHeader("Edit Provider"),
                dbc.ModalBody([
                    dbc.Row([dbc.Col([dbc.Label("Code (Read-only)"), dbc.Input(id="services-edit-code", type="text", disabled=True)])]),
                    dbc.Row([dbc.Col([dbc.Label("State"), dcc.Dropdown(id="services-edit-state", options=[{"label": s, "value": s} for s in sorted(pd.DataFrame(q3_data)['STATE'].dropna().unique())] if q3_data else [], placeholder="Select State")])]),
                    dbc.Row([dbc.Col([dbc.Label("Provider Name"), dbc.Input(id="services-edit-provider-name", type="text", placeholder="Enter Provider Name")])]),
                    dbc.Row([dbc.Col([dbc.Label("Address"), dbc.Input(id="services-edit-address", type="text", placeholder="Enter Address")])]),
                    dbc.Row([dbc.Col([dbc.Label("Location"), dbc.Input(id="services-edit-location", type="text", placeholder="Enter Location")])]),
                    dbc.Row([dbc.Col([dbc.Label("Provider (Auto-filled)"), dbc.Input(id="services-edit-provider", type="text", placeholder="Auto-filled from Name + Location", disabled=True)])]),
                ]),
                dbc.ModalFooter([
                    dbc.Button("Save", id="services-edit-save-btn", color="primary"),
                    dbc.Button("Close", id="services-edit-close-btn", color="secondary", className="ms-2"),
                ]),
            ], id="services-edit-modal", is_open=False),
            html.Div(id="services-edit-message"),
            html.Div(id="services-add-message"),
        ])


@callback(
    Output("services-provider", "value"),
    Input("services-provider-name", "value"),
    Input("services-location", "value"),
    prevent_initial_call=True,
)
def auto_fill_provider(provider_name, location):
    if provider_name and location:
        return f"{provider_name} - {location}"
    elif provider_name:
        return provider_name
    return ""


@callback(
    Output("services-edit-provider", "value", allow_duplicate=True),
    Input("services-edit-provider-name", "value"),
    Input("services-edit-location", "value"),
    prevent_initial_call=True,
)
def auto_fill_edit_provider(provider_name, location):
    if provider_name and location:
        return f"{provider_name} - {location}"
    elif provider_name:
        return provider_name
    return ""


@callback(
    Output("services-add-message","children"),
    Input("services-submit-btn",  "n_clicks"),
    State("services-code",        "value"),
    State("services-state",       "value"),
    State("services-provider-name","value"),
    State("services-address",     "value"),
    State("services-provider",    "value"),
    State("services-location",    "value"),
    State("auth-store",           "data"),
    prevent_initial_call=True,
)
def add_provider(n_clicks, code, state, provider_name, address, provider, location, auth_data):
    if not auth_data or not auth_data.get("authenticated"):
        return ""
    if auth_data.get("username", "") != "MedicalServices" or not n_clicks:
        return ""
    missing = [f for f, v in [('Code', code), ('State', state), ('Provider Name', provider_name),
                               ('Address', address), ('Provider', provider), ('Location', location)] if not v]
    if missing:
        return dbc.Alert(f"Please fill: {', '.join(missing)}", color="danger")
    try:
        conn = engine.raw_connection()
        try:
            cursor = conn.cursor()
            new_values = {
                "CODE": code,
                "STATE": state,
                "PROVIDER_NAME": provider_name,
                "ADDRESS": address,
                "PROVIDER": provider,
                "Location": location
            }
            _log_audit(conn, "demo_Updated_Wellness_Providers", "INSERT", code, auth_data.get("username"), None, new_values)
            cursor.execute("INSERT INTO demo_Updated_Wellness_Providers (CODE, STATE, PROVIDER_NAME, ADDRESS, PROVIDER, Location) VALUES (?, ?, ?, ?, ?, ?)",
                (code, state, provider_name, address, provider, location))
            conn.commit()
            cursor.close()
        finally:
            conn.close()
        invalidate_cache()
        return dbc.Alert("Provider added successfully!", color="success")
    except Exception as e:
        return dbc.Alert(f"Error adding provider: {e}", color="danger")


@callback(
    Output("services-modal", "is_open"),
    Input("services-add-btn", "n_clicks"),
    Input("services-submit-btn", "n_clicks"),
    Input("services-close-btn", "n_clicks"),
    State("services-modal", "is_open"),
    prevent_initial_call=True,
)
def toggle_services_modal(add_clicks, submit_clicks, close_clicks, is_open):
    ctx = callback_context
    if not ctx.triggered:
        return is_open
    trigger_id = ctx.triggered[0]['prop_id'].split('.')[0]
    if trigger_id == "services-add-btn":
        return True
    elif trigger_id in ["services-submit-btn", "services-close-btn"]:
        return False
    return is_open


@callback(
    Output("plans-modal", "is_open"),
    Input("plans-add-btn", "n_clicks"),
    Input("plans-submit-btn", "n_clicks"),
    Input("plans-close-btn", "n_clicks"),
    State("plans-modal", "is_open"),
    prevent_initial_call=True,
)
def toggle_plans_modal(add_clicks, submit_clicks, close_clicks, is_open):
    ctx = callback_context
    if not ctx.triggered:
        return is_open
    trigger_id = ctx.triggered[0]['prop_id'].split('.')[0]
    if trigger_id == "plans-add-btn":
        return True
    elif trigger_id in ["plans-submit-btn", "plans-close-btn"]:
        return False
    return is_open


@callback(
    Output("services-save-message",   "children"),
    Input("services-save-btn",        "n_clicks"),
    State("services-providers-table", "data"),
    State("auth-store",               "data"),
    prevent_initial_call=True,
)
def save_providers(n_clicks, table_data, auth_data):
    if not auth_data or not auth_data.get("authenticated"):
        return ""
    if auth_data.get("username", "") != "MedicalServices" or not n_clicks or not table_data:
        return ""
    try:
        conn = engine.raw_connection()
        try:
            cursor = conn.cursor()
            for row in table_data:
                code = row.get('CODE')
                if code:
                    cursor.execute("SELECT STATE, PROVIDER_NAME, ADDRESS, PROVIDER, Location FROM demo_Updated_Wellness_Providers WHERE CODE=?", (code,))
                    old_row = cursor.fetchone()
                    
                    old_state = old_row[0] if old_row else None
                    old_provider_name = old_row[1] if old_row else None
                    old_address = old_row[2] if old_row else None
                    old_provider = old_row[3] if old_row else None
                    old_location = old_row[4] if old_row else None
                    
                    new_state = row.get('STATE')
                    new_provider_name = row.get('PROVIDER_NAME')
                    new_address = row.get('ADDRESS')
                    new_provider = row.get('PROVIDER')
                    new_location = row.get('Location')
                    
                    if (old_state or '') != (new_state or ''):
                        cursor.execute("INSERT INTO WellnessPortalAuditTrail (ModuleName, ModifiedBy, FieldChangedName, PreviousValue, NewValue) VALUES (?, ?, ?, ?, ?)", 
                            ("MedicalServices", "MedicalServices", "STATE", old_state, new_state))
                    if (old_provider_name or '') != (new_provider_name or ''):
                        cursor.execute("INSERT INTO WellnessPortalAuditTrail (ModuleName, ModifiedBy, FieldChangedName, PreviousValue, NewValue) VALUES (?, ?, ?, ?, ?)", 
                            ("MedicalServices", "MedicalServices", "PROVIDER_NAME", old_provider_name, new_provider_name))
                    if (old_address or '') != (new_address or ''):
                        cursor.execute("INSERT INTO WellnessPortalAuditTrail (ModuleName, ModifiedBy, FieldChangedName, PreviousValue, NewValue) VALUES (?, ?, ?, ?, ?)", 
                            ("MedicalServices", "MedicalServices", "ADDRESS", old_address, new_address))
                    if (old_provider or '') != (new_provider or ''):
                        cursor.execute("INSERT INTO WellnessPortalAuditTrail (ModuleName, ModifiedBy, FieldChangedName, PreviousValue, NewValue) VALUES (?, ?, ?, ?, ?)", 
                            ("MedicalServices", "MedicalServices", "PROVIDER", old_provider, new_provider))
                    if (old_location or '') != (new_location or ''):
                        cursor.execute("INSERT INTO WellnessPortalAuditTrail (ModuleName, ModifiedBy, FieldChangedName, PreviousValue, NewValue) VALUES (?, ?, ?, ?, ?)", 
                            ("MedicalServices", "MedicalServices", "Location", old_location, new_location))
                    
                    cursor.execute("UPDATE demo_Updated_Wellness_Providers SET STATE=?, PROVIDER_NAME=?, ADDRESS=?, PROVIDER=?, Location=? WHERE CODE=?", 
                        (new_state, new_provider_name, new_address, new_provider, new_location, code))
            conn.commit()
            cursor.close()
        finally:
            conn.close()
        
        invalidate_cache()
        return dbc.Alert("Changes saved successfully!", color="success")
    except Exception as e:
        return dbc.Alert(f"Error saving changes: {e}", color="danger")


@callback(
    Output("services-delete-message",  "children"),
    Input("services-delete-btn",       "n_clicks"),
    State("services-providers-table",  "selected_rows"),
    State("services-providers-table",  "data"),
    State("auth-store",                "data"),
    prevent_initial_call=True,
)
def delete_providers(n_clicks, selected_rows, table_data, auth_data):
    if not auth_data or not auth_data.get("authenticated"):
        return ""
    if auth_data.get("username", "") != "MedicalServices" or not n_clicks or not selected_rows or not table_data:
        return ""
    try:
        conn = engine.raw_connection()
        try:
            cursor = conn.cursor()
            for idx in selected_rows:
                row = table_data[idx]
                code = row.get('CODE')
                if code:
                    old_values = {
                        "CODE": code,
                        "STATE": row.get('STATE'),
                        "PROVIDER_NAME": row.get('PROVIDER_NAME'),
                        "ADDRESS": row.get('ADDRESS'),
                        "PROVIDER": row.get('PROVIDER'),
                        "Location": row.get('Location')
                    }
                    _log_audit(conn, "demo_Updated_Wellness_Providers", "DELETE", code, auth_data.get("username"), old_values, None)
                    cursor.execute("DELETE FROM demo_Updated_Wellness_Providers WHERE CODE=?", (code,))
            conn.commit()
            cursor.close()
        finally:
            conn.close()
        invalidate_cache()
        return dbc.Alert("Selected provider(s) deleted successfully!", color="success")
    except Exception as e:
        return dbc.Alert(f"Error deleting provider(s): {e}", color="danger")


@callback(
    Output("services-edit-modal", "is_open"),
    Output("services-edit-code", "value"),
    Output("services-edit-state", "value"),
    Output("services-edit-provider-name", "value"),
    Output("services-edit-address", "value"),
    Output("services-edit-location", "value"),
    Output("services-edit-provider", "value"),
    Input("services-edit-btn", "n_clicks"),
    State("services-providers-table", "selected_rows"),
    State("services-providers-table", "data"),
    prevent_initial_call=True,
)
def open_edit_provider_modal(n_clicks, selected_rows, table_data):
    if not n_clicks or not selected_rows or not table_data:
        return False, "", None, "", "", "", ""
    idx = selected_rows[0]
    row = table_data[idx]
    return True, row.get('CODE', ''), row.get('STATE'), row.get('PROVIDER_NAME', ''), row.get('ADDRESS', ''), row.get('Location', ''), row.get('PROVIDER', '')


@callback(
    Output("services-edit-message", "children", allow_duplicate=True),
    Input("services-edit-save-btn", "n_clicks"),
    State("services-edit-code", "value"),
    State("services-edit-state", "value"),
    State("services-edit-provider-name", "value"),
    State("services-edit-address", "value"),
    State("services-edit-provider", "value"),
    State("services-edit-location", "value"),
    State("auth-store", "data"),
    prevent_initial_call=True,
)
def save_edit_provider(n_clicks, code, state, provider_name, address, provider, location, auth_data):
    if not auth_data or not auth_data.get("authenticated"):
        return ""
    if auth_data.get("username", "") != "MedicalServices" or not n_clicks or not code:
        return ""
    try:
        conn = engine.raw_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT STATE, PROVIDER_NAME, ADDRESS, PROVIDER, Location FROM demo_Updated_Wellness_Providers WHERE CODE=?", (code,))
            old_row = cursor.fetchone()
            old_values = {
                "STATE": old_row[0] if old_row else None,
                "PROVIDER_NAME": old_row[1] if old_row else None,
                "ADDRESS": old_row[2] if old_row else None,
                "PROVIDER": old_row[3] if old_row else None,
                "Location": old_row[4] if old_row else None
            }
            new_values = {
                "STATE": state,
                "PROVIDER_NAME": provider_name,
                "ADDRESS": address,
                "PROVIDER": provider,
                "Location": location
            }
            _log_audit(conn, "demo_Updated_Wellness_Providers", "UPDATE", code, auth_data.get("username"), old_values, new_values)
            cursor.execute("UPDATE demo_Updated_Wellness_Providers SET STATE=?, PROVIDER_NAME=?, ADDRESS=?, PROVIDER=?, Location=? WHERE CODE=?", 
                (state, provider_name, address, provider, location, code))
            conn.commit()
            cursor.close()
        finally:
            conn.close()
        invalidate_cache()
        return dbc.Alert("Provider updated successfully!", color="success")
    except Exception as e:
        return dbc.Alert(f"Error updating provider: {e}", color="danger")


@callback(
    Output("services-edit-modal", "is_open", allow_duplicate=True),
    Input("services-edit-close-btn", "n_clicks"),
    prevent_initial_call=True,
)
def close_edit_provider_modal(n_clicks):
    return False


@callback(
    Output("plans-add-message", "children"),
    Input("plans-submit-btn",   "n_clicks"),
    State("plans-client-name",       "value"),
    State("plans-policy-no",         "value"),
    State("plans-client-plan",       "value"),
    State("plans-customization",     "value"),
    State("plans-wellness-benefits", "value"),
    State("auth-store",              "data"),
    prevent_initial_call=True,
)
def add_plan(n_clicks, client_name, policy_no, client_plan, customization, wellness_benefits, auth_data):
    if not auth_data or not auth_data.get("authenticated"):
        return ""
    if auth_data.get("username", "") != "ClientServices" or not n_clicks:
        return ""
    missing = [f for f, v in [('Client Name', client_name), ('Policy No', policy_no),
                               ('Client Plan', client_plan), ('Customization', customization),
                               ('Wellness Benefits', wellness_benefits)] if not v]
    if missing:
        return dbc.Alert(f"Please fill: {', '.join(missing)}", color="danger")
    try:
        conn = engine.raw_connection()
        try:
            cursor = conn.cursor()
            new_values = {
                "CLIENT_NAME": client_name,
                "PolicyNo": policy_no,
                "CLIENT_PLAN": client_plan,
                "CUSTOMIZATION": customization,
                "WELLNESS_BENEFITS": wellness_benefits
            }
            _log_audit(conn, "demo_Wellness_Plans_and_Benefits", "INSERT", policy_no, auth_data.get("username"), None, new_values)
            cursor.execute("INSERT INTO demo_Wellness_Plans_and_Benefits (CLIENT_NAME, PolicyNo, CLIENT_PLAN, CUSTOMIZATION, WELLNESS_BENEFITS) VALUES (?, ?, ?, ?, ?)",
                (client_name, policy_no, client_plan, customization, wellness_benefits))
            conn.commit()
            cursor.close()
        finally:
            conn.close()
        invalidate_cache()
        return dbc.Alert("Plan added successfully!", color="success")
    except Exception as e:
        return dbc.Alert(f"Error adding plan: {e}", color="danger")


@callback(
    Output("plans-save-message", "children"),
    Input("plans-save-btn",      "n_clicks"),
    State("services-plans-table","data"),
    State("auth-store",          "data"),
    prevent_initial_call=True,
)
def save_plans(n_clicks, table_data, auth_data):
    if not auth_data or not auth_data.get("authenticated"):
        return ""
    if auth_data.get("username", "") != "ClientServices" or not n_clicks or not table_data:
        return ""
    try:
        conn = engine.raw_connection()
        try:
            cursor = conn.cursor()
            for row in table_data:
                client_name = row.get('CLIENT_NAME')
                policy_no   = row.get('PolicyNo')
                if client_name and policy_no:
                    cursor.execute("SELECT CLIENT_PLAN, CUSTOMIZATION, WELLNESS_BENEFITS FROM demo_Wellness_Plans_and_Benefits WHERE CLIENT_NAME=? AND PolicyNo=?", (client_name, policy_no))
                    old_row = cursor.fetchone()
                    
                    old_client_plan = old_row[0] if old_row else None
                    old_customization = old_row[1] if old_row else None
                    old_wellness_benefits = old_row[2] if old_row else None
                    
                    new_client_plan = row.get('CLIENT_PLAN')
                    new_customization = row.get('CUSTOMIZATION')
                    new_wellness_benefits = row.get('WELLNESS_BENEFITS')
                    
                    if (old_client_plan or '') != (new_client_plan or ''):
                        cursor.execute("INSERT INTO WellnessPortalAuditTrail (ModuleName, ModifiedBy, FieldChangedName, PreviousValue, NewValue) VALUES (?, ?, ?, ?, ?)", 
                            ("ClientServices", "ClientServices", "CLIENT_PLAN", old_client_plan, new_client_plan))
                    if (old_customization or '') != (new_customization or ''):
                        cursor.execute("INSERT INTO WellnessPortalAuditTrail (ModuleName, ModifiedBy, FieldChangedName, PreviousValue, NewValue) VALUES (?, ?, ?, ?, ?)", 
                            ("ClientServices", "ClientServices", "CUSTOMIZATION", old_customization, new_customization))
                    if (old_wellness_benefits or '') != (new_wellness_benefits or ''):
                        cursor.execute("INSERT INTO WellnessPortalAuditTrail (ModuleName, ModifiedBy, FieldChangedName, PreviousValue, NewValue) VALUES (?, ?, ?, ?, ?)", 
                            ("ClientServices", "ClientServices", "WELLNESS_BENEFITS", old_wellness_benefits, new_wellness_benefits))
                    
                    cursor.execute("UPDATE demo_Wellness_Plans_and_Benefits SET CLIENT_PLAN=?, CUSTOMIZATION=?, WELLNESS_BENEFITS=? WHERE CLIENT_NAME=? AND PolicyNo=?", 
                        (new_client_plan, new_customization, new_wellness_benefits, client_name, policy_no))
            conn.commit()
            cursor.close()
        finally:
            conn.close()
        
        invalidate_cache()
        return dbc.Alert("Changes saved successfully!", color="success")
    except Exception as e:
        return dbc.Alert(f"Error saving changes: {e}", color="danger")


@callback(
    Output("plans-delete-message", "children"),
    Input("plans-delete-btn",      "n_clicks"),
    State("services-plans-table",  "selected_rows"),
    State("services-plans-table",  "data"),
    State("auth-store",            "data"),
    prevent_initial_call=True,
)
def delete_plans(n_clicks, selected_rows, table_data, auth_data):
    if not auth_data or not auth_data.get("authenticated"):
        return ""
    if auth_data.get("username", "") != "ClientServices" or not n_clicks or not selected_rows or not table_data:
        return ""
    try:
        conn = engine.raw_connection()
        try:
            cursor = conn.cursor()
            for idx in selected_rows:
                row = table_data[idx]
                client_name = row.get('CLIENT_NAME')
                policy_no   = row.get('PolicyNo')
                if client_name and policy_no:
                    old_values = {
                        "CLIENT_NAME": client_name,
                        "PolicyNo": policy_no,
                        "CLIENT_PLAN": row.get('CLIENT_PLAN'),
                        "CUSTOMIZATION": row.get('CUSTOMIZATION'),
                        "WELLNESS_BENEFITS": row.get('WELLNESS_BENEFITS')
                    }
                    _log_audit(conn, "demo_Wellness_Plans_and_Benefits", "DELETE", f"{client_name}|{policy_no}", auth_data.get("username"), old_values, None)
                    cursor.execute("DELETE FROM demo_Wellness_Plans_and_Benefits WHERE CLIENT_NAME=? AND PolicyNo=?", (client_name, policy_no))
            conn.commit()
            cursor.close()
        finally:
            conn.close()
        invalidate_cache()
        return dbc.Alert("Selected plan(s) deleted successfully!", color="success")
    except Exception as e:
        return dbc.Alert(f"Error deleting plan(s): {e}", color="danger")


@callback(
    Output("plans-edit-modal", "is_open"),
    Output("plans-edit-policy-no", "value"),
    Output("plans-edit-client-name", "value"),
    Output("plans-edit-client-plan", "value"),
    Output("plans-edit-customization", "value"),
    Output("plans-edit-wellness-benefits", "value"),
    Input("plans-edit-btn", "n_clicks"),
    State("services-plans-table", "selected_rows"),
    State("services-plans-table", "data"),
    prevent_initial_call=True,
)
def open_edit_plan_modal(n_clicks, selected_rows, table_data):
    if not n_clicks or not selected_rows or not table_data:
        return False, "", "", "", "", ""
    idx = selected_rows[0]
    row = table_data[idx]
    return True, row.get('PolicyNo', ''), row.get('CLIENT_NAME', ''), row.get('CLIENT_PLAN', ''), row.get('CUSTOMIZATION', ''), row.get('WELLNESS_BENEFITS', '')


@callback(
    Output("plans-edit-message", "children", allow_duplicate=True),
    Input("plans-edit-save-btn", "n_clicks"),
    State("plans-edit-policy-no", "value"),
    State("plans-edit-client-name", "value"),
    State("plans-edit-client-plan", "value"),
    State("plans-edit-customization", "value"),
    State("plans-edit-wellness-benefits", "value"),
    State("auth-store", "data"),
    prevent_initial_call=True,
)
def save_edit_plan(n_clicks, policy_no, client_name, client_plan, customization, wellness_benefits, auth_data):
    if not auth_data or not auth_data.get("authenticated"):
        return ""
    if auth_data.get("username", "") != "ClientServices" or not n_clicks or not policy_no:
        return ""
    try:
        conn = engine.raw_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT CLIENT_NAME, CLIENT_PLAN, CUSTOMIZATION, WELLNESS_BENEFITS FROM demo_Wellness_Plans_and_Benefits WHERE PolicyNo=?", (policy_no,))
            old_row = cursor.fetchone()
            old_values = {
                "CLIENT_NAME": old_row[0] if old_row else None,
                "CLIENT_PLAN": old_row[1] if old_row else None,
                "CUSTOMIZATION": old_row[2] if old_row else None,
                "WELLNESS_BENEFITS": old_row[3] if old_row else None
            }
            new_values = {
                "CLIENT_NAME": client_name,
                "CLIENT_PLAN": client_plan,
                "CUSTOMIZATION": customization,
                "WELLNESS_BENEFITS": wellness_benefits
            }
            _log_audit(conn, "demo_Wellness_Plans_and_Benefits", "UPDATE", policy_no, auth_data.get("username"), old_values, new_values)
            cursor.execute("UPDATE demo_Wellness_Plans_and_Benefits SET CLIENT_NAME=?, CLIENT_PLAN=?, CUSTOMIZATION=?, WELLNESS_BENEFITS=? WHERE PolicyNo=?", 
                (client_name, client_plan, customization, wellness_benefits, policy_no))
            conn.commit()
            cursor.close()
        finally:
            conn.close()
        invalidate_cache()
        return dbc.Alert("Plan updated successfully!", color="success")
    except Exception as e:
        return dbc.Alert(f"Error updating plan: {e}", color="danger")


@callback(
    Output("plans-edit-modal", "is_open", allow_duplicate=True),
    Input("plans-edit-close-btn", "n_clicks"),
    prevent_initial_call=True,
)
def close_edit_plan_modal(n_clicks):
    return False