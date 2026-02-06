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
                self.send_header('Location', f'{DASHBOARD_URL}/verify-error.html?reason=missing')
                self.end_headers()
                return

            client = get_sheets_client()
            sheet = client.open_by_key(SHEET_ID).sheet1
            row_num, subscriber = find_subscriber_by_token(sheet, token)

            if not subscriber:
                self.send_response(302)
                self.send_header('Location', f'{DASHBOARD_URL}/verify-error.html?reason=invalid')
                self.end_headers()
                return

            if subscriber.get('status') == 'verified':
                self.send_response(302)
                self.send_header('Location', f'{DASHBOARD_URL}/verify-success.html?already=true')
                self.end_headers()
                return

            now = datetime.utcnow().isoformat() + 'Z'
            sheet.update_cell(row_num, 6, 'verified')
            sheet.update_cell(row_num, 8, now)

            self.send_response(302)
            self.send_header('Location', f'{DASHBOARD_URL}/verify-success.html')
            self.end_headers()

        except Exception as e:
            print(f"Error: {e}")
            self.send_response(302)
            self.send_header('Location', f'{DASHBOARD_URL}/verify-error.html?reason=error')
            self.end_headers()
