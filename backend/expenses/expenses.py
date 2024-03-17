from os import listdir

import pandas as pd
from ofxparse import OfxParser
from toolz import thread_first

from backend.utils.constants import CREDIT_CARD_OFX_PATH, NUCONTA_OFX_PATH


def is_ofx_filename(filename):
    if '.' in filename:
        extension = str.split(filename, '.')[1]
        return extension == 'ofx'

    return False


def get_ofx_files(files_path=CREDIT_CARD_OFX_PATH):
    return [str(files_path.joinpath(f)) for f in listdir(files_path) if is_ofx_filename(f)]


def parse_ofx_files(files):
    parsed = []
    for file_path in files:
        with open(file_path, encoding='latin-1') as f:
            parsed.append(OfxParser.parse(f))

    return parsed


def get_transactions(ofx):
    if ofx.account is None:
        raise Exception('Account key missing')

    if ofx.account.statement is None:
        raise Exception('Statement key missing')

    if ofx.account.statement.transactions is None:
        raise Exception('Transactions key missing')

    return ofx.account.statement.transactions


def parse_transaction(transaction):
    return [transaction.id, transaction.date, transaction.type, transaction.amount, transaction.memo]


def ofx_to_pandas(ofx_list):
    column_names = ['ofx_id', 'data', 'tipo', 'valor', 'descricao']
    transactions = [parse_transaction(transaction) for ofx in ofx_list for transaction in get_transactions(ofx)]
    return pd.DataFrame(data=transactions, columns=column_names)


def cast_date(df):
    df['data'] = pd.to_datetime(df['data'].dt.date)
    return df


def cast_value(df):
    df['valor'] = abs(df['valor'].astype(float))
    return df


def project_columns(df):
    return df[['ofx_id', 'data', 'tipo', 'valor', 'descricao']]


def get_ofx_dataframe(files_path):
    df = thread_first(
        files_path,
        get_ofx_files,
        parse_ofx_files,
        ofx_to_pandas,
        cast_date,
        cast_value,
        project_columns
    ).drop_duplicates()

    return df


def get_credit_card_dataframe():
    df = get_ofx_dataframe(CREDIT_CARD_OFX_PATH)
    df['pgto'] = 'CC'
    return df


def get_debit_dataframe():
    df = get_ofx_dataframe(NUCONTA_OFX_PATH)
    df['pgto'] = 'DB'
    return df


def get_dataframes():
    return pd.concat([get_credit_card_dataframe(), get_debit_dataframe()])

def run_ofx_parser():
    print('run_ofx_parser...')
    df = get_dataframes()
    print(df.show())
