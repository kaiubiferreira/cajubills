use finance;

DROP TABLE fixed_income_operations ;
CREATE TABLE fixed_income_operations (
	asset VARCHAR(50),
	operation_type VARCHAR(50),
	quotas DOUBLE,
	purchase_date DATE,
	due_date DATE,
	financial_index VARCHAR(50),
	value DOUBLE,
	pre_rate DOUBLE,
	post_rate DOUBLE,
	tax_rate DOUBLE,
	is_pgbl BOOL,
	PRIMARY KEY (asset, purchase_date, operation_type, due_date, financial_index)
)

DROP TABLE variable_income_operations;
CREATE TABLE variable_income_operations (
  ticker varchar(50) NOT NULL,
  operation_type varchar(10) NOT NULL,
  operation_date date NOT NULL,
  amount double NOT NULL,
  price double NOT NULL,
  currency varchar(50) DEFAULT NULL,
  PRIMARY KEY (ticker, operation_type, operation_date, amount, price)
)

DROP TABLE asset_price;
CREATE TABLE asset_price (
    ticker VARCHAR(50),
    quote_date DATE,
    open_price DOUBLE,
    close_price DOUBLE,
    PRIMARY KEY (ticker, quote_date)
)

DROP TABLE daily_asset_price;
CREATE TABLE daily_asset_price (
    ticker VARCHAR(50),
    date DATE,
    price DOUBLE,
    PRIMARY KEY (ticker, date)
)

DROP TABLE dates;
CREATE TABLE dates (
    date DATE,
    PRIMARY KEY (date)
)

DROP TABLE variable_income_daily_balance;
CREATE TABLE variable_income_daily_balance (
  ticker varchar(50) NOT NULL,
  date DATE NOT NULL,
  price double NOT NULL,
  dolar_price double NOT NULL,
  currency varchar(50) DEFAULT NULL,
  amount_change double,
  amount double,
  value double,
  PRIMARY KEY (ticker, date)
)

CREATE TABLE index_series(
    financial_index varchar(30),
    date DATE,
    factor DOUBLE,
    PRIMARY KEY (financial_index, date)
);

DROP TABLE fixed_income_daily_balance ;
CREATE TABLE fixed_income_daily_balance (
	asset VARCHAR(50),
	due_date DATE,
	date DATE,
	tax_rate DOUBLE,
	deposit_value DOUBLE,
	gross_value DOUBLE,
	tax_value DOUBLE,
	net_value DOUBLE,
	PRIMARY KEY (asset, due_date, date)
)

DROP TABLE daily_balance ;
CREATE TABLE daily_balance (
	asset VARCHAR(50),
	date DATE,
	value DOUBLE,
	type VARCHAR(50),
	PRIMARY KEY (asset, type, date)
)

DROP TABLE fgts_operations;
CREATE TABLE fgts_operations (
    date DATE,
    company VARCHAR(50),
    operation VARCHAR(50),
    value DOUBLE,
    balance DOUBLE,
    PRIMARY KEY (date, company, operation)
)

DROP TABLE fgts_daily_balance;
CREATE TABLE fgts_daily_balance (
    date DATE,
    balance DOUBLE,
    PRIMARY KEY (date)
)

DROP TABLE operations;
CREATE TABLE operations (
 asset VARCHAR(50),
 operation_type VARCHAR(50),
 operation_date DATE,
 value DOUBLE,
 currency VARCHAR(50),
 dolar_price DOUBLE
)

DROP TABLE financial_returns;
CREATE TABLE financial_returns(
    asset VARCHAR(50),
    year  int,
    month int,
    month_start_value DOUBLE,
    month_end_value DOUBLE,
    deposit DOUBLE,
    net_increase DOUBLE,
    profit DOUBLE,
    relative_return DOUBLE,
    PRIMARY KEY (asset, year, month)
)

DROP TABLE summary_returns;
CREATE TABLE summary_returns(
    year  int,
    month int,
    month_end_value DOUBLE,
    total_deposit DOUBLE,
    total_profit DOUBLE,
    total_return DOUBLE,
    moving_avg_deposit_3 DOUBLE,
    moving_avg_profit_3 DOUBLE,
    moving_avg_return_3 DOUBLE,
    moving_avg_deposit_6 DOUBLE,
    moving_avg_profit_6 DOUBLE,
    moving_avg_return_6 DOUBLE,
    moving_avg_deposit_9 DOUBLE,
    moving_avg_profit_9 DOUBLE,
    moving_avg_return_9 DOUBLE,
    moving_avg_deposit_12 DOUBLE,
    moving_avg_profit_12 DOUBLE,
    moving_avg_return_12 DOUBLE,
    PRIMARY KEY (year, month)
)

DROP TABLE target_percentage;
CREATE TABLE target_percentage(
    name VARCHAR(50),
    percentage DOUBLE,
    PRIMARY KEY (name)
)
