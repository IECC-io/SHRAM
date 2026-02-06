from flask import Flask, request, redirect
import json
import os
import gspread
from oauth2client.service_account import ServiceAccountCredentials

app = Flask(__name__)

GOOGLE_SHEETS_CREDENTIALS = os.environ.get('GOOGLE_SHEETS_CREDENTIALS')
SHEET_ID = os.environ.get('SHEET_ID')
DASHBOARD_URL = 'https://shram.info'


def get_sheets_client():
    scope = [
        'https://spreadsheets.google.com/feeds',
        'https://www.googleapis.com/auth/drive'
    ]
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
    except Exception as e:
        print(f"Error finding subscriber: {e}")
        return None, None


@app.route('/api/unsubscribe', methods=['GET'])
def unsubscribe():
    try:
        token = request.args.get('token')

        if not token:
            return redirect(f'{DASHBOARD_URL}/unsubscribe-error.html?reason=missing_token')

        client = get_sheets_client()
        sheet = client.open_by_key(SHEET_ID).sheet1

        row_num, subscriber = find_subscriber_by_token(sheet, token)

        if not subscriber:
            return redirect(f'{DASHBOARD_URL}/unsubscribe-success.html?already=true')

        if subscriber.get('status') == 'unsubscribed':
            return redirect(f'{DASHBOARD_URL}/unsubscribe-success.html?already=true')

        sheet.update_cell(row_num, 6, 'unsubscribed')

        return redirect(f'{DASHBOARD_URL}/unsubscribe-success.html')

    except Exception as e:
        print(f"Unsubscribe error: {e}")
        return redirect(f'{DASHBOARD_URL}/unsubscribe-error.html?reason=error')
