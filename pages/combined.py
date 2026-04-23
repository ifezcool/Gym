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
import io
import zipfile
from dotenv import load_dotenv
from azure.storage.blob import BlobServiceClient, generate_blob_sas, BlobSasPermissions
from datetime import datetime, timedelta

register_page(__name__, path='/wellness', title='AVON HMO Wellness Portal')

SHIELD_EMBLEM = Svg(
    width="30", height="30", viewBox="0 0 24 24",
    fill="none", stroke="white",
    style={"strokeWidth": "2", "strokeLinecap": "round", "strokeLinejoin": "round"},
    children=[
        Path(d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"),
        Path(d="m9 12 2 2 4-4")
    ]
)

# ── Styles ────────────────────────────────────────────────────────────────────
PURPLE_TABLE_STYLE = {
    "style_header": {
        "backgroundColor": "#5B21B6",
        "color": "white",
        "fontWeight": "600",
        "textAlign": "left",
        "fontSize": "12px",
        "letterSpacing": "0.04em",
        "textTransform": "uppercase",
        "padding": "12px 10px",
        "border": "none",
    },
    "style_cell": {
        "textAlign": "left",
        "padding": "10px",
        "fontSize": "13px",
        "fontFamily": "Inter, sans-serif",
        "overflow": "hidden",
        "textOverflow": "ellipsis",
        "maxWidth": "200px",
        "border": "none",
        "borderBottom": "1px solid #F3F4F6",
    },
    "style_data_conditional": [
        {"if": {"row_index": "odd"}, "backgroundColor": "#F5F3FF"},
        {"if": {"state": "selected"}, "backgroundColor": "#EDE9FE", "border": "1px solid #7C3AED"},
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
        field_changed = f"{operation} - {record_key}"
        cursor.execute("""
            INSERT INTO WellnessPortalAuditTrail (ModuleName, ModifiedBy, FieldChangedName, PreviousValue, NewValue)
            VALUES (?, ?, ?, ?, ?)
        """, (table_name, changed_by, field_changed, old_json, new_json))
        conn.commit()
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
    "WHERE PolicyEndDate >= DATEADD(MONTH, -24, GETDATE())"
)
query_ps_q3 = (
    "select a.*, name as ProviderName "
    "from demo_Updated_Wellness_Providers a "
    "left join [dbo].[tbl_ProviderList_stg] b on a.code = b.code"
)
query_ps_q4 = (
    "SELECT * FROM demo_tbl_enrollee_wellness_result_data "
    "WHERE test_result_link IS NOT NULL AND test_result_link <> ''"
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
_wellness_data_ready = threading.Event()


def load_all_data():
    global wellness_providers, loyalty_enrollees, filled_wellness_df, wellness_df
    print("[LOADING] Loading wellness providers data...")
    wellness_providers = cached_read_sql(query3w)
    print("[COMPLETE] Wellness providers data loaded!")
    print("[LOADING] Loading loyalty enrollees data...")
    loyalty_enrollees = cached_read_sql(query4w)
    print("[COMPLETE] Loyalty enrollees data loaded!")
    print("[LOADING] Loading filled wellness data...")
    filled_wellness_df = cached_read_sql(query2w)
    print("[COMPLETE] Filled wellness data loaded!")
    print("[LOADING] Loading wellness_df...")
    wellness_df = cached_read_sql(query1)
    wellness_df['memberno'] = wellness_df['memberno'].astype(int).astype(str)
    print("[COMPLETE] wellness_df loaded!")
    filled_wellness_df['MemberNo'] = filled_wellness_df['MemberNo'].astype(str)
    loyalty_enrollees['MemberNo']  = loyalty_enrollees['MemberNo'].astype(str)
    print("[ALL COMPLETE] All startup data loaded successfully!")
    _wellness_data_ready.set()


def _prewarm_wellness():
    try:
        load_all_data()
        print("[cache] Wellness pre-warm complete.")
    except Exception as e:
        print(f"[cache] Wellness pre-warm warning: {e}")


def _prewarm_provider_data():
    try:
        print("[LOADING] Pre-warming provider portal queries...")
        cached_read_sql(query_ps_q2)
        print("[COMPLETE] query_ps_q2 loaded!")
        cached_read_sql(query_ps_q3)
        print("[COMPLETE] query_ps_q3 loaded!")
        cached_read_sql(query_ps_q4)
        print("[COMPLETE] query_ps_q4 loaded!")
        cached_read_sql(query_ps_q5)
        print("[COMPLETE] query_ps_q5 loaded!")
        print("[cache] Provider data pre-warm complete.")
    except Exception as e:
        print(f"[cache] Provider data pre-warm warning: {e}")


threading.Thread(target=_prewarm_wellness, daemon=True).start()
threading.Thread(target=_prewarm_provider_data, daemon=True).start()


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


def list_member_results_by_period(conn_str_val, container_name, member_rows, member_no):
    try:
        result_dict = {}
        bsc = BlobServiceClient.from_connection_string(conn_str_val)
        cc = bsc.get_container_client(container_name)
        
        for row in member_rows:
            pa_provider = row.get('PA_Provider')
            if pa_provider is None or (isinstance(pa_provider, float) and pd.isna(pa_provider)) or (isinstance(pa_provider, str) and not pa_provider.strip()):
                continue
            
            norm_provider = str(pa_provider).replace(" ", "").lower()
            client = row.get('Client', '')
            norm_client = str(client).replace(" ", "").lower() if client else ''
            
            policy_end = row.get('PolicyEndDate')
            if policy_end:
                if hasattr(policy_end, 'strftime'):
                    policy_end_str = policy_end.strftime('%Y-%m-%d')
                else:
                    policy_end_str = str(policy_end)
            else:
                continue
            
            prefix = f"{norm_provider}/{norm_client}/{policy_end_str}/{member_no}"
            
            blobs = list(cc.list_blobs(name_starts_with=prefix))
            
            policy_start = row.get('PolicyStartDate')
            try:
                if policy_start:
                    start_dt = pd.to_datetime(policy_start)
                    end_dt = pd.to_datetime(policy_end)
                    period_label = f"{start_dt.strftime('%b/%Y')} - {end_dt.strftime('%b/%Y')}"
                else:
                    end_dt = pd.to_datetime(policy_end)
                    period_label = str(end_dt.year)
            except:
                period_label = str(policy_end)
            
            if period_label not in result_dict:
                result_dict[period_label] = []
            
            for blob in blobs:
                result_dict[period_label].append({
                    "blob_name": blob.name,
                    "filename": blob.name.split("/")[-1]
                })
        
        return result_dict
    except Exception as e:
        return {}


def generate_sas_url(conn_str_val, container_name, blob_name, expiry_hours=1):
    try:
        import re
        account_name_match = re.search(r'AccountName=([^;]+)', conn_str_val)
        account_key_match = re.search(r'AccountKey=([^;]+)', conn_str_val)
        
        if not account_name_match or not account_key_match:
            return None
        
        account_name = account_name_match.group(1)
        account_key = account_key_match.group(1)
        
        sas_token = generate_blob_sas(
            account_name=account_name,
            container_name=container_name,
            blob_name=blob_name,
            account_key=account_key,
            permission=BlobSasPermissions(read=True),
            expiry=datetime.utcnow() + timedelta(hours=expiry_hours)
        )
        
        return f"https://{account_name}.blob.core.windows.net/{container_name}/{blob_name}?{sas_token}"
    except Exception as e:
        return None


def zip_blobs_to_bytes(conn_str_val, container_name, blob_names):
    try:
        bsc = BlobServiceClient.from_connection_string(conn_str_val)
        cc = bsc.get_container_client(container_name)
        
        buffer = io.BytesIO()
        
        with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            for blob_name in blob_names:
                blob_client = cc.get_blob_client(blob_name)
                blob_bytes = blob_client.download_blob().readall()
                archive_name = blob_name.split("/")[-1]
                zf.writestr(archive_name, blob_bytes)
        
        buffer.seek(0)
        return buffer.read()
    except Exception as e:
        return None


def send_email_with_attachment(recipient_email, enrollee_name, provider_name,
                               test_date, subject, uploaded_files,
                               selected_date=None, selected_provider=None, wellness_benefits=None,
                               bcc_email='ifeoluwa.adeniyi@avonhealthcare.com'):
    sender_email   = 'noreply@avonhealthcare.com'
    email_password = os.environ.get('email_password')

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
    family_options = [
        {'label': v, 'value': v} for v in [
            'HYPERTENSION (HIGH BLOOD PRESSURE)', 'DIABETES', 'CANCER (ANY TYPE)', 'ASTHMA',
            'ARTHRITIS', 'HIGH CHOLESTEROL', 'HEART ATTACK', 'EPILEPSY', 'STROKE', 'MENTAL ILLNESS'
        ]
    ]
    current_options = [
        {'label': v, 'value': v} for v in [
            'HYPERTENSION (HIGH BLOOD PRESSURE)', 'DIABETES', 'CANCER (ANY TYPE)', 'ASTHMA',
            'PEPTIC ULCER DISEASE', 'GLAUCOMA', 'ALLERGY', 'ARTHRITIS/LOW BACK PAIN', 'ANXIETY/DEPRESSION'
        ]
    ]
    surgery_types = [
        ('CAESAREAN SECTION', 'q-surg-caesarean', 'q-surg-caesarean-year'),
        ('FRACTURE REPAIR', 'q-surg-fracture', 'q-surg-fracture-year'),
        ('HERNIA', 'q-surg-hernia', 'q-surg-hernia-year'),
        ('LUMP REMOVAL', 'q-surg-lump', 'q-surg-lump-year'),
        ('APPENDICECTOMY', 'q-surg-appendix', 'q-surg-appendix-year'),
        ('SPINE SURGERY', 'q-surg-spine', 'q-surg-spine-year'),
    ]
    matrix_options = [
        {'label': '', 'value': 'Never'},
        {'label': '', 'value': 'Occasionally'},
        {'label': '', 'value': 'Always'},
        {'label': '', 'value': 'I Do Not Know'}
    ]
    food_nutrition_questions = [
        ('I avoid eating foods that are high in fat', 'q-avoid-fat'),
        ('I eat vegetables and fruits regularly', 'q-eats-veg'),
        ('I drink 6–8 glasses of water a day', 'q-drinks-water'),
        ('I avoid the use or minimise my exposure to alcohol', 'q-avoids-alcohol'),
        ('I avoid the use of tobacco products', 'q-avoids-tobacco'),
    ]
    physical_activity_questions = [
        ('I am physically fit and exercise at least 30 minutes regularly', 'q-exercises'),
        ('I maintain my weight within the recommendation for my weight, age and height', 'q-weight'),
        ('I enjoy more than 6 hours of sleep at night', 'q-sleep-hours'),
    ]
    preventive_checks_questions = [
        ('My blood pressure is within normal range without the use of drugs', 'q-blood-pressure'),
        ('My cholesterol level is within the normal range', 'q-cholesterol'),
    ]
    mental_health_questions = [
        ('I enjoy my work and life', 'q-enjoys-work'),
        ('I enjoy the support from friends and family', 'q-social-support'),
        ('I feel down, depressed, hopeless, tired or have little energy', 'q-feels-depressed'),
        ('I have trouble falling asleep, staying asleep, or sleeping too much', 'q-sleep-trouble'),
        ('I have trouble concentrating on things, such as reading the newspaper or watching TV', 'q-concentration'),
        ('I think I would be better off dead or better off hurting myself in some way', 'q-self-harm'),
    ]

    def build_matrix_table(title, questions):
        header_style = {"backgroundColor": "#5B21B6", "color": "white", "textAlign": "center", "padding": "10px", "width": "35%"}
        td_style = {"padding": "8px", "verticalAlign": "middle"}
        question_td_style = {"padding": "16px 8px 16px 0", "fontSize": "14px", "verticalAlign": "middle", "width": "35%"}
        answer_td_style = {"padding": "8px", "verticalAlign": "middle", "textAlign": "center", "width": "13.75%"}

        rows = []
        header_row = html.Tr([
            html.Th("", style={**header_style, "width": "35%"}),
            html.Th("Never", style={**header_style, "width": "16.25%", "lineHeight": "1.2", "fontSize": "12px"}),
            html.Th("Occasionally", style={**header_style, "width": "16.25%", "lineHeight": "1.2", "fontSize": "12px"}),
            html.Th("Always", style={**header_style, "width": "16.25%", "lineHeight": "1.2", "fontSize": "12px"}),
            html.Th("I Do Not Know", style={**header_style, "width": "16.25%", "lineHeight": "1.2", "fontSize": "12px"}),
        ])
        rows.append(header_row)

        for idx, (question_text, qid) in enumerate(questions):
            bg_color = "#F5F3FF" if idx % 2 == 1 else "white"
            row = html.Tr(style={"borderBottom": "1px solid #f0f0f0", "backgroundColor": bg_color}, children=[
                html.Td(question_text, style={**question_td_style}),
                html.Td(dcc.RadioItems(id=qid, options=matrix_options, value=None,
                           style={"display": "flex", "justifyContent": "space-around", "alignItems": "center", "width": "100%"},
                           inputStyle={"margin": "0", "cursor": "pointer", "transform": "scale(1.2)"},
                           labelStyle={"margin": "0", "display": "flex"}),
                       colSpan=4, style={"verticalAlign": "middle"}),
            ])
            rows.append(row)

        table = html.Table(children=rows, style={"width": "100%", "borderCollapse": "collapse", "tableLayout": "fixed"})

        return html.Div(dbc.Card([
            dbc.CardHeader(html.H6(title, className="mb-0 fw-bold")),
            dbc.CardBody(table)
        ]), style={"overflowX": "auto"})

    sections = []

    sections.append(html.Div([
        html.H5("1. Family Medical History", className="fw-semibold"),
        html.P("Is there a history of any of the following conditions among your family members or relatives?", className="text-muted small mb-3"),
        dcc.Dropdown(id='q-family-history', options=family_options, multi=True, placeholder="Select all that apply")
    ], className="mb-4"))

    sections.append(html.Div([
        html.H5("2. Personal Medical History", className="fw-semibold"),
        html.P("Do you have any of the following medical condition(s) that you are currently managing?", className="text-muted small mb-3"),
        dcc.Dropdown(id='q-current-conditions', options=current_options, multi=True, placeholder="Select all that apply")
    ], className="mb-4"))

    sections.append(html.Div([
        html.H5("3. Past Surgical History", className="fw-semibold"),
        html.P("Have you ever had surgery for any of the following? If yes, please select and optionally note the year.", className="text-muted small mb-3"),
        html.Div([
            html.Div([
                html.Span("Surgery Type", className="fw-medium"), html.Span("Year (if applicable)", className="fw-medium float-end")
            ], className="fw-bold mb-2")
        ]),
        html.Table([
            html.Tr([
                html.Td([
                    dbc.Checkbox(id=f"{surg[1]}", value=False, label=surg[0])
                ], style={"padding": "8px", "verticalAlign": "middle", "width": "55%"}),
                html.Td([
                    dbc.Input(id=f"{surg[2]}", type="number", min=1900, max=dt.datetime.now().year,
                             placeholder="Year", style={"width": "90px"})
                ], style={"padding": "8px", "verticalAlign": "middle", "width": "45%"})
            ]) for surg in surgery_types
        ], style={"width": "100%"})
    ], className="mb-4"))

    sections.append(html.Div([
        html.H5("4. Healthy Living Survey Questionnaire", className="fw-semibold"),
        build_matrix_table("FOOD AND NUTRITION", food_nutrition_questions),
        html.Br(),
        build_matrix_table("PHYSICAL ACTIVITIES", physical_activity_questions),
        html.Br(),
        build_matrix_table("PREVENTIVE CHECKS", preventive_checks_questions),
        html.Br(),
        build_matrix_table("MENTAL HEALTH", mental_health_questions),
    ], className="mb-4"))

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


ps_login_layout = html.Div(style={"background": "#F9FAFB", "minHeight": "100vh"}, children=[
    html.Div(
        html.A("← Back to Wellness Portal", href="/wellness",
               style={"color": "#5B21B6", "fontWeight": "600", "textDecoration": "none", "fontSize": "14px"}),
        style={"padding": "16px 24px"}
    ),
    dbc.Row([
        dbc.Col([
            html.Br(), html.Br(), html.Br(),
            html.Div(style={
                "borderRadius": "20px",
                "border": "none",
                "boxShadow": "0 20px 25px rgba(0,0,0,0.08)",
                "padding": "40px",
                "background": "#fff"
            }, children=[
                html.H2("Provider Portal Login", style={
                    "fontWeight": "700", "color": "#111827", "textAlign": "center", "marginBottom": "8px"
                }),
                html.P("Login with your username and password to access the portal.", 
                       style={"textAlign": "center", "color": "#6B7280", "marginBottom": "24px"}),
                dbc.Label("Username", className="avon-label"),
                dbc.Input(id="login-username", type="text", placeholder="Enter username", className="mb-3"),
                dbc.Label("Password", className="avon-label"),
                dbc.Input(id="login-password", type="password", placeholder="Enter password", className="mb-3"),
                dbc.Button("Login", id="login-button", 
                           className="w-100 btn-avon-primary",
                           style={"background": "linear-gradient(135deg,#5B21B6,#7C3AED)", 
                                  "border": "none", "borderRadius": "10px", "fontWeight": "600", "height": "44px"}),
                html.Div(id="login-error", style={"color": "#DC2626", "textAlign": "center", "marginTop": "12px"})
            ])
        ], width={"size": 6, "offset": 3})
    ])
])

ps_provider_layout = html.Div(style={"background": "#F9FAFB", "minHeight": "100vh"}, children=[

    html.Header(className="avon-topbar", children=[
        html.Div(style={"display": "flex", "alignItems": "center", "gap": "10px"}, children=[
            html.Div(className="avon-logo-mark", children=[SHIELD_EMBLEM]),
            html.Span("AVON HMO", style={"fontWeight": "700", "fontSize": "1rem", "color": "#5B21B6"}),
        ]),
        html.Div(className="avon-auth-pill", children=[
            html.Span(id="provider-welcome"),
            dbc.Button("Logout", id="logout-btn", size="sm", color="danger",
                       style={"marginLeft": "12px", "borderRadius": "8px",
                              "fontSize": "0.8125rem", "padding": "4px 12px"})
        ])
    ]),

    dbc.Container([
        dbc.Row([
            dbc.Col([
                html.Div(className="provider-sidebar-card", style={"padding": "20px"}, children=[
                    html.P("Select an action below:",
                           style={"color": "#374151", "marginBottom": "16px", "fontSize": "0.875rem"}),
                    html.Div(style={"display": "flex", "flexDirection": "column", "gap": "8px"}, children=[
                        dbc.Button("View Wellness Enrollees", id="provider-nav-view-btn",
                                   className="provider-nav-btn",
                                   style={"background": "linear-gradient(135deg,#5B21B6,#7C3AED)",
                                          "color": "white", "border": "none",
                                          "borderRadius": "8px", "textAlign": "left",
                                          "padding": "10px 14px", "fontWeight": "500"}),
                        dbc.Button("Submit Wellness Results", id="provider-nav-submit-btn",
                                   className="provider-nav-btn",
                                   style={"background": "linear-gradient(135deg,#5B21B6,#7C3AED)",
                                          "color": "white", "border": "none",
                                          "borderRadius": "8px", "textAlign": "left",
                                          "padding": "10px 14px", "fontWeight": "500"}),
                    ])
                ])
            ], width=3),
            dbc.Col([html.Div(id="provider-content"), dcc.Store(id="provider-active-view")], width=9)
        ], style={"marginTop": "24px"})
    ], fluid=True, style={"maxWidth": "1400px"})
])

ps_claims_layout = html.Div(style={"background": "#F9FAFB", "minHeight": "100vh"}, children=[

    html.Header(className="avon-topbar", children=[
        html.Div(style={"display": "flex", "alignItems": "center", "gap": "10px"}, children=[
            html.Div(className="avon-logo-mark", children=[SHIELD_EMBLEM]),
            html.Span("AVON HMO", style={"fontWeight": "700", "fontSize": "1rem", "color": "#5B21B6"}),
        ]),
        html.Div(className="avon-auth-pill", children=[
            html.Span(id="claims-welcome"),
            dbc.Button("Logout", id="logout-btn", size="sm", color="danger",
                       style={"marginLeft": "12px", "borderRadius": "8px",
                              "fontSize": "0.8125rem", "padding": "4px 12px"})
        ])
    ]),

    dbc.Container([
        dbc.Row([
            dbc.Col([
                html.Div(className="provider-sidebar-card", style={"padding": "20px"}, children=[
                    html.P("Select a provider and member to view submitted wellness results.",
                           style={"color": "#374151", "marginBottom": "16px", "fontSize": "0.875rem"}),
                    dbc.Label("Select Provider", className="avon-label"),
                    dcc.Dropdown(id="claims-provider-select", placeholder="Select Provider",
                                 className="mb-3"),
                    dbc.Label("Select Member", className="avon-label"),
                    dcc.Dropdown(id="claims-member-select", placeholder="Select Member",
                                 className="mb-3"),
                    dbc.Label("Select Policy Period", className="avon-label"),
                    dcc.Dropdown(id="claims-policy-period-select", placeholder="Select Policy Period",
                                 className="mb-3"),
                ])
            ], width=3),
            dbc.Col([html.Div(id="claims-content")], width=9)
        ], style={"marginTop": "24px"})
    ], fluid=True)
])

ps_contact_layout = html.Div(style={"background": "#F9FAFB", "minHeight": "100vh"}, children=[

    # ── Topbar ──────────────────────────────────────────────────────────────
    html.Header(className="avon-topbar", children=[
        html.Div(style={"display": "flex", "alignItems": "center", "gap": "10px"}, children=[
            html.Div(className="avon-logo-mark", children=[SHIELD_EMBLEM]),
            html.Span("AVON HMO", style={"fontWeight": "700", "fontSize": "1rem", "color": "#5B21B6"}),
        ]),
        # Auth pill — right side
        html.Div(className="avon-auth-pill", children=[
            html.Span(id="contact-welcome"),
            dbc.Button("Logout", id="logout-btn", size="sm", color="danger",
                       style={"marginLeft": "12px", "borderRadius": "8px",
                              "fontSize": "0.8125rem", "padding": "4px 12px"})
        ])
    ]),

    # ── Body ────────────────────────────────────────────────────────────────
    dbc.Container([
        dbc.Row([
            # Sidebar
            dbc.Col([
                html.Div(className="provider-sidebar-card", style={"padding": "20px"}, children=[
                    html.P("Kindly input a Member ID to check eligibility and booking status:",
                           style={"color": "#374151", "marginBottom": "12px", "fontSize": "0.875rem"}),
                    dbc.Input(id="contact-enrollee-id", type="text",
                              placeholder="Enter Member ID", className="mb-3"),
                    dbc.Button("Search", id="contact-search-button",
                               className="w-100 btn-avon-primary"),
                ])
            ], width=3),
            # Content
            dbc.Col([
                dcc.Loading(type="circle", color="#5B21B6",
                            children=html.Div(id="contact-content")),
                dcc.Download(id="contact-download")
            ], width=9)
        ], style={"marginTop": "24px"})
    ], fluid=True)
])

ps_services_layout = html.Div(style={"background": "#F9FAFB", "minHeight": "100vh"}, children=[

    html.Header(className="avon-topbar", children=[
        html.Div(style={"display": "flex", "alignItems": "center", "gap": "10px"}, children=[
            html.Div(className="avon-logo-mark", children=[SHIELD_EMBLEM]),
            html.Span("AVON HMO", style={"fontWeight": "700", "fontSize": "1rem", "color": "#5B21B6"}),
        ]),
        html.Div(className="avon-auth-pill", children=[
            html.Span(id="services-welcome"),
            dbc.Button("Logout", id="logout-btn", size="sm", color="danger",
                       style={"marginLeft": "12px", "borderRadius": "8px",
                              "fontSize": "0.8125rem", "padding": "4px 12px"})
        ])
    ]),

    dbc.Container([
        dbc.Row([
            dbc.Col([
                dcc.Loading(type="circle", color="#5B21B6",
                            children=html.Div(id="services-content"))
            ], width=12)
        ], style={"marginTop": "24px"})
    ], fluid=True)
])



# =============================================================================
# WELLNESS PORTAL — LOADING SCREEN
# =============================================================================
def wellness_loading_screen():
    return html.Div([
        html.Div(className="purple-skew"),
        html.Div(className="green-blob"),
        html.Div([
            html.Div(className="logo-container mb-4", children=[SHIELD_EMBLEM]),
            html.H3("Loading portal data...", className="mb-3", style={"color": "#44337A"}),
            dbc.Spinner(size="lg", color="primary"),
            html.P("Please wait while we load the wellness portal", className="mt-3", style={"color": "#718096"})
        ], className="text-center")
    ], className="gradient-bg min-vh-100 d-flex align-items-center justify-content-center p-4 position-relative overflow-hidden")


# =============================================================================
# WELLNESS PORTAL — MAIN PORTAL LAYOUT
# =============================================================================
def wellness_portal_layout():
    return html.Div(style={"background": "#F9FAFB", "minHeight": "100vh"}, children=[
        # Sticky topbar
        html.Header(className="avon-topbar", children=[
            html.A(className="avon-topbar-brand", href="/", children=[
                html.Div(className="avon-logo-mark", children=[SHIELD_EMBLEM]),
                html.Span("AVON HMO")
            ]),
            html.A("⚕ Provider Portal",
                   href="/wellness/provider",
                   className="avon-btn avon-btn-secondary",
                   style={"fontSize": "0.8125rem", "height": "36px", "padding": "0 14px"},
                   id="go-to-provider-btn")
        ]),

        dcc.Location(id='url-welcome', refresh=False),

        # Hero
        html.Section(style={
            "background": "linear-gradient(135deg, #F5F3FF 0%, #fff 60%, #F0FDF4 100%)",
            "padding": "56px 24px 48px",
            "textAlign": "center",
            "borderBottom": "1px solid #F3F4F6",
        }, children=[
            html.Div(className="logo-container", style={"marginBottom": "16px"}, children=[SHIELD_EMBLEM]),
            html.Span("Annual Wellness Portal", style={
                "display": "inline-block", "background": "#EDE9FE", "color": "#5B21B6",
                "fontSize": "0.75rem", "fontWeight": "600", "letterSpacing": "0.06em",
                "textTransform": "uppercase", "padding": "4px 12px",
                "borderRadius": "9999px", "marginBottom": "16px"
            }),
            html.H1("Check Your Wellness Eligibility", style={
                "fontSize": "clamp(1.5rem, 3vw, 2.25rem)",
                "fontWeight": "700", "color": "#111827",
                "maxWidth": "540px", "margin": "0 auto 10px"
            }),
            html.P("Enter your Member ID to check eligibility and book your annual wellness checkup.",
                   style={"color": "#6B7280", "maxWidth": "460px",
                          "margin": "0 auto", "lineHeight": "1.6", "fontSize": "0.9375rem"})
        ]),

        # Main content
        html.Div(style={"maxWidth": "600px", "margin": "0 auto", "padding": "32px 16px 80px"}, children=[
            # ID lookup card
            html.Div(className="wellness-card", style={"padding": "28px", "marginBottom": "24px"}, children=[
                html.Label("Member Number / Policy ID", className="avon-label"),
                dcc.Input(
                    id='enrollee-id-input', type='text',
                    placeholder='Enter your Member ID',
                    className='form-control',
                    style={"marginBottom": "16px", "fontSize": "1rem"}
                ),
                html.Div(id='eligibility-message', style={"marginBottom": "12px"}),
                dbc.Button([html.Span("Check Eligibility"), html.Span(" →", style={"marginLeft": "6px"})],
                           id='member-id-submit-btn',
                           className="w-100 btn-avon-primary",
                           style={"height": "44px", "fontSize": "0.9375rem"}),
                html.P("Your Member ID is on your AVON HMO e-card or policy document.",
                       style={"textAlign": "center", "marginTop": "12px",
                              "fontSize": "0.8125rem", "color": "#9CA3AF"})
            ]),

            dbc.Row([dbc.Col(id='already-booked-section', width=12)]),
            dbc.Row([dbc.Col(id='enrollment-form-section', width=12)]),
        ]),

        html.Footer(className="avon-footer", children=[
            f"© {dt.datetime.now().year} AVON HMO. All rights reserved."
        ])
    ])


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
    return _wellness_data_ready.is_set()


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
    State('q-family-history',         'value'),
    State('q-current-conditions',   'value'),
    State('q-surg-caesarean',       'value'),
    State('q-surg-caesarean-year',   'value'),
    State('q-surg-fracture',        'value'),
    State('q-surg-fracture-year',  'value'),
    State('q-surg-hernia',          'value'),
    State('q-surg-hernia-year',     'value'),
    State('q-surg-lump',           'value'),
    State('q-surg-lump-year',       'value'),
    State('q-surg-appendix',        'value'),
    State('q-surg-appendix-year',  'value'),
    State('q-surg-spine',          'value'),
    State('q-surg-spine-year',      'value'),
    State('q-avoid-fat',           'value'),
    State('q-eats-veg',            'value'),
    State('q-drinks-water',         'value'),
    State('q-avoids-alcohol',      'value'),
    State('q-avoids-tobacco',       'value'),
    State('q-exercises',           'value'),
    State('q-weight',              'value'),
    State('q-sleep-hours',         'value'),
    State('q-blood-pressure',     'value'),
    State('q-cholesterol',        'value'),
    State('q-enjoys-work',        'value'),
    State('q-social-support',      'value'),
    State('q-feels-depressed',      'value'),
    State('q-sleep-trouble',        'value'),
    State('q-concentration',      'value'),
    State('q-self-harm',          'value'),
    prevent_initial_call=True
)
def submit_form(submit_clicks, close_clicks, enrollee_id, email, mobile, gender,
                job_type, state, provider, selected_date, session, enrollee_data,
                q_family_history, q_current_conditions,
                q_surg_caesarean, q_surg_caesarean_year,
                q_surg_fracture, q_surg_fracture_year,
                q_surg_hernia, q_surg_hernia_year,
                q_surg_lump, q_surg_lump_year,
                q_surg_appendix, q_surg_appendix_year,
                q_surg_spine, q_surg_spine_year,
                q_avoid_fat, q_eats_veg, q_drinks_water, q_avoids_alcohol, q_avoids_tobacco,
                q_exercises, q_weight, q_sleep_hours,
                q_blood_pressure, q_cholesterol,
                q_enjoys_work, q_social_support, q_feels_depressed, q_sleep_trouble,
                q_concentration, q_self_harm):
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

    if q_family_history:
        family_history_conditions = ', '.join(q_family_history)
    else:
        family_history_conditions = ''

    if q_current_conditions:
        current_medical_conditions = ', '.join(q_current_conditions)
    else:
        current_medical_conditions = ''

    surgeries = []
    surgery_list = [
        ('CAESAREAN SECTION', q_surg_caesarean, q_surg_caesarean_year),
        ('FRACTURE REPAIR', q_surg_fracture, q_surg_fracture_year),
        ('HERNIA', q_surg_hernia, q_surg_hernia_year),
        ('LUMP REMOVAL', q_surg_lump, q_surg_lump_year),
        ('APPENDICECTOMY', q_surg_appendix, q_surg_appendix_year),
        ('SPINE SURGERY', q_surg_spine, q_surg_spine_year),
    ]
    for name, checked, year in surgery_list:
        if checked:
            if year:
                surgeries.append(f"{name} ({year})")
            else:
                surgeries.append(name)
    past_surgeries = ', '.join(surgeries) if surgeries else ''

    date_submitted = dt.datetime.now()

    try:
        conn = engine.raw_connection()
        cursor = conn.cursor()
        try:
            insert_query1 = """
            INSERT INTO [dbo].[Member_Health_Assessment]
            (MemberNo, MemberName, Client, Policy, PolicyStartDate, PolicyEndDate,
            email, mobile_num, job_type, Age, State, Selected_Provider, sex, wellness_benefits,
            selected_date, selected_session,
            FamilyHistoryConditions, CurrentMedicalConditions, PastSurgeries,
            AvoidHighFatFoods, EatsVegetablesAndFruits, DrinksWaterDaily, AvoidsAlcohol, AvoidsTobacco,
            ExercisesRegularly, MaintainsHealthyWeight, SleepsMoreThan6Hours,
            BloodPressureNormal, CholesterolNormal,
            EnjoysWorkAndLife, HasSocialSupport, FeelsDepressedOrTired,
            HasSleepTrouble, HasConcentrationTrouble, HasSelfHarmThoughts,
            date_submitted)
            OUTPUT INSERTED.ID
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            cursor.execute(insert_query1, (
                enrollee_id, enrollee_data['member_name'], client, policy,
                enrollee_data['policystart'], enrollee_data['policyend'],
                email, mobile, job_type, age, state, provider, member_gender, benefits,
                None if date_communicated else selected_date_str, session,
                family_history_conditions, current_medical_conditions, past_surgeries,
                q_avoid_fat, q_eats_veg, q_drinks_water, q_avoids_alcohol, q_avoids_tobacco,
                q_exercises, q_weight, q_sleep_hours,
                q_blood_pressure, q_cholesterol,
                q_enjoys_work, q_social_support, q_feels_depressed,
                q_sleep_trouble, q_concentration, q_self_harm,
                date_submitted
            ))

            row = cursor.fetchone()
            assessment_id = row[0] if row else None

            if assessment_id is None:
                raise ValueError("Failed to retrieve inserted ID from Member_Health_Assessment.")

            booking_reference = f"WB-{dt.datetime.now().strftime('%Y%m%d')}-{str(assessment_id).zfill(5)}"

            insert_query2 = """
            INSERT INTO [dbo].[wellness_booking_details] (AssessmentID, MemberNo, MemberName, Client, Policy, PolicyStartDate, PolicyEndDate, email, mobile_num, job_type, Age, State, Selected_Provider, sex, wellness_benefits, selected_date, selected_session, date_submitted, booking_status, booking_reference)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            cursor.execute(insert_query2, (
                assessment_id, enrollee_id, enrollee_data['member_name'], client, policy,
                enrollee_data['policystart'], enrollee_data['policyend'], email, mobile, job_type,
                age, state, provider, member_gender, benefits,
                None if date_communicated else selected_date_str, session,
                date_submitted, 'Pending', booking_reference
            ))

            conn.commit()

        except Exception as e:
            conn.rollback()
            raise e
        finally:
            cursor.close()
            conn.close()

        date_submitted_str = date_submitted.strftime('%Y-%m-%d %H:%M:%S')
        sender_email   = 'noreply@avonhealthcare.com'
        email_password = os.environ.get('email_password')
        recipient_email = 'ifeoluwa.adeniyi@avonhealthcare.com'
        email_body = f"""
            Dear Contact Centre,<br><br>
            The following enrollee has completed their wellness booking and is awaiting a PA Code. Please log into the Contact Centre portal and issue a PA Code for this member.<br><br>
            <table border="1" cellpadding="5" cellspacing="0" style="border-collapse: collapse;">
                <tr>
                    <th style="background-color: #f2f2f2;">Member ID</th>
                    <td>{enrollee_id}</td>
                </tr>
                <tr>
                    <th style="background-color: #f2f2f2;">Member Name</th>
                    <td>{enrollee_data['member_name']}</td>
                </tr>
                <tr>
                    <th style="background-color: #f2f2f2;">Client</th>
                    <td>{client}</td>
                </tr>
                <tr>
                    <th style="background-color: #f2f2f2;">Selected Provider</th>
                    <td>{provider}</td>
                </tr>
                <tr>
                    <th style="background-color: #f2f2f2;">Appointment Date</th>
                    <td>{selected_date_str}</td>
                </tr>
                <tr>
                    <th style="background-color: #f2f2f2;">Wellness Benefits</th>
                    <td>{benefits}</td>
                </tr>
                <tr>
                    <th style="background-color: #f2f2f2;">Date Submitted</th>
                    <td>{date_submitted_str}</td>
                </tr>
            </table>
        """
        try:
            s = smtplib.SMTP('smtp.office365.com', 587)
            s.starttls()
            s.login(sender_email, email_password)
            msg = MIMEMultipart()
            msg['From']    = 'AVON HMO Medical Services'
            msg['To']      = recipient_email
            msg['Subject'] = f'WELLNESS BOOKING NOTIFICATION — ACTION REQUIRED: {enrollee_id}'
            msg.attach(MIMEText(email_body, 'html'))
            s.sendmail(sender_email, [recipient_email], msg.as_string())
            s.quit()
        except Exception as e:
            print(f"Contact centre email error: {e}")

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
        subtitle = "Provider Submission Portal"
    elif u.startswith("claim"):
        subtitle = "Results Review Portal"
    elif u.startswith("contact"):
        subtitle = "PA Code & Results Portal"
    elif u in ("ClientServices", "MedicalServices"):
        subtitle = "Services Management Portal"
    else:
        return ps_login_layout

    return html.Div(style={
        "minHeight": "100vh", "background": "#F9FAFB",
        "display": "flex", "alignItems": "center", "justifyContent": "center",
        "flexDirection": "column", "textAlign": "center", "padding": "40px"
    }, children=[
        html.Div(className="logo-container", style={"marginBottom": "20px"}, children=[SHIELD_EMBLEM]),
        html.P("AVON HMO", style={
            "fontWeight": "700", "fontSize": "1.125rem",
            "color": "#5B21B6", "marginBottom": "4px"
        }),
        html.P(subtitle, style={
            "color": "#6B7280", "fontSize": "0.875rem", "marginBottom": "20px"
        }),
        dbc.Spinner(size="md", color="primary"),
        html.P("Loading portal data, please wait…", style={
            "color": "#9CA3AF", "fontSize": "0.8125rem", "marginTop": "16px"
        }),
    ])


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
    Output("provider-active-view", "data"),
    Input("provider-nav-view-btn",   "n_clicks"),
    Input("provider-nav-submit-btn", "n_clicks"),
    State("store-q2",  "data"),
    State("store-q4",  "data"),
    State("auth-store","data"),
    prevent_initial_call=False,
)
def update_provider_content(view_clicks, submit_clicks, q2_data, q4_data, auth_data):
    ctx = callback_context
    if not ctx.triggered:
        option = "view"
    else:
        triggered_id = ctx.triggered[0]["prop_id"].split(".")[0]
        option = "submit" if triggered_id == "provider-nav-submit-btn" else "view"
    if not auth_data or not q2_data or not auth_data.get("username", "").startswith("234"):
        return "", None
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

    pdf = filled_df[mask][['MemberNo', 'MemberName', 'IssuedPACode', 'PA_Tests', 'date_submitted']].copy()
    submitted_members = set(result_df['memberno'].astype(str).tolist()) if not result_df.empty else set()
    pdf['SubmissionStatus'] = pdf['MemberNo'].apply(
        lambda x: 'Submitted' if x in submitted_members else 'Not Submitted'
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
                columns=[{"name": "Date Submitted" if i == "date_submitted" else i, "id": i} for i in pdf.columns],
                style_header=PURPLE_TABLE_STYLE["style_header"],
                style_cell={**PURPLE_TABLE_STYLE["style_cell"], "fontFamily": "Arial"},
                style_data_conditional=PURPLE_TABLE_STYLE["style_data_conditional"] + [
                    {"if": {"filter_query": '{SubmissionStatus} = "Submitted"',     "column_id": "SubmissionStatus"}, "backgroundColor": "green", "color": "white"},
                    {"if": {"filter_query": '{SubmissionStatus} = "Not Submitted"', "column_id": "SubmissionStatus"}, "backgroundColor": "red",   "color": "white"},
                ],
                style_table={"overflowX": "auto"}, page_size=20,
            )
        ]), option
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
        ]), option


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
        html.Div(id="upload-filename-display"),
        html.Br(),
        dbc.Button("Submit Results", id="submit-results-btn", color="success"),
        html.Div(id="ps-submission-message")
    ])


ACTIVE_BTN_STYLE = {
    "background": "linear-gradient(135deg, #3B0F8C, #5B21B6)",
    "color": "white",
    "border": "none",
    "borderRadius": "8px",
    "textAlign": "left",
    "padding": "10px 14px",
    "fontWeight": "700",
    "boxShadow": "inset 0 2px 6px rgba(0,0,0,0.2)",
    "borderLeft": "3px solid #EDE9FE"
}

INACTIVE_BTN_STYLE = {
    "background": "linear-gradient(135deg, #5B21B6, #7C3AED)",
    "color": "white",
    "border": "none",
    "borderRadius": "8px",
    "textAlign": "left",
    "padding": "10px 14px",
    "fontWeight": "500"
}


@callback(
    Output("provider-nav-view-btn",   "style"),
    Output("provider-nav-submit-btn", "style"),
    Input("provider-active-view", "data"),
    prevent_initial_call=False,
)
def update_provider_button_styles(active_view):
    view_active = active_view != "submit"
    return (
        ACTIVE_BTN_STYLE if view_active else INACTIVE_BTN_STYLE,
        INACTIVE_BTN_STYLE if view_active else ACTIVE_BTN_STYLE
    )


@callback(
    Output("upload-filename-display", "children"),
    Input("upload-results", "filename"),
    prevent_initial_call=True,
    allow_duplicate=False,
)
def display_uploaded_filenames(filenames):
    if not filenames:
        return ""
    return html.Div([html.P(fn, style={"color": "green"}) for fn in filenames])


@callback(
    Output("ps-submission-message", "children"),
    Output("store-q4", "data", allow_duplicate=True),
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
        return "", dash.no_update
    missing = [f for f, v in [('PA Code', pa_code), ('Tests Conducted', tests_conducted),
                               ('Test Date', test_date), ('Uploaded File', uploaded_filenames)] if not v]
    if missing:
        return dbc.Alert(f"Compulsory fields missing: {', '.join(missing)}", color="danger"), dash.no_update

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

    q4_df = cached_read_sql(query_ps_q4)
    q4_data = q4_df.to_dict('records')

    ok, msg = send_email_with_attachment(
        row['email'], row['MemberName'], auth_data.get("providername", ""),
        test_date, 'AVON HMO ANNUAL TEST RESULTS', uploaded_files
    )
    if ok:
        return dbc.Alert("Results submitted. Email sent to enrollee.", color="success"), q4_data
    return dbc.Alert(msg, color="danger"), q4_data


@callback(
    Output("contact-policy-year-select", "options"),
    Input("data-ready-store-ps",   "data"),
    State("store-q2",              "data"),
    prevent_initial_call=False,
)


@callback(
    Output("claims-provider-select", "options"),
    Input("data-ready-store-ps",   "data"),
    State("store-q2",              "data"),
    prevent_initial_call=False,
)
def load_claims_providers(ready, q2_data):
    if not ready or not q2_data:
        return []
    df = pd.DataFrame(q2_data)
    if 'PA_Provider' not in df.columns:
        return []
    providers = df['PA_Provider'].dropna().str.split('-').str[0].str.strip().unique()
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
    if 'PA_Provider' not in df.columns or 'MemberNo' not in df.columns or 'MemberName' not in df.columns:
        return []
    df['MemberNo'] = df['MemberNo'].astype(str)
    df['member'] = df['MemberNo'].str.cat(df['MemberName'].astype(str), sep=' - ')
    if provider:
        df['PA_Provider_cleaned'] = df['PA_Provider'].str.split('-').str[0].str.strip()
        filtered = df[df['PA_Provider_cleaned'] == provider]
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
        df['PA_Provider_cleaned'] = df['PA_Provider'].str.split('-').str[0].str.strip()
        df = df[df['PA_Provider_cleaned'] == provider]
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
    df['PolicyStartDate'] = pd.to_datetime(df['PolicyStartDate'], errors='coerce')
    df['PolicyEndDate'] = pd.to_datetime(df['PolicyEndDate'], errors='coerce')
    if policy_period:
        start_date, end_date = policy_period.split('|')
        df = df[(df['PolicyStartDate'].dt.strftime('%Y-%m-%d') == start_date) & 
                (df['PolicyEndDate'].dt.strftime('%Y-%m-%d') == end_date)]
    if df.empty:
        return html.Div("No records found for the selected criteria.", style={"color": "red"})
    row = df.sort_values('date_submitted', ascending=False).iloc[0]
    actual_provider = row['PA_Provider']
    return html.Div([
        html.H3(f"Test Results for {member}", style={"color": "green"}),
        html.H4(f"Client: {row['Client']}",                                  style={"color": "purple"}),
        html.H4(f"PA Code Issued to Provider: {row['IssuedPACode']}",        style={"color": "purple"}),
        html.H4(f"Wellness Tests PA Code was Issued for: {row['PA_Tests']}", style={"color": "purple"}),
        html.Hr(),
        html.H4("Results:"),
        display_member_results(conn_str, 'annual-wellness-results',
                               actual_provider, row['Client'], member_id, row['PolicyEndDate'])
    ])


@callback(
    Output("contact-content",      "children"),
    Input("contact-search-button", "n_clicks"),
    Input("data-ready-store-ps",   "data"),
    State("auth-store",            "data"),
    State("contact-enrollee-id",   "value"),
    State("store-q3",  "data"),
    prevent_initial_call=False,
)
def search_enrollee(n_clicks, data_ready, auth_data, enrollee_id, q3_data):
    if not auth_data or not auth_data.get("authenticated"):
        return ""
    if not auth_data.get("username", "").startswith("contact"):
        return ""
    if not data_ready:
        return ""

    invalidate_cache()
    filled_df = cached_read_sql(query_ps_q2)
    q4_data = cached_read_sql(query_ps_q4).to_dict('records')
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
        html.H4("Wellness Enrollee Overview", style={"color": "#5B21B6", "marginBottom": "20px"}),
        dbc.Row([
            dbc.Col([
                html.Div(className="avon-stat-card avon-stat-purple", children=[
                    html.Div(f"{total_records}", className="avon-stat-number"),
                    html.Div("Total Enrollee Records", className="avon-stat-label"),
                ])
            ], width=4),
            dbc.Col([
                html.Div(className="avon-stat-card avon-stat-green", children=[
                    html.Div(f"{records_with_pa}", className="avon-stat-number"),
                    html.Div("Records with PA Code", className="avon-stat-label"),
                ])
            ], width=4),
            dbc.Col([
                html.Div(className="avon-stat-card avon-stat-red", children=[
                    html.Div(f"{records_without_pa}", className="avon-stat-number"),
                    html.Div("Records without PA Code", className="avon-stat-label"),
                ])
            ], width=4),
        ], className="mb-4"),
        html.H5("All Enrollees", style={"color": "#5B21B6", "marginBottom": "10px"}),
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

        table_rows = []
        for idx, (label, values) in enumerate(booking.iterrows()):
            bg_color = "#FFFFFF" if idx % 2 == 0 else "#F5F3FF"
            table_rows.append(
                html.Tr([
                    html.Td(label, style={
                        'fontWeight': '600',
                        'color': '#374151',
                        'padding': '10px 14px',
                        'width': '40%',
                        'backgroundColor': bg_color,
                        'borderRight': '1px solid #E9D8FD'
                    }),
                    html.Td(str(values[0]), style={
                        'color': '#111827',
                        'padding': '10px 14px',
                        'backgroundColor': bg_color,
                        'borderBottom': '1px solid #F3F4F6',
                        'border': '1px solid #F3F4F6'
                    })
                ], style={'borderBottom': '1px solid #F3F4F6'})
            )
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
            html.H4(f"Wellness Booking Details for {row['MemberName']}", style={"color": "#5B21B6"}),
            html.Label("Select Policy Year", style={"fontWeight": "bold", "color": "#5B21B6"}),
            dcc.Dropdown(id="contact-policy-year", options=current_year_options, value='current', clearable=False),
            html.Br(),
            html.H5("Booking Details", style={"color": "#5B21B6"}),
            html.Table(table_rows, style={
                'width': '100%',
                'borderCollapse': 'collapse',
                'border': '1px solid #E9D8FD',
                'borderRadius': '10px',
                'overflow': 'hidden',
                'fontSize': '0.875rem'
            }),
            html.Hr(),
            html.H4("Kindly Update Details of PA Code Issued to Provider for the Enrollee", style={"color": "#5B21B6"}),
            dbc.Label("Input the Generated PA Code"),
            dbc.Input(id="contact-pacode", type="text", placeholder="Enter PA Code", value=row.get('IssuedPACode', '')),
            html.Br(),
            dbc.Label("Select the Tests Conducted"),
            dcc.Dropdown(id="contact-pa-tests", options=PA_TESTS_OPTIONS, multi=True,
                         value=[t.strip() for t in str(row.get('PA_Tests', '') or '').split(',') if t.strip()]),
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
            result_alert,
            html.Hr(),
            html.H4("Submitted Wellness Results", style={"color": "#5B21B6"}),
            dcc.Dropdown(
                id="contact-results-period-filter",
                options=[{'label': 'All Periods', 'value': 'all'}] + [
                    {'label': period, 'value': period} 
                    for period in list_member_results_by_period(
                        conn_str, 'annual-wellness-results', 
                        member_df.to_dict('records'), enrollee_id
                    ).keys()
                ],
                value="all",
                clearable=False
            ),
            html.Div(id="contact-results-list"),
            dbc.Button("Download All Results (ZIP)", id="contact-download-all-btn", color="primary", style={"marginTop": "10px"}),
            html.Div(id="contact-download-msg")
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
    pa_tests_value = [t.strip() for t in str(row.get('PA_Tests', '') or '').split(',') if t.strip()]
    return (row.get('IssuedPACode', ''), pa_tests_value, row.get('PA_Provider', ''), row.get('PAIssueDate', None))


@callback(
    Output("contact-pa-message",   "children"),
    Output("store-q2",            "data", allow_duplicate=True),
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
        return "", dash.no_update
    if not auth_data.get("username", "").startswith("contact") or not n_clicks:
        return "", dash.no_update
    missing = [f for f, v in [('PA Code', pacode), ('Tests Conducted', pa_tests), ('Provider', pa_provider)] if not v]
    if missing:
        return dbc.Alert(f"Please fill: {', '.join(missing)}", color="danger"), dash.no_update

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

    policy_start = target_row['PolicyStartDate']
    policy_end = target_row['PolicyEndDate']
    try:
        policy_start = pd.to_datetime(policy_start).to_pydatetime() if not isinstance(policy_start, dt.datetime) else policy_start
        policy_end = pd.to_datetime(policy_end).to_pydatetime() if not isinstance(policy_end, dt.datetime) else policy_end
    except Exception as e:
        return dbc.Alert(f"Error parsing date: {e}", color="danger"), dash.no_update
    
    conn = engine.raw_connection()
    try:
        cursor = conn.cursor()
        if pa_issue_date:
            cursor.execute("""
                UPDATE demo_tbl_annual_wellness_enrollee_data
                SET IssuedPACode = ?, PA_Tests = ?, PA_Provider = ?, PAIssueDate = ?
                WHERE MemberNo = ? AND PolicyStartDate = ? AND PolicyEndDate = ?
            """, (pacode, ','.join(pa_tests) if isinstance(pa_tests, list) else pa_tests, pa_provider, pa_issue_date, enrollee_id, policy_start, policy_end))
        else:
            cursor.execute("""
                UPDATE demo_tbl_annual_wellness_enrollee_data
                SET IssuedPACode = ?, PA_Tests = ?, PA_Provider = ?, PAIssueDate = NULL
                WHERE MemberNo = ? AND PolicyStartDate = ? AND PolicyEndDate = ?
            """, (pacode, ','.join(pa_tests) if isinstance(pa_tests, list) else pa_tests, pa_provider, enrollee_id, policy_start, policy_end))
        conn.commit()
        cursor.close()
    finally:
        conn.close()
    
    invalidate_cache()
    fresh_q2 = cached_read_sql(query_ps_q2).to_dict('records')

    if policy_year == 'current':
        ok, msg = send_pa_code_email(
            target_row.get('email', ''), target_row.get('MemberName', ''),
            target_row.get('selected_date', ''), target_row.get('selected_provider', ''),
            target_row.get('Wellness_benefits', '')
        )
        if ok:
            return dbc.Alert("PA Code successfully updated for the enrollee. Scheduling email sent.", color="success"), fresh_q2
        else:
            return dbc.Alert(f"PA Code updated but email failed: {msg}", color="warning"), fresh_q2
    else:
        return dbc.Alert(f"PA Code successfully updated for the enrollee for policy year {policy_year}.", color="success"), fresh_q2


@callback(
    Output("contact-results-list", "children"),
    Input("contact-results-period-filter", "value"),
    State("contact-enrollee-id", "value"),
    State("store-q2", "data"),
    State("auth-store", "data"),
    prevent_initial_call=True,
)
def list_enrollee_results(period_filter, enrollee_id, q2_data, auth_data):
    if not auth_data or not auth_data.get("authenticated"):
        return ""
    if not auth_data.get("username", "").startswith("contact"):
        return ""
    if not enrollee_id or not q2_data or not period_filter:
        return ""
    
    df = pd.DataFrame(q2_data)
    df['MemberNo'] = df['MemberNo'].astype(str)
    member_df = df[df['MemberNo'] == enrollee_id]
    
    if member_df.empty:
        return ""
    
    member_rows = member_df.to_dict('records')
    results_dict = list_member_results_by_period(conn_str, 'annual-wellness-results', member_rows, enrollee_id)
    
    if not results_dict:
        return dbc.Alert("No results were found.", color="warning")
    
    if period_filter == "all":
        periods_to_show = results_dict.keys()
    else:
        periods_to_show = [period_filter] if period_filter in results_dict else []
    
    output_elements = []
    for period in periods_to_show:
        blobs = results_dict.get(period, [])
        output_elements.append(html.H6(period, style={"color": "#5B21B6", "marginTop": "10px"}))
        
        if not blobs:
            output_elements.append(html.Div(f"No files for {period}", style={"color": "#6B7280", "fontSize": "0.875rem"}))
        else:
            table_rows = []
            for blob in blobs:
                filename = blob.get('filename', '')
                blob_name = blob.get('blob_name', '')
                sas_url = generate_sas_url(conn_str, 'annual-wellness-results', blob_name)
                
                download_cell = (
                    html.A("Download", href=sas_url, target="_blank") 
                    if sas_url else 
                    html.Span("Unavailable", style={"color": "#6B7280"})
                )
                
                table_rows.append(html.Tr([
                    html.Td(filename),
                    html.Td(period),
                    html.Td(download_cell)
                ]))
            
            output_elements.append(dbc.Table(
                [
                    html.Thead(html.Tr([
                        html.Th("Filename"), html.Th("Policy Period"), html.Th("Download")
                    ]))
                ] + [html.Tbody(table_rows)],
                striped=True, bordered=True, hover=True
            ))
    
    return html.Div(output_elements)


@callback(
    Output("contact-download", "data"),
    Output("contact-download-msg", "children"),
    Input("contact-download-all-btn", "n_clicks"),
    State("contact-results-period-filter", "value"),
    State("contact-enrollee-id", "value"),
    State("store-q2", "data"),
    State("auth-store", "data"),
    prevent_initial_call=True,
)
def download_all_results(n_clicks, period_filter, enrollee_id, q2_data, auth_data):
    if not auth_data or not auth_data.get("authenticated"):
        return dash.no_update, ""
    if not auth_data.get("username", "").startswith("contact"):
        return dash.no_update, ""
    if not n_clicks:
        return dash.no_update, ""
    
    df = pd.DataFrame(q2_data)
    df['MemberNo'] = df['MemberNo'].astype(str)
    member_df = df[df['MemberNo'] == enrollee_id]
    
    if member_df.empty:
        return dash.no_update, ""
    
    member_rows = member_df.to_dict('records')
    results_dict = list_member_results_by_period(conn_str, 'annual-wellness-results', member_rows, enrollee_id)
    
    if not results_dict:
        return dash.no_update, dbc.Alert("No files to download.", color="warning")
    
    if period_filter == "all":
        all_blobs = []
        for period_blobs in results_dict.values():
            all_blobs.extend(period_blobs)
        blob_names = [b['blob_name'] for b in all_blobs]
    else:
        blob_names = [b['blob_name'] for b in results_dict.get(period_filter, [])]
    
    if not blob_names:
        return dash.no_update, dbc.Alert("No files to download.", color="warning")
    
    if len(blob_names) > 20:
        return dash.no_update, dbc.Alert("Download is too large. Please filter by a specific policy period.", color="danger")
    
    zip_bytes = zip_blobs_to_bytes(conn_str, 'annual-wellness-results', blob_names)
    
    if zip_bytes is None:
        return dash.no_update, dbc.Alert("The ZIP could not be created.", color="danger")
    
    return dcc.send_bytes(zip_bytes, f"{enrollee_id}_wellness_results.zip"), ""


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
            html.H4("Wellness Plans & Benefits", style={"color": "#5B21B6"}),
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
                dbc.Button("Update Member's Wellness Provider", id="plans-change-provider-btn", color="info", className="me-2"),
            ], className="mb-2"),
            html.Div(id="plans-edit-message"),
            html.Div(id="plans-add-message"),
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
            dbc.Modal([
                dbc.ModalHeader("Confirm Delete"),
                dbc.ModalBody("Are you sure you want to delete the selected plan(s)? This action cannot be undone."),
                dbc.ModalFooter([
                    dbc.Button("Yes, Delete", id="plans-delete-confirm-yes", color="danger"),
                    dbc.Button("Cancel", id="plans-delete-confirm-no", color="secondary", className="ms-2"),
                ]),
            ], id="plans-delete-confirm-modal", is_open=False),
            dbc.Modal([
                dbc.ModalHeader("Update Wellness Provider for Member"),
                dbc.ModalBody([
                    dbc.Row([dbc.Col([dbc.Label("Member ID"), dbc.Input(id="plans-change-member-id", type="text", placeholder="Enter Member ID")])]),
                    dbc.Row([dbc.Col([dbc.Label("New Provider"), dcc.Dropdown(id="plans-change-provider-dropdown", placeholder="Select Provider")])]),
                    dbc.Row([dbc.Col([dbc.Label("New Appointment Date"), dcc.DatePickerSingle(id="plans-change-date-picker", placeholder="Select Date")])]),
                    html.Div(id="plans-change-provider-message"),
                ]),
                dbc.ModalFooter([
                    dbc.Button("Submit", id="plans-change-submit-btn", color="primary"),
                    dbc.Button("Close", id="plans-change-close-btn", color="secondary", className="ms-2"),
                ]),
            ], id="plans-change-provider-modal", is_open=False),
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
            html.H4("Wellness Providers", style={"color": "#5B21B6"}),
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
            html.Div(id="services-edit-message"),
            html.Div(id="services-add-message"),
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
            dbc.Modal([
                dbc.ModalHeader("Confirm Delete"),
                dbc.ModalBody("Are you sure you want to delete the selected provider(s)? This action cannot be undone."),
                dbc.ModalFooter([
                    dbc.Button("Yes, Delete", id="services-delete-confirm-yes", color="danger"),
                    dbc.Button("Cancel", id="services-delete-confirm-no", color="secondary", className="ms-2"),
                ]),
            ], id="services-delete-confirm-modal", is_open=False),
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
    Output("services-delete-confirm-modal", "is_open"),
    Input("services-delete-btn",       "n_clicks"),
    Input("services-delete-confirm-yes", "n_clicks"),
    Input("services-delete-confirm-no",  "n_clicks"),
    prevent_initial_call=True,
)
def delete_providers_confirm(delete_clicks, yes_clicks, no_clicks):
    ctx = callback_context
    if not ctx.triggered:
        return False
    triggered_id = ctx.triggered[0]["prop_id"].split(".")[0]
    if triggered_id in ("services-delete-btn"):
        return True
    return False


@callback(
    Output("services-delete-message",  "children"),
    Input("services-delete-confirm-yes", "n_clicks"),
    State("services-providers-table",  "selected_rows"),
    State("services-providers-table",  "data"),
    State("auth-store",                "data"),
    prevent_initial_call=True,
)
def delete_providers(yes_clicks, selected_rows, table_data, auth_data):
    if not auth_data or not auth_data.get("authenticated"):
        return ""
    if auth_data.get("username", "") != "MedicalServices" or not yes_clicks or not selected_rows or not table_data:
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
            cursor.execute("UPDATE demo_Updated_Wellness_Providers SET STATE=?, PROVIDER_NAME=?, ADDRESS=?, PROVIDER=?, Location=? WHERE CODE=?", 
                (state, provider_name, address, provider, location, code))
            conn.commit()
            _log_audit(conn, "demo_Updated_Wellness_Providers", "UPDATE", code, auth_data.get("username"), old_values, new_values)
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
    Output("plans-delete-confirm-modal", "is_open"),
    Input("plans-delete-btn",      "n_clicks"),
    Input("plans-delete-confirm-yes", "n_clicks"),
    Input("plans-delete-confirm-no",  "n_clicks"),
    prevent_initial_call=True,
)
def delete_plans_confirm(delete_clicks, yes_clicks, no_clicks):
    ctx = callback_context
    if not ctx.triggered:
        return False
    triggered_id = ctx.triggered[0]["prop_id"].split(".")[0]
    if triggered_id in ("plans-delete-btn"):
        return True
    return False


@callback(
    Output("plans-change-provider-modal", "is_open"),
    Output("plans-change-provider-dropdown", "options"),
    Input("plans-change-provider-btn", "n_clicks"),
    Input("plans-change-close-btn", "n_clicks"),
    State("store-q3", "data"),
    prevent_initial_call=True,
)
def open_change_provider_modal(btn_clicks, close_clicks, q3_data):
    ctx = callback_context
    if not ctx.triggered:
        return False, []
    triggered_id = ctx.triggered[0]["prop_id"].split(".")[0]
    if triggered_id == "plans-change-close-btn":
        return False, []
    if q3_data:
        df = pd.DataFrame(q3_data)
        options = [{"label": p, "value": p} for p in sorted(df['PROVIDER'].dropna().unique())]
    else:
        options = []
    return True, options


@callback(
    Output("plans-change-provider-message", "children"),
    Input("plans-change-submit-btn", "n_clicks"),
    State("plans-change-member-id", "value"),
    State("plans-change-provider-dropdown", "value"),
    State("plans-change-date-picker", "date"),
    State("auth-store", "data"),
    prevent_initial_call=True,
)
def update_member_provider(submit_clicks, member_id, new_provider, new_date, auth_data):
    if not auth_data or not auth_data.get("authenticated"):
        return ""
    if auth_data.get("username", "") != "ClientServices" or not submit_clicks or not member_id or not new_provider or not new_date:
        return dbc.Alert("Please fill in all fields.", color="warning")
    email_warning = ""
    try:
        conn = engine.raw_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT selected_provider, selected_date, IssuedPACode FROM demo_tbl_annual_wellness_enrollee_data WHERE MemberNo = ?", (member_id,))
            row = cursor.fetchone()
            if not row:
                return dbc.Alert("Member not found.", color="danger")
            old_provider = row[0]
            old_date = row[1]
            current_pa_code = row[2] if len(row) > 2 else None
            cursor.execute(
                "UPDATE demo_tbl_annual_wellness_enrollee_data SET selected_provider = ?, selected_date = ? WHERE MemberNo = ?",
                (new_provider, new_date, member_id)
            )
            _log_audit(conn, "demo_tbl_annual_wellness_enrollee_data", "UPDATE", member_id, auth_data.get("username"),
                       {"selected_provider": old_provider, "selected_date": str(old_date)},
                       {"selected_provider": new_provider, "selected_date": new_date})
            conn.commit()

            sender_email = 'noreply@avonhealthcare.com'
            email_password = os.environ.get('email_password')
            recipient_email = 'ifeoluwa.adeniyi@avonhealthcare.com'

            pa_code_display = current_pa_code if current_pa_code and str(current_pa_code).strip() else "None issued"

            body = f"""
            <html>
            <body>
            <p>Dear Client Services Team,</p>
            <p>The wellness provider for the following member has been changed:</p>
            <table style="border-collapse: collapse; width: 100%; max-width: 500px; margin-top: 10px;">
                <tr style="background-color: #59058D; color: white;">
                    <th style="border: 1px solid #ddd; padding: 8px; text-align: left;">Field</th>
                    <th style="border: 1px solid #ddd; padding: 8px; text-align: left;">Details</th>
                </tr>
                <tr>
                    <td style="border: 1px solid #ddd; padding: 8px; font-weight: 600;">Member ID</td>
                    <td style="border: 1px solid #ddd; padding: 8px;">{member_id}</td>
                </tr>
                <tr style="background-color: #f9f9f9;">
                    <td style="border: 1px solid #ddd; padding: 8px; font-weight: 600;">Old Provider</td>
                    <td style="border: 1px solid #ddd; padding: 8px;">{old_provider or 'N/A'}</td>
                </tr>
                <tr>
                    <td style="border: 1px solid #ddd; padding: 8px; font-weight: 600;">New Provider</td>
                    <td style="border: 1px solid #ddd; padding: 8px;">{new_provider}</td>
                </tr>
                <tr style="background-color: #f9f9f9;">
                    <td style="border: 1px solid #ddd; padding: 8px; font-weight: 600;">Current PA Code</td>
                    <td style="border: 1px solid #ddd; padding: 8px;">{pa_code_display}</td>
                </tr>
            </table>
            <p style="margin-top: 15px;"><strong>ACTION REQUIRED:</strong> The existing PA code has been revoked. Please issue a new PA code to the member for the new provider.</p>
            <p>Regards,<br>Wellness Portal System</p>
            </body>
            </html>
            """

            try:
                s = smtplib.SMTP('smtp.office365.com', 587)
                s.starttls()
                s.login(sender_email, email_password)
                msg = MIMEMultipart()
                msg['From'] = 'AVON HMO Wellness Portal'
                msg['To'] = recipient_email
                msg['Subject'] = 'WELLNESS PROVIDER CHANGE — PA CODE ACTION REQUIRED'
                msg.attach(MIMEText(body, 'html'))
                s.sendmail(sender_email, [recipient_email], msg.as_string())
                s.quit()
            except Exception as email_err:
                email_warning = " (Note: notification email failed to send.)"
                print(f"Email error: {email_err}")

        finally:
            conn.close()
        invalidate_cache()
        return dbc.Alert("Provider updated successfully!" + email_warning, color="success")
    except Exception as e:
        return dbc.Alert(f"Error updating provider: {e}", color="danger")


@callback(
    Output("plans-delete-message", "children"),
    Input("plans-delete-confirm-yes", "n_clicks"),
    State("services-plans-table",  "selected_rows"),
    State("services-plans-table",  "data"),
    State("auth-store",            "data"),
    prevent_initial_call=True,
)
def delete_plans(yes_clicks, selected_rows, table_data, auth_data):
    if not auth_data or not auth_data.get("authenticated"):
        return ""
    if auth_data.get("username", "") != "ClientServices" or not yes_clicks or not selected_rows or not table_data:
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
            cursor.execute("UPDATE demo_Wellness_Plans_and_Benefits SET CLIENT_NAME=?, CLIENT_PLAN=?, CUSTOMIZATION=?, WELLNESS_BENEFITS=? WHERE PolicyNo=?", 
                (client_name, client_plan, customization, wellness_benefits, policy_no))
            conn.commit()
            _log_audit(conn, "demo_Wellness_Plans_and_Benefits", "UPDATE", policy_no, auth_data.get("username"), old_values, new_values)
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