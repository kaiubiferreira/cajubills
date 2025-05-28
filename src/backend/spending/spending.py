from .ofx_parser import parse_ofx_files


def process_all(target_db: str = "local"):
    """
    Processes all spending data from OFX files and writes it to the database.
    The target database can be specified.
    """
    print(f"Initiating spending data processing for target_db: '{target_db}'...")
    parse_ofx_files(target_db=target_db)
    print(f"Spending data processing complete. Data should be in table 'ofx_transactions' in '{target_db}' database.")

# Example of how to run this if needed directly (though typically called by a larger process)
# if __name__ == '__main__':
#     print("Running spending.py process_all directly...")
#     process_all(target_db="local") # or "remote"
