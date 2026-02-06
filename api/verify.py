"""
Vercel Serverless Function: Handle email verification

Endpoint: GET /api/verify?token=<uuid>

Actions:
1. Look up token in Google Sheets
2. Update status to "verified"
3. Redirect to success page
"""

import json
import os
from datetime import datetime
from urllib.parse import parse_qs, urlparse
import gspread
from oauth2client.service_account import ServiceAccountCredentials


# Configuration from environment variables
GOOGLE_SHEETS_CREDENTIALS = os.environ.get('GOOGLE_SHEETS_CREDENTIALS')
SHEET_ID = os.environ.get('SHEET_ID')
DASHBOARD_URL = 'https://shram.info'


def get_sheets_client():
    """Initialize Google Sheets client."""
    scope = [
        'https://spreadsheets.google.com/feeds',
        'https://www.googleapis.com/auth/drive'
    ]
    creds_dict = json.loads(GOOGLE_SHEETS_CREDENTIALS)
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    return gspread.authorize(creds)


def find_subscriber_by_token(sheet, token):
    """Find subscriber row by verification token."""
    try:
        records = sheet.get_all_records()
        for i, record in enumerate(records):
            if record.get('verification_token') == token:
                return i + 2, record  # +2 for header row and 1-indexing
        return None, None
    except Exception as e:
        print(f"Error finding subscriber: {e}")
        return None, None


def handler(request):
    """Vercel serverless function handler."""
    try:
        # Parse query parameters from the request URL
        url = request.url if hasattr(request, 'url') else request.path
        parsed_url = urlparse(url)
        query_params = parse_qs(parsed_url.query)

        # Also check request.query for Vercel's parsed query params
        if hasattr(request, 'query') and request.query:
            token = request.query.get('token')
        else:
            token = query_params.get('token', [None])[0]

        if not token:
            return {
                'statusCode': 302,
                'headers': {
                    'Location': f'{DASHBOARD_URL}/verify-error.html?reason=missing_token'
                }
            }

        # Connect to Google Sheets
        client = get_sheets_client()
        sheet = client.open_by_key(SHEET_ID).sheet1

        # Find subscriber by token
        row_num, subscriber = find_subscriber_by_token(sheet, token)

        if not subscriber:
            return {
                'statusCode': 302,
                'headers': {
                    'Location': f'{DASHBOARD_URL}/verify-error.html?reason=invalid_token'
                }
            }

        # Check if already verified
        if subscriber.get('status') == 'verified':
            return {
                'statusCode': 302,
                'headers': {
                    'Location': f'{DASHBOARD_URL}/verify-success.html?already=true'
                }
            }

        # Update status to verified
        # Columns: email(A), name(B), districts(C), receive_forecasts(D),
        #          verification_token(E), status(F), subscribed_at(G), verified_at(H), last_alert_sent(I)
        now = datetime.utcnow().isoformat() + 'Z'

        # Update status (column F) and verified_at (column H)
        sheet.update_cell(row_num, 6, 'verified')  # status
        sheet.update_cell(row_num, 8, now)  # verified_at

        return {
            'statusCode': 302,
            'headers': {
                'Location': f'{DASHBOARD_URL}/verify-success.html'
            }
        }

    except Exception as e:
        print(f"Verification error: {e}")
        return {
            'statusCode': 302,
            'headers': {
                'Location': f'{DASHBOARD_URL}/verify-error.html?reason=error'
            }
        }
