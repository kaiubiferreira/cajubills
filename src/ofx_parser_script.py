import pandas as pd
from ofxparse import OfxParser
import os
import glob # For finding files
from categorization_rules import CATEGORIZATION_RULES # Import the rules

# Define column names for consistency
COLUMN_ID = 'id'
COLUMN_DATE = 'date'
COLUMN_TYPE = 'type'
COLUMN_AMOUNT = 'amount'
COLUMN_MEMO = 'memo'
COLUMN_ACCOUNT_TYPE = 'account_type'
COLUMN_MAIN_CATEGORY = 'main_category' # New column for main categorization
COLUMN_SUB_CATEGORY = 'sub_category'   # New column for sub-categorization

def _load_user_defined_categories(user_categories_file: str) -> pd.DataFrame:
    """Loads user-defined categories from a CSV file."""
    if user_categories_file and os.path.exists(user_categories_file):
        try:
            return pd.read_csv(user_categories_file)
        except Exception as e:
            print(f"Error loading user-defined categories from {user_categories_file}: {e}")
            return pd.DataFrame(columns=[COLUMN_ID, COLUMN_MAIN_CATEGORY, COLUMN_SUB_CATEGORY])
    return pd.DataFrame(columns=[COLUMN_ID, COLUMN_MAIN_CATEGORY, COLUMN_SUB_CATEGORY])

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
        # Return empty DataFrame with all expected base columns if no transactions
        return pd.DataFrame(columns=expected_columns)

    df = pd.DataFrame(transactions_list)
    df[COLUMN_DATE] = pd.to_datetime(df[COLUMN_DATE]).dt.normalize()
    df[COLUMN_AMOUNT] = df[COLUMN_AMOUNT].astype(float)
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
        final_columns = [COLUMN_ID, COLUMN_DATE, COLUMN_TYPE, COLUMN_AMOUNT, COLUMN_MEMO, COLUMN_ACCOUNT_TYPE, COLUMN_MAIN_CATEGORY, COLUMN_SUB_CATEGORY]
        return pd.DataFrame(columns=final_columns)

    combined_df = pd.concat(all_dfs, ignore_index=True)
    return combined_df

def categorize_transactions(df: pd.DataFrame, user_categories_file: str = None) -> pd.DataFrame:
    """
    Adds 'main_category' and 'sub_category' columns to the DataFrame.
    Prioritizes user-defined categories, then uses the global CATEGORIZATION_RULES.
    """
    if COLUMN_MEMO not in df.columns and COLUMN_ID not in df.columns:
        print(f"Warning: Neither Memo column ('{COLUMN_MEMO}') nor ID column ('{COLUMN_ID}') found. Cannot categorize effectively.")
        df[COLUMN_MAIN_CATEGORY] = 'Erro - Sem Info Suficiente'
        df[COLUMN_SUB_CATEGORY] = 'Erro - Sem Info Suficiente'
        return df

    # Initialize categories
    df[COLUMN_MAIN_CATEGORY] = 'Não Categorizado'
    df[COLUMN_SUB_CATEGORY] = 'Não Categorizado'

    # Load user-defined categories
    user_categories_df = _load_user_defined_categories(user_categories_file)
    user_categories_map = {}
    if not user_categories_df.empty and COLUMN_ID in user_categories_df.columns:
        for _, row in user_categories_df.iterrows():
            user_categories_map[row[COLUMN_ID]] = (row[COLUMN_MAIN_CATEGORY], row[COLUMN_SUB_CATEGORY])

    for index, row in df.iterrows():
        transaction_id = row.get(COLUMN_ID)
        categorized_by_user = False

        # 1. Prioritize user-defined categories by transaction ID
        if transaction_id and transaction_id in user_categories_map:
            main_cat, sub_cat = user_categories_map[transaction_id]
            df.loc[index, COLUMN_MAIN_CATEGORY] = main_cat
            df.loc[index, COLUMN_SUB_CATEGORY] = sub_cat
            categorized_by_user = True
            continue # Move to next transaction if categorized by user

        # 2. Fallback to rule-based categorization if not categorized by user
        if COLUMN_MEMO in row:
            memo = str(row[COLUMN_MEMO]).lower()
            if not memo or pd.isna(row[COLUMN_MEMO]):
                # If memo is empty but not categorized by user, it remains 'Não Categorizado'
                continue

            for keywords, category_name in CATEGORIZATION_RULES:
                all_keywords_found = True
                for keyword in keywords:
                    if keyword.lower() not in memo:
                        all_keywords_found = False
                        break
                
                if all_keywords_found:
                    main_cat, sub_cat = category_name # category_name is (main_category, sub_category)
                    df.loc[index, COLUMN_MAIN_CATEGORY] = main_cat
                    df.loc[index, COLUMN_SUB_CATEGORY] = sub_cat
                    break # Move to the next transaction once categorized by rules
            # If no rule matched, it remains 'Não Categorizado' (or its initial user-defined value if ID matched but memo didn't)
        # If no memo, and not user categorized, it remains 'Não Categorizado'
    return df

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
            print("\n--- Combined Transactions DataFrame (Before Categorization) ---")
            print(f"Shape: {combined_transactions_df.shape}")
            # print("\nInfo:")
            # combined_transactions_df.info()
            # print("\nHead:")
            # print(combined_transactions_df.head())

            # Categorize transactions
            print("\nCategorizando transações...")
            # Define the path to user_defined_categories.csv
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) if "__file__" in locals() else "."
            current_path_main = os.path.abspath(".")
            if os.path.basename(current_path_main) == "src":
                 project_root_main = os.path.dirname(current_path_main)
            else:
                 project_root_main = current_path_main
            user_categories_csv_path = os.path.join(project_root_main, 'resources', 'user_defined_categories.csv')
            
            categorized_df = categorize_transactions(combined_transactions_df.copy(), user_categories_csv_path) # Use .copy()

            print("\n--- DataFrame de Transações Categorizadas (Todas as Categorias) ---")
            if categorized_df.empty:
                print(f"Nenhuma transação encontrada ou DataFrame está vazio após a categorização.")
            else:
                print(f"Shape: {categorized_df.shape}")
                print("\nInfo:")
                categorized_df.info()
                print("\nCabeçalho (com categorias):")
                print(categorized_df[[COLUMN_MEMO, COLUMN_MAIN_CATEGORY, COLUMN_SUB_CATEGORY]].head())
                print("\nFinal (com categorias):")
                print(categorized_df[[COLUMN_MEMO, COLUMN_MAIN_CATEGORY, COLUMN_SUB_CATEGORY]].tail())
                
                print(f"\nTipos de conta encontrados: {categorized_df[COLUMN_ACCOUNT_TYPE].unique().tolist()}")
                print("\nContagem de valores para 'account_type':")
                print(categorized_df[COLUMN_ACCOUNT_TYPE].value_counts())

                print("\nContagem de valores para 'main_category':")
                print(categorized_df[COLUMN_MAIN_CATEGORY].value_counts().sort_index())
                print("\nContagem de valores para 'sub_category':")
                print(categorized_df[COLUMN_SUB_CATEGORY].value_counts().sort_index())

                uncategorized_count = (categorized_df[COLUMN_MAIN_CATEGORY] == 'Não Categorizado').sum()
                total_transactions = len(categorized_df)
                if total_transactions > 0:
                    percent_uncategorized = (uncategorized_count / total_transactions) * 100
                    print(f"\nNúmero de transações Não Categorizadas (principal): {uncategorized_count} ({percent_uncategorized:.2f}% do total)")
                    if uncategorized_count > 0 and uncategorized_count < 20: # Print some uncategorized memos if not too many
                        print("\nExemplo de Memos Não Categorizados (principal):")
                        print(categorized_df[categorized_df[COLUMN_MAIN_CATEGORY] == 'Não Categorizado'][[COLUMN_MEMO, COLUMN_MAIN_CATEGORY, COLUMN_SUB_CATEGORY]].head(10).to_string())
                
                # Total amount of transactions (will be for the filtered category if filter is active)
                print(f"\nValor total de todas as transações:")
                print(categorized_df[COLUMN_AMOUNT].sum())
                
                # Total amount of transactions by account type (for the filtered category)
                print(f"\nValor total por tipo de conta (todas as categorias):")
                print(categorized_df.groupby(COLUMN_ACCOUNT_TYPE)[COLUMN_AMOUNT].sum())
                
                # Total amount by category (will be just the one category if filtered)
                print(f"\nValor total por categoria principal e subcategoria (todas as categorias):")
                print(categorized_df.groupby([COLUMN_MAIN_CATEGORY, COLUMN_SUB_CATEGORY])[COLUMN_AMOUNT].sum().sort_values(ascending=False))

        else:
            print("\nNenhuma transação foi processada de nenhum arquivo OFX.") 