from datetime import date, datetime

NU_PRICES = [
    ("NU", date(2020, 4, 1), 1.7354, 1.7354),
    ("NU", date(2020, 7, 1), 1.7883, 1.7883),
    ("NU", date(2020, 10, 1), 1.7883, 1.7883),
    ("NU", date(2021, 1, 1), 3.9783, 3.9783),
    ("NU", date(2021, 4, 1), 3.9783, 3.9783),
    ("NU", date(2021, 7, 1), 4.5283, 4.5283),
    ("NU", date(2021, 10, 1), 4.5283, 4.5283)
]

SPREADSHEET_NAME = "RSU + ETF"
STOCK_SHEET = "01 - Stock Trade"
FIXED_INCOME_SHEET = "02 - Fixed Income"
FGTS_SHEET = "03 - FGTS"
CDI_SHEET = "04 - CDI"
IPCA_SHEET = "05 - IPCA"
TARGET_SHEET = "06 - Target"
FIXED_INCOME_TARGET = 30
EQUITY_TARGET = 70
BIRTH_DATE = datetime(1993, 9, 1) 