
import os
from datetime import datetime

import gspread
import requests
from dotenv import load_dotenv
from google.oauth2.service_account import Credentials

# -----------------------------------
# LOAD ENV VARIABLES
# -----------------------------------

load_dotenv()

SPREADSHEET_ID = os.getenv("GOOGLE_SHEET_ID")
WORKSHEET_NAME = os.getenv("GOOGLE_WORKSHEET_NAME")
GOOGLE_CREDENTIALS = os.getenv("GOOGLE_CREDENTIALS")

# -----------------------------------
# CONFIG
# -----------------------------------

TIMEOUT = 8

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

# -----------------------------------
# GOOGLE AUTH
# -----------------------------------

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets"
]

creds = Credentials.from_service_account_file(
    GOOGLE_CREDENTIALS,
    scopes=SCOPES
)

client = gspread.authorize(creds)

spreadsheet = client.open_by_key(SPREADSHEET_ID)

worksheet = spreadsheet.worksheet(WORKSHEET_NAME)

# -----------------------------------
# GET ALL DATA
# -----------------------------------

rows = worksheet.get_all_records()

headers = worksheet.row_values(1)

# -----------------------------------
# ENSURE site_status COLUMN EXISTS
# -----------------------------------

if "site_status" not in headers:
    worksheet.update_cell(1, len(headers) + 1, "site_status")
    headers.append("site_status")

if "last_checked" not in headers:
    worksheet.update_cell(1, len(headers) + 1, "last_checked")
    headers.append("last_checked")

# Refresh headers
headers = worksheet.row_values(1)

# Get column indexes
web_address_col = headers.index("Web Address") + 1
status_col = headers.index("site_status") + 1
checked_col = headers.index("last_checked") + 1

# -----------------------------------
# WEBSITE CHECKER
# -----------------------------------

def normalize_url(url):
    url = str(url).strip()

    if not url:
        return None

    if not url.startswith("http://") and not url.startswith("https://"):
        url = "https://" + url

    return url


def check_website(url):
    try:
        response = requests.get(
            url,
            headers=HEADERS,
            timeout=TIMEOUT,
            allow_redirects=True
        )

        status_code = response.status_code

        # Active website
        if 200 <= status_code < 400:
            return "active"

        # Still exists but protected
        if status_code in [401, 403]:
            return "active"

        return "inactive"

    except requests.exceptions.RequestException:
        return "inactive"

# -----------------------------------
# LOOP THROUGH ROWS
# -----------------------------------

for row_index, row in enumerate(rows, start=2):

    raw_url = row.get("Web Address")

    url = normalize_url(raw_url)

    if not url:
        print(f"Row {row_index}: Missing URL")
        continue

    print(f"Checking: {url}")

    status = check_website(url)

    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Update Google Sheet
    worksheet.update_cell(row_index, status_col, status)
    worksheet.update_cell(row_index, checked_col, current_time)

    print(f"{url} -> {status}")

print("Done.")

