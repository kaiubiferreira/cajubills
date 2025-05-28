import os

import gspread
from cachetools import TTLCache
from cachetools import cached
from oauth2client.service_account import ServiceAccountCredentials

from backend.investments.contants import *

cache = TTLCache(maxsize=1, ttl=3600)  # Cache can hold 1 item, expires after 1 hour


@cached(cache)
def connect():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    current_dir = os.path.dirname(os.path.abspath(__file__))  # Path to the directory of the current script
    key_file_path = os.path.join(current_dir, '../../..', 'resources', 'google_sheets_key.json')
    creds = ServiceAccountCredentials.from_json_keyfile_name(key_file_path, scope)
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


def get_fixed_income():
    sheet = get_sheet(FIXED_INCOME_SHEET)
    data = sheet.get_all_records()

    data_tuple = [
        (d['asset'],
         d['operation_type'],
         str(d['quotas']),
         d['purchase_date'],
         d['due_date'],
         d['financial_index'],
         str(d['value']),
         str(d['pre_rate']),
         str(d['post_rate']),
         str(d['tax_rate']),
         str(d['is_pgbl'])) for d in data]

    return data_tuple


def get_fgts():
    sheet = get_sheet(FGTS_SHEET)
    data = sheet.get_all_records()

    data_tuple = [
        (d['date'],
         d['company'],
         d['operation'],
         str(d['value']),
         str(d['balance'])) for d in data]

    return data_tuple


def get_cdi():
    sheet = get_sheet(CDI_SHEET)
    data = sheet.get_all_records()

    data_tuple = [
        (d['financial_index'],
         d['date'],
         str(d['daily_factor'])) for d in data]

    return data_tuple


def get_ipca():
    sheet = get_sheet(IPCA_SHEET)
    data = sheet.get_all_records()

    data_tuple = [
        (d['index'],
         d['date'],
         str(d['ipca'])) for d in data]

    return data_tuple


def get_target():
    sheet = get_sheet(TARGET_SHEET)
    data = sheet.get_all_records()

    data_tuple = [
        (d['name'],
         str(d['percentage'])) for d in data]

    return data_tuple

