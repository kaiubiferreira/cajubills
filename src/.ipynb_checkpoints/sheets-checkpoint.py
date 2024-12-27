import gspread
from oauth2client.service_account import ServiceAccountCredentials

from src.contants import *


def connect():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name("resources/google_sheets_key.json", scope)
    client = gspread.authorize(creds)

    return client


def get_sheet(sheet_name):
    client = connect()
    spreadsheet = client.open(SPREADSHEET_NAME)
    sheet = spreadsheet.worksheet(sheet_name)
    return sheet


def get_stock():
    sheet = get_sheet(STOCK_SHEET)
    data = sheet.get_all_records()
    data_tuple = [
        (d['ticker'],
         d['operation_type'],
         d['operation_date'],
         str(d['amount']),
         str(d['price']),
         d['currency']) for d
        in data]

    return data_tuple
