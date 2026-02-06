from http.server import BaseHTTPRequestHandler
import json
import os
from datetime import datetime
from urllib.parse import parse_qs, urlparse
import gspread
from oauth2client.service_account import ServiceAccountCredentials

GOOGLE_SHEETS_CREDENTIALS = os.environ.get('GOOGLE_SHEETS_CREDENTIALS')
SHEET_ID = os.environ.get('SHEET_ID')
DASHBOARD_URL = 'https://shram.info'


def get_sheets_client():
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds_dict = json.loads(GOOGLE_SHEETS_CREDENTIALS)
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    return gspread.authorize(creds)


def log_subscriber_activity(client, action, email, details=None):
    """Log subscriber activity to Activity Log sheet."""
    try:
        spreadsheet = client.open_by_key(SHEET_ID)
        try:
            log_sheet = spreadsheet.worksheet('Activity Log')
        except:
            log_sheet = spreadsheet.add_worksheet(title='Activity Log', rows=1000, cols=10)
            log_sheet.append_row(['timestamp', 'action', 'email', 'details', 'ip_address'])

        now = datetime.utcnow().isoformat() + 'Z'
        details_str = json.dumps(details) if details else ''
        log_sheet.append_row([now, action, email, details_str, ''])
    except Exception as e:
        print(f"Warning: Could not log activity: {e}")


def find_subscriber_by_token(sheet, token):
    try:
        records = sheet.get_all_records()
        for i, record in enumerate(records):
            if record.get('verification_token') == token:
                return i + 2, record
        return None, None
    except:
        return None, None


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            parsed = urlparse(self.path)
            params = parse_qs(parsed.query)
            token = params.get('token', [None])[0]

            if not token:
                self.send_response(302)
                self.send_header('Location', f'{DASHBOARD_URL}/unsubscribe-success.html')
                self.end_headers()
                return

            client = get_sheets_client()
            sheet = client.open_by_key(SHEET_ID).sheet1
            row_num, subscriber = find_subscriber_by_token(sheet, token)

            if not subscriber or subscriber.get('status') == 'unsubscribed':
                self.send_response(302)
                self.send_header('Location', f'{DASHBOARD_URL}/unsubscribe-success.html')
                self.end_headers()
                return

            # Column 11 = status
            # Columns: email, name, phone, districts, met_levels, alert_zones, sun_shade, receive_forecasts, receive_sms, verification_token, status, subscribed_at, verified_at, last_alert_sent
            sheet.update_cell(row_num, 11, 'unsubscribed')

            # Log the unsubscribe
            log_subscriber_activity(client, 'unsubscribed', subscriber.get('email', ''))

            self.send_response(302)
            self.send_header('Location', f'{DASHBOARD_URL}/unsubscribe-success.html')
            self.end_headers()

        except Exception as e:
            print(f"Error: {e}")
            self.send_response(302)
            self.send_header('Location', f'{DASHBOARD_URL}/unsubscribe-success.html')
            self.end_headers()
