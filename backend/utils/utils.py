from datetime import datetime

import pandas as pd

def parse_date(date):
    formats = ['%Y-%m-%d %H:%M:%S', '%d/%m/%Y %H:%M:%S', '%d/%m/%Y']
    for date_format in formats:
        try:
            return datetime.strptime(date[:19], date_format)
        except:
            pass

    raise Exception(f'Could not parse {date} to formats {formats}')


def parse_float(value):
    value = value.lower().replace('r$', '').strip()
    if '.' in value and ',' in value:
        if value.index('.') < value.index(','):
            return float(value.replace('.', '').replace(',', '.'))
        else:
            return float(value.replace(',', ''))

    elif ',' in value:
        return float(value.replace(',', '.'))

    else:
        return float(value)


def add_hash_id(df, columns=None):
    if not columns:
        columns = df.columns

    df['hash_id'] = df[columns].apply(lambda r: hash(','.join([str(r[c]) for c in columns])), axis=1)
    return df


def coalesce(s, *series):
    """coalesce the column information like a SQL coalesce."""
    for other in series:
        s = s.mask(pd.isnull, other)
    return s
