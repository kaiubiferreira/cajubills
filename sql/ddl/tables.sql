use finance;

CREATE TABLE fixed_income (
    purchase_id INTEGER PRIMARY KEY AUTO_INCREMENT,
	asset VARCHAR(50),
	purchaseDate DATE,
	dueDate DATE,
	financialIndex VARCHAR(50),
	value DOUBLE,
	preRate DOUBLE,
	postRate DOUBLE
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


INSERT INTO asset_price ap(ticker, quote_date, open_price, close_price)
VALUES
(
("NU", "2020-04-01", 1.7354,  1.7354)
("NU", "2020-07-01", 1.7883,  1.7883)
("NU", "2020-10-01", 1.7883,  1.7883)
("NU", "2021-01-01", 3.9783,  3.9783)
("NU", "2021-04-01", 3.9783,  3.9783)
("NU", "2021-07-01", 4.5283,  4.5283)
("NU", "2021-10-01", 4.5283,  4.5283)
)
