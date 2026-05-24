
import os
import asyncio
from datetime import datetime

import gspread
import httpx
from dotenv import load_dotenv
from google.oauth2.service_account import Credentials

# -----------------------------------
# CONFIG
# -----------------------------------

load_dotenv()

SPREADSHEET_ID = os.getenv("GOOGLE_SHEET_ID")
WORKSHEET_NAME = os.getenv("GOOGLE_WORKSHEET_NAME")
GOOGLE_CREDENTIALS = os.getenv("GOOGLE_CREDENTIALS")

TIMEOUT = 8
CONCURRENCY = 25  # adjust based on machine/network

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

# -----------------------------------
# GOOGLE AUTH
# -----------------------------------

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

creds = Credentials.from_service_account_file(
    GOOGLE_CREDENTIALS,
    scopes=SCOPES
)

client = gspread.authorize(creds)

spreadsheet = client.open_by_key(SPREADSHEET_ID)
worksheet = spreadsheet.worksheet(WORKSHEET_NAME)

# -----------------------------------
# LOAD DATA
# -----------------------------------

rows = worksheet.get_all_records()
headers = worksheet.row_values(1)

def ensure_column(name):
    if name not in headers:
        worksheet.update_cell(1, len(headers) + 1, name)
        headers.append(name)

ensure_column("site_status")
ensure_column("last_checked")

headers = worksheet.row_values(1)

url_col = headers.index("Web Address")
status_col = headers.index("site_status")
checked_col = headers.index("last_checked")

# -----------------------------------
# HELPERS
# -----------------------------------

def normalize_url(url):
    if not url:
        return None

    url = str(url).strip()

    if not url.startswith("http"):
        url = "https://" + url

    return url


async def check_site(client, url):
    try:
        r = await client.get(url, timeout=TIMEOUT)

        if 200 <= r.status_code < 400:
            return "active"

        if r.status_code in [401, 403]:
            return "active"

        return "inactive"

    except Exception:
        return "inactive"


# -----------------------------------
# PROCESS BATCH WITH CONCURRENCY
# -----------------------------------

async def process_sites(urls):
    semaphore = asyncio.Semaphore(CONCURRENCY)

    async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True) as http:

        async def bound_check(url):
            async with semaphore:
                return await check_site(http, url)

        tasks = [bound_check(url) for url in urls]
        return await asyncio.gather(*tasks)


# -----------------------------------
# MAIN FLOW
# -----------------------------------

urls = []
row_map = []

for i, row in enumerate(rows, start=2):
    url = normalize_url(row.get("Web Address"))

    if not url:
        continue

    urls.append(url)
    row_map.append(i)

print(f"Checking {len(urls)} websites...")

results = asyncio.run(process_sites(urls))

timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# -----------------------------------
# BATCH UPDATE PREPARATION
# -----------------------------------

status_updates = []
time_updates = []

for status in results:
    status_updates.append([status])
    time_updates.append([timestamp])

# -----------------------------------
# SINGLE BATCH WRITE (FAST PART)
# -----------------------------------

status_range = f"{gspread.utils.rowcol_to_a1(2, status_col + 1)}:{gspread.utils.rowcol_to_a1(len(results)+1, status_col + 1)}"
time_range = f"{gspread.utils.rowcol_to_a1(2, checked_col + 1)}:{gspread.utils.rowcol_to_a1(len(results)+1, checked_col + 1)}"

worksheet.update(status_range, status_updates)
worksheet.update(time_range, time_updates)

print("Done.")
