import glob
import os

import pandas as pd
from ofxparse import OfxParser

from .categorization_rules import CATEGORIZATION_RULES  # Import the rules
from sql.connection import db_connect # Corrected import: removed 'src.'

# Define column names for consistency (can be shared or defined where needed)
COLUMN_ID = 'id'
COLUMN_DATE = 'date'
COLUMN_TYPE = 'type'
COLUMN_AMOUNT = 'amount'
COLUMN_MEMO = 'memo'
COLUMN_ACCOUNT_TYPE = 'account_type'  # Kept for categorization logic
COLUMN_MAIN_CATEGORY = 'main_category'
COLUMN_SUB_CATEGORY = 'sub_category'


# COLUMN_ACCOUNT_TYPE = 'account_type' # This might be added by the caller if needed

def _correct_ofx_char_encoding(text: str) -> str:
    """
    Attempts to correct a common character encoding issue found in OFX files
    where text intended as UTF-8 (e.g., "Crédito") is misinterpreted due to
    an incorrect 'cp1252' (Windows-1252) decoding, resulting in mojibake
    (e.g., "CrÃ©dito").
    """
    if not text:
        return text
    try:
        # Attempt to reverse the incorrect cp1252 decoding then decode as UTF-8
        original_utf8_bytes = text.encode('cp1252')
        corrected_text = original_utf8_bytes.decode('utf-8')
        # Heuristic: if 'Ã' was present and is now gone, it's likely corrected
        if corrected_text != text and 'Ã' in text and 'Ã©' not in corrected_text.lower() and 'ã' not in corrected_text.lower():  # Avoid over-correction of legitimate extended chars
            # Basic check to see if it looks more like valid text (less gibberish)
            if sum(1 for char in corrected_text if ord(char) > 127) < sum(
                    1 for char in text if ord(char) > 127) or 'Ã' not in corrected_text:
                # print(f"Corrected: '{text}' -> '{corrected_text}'")
                return corrected_text
        return text
    except UnicodeEncodeError:  # text might already be utf-8
        return text
    except UnicodeDecodeError:  # original_utf8_bytes might not be valid utf-8
        return text
    except Exception:  # Catch any other unforeseen errors
        return text


def _parse_single_ofx_to_dataframe(file_path: str) -> pd.DataFrame:
    """
    Parses a single OFX file and converts its transactions into a Pandas DataFrame.
    """
    expected_columns = [COLUMN_ID, COLUMN_DATE, COLUMN_TYPE, COLUMN_AMOUNT, COLUMN_MEMO]
    transactions_list = []

    try:
        with open(file_path, 'rb') as f:
            ofx = OfxParser.parse(f)
    except FileNotFoundError:
        print(f"Error: File not found at {file_path}")
        return pd.DataFrame(columns=expected_columns)
    except Exception as e:
        print(f"Error parsing OFX file {file_path}: {e}")
        return pd.DataFrame(columns=expected_columns)

    if ofx.account is None:
        print(f"Warning: No account information found in {file_path}. Attempting to find transactions if possible.")
        # Fallback: some OFX files might have transactions without a clear account wrapper at top level
        # This part is speculative as OfxParser usually expects ofx.account
        if hasattr(ofx, 'statements') and ofx.statements:  # Check for statements directly if account is None
            for stmt in ofx.statements:
                if stmt.transactions:
                    for transaction in stmt.transactions:
                        transactions_list.append({
                            COLUMN_ID: transaction.id,
                            COLUMN_DATE: transaction.date,
                            COLUMN_TYPE: transaction.type,
                            COLUMN_AMOUNT: transaction.amount,
                            COLUMN_MEMO: _correct_ofx_char_encoding(transaction.memo)
                        })
        elif hasattr(ofx, 'signon') and hasattr(ofx.signon,
                                                'statements') and ofx.signon.statements:  # Another possible structure
            for stmt in ofx.signon.statements:
                if stmt.transactions:
                    for transaction in stmt.transactions:
                        transactions_list.append({
                            COLUMN_ID: transaction.id,
                            COLUMN_DATE: transaction.date,
                            COLUMN_TYPE: transaction.type,
                            COLUMN_AMOUNT: transaction.amount,
                            COLUMN_MEMO: _correct_ofx_char_encoding(transaction.memo)
                        })
        if not transactions_list:
            print(f"Warning: No account information and no fallback transactions found in {file_path}.")
            return pd.DataFrame(columns=expected_columns)

    elif ofx.account.statement is None:
        print(
            f"Warning: No statement found for account {ofx.account.account_id if hasattr(ofx.account, 'account_id') else 'N/A'} in {file_path}.")
        return pd.DataFrame(columns=expected_columns)
    elif not ofx.account.statement.transactions:
        print(
            f"Warning: No transactions found in statement for account {ofx.account.account_id if hasattr(ofx.account, 'account_id') else 'N/A'} in {file_path}.")
        return pd.DataFrame(columns=expected_columns)
    else:  # Standard case: transactions under ofx.account.statement
        for transaction in ofx.account.statement.transactions:
            transactions_list.append({
                COLUMN_ID: transaction.id,
                COLUMN_DATE: transaction.date,
                COLUMN_TYPE: transaction.type,
                COLUMN_AMOUNT: transaction.amount,
                COLUMN_MEMO: _correct_ofx_char_encoding(transaction.memo)
            })

    if not transactions_list:
        return pd.DataFrame(columns=expected_columns)

    df = pd.DataFrame(transactions_list)
    df[COLUMN_DATE] = pd.to_datetime(df[COLUMN_DATE]).dt.normalize()
    df[COLUMN_AMOUNT] = df[COLUMN_AMOUNT].astype(float)
    # Ensure defined column order
    df = df[expected_columns]
    return df


def parse_ofx_files_to_dataframe(base_resources_files_path: str) -> pd.DataFrame:
    """
    Processes all OFX files from predefined subdirectories (account types)
    within the given base_resources_files_path, adds 'account_type',
    and concatenates them into a single DataFrame.
    """
    all_dfs = []
    # Define account type subdirectories and their corresponding names
    account_type_subdirs = {
        "credit_card": "Credit Card",
        "nuconta": "Nuconta"
        # Add more mappings here if needed
    }

    final_columns_expected = [COLUMN_ID, COLUMN_DATE, COLUMN_TYPE, COLUMN_AMOUNT, COLUMN_MEMO, COLUMN_ACCOUNT_TYPE]

    if not os.path.isdir(base_resources_files_path):
        print(f"Error: Base OFX resources directory not found: {base_resources_files_path}")
        return pd.DataFrame(columns=final_columns_expected)

    found_any_files = False
    for subdir_name, account_type_name in account_type_subdirs.items():
        current_path = os.path.join(base_resources_files_path, subdir_name)
        if not os.path.isdir(current_path):
            print(f"Warning: Subdirectory for account type '{account_type_name}' not found: {current_path}")
            continue

        ofx_files = glob.glob(os.path.join(current_path, '*.ofx'))
        if not ofx_files:
            print(f"No OFX files found in {current_path} for account type '{account_type_name}'.")
            continue
        
        found_any_files = True
        print(f"Found {len(ofx_files)} OFX files in {current_path} for account type '{account_type_name}'. Processing...")
        for file_path in ofx_files:
            print(f"Processing file: {file_path}")
            df = _parse_single_ofx_to_dataframe(file_path)
            if not df.empty:
                df[COLUMN_ACCOUNT_TYPE] = account_type_name # Add account type
                all_dfs.append(df)
            else:
                print(f"Warning: No data parsed from {file_path}")

    if not found_any_files:
        print(f"No OFX files found in any of the specified subdirectories within {base_resources_files_path}")
        # Return an empty DataFrame with all expected columns, including account_type
        return pd.DataFrame(columns=final_columns_expected)
        
    if not all_dfs:
        print("No data parsed from any OFX file across all subdirectories.")
        return pd.DataFrame(columns=final_columns_expected)

    combined_df = pd.concat(all_dfs, ignore_index=True)
    # Ensure all expected columns are present, even if some files had no data for some specific new columns (though account_type is added to all non-empty dfs)
    for col in final_columns_expected:
        if col not in combined_df.columns:
            combined_df[col] = pd.NA # Or appropriate default
            
    combined_df = combined_df[final_columns_expected] # Enforce column order and selection
    print(f"Successfully combined OFX files from subdirectories into a DataFrame with shape {combined_df.shape}.")
    return combined_df


# Moved from spending.py
def _load_user_defined_categories(user_categories_file: str) -> pd.DataFrame:
    """Loads user-defined categories from a CSV file."""
    if user_categories_file and os.path.exists(user_categories_file):
        try:
            return pd.read_csv(user_categories_file)
        except Exception as e:
            print(f"Error loading user-defined categories from {user_categories_file}: {e}")
            return pd.DataFrame(columns=[COLUMN_ID, COLUMN_MAIN_CATEGORY, COLUMN_SUB_CATEGORY])
    return pd.DataFrame(columns=[COLUMN_ID, COLUMN_MAIN_CATEGORY, COLUMN_SUB_CATEGORY])


# Moved from spending.py
def _categorize_transactions_internal(df: pd.DataFrame, user_categories_file: str = None) -> pd.DataFrame:
    """
    Adds 'main_category' and 'sub_category' columns to the DataFrame.
    Prioritizes user-defined categories, then uses the global CATEGORIZATION_RULES.
    This internal version now expects COLUMN_ACCOUNT_TYPE to potentially be present and usable.
    """
    if COLUMN_MEMO not in df.columns and COLUMN_ID not in df.columns:
        print(
            f"Warning: Neither Memo column ('{COLUMN_MEMO}') nor ID column ('{COLUMN_ID}') found. Cannot categorize effectively.")
        df[COLUMN_MAIN_CATEGORY] = 'Erro - Sem Info Suficiente'
        df[COLUMN_SUB_CATEGORY] = 'Erro - Sem Info Suficiente'
        return df

    df[COLUMN_MAIN_CATEGORY] = 'Não Categorizado'
    df[COLUMN_SUB_CATEGORY] = 'Não Categorizado'

    user_categories_df = _load_user_defined_categories(user_categories_file)
    user_categories_map = {}
    if not user_categories_df.empty and COLUMN_ID in user_categories_df.columns:
        for _, row in user_categories_df.iterrows():
            user_categories_map[row[COLUMN_ID]] = (row[COLUMN_MAIN_CATEGORY], row[COLUMN_SUB_CATEGORY])

    for index, row in df.iterrows():
        transaction_id = row.get(COLUMN_ID)

        if transaction_id and transaction_id in user_categories_map:
            main_cat, sub_cat = user_categories_map[transaction_id]
            df.loc[index, COLUMN_MAIN_CATEGORY] = main_cat
            df.loc[index, COLUMN_SUB_CATEGORY] = sub_cat
            continue

        if COLUMN_MEMO in row:
            memo = str(row[COLUMN_MEMO]).lower()
            if not memo or pd.isna(row[COLUMN_MEMO]):
                continue

            for keywords, category_name in CATEGORIZATION_RULES:
                all_keywords_found = True
                for keyword in keywords:
                    if keyword.lower() not in memo:
                        all_keywords_found = False
                        break

                if all_keywords_found:
                    main_cat, sub_cat = category_name
                    df.loc[index, COLUMN_MAIN_CATEGORY] = main_cat
                    df.loc[index, COLUMN_SUB_CATEGORY] = sub_cat
                    break
    return df


def get_categorized_transactions() -> pd.DataFrame: # Removed arguments as paths are now module-level constants
    """
    Parses all OFX files from predefined subdirectories, adds account_type, 
    categorizes them, and returns a unified DataFrame.
    """
    print(f"Starting OFX processing and categorization from base path: {BASE_OFX_FILES_PATH}")
    # Pass the new base path to the updated parsing function
    raw_transactions_df = parse_ofx_files_to_dataframe(BASE_OFX_FILES_PATH)

    if raw_transactions_df.empty:
        print("No transactions parsed from OFX files. Returning empty DataFrame.")
        empty_df_cols = [COLUMN_ID, COLUMN_DATE, COLUMN_TYPE, COLUMN_AMOUNT, COLUMN_MEMO,
                         COLUMN_ACCOUNT_TYPE, COLUMN_MAIN_CATEGORY, COLUMN_SUB_CATEGORY]
        return pd.DataFrame(columns=empty_df_cols)

    print(f"Successfully parsed {len(raw_transactions_df)} raw transactions including account types.")
    print("Categorizing transactions...")
    categorized_df = _categorize_transactions_internal(raw_transactions_df.copy(), USER_CATEGORIES_CSV_PATH)

    if categorized_df.empty:
        print("DataFrame is empty after categorization attempt.")
    else:
        print(f"Successfully categorized transactions. Final DataFrame shape: {categorized_df.shape}")
    return categorized_df


# Path definitions
# Corrected: three levels up to project root, then to /resources/files/
BASE_OFX_FILES_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "..", "resources", "files") 
USER_CATEGORIES_CSV_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "..", "resources", "user_defined_categories.csv")

def parse_ofx_files_and_write_to_db(target_db: str = "local", if_exists_strategy: str = "replace"):
    """
    Processes OFX files, categorizes transactions, and writes the result to
    the 'ofx_transactions' table in the specified database.
    """
    print(f"Starting OFX processing for database target: {target_db}")
    # get_categorized_transactions now uses module-level constants for paths
    transactions_df = get_categorized_transactions()

    if transactions_df.empty:
        print("No transactions to process or write to the database.")
        return

    print(f"Processed {len(transactions_df)} transactions initially.")

    conn = None
    try:
        conn = db_connect(target_db=target_db)
        cursor = conn.cursor() # Get a cursor for manual operations if needed

        # Step 1: Prepare and upsert categories
        if COLUMN_MAIN_CATEGORY in transactions_df.columns and COLUMN_SUB_CATEGORY in transactions_df.columns:
            unique_categories_df = transactions_df[[COLUMN_MAIN_CATEGORY, COLUMN_SUB_CATEGORY]].drop_duplicates().copy()
            # Remove rows where main_category or sub_category might be None or empty, if necessary
            unique_categories_df.dropna(subset=[COLUMN_MAIN_CATEGORY, COLUMN_SUB_CATEGORY], inplace=True)
            # Filter out placeholder categories if they are not desired in the categories table
            placeholder_main = 'Não Categorizado'
            placeholder_sub = 'Não Categorizado'
            error_placeholder_main = 'Erro - Sem Info Suficiente' 
            error_placeholder_sub = 'Erro - Sem Info Suficiente'

            unique_categories_df = unique_categories_df[
                ~((unique_categories_df[COLUMN_MAIN_CATEGORY] == placeholder_main) & (unique_categories_df[COLUMN_SUB_CATEGORY] == placeholder_sub)) &
                ~((unique_categories_df[COLUMN_MAIN_CATEGORY] == error_placeholder_main) & (unique_categories_df[COLUMN_SUB_CATEGORY] == error_placeholder_sub))
            ]

            if not unique_categories_df.empty:
                print(f"Found {len(unique_categories_df)} unique valid category pairs to upsert into 'transaction_categories'.")
                try:
                    # For SQLite, to_sql with 'append' will raise IntegrityError for duplicate PKs.
                    # For MySQL, INSERT IGNORE or ON DUPLICATE KEY UPDATE would be better for upsert.
                    # Pandas to_sql doesn't directly support INSERT IGNORE.
                    # A common workaround is to iterate and insert, or fetch existing and insert new.
                    # Let's try a safer approach: fetch existing, then insert new ones.
                    
                    existing_categories_df = pd.read_sql("SELECT main_category, sub_category FROM transaction_categories", conn)
                    existing_tuples = set(tuple(x) for x in existing_categories_df.to_numpy())
                    
                    categories_to_insert = []
                    for index, row in unique_categories_df.iterrows():
                        cat_tuple = (row[COLUMN_MAIN_CATEGORY], row[COLUMN_SUB_CATEGORY])
                        if cat_tuple not in existing_tuples:
                            categories_to_insert.append(cat_tuple)

                    if categories_to_insert:
                        new_categories_df = pd.DataFrame(categories_to_insert, columns=[COLUMN_MAIN_CATEGORY, COLUMN_SUB_CATEGORY])
                        new_categories_df.to_sql(
                            name='transaction_categories',
                            con=conn,
                            if_exists='append',
                            index=False,
                            chunksize=500
                        )
                        print(f"Successfully wrote {len(new_categories_df)} new unique categories to 'transaction_categories' table.")
                    else:
                        print("No new categories to insert into 'transaction_categories'. All found categories already exist.")

                except Exception as cat_e:
                    print(f"Error writing categories to database: {cat_e}")
                    # Decide if you want to proceed if categories fail to write.
                    # For now, we will proceed to write transactions.
            else:
                print("No valid unique categories found in transactions to upsert.")
        else:
            print("Warning: Main category or sub category columns not found in transactions DataFrame. Cannot populate 'transaction_categories' table.")

        # Step 2: Write transactions to 'ofx_transactions' table
        print(f"Attempting to write {len(transactions_df)} transactions to database table 'ofx_transactions'...")
        # Standardize Date format for SQLite compatibility if not already
        if 'date' in transactions_df.columns:
            transactions_df['date'] = pd.to_datetime(transactions_df['date']).dt.strftime('%Y-%m-%d')

        transactions_df.to_sql(
            name='ofx_transactions',
            con=conn,
            if_exists=if_exists_strategy, # 'replace', 'append', or 'fail'
            index=False,
            chunksize=1000 # Optional: for large DataFrames
        )
        print(f"Successfully wrote {len(transactions_df)} transactions to 'ofx_transactions' table using '{if_exists_strategy}' strategy.")

    except Exception as e:
        print(f"Error writing transactions to database: {e}")
    finally:
        if conn:
            conn.close()
            print("Database connection closed.")

# This is the function that spending.py currently calls.
def parse_ofx_files(target_db: str = "local"): 
    """
    Main function to process OFX files and store them in the database.
    """
    print("parse_ofx_files called, initiating data processing and DB write...")
    parse_ofx_files_and_write_to_db(target_db=target_db, if_exists_strategy="replace")
    print("parse_ofx_files: OFX data processing and database write attempt completed.")

# Example of how this module could be run directly (for testing)
if __name__ == '__main__':
    print("Running ofx_parser.py directly for testing...")
    # To test writing to local SQLite DB
    parse_ofx_files(target_db="local")
    
    # To test (if configured) writing to remote DB (ensure connection details are correct in connection.py)
    # print("\\nAttempting to process for remote DB (ensure connection is configured)...")
    # parse_ofx_files(target_db="remote")
    print("Direct execution test finished.")
