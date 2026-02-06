"""
Vercel Serverless Function: Handle unsubscribe requests

Endpoint: GET /api/unsubscribe?token=<uuid>

Actions:
1. Look up token in Google Sheets
2. Mark as unsubscribed (or delete row)
3. Redirect to confirmation page
"""

import json
import os
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
                    'Location': f'{DASHBOARD_URL}/unsubscribe-error.html?reason=missing_token'
                }
            }

        # Connect to Google Sheets
        client = get_sheets_client()
        sheet = client.open_by_key(SHEET_ID).sheet1

        # Find subscriber by token
        row_num, subscriber = find_subscriber_by_token(sheet, token)

        if not subscriber:
            # Token not found - might already be unsubscribed
            return {
                'statusCode': 302,
                'headers': {
                    'Location': f'{DASHBOARD_URL}/unsubscribe-success.html?already=true'
                }
            }

        # Check if already unsubscribed
        if subscriber.get('status') == 'unsubscribed':
            return {
                'statusCode': 302,
                'headers': {
                    'Location': f'{DASHBOARD_URL}/unsubscribe-success.html?already=true'
                }
            }

        # Mark as unsubscribed (keeping record for audit trail)
        sheet.update_cell(row_num, 6, 'unsubscribed')  # status column

        return {
            'statusCode': 302,
            'headers': {
                'Location': f'{DASHBOARD_URL}/unsubscribe-success.html'
            }
        }

    except Exception as e:
        print(f"Unsubscribe error: {e}")
        return {
            'statusCode': 302,
            'headers': {
                'Location': f'{DASHBOARD_URL}/unsubscribe-error.html?reason=error'
            }
        }
