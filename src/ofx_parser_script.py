import pandas as pd
from ofxparse import OfxParser
import os
import glob # For finding files

# Define column names for consistency
COLUMN_ID = 'id'
COLUMN_DATE = 'date'
COLUMN_TYPE = 'type'
COLUMN_AMOUNT = 'amount'
COLUMN_MEMO = 'memo'
COLUMN_ACCOUNT_TYPE = 'account_type'

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
        original_utf8_bytes = text.encode('cp1252')
        corrected_text = original_utf8_bytes.decode('utf-8')
        if corrected_text != text and 'Ã' in text and 'Ã' not in corrected_text:
            return corrected_text
        return text
    except UnicodeEncodeError:
        return text
    except UnicodeDecodeError:
        return text
    except Exception:
        return text

def parse_ofx_to_dataframe(file_path: str) -> pd.DataFrame:
    """
    Parses an OFX file and converts its transactions into a Pandas DataFrame.
    Original columns: 'id', 'date', 'type', 'amount', 'memo'.
    """
    expected_columns = [COLUMN_ID, COLUMN_DATE, COLUMN_TYPE, COLUMN_AMOUNT, COLUMN_MEMO]
    try:
        with open(file_path, 'rb') as f:
            ofx = OfxParser.parse(f)
    except FileNotFoundError:
        print(f"Error: File not found at {file_path}")
        return pd.DataFrame(columns=expected_columns)
    except Exception as e:
        print(f"Error parsing OFX file {file_path}: {e}")
        return pd.DataFrame(columns=expected_columns)

    transactions_list = []

    if ofx.account is None:
        print(f"Warning: No account information found in {file_path}.")
        return pd.DataFrame(columns=expected_columns)

    if ofx.account.statement is None:
        print(f"Warning: No statement found for account {ofx.account.account_id if hasattr(ofx.account, 'account_id') else 'N/A'} in {file_path}.")
        return pd.DataFrame(columns=expected_columns)

    if not ofx.account.statement.transactions:
        print(f"Warning: No transactions found in statement for account {ofx.account.account_id if hasattr(ofx.account, 'account_id') else 'N/A'} in {file_path}.")
        return pd.DataFrame(columns=expected_columns)

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
    df[COLUMN_AMOUNT] = abs(df[COLUMN_AMOUNT])
    df = df[expected_columns] # Ensure defined column order before adding new ones
    return df

def process_all_ofx_files(base_dir: str) -> pd.DataFrame:
    """
    Processes all OFX files in specified subdirectories ('credit_card', 'nuconta')
    of the base_dir, adds an 'account_type' column, and concatenates them.
    """
    all_dfs = []
    
    # Define account types and their corresponding directories
    account_type_map = {
        'Credit Card': os.path.join(base_dir, 'credit_card'),
        'Nuconta': os.path.join(base_dir, 'nuconta')
    }

    for acc_type, acc_dir_path in account_type_map.items():
        if not os.path.isdir(acc_dir_path):
            print(f"Warning: Directory not found: {acc_dir_path}")
            continue
            
        ofx_files = glob.glob(os.path.join(acc_dir_path, '*.ofx'))
        if not ofx_files:
            print(f"No OFX files found in {acc_dir_path}")
            
        for file_path in ofx_files:
            print(f"Processing {acc_type} file: {file_path}")
            df = parse_ofx_to_dataframe(file_path)
            if not df.empty:
                df[COLUMN_ACCOUNT_TYPE] = acc_type
                all_dfs.append(df)
            else:
                print(f"Warning: No data parsed from {file_path}")

    if not all_dfs:
        print("No OFX files processed or no data found in any OFX file.")
        # Return an empty DataFrame with all expected columns including the new one
        final_columns = [COLUMN_ID, COLUMN_DATE, COLUMN_TYPE, COLUMN_AMOUNT, COLUMN_MEMO, COLUMN_ACCOUNT_TYPE]
        return pd.DataFrame(columns=final_columns)

    combined_df = pd.concat(all_dfs, ignore_index=True)
    return combined_df

if __name__ == '__main__':
    workspace_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) if "__file__" in locals() else "." 
    current_path = os.path.abspath(".")
    if os.path.basename(current_path) == "src":
        project_root_path = os.path.dirname(current_path)
    else:
        project_root_path = current_path # Assume current dir is project root

    resources_base_path = os.path.join(project_root_path, 'resources', 'files')

    print(f"Looking for OFX files in subdirectories of: {resources_base_path}")

    if not os.path.isdir(resources_base_path):
        print(f"Error: Base directory for OFX files not found: {resources_base_path}")
        print("Please ensure the 'resources/files' directory exists at the project root or adjust path.")
    else:
        combined_transactions_df = process_all_ofx_files(resources_base_path)

        if not combined_transactions_df.empty:
            print("\n--- Combined Transactions DataFrame ---")
            print(f"Shape: {combined_transactions_df.shape}")
            print("\nInfo:")
            combined_transactions_df.info()
            print("\nHead:")
            print(combined_transactions_df.head())
            print("\nTail:")
            print(combined_transactions_df.tail())
            print(f"\nAccount types found: {combined_transactions_df[COLUMN_ACCOUNT_TYPE].unique().tolist()}")
            
            # Example: Display value counts for account types
            print("\nValue counts for 'account_type':")
            print(combined_transactions_df[COLUMN_ACCOUNT_TYPE].value_counts())
        else:
            print("\nNo transactions were processed from any OFX files.") 