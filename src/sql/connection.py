import mysql.connector
import pandas as pd
from sqlalchemy import create_engine


def db_connect():
    host = "finance.cvm2aaxkmu43.us-east-2.rds.amazonaws.com"
    user = "admin"
    password = "Nk7f4mJr6?A"
    database = "finance"

    conn = mysql.connector.connect(
        host=host,
        user=user,
        password=password,
        database=database
    )

    return conn


def db_connect_alchemy():
    host = "finance.cvm2aaxkmu43.us-east-2.rds.amazonaws.com"
    user = "admin"
    password = "Nk7f4mJr6?A"
    database = "finance"

    # Create a connection string
    connection_string = f'mysql+mysqlconnector://{user}:{password}@{host}/{database}'

    # Create the database engine
    engine = create_engine(connection_string)
    return engine


def run_query(query):
    conn = db_connect()
    df = pd.read_sql(query, conn)
    conn.close()
    return df
