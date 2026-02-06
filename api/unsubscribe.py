from http.server import BaseHTTPRequestHandler
import json
import os
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

            sheet.update_cell(row_num, 6, 'unsubscribed')

            self.send_response(302)
            self.send_header('Location', f'{DASHBOARD_URL}/unsubscribe-success.html')
            self.end_headers()

        except Exception as e:
            print(f"Error: {e}")
            self.send_response(302)
            self.send_header('Location', f'{DASHBOARD_URL}/unsubscribe-success.html')
            self.end_headers()
