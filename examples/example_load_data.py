from __future__ import annotations

import argparse
import logging
import sys
import time
from os import path as os_path

import numpy as np
import pandas as pd

from src import pyfinbot

_logger = logging.getLogger(__name__)

MODULE_DIR = os_path.dirname(os_path.abspath(__file__))

parser = argparse.ArgumentParser()
parser.add_argument("--instance", default="", help="instance name will be used to locate config (default: '')")
parser.add_argument("--config_path", default="", help="path to desired config (default: '')")
parser.add_argument("--logs_dir", default="", help="directory to desired logs (default: '')")


def close():
    _logger.info("Closing")
    time.sleep(2)
    sys.exit(f"Thanks for using {pyfinbot.version.PROJECT_NAME_TEXT}")


def getStockID(cur, symbol: str, stock_name: str = "") -> int:
    """Query for stock ID or insert a new stock."""
    cur.execute(
        "SELECT id FROM stock WHERE symbol = %s LIMIT 1;",
        (symbol,)
    )
    stock_id = cur.fetchone()
    if stock_id:
        return stock_id[0]

    return pyfinbot.database.insertRecord(cur, "stock", {"symbol": symbol, "name": stock_name})


def loadDataFromExcel(env, excel_file_path: str, target_version: int):
    """Load data from an Excel file and insert it into the database with transaction rollback on error."""
    conn, cur = None, None
    excel_file_path = os_path.abspath(excel_file_path)
    try:
        # Ensure the database connection is available
        try:
            conn, cur = pyfinbot.database.connect(env, enforce_version=target_version, autocommit=False)
        except pyfinbot.DatabaseNotFoundError:
            pyfinbot.database.createDatabase(env, target_version)
            conn, cur = pyfinbot.database.connect(env, autocommit=False)

        # Create a guest user
        user_id = pyfinbot.database.insertRecord(cur, "users", {"name": "Guest"})

        # Load the Excel file
        schema = {
            "Type": 'string',
            "Stock": 'string',
            "Units": np.float64,
            "Price": np.float64,
            "Fee": np.float64,
        }

        # Read Excel file
        df = pd.read_excel(excel_file_path, "Transactions", dtype=schema, parse_dates=["Date"])
        _logger.info("Excel file loaded successfully.")

        # Loop through each row in the DataFrame and insert the data into the database
        for index, row in df.iterrows():
            row['Type'] = row['Type'].strip().lower()
            row['Stock'] = row['Stock'].strip().upper()
            value = round(row['Units'] * row['Price'], 7)
            if row['Type'] == 'Buy':
                cost = -round(value + row['Fee'], 7)
            else:
                cost = round(value - row['Fee'], 7)
            date = row['Date']
            fy = f"{date.year}-{date.year + 1}" if date.month >= 7 else f"{date.year - 1}-{date.year}"

            stock_id = getStockID(cur, row['Stock'])

            # Create the transaction
            pyfinbot.database.insertRecord(cur, "transaction", {
                "user_id": user_id,
                "stock_id": stock_id,
                "date": date,
                "type": row['Type'],
                "units": row['Units'],
                "price": row['Price'],
                "value": value,
                "fee": row['Fee'],
                "cost": cost,
                "fy": fy
            }, user_id)

        # Commit the transaction after all rows are inserted
        conn.commit()
        _logger.info(f"Data from Excel has been successfully loaded into the database v{target_version}.")

    except Exception as e:
        _logger.error(f"An error occurred while loading data from Excel: {e}")
        if conn:
            _logger.debug("Rolling back the transaction due to error.")
            conn.rollback()  # Rollback the transaction if any error occurs
        raise
    finally:
        if conn:
            conn.close()  # Ensure the connection is closed
            _logger.debug("Database connection closed.")


def main():
    """
    Main function to load the environment, parse command-line arguments, and execute the data loading process.
    """
    args = parser.parse_args()
    instance: str = args.instance
    config_path: str = args.config_path
    logs_dir: str = args.logs_dir

    project_name = pyfinbot.version.PROJECT_NAME

    # Determine default config and logs paths if not provided
    if not config_path:
        config_filename = f"{project_name}{'' if not instance else '_' + instance}.conf"
        config_path = f"configs/{config_filename}"
    if not logs_dir:
        logs_instance_folder = f"{project_name}{'' if not instance else '_' + instance}"
        logs_dir = f"logs/{logs_instance_folder}"

    config_path = os_path.abspath(config_path)
    logs_dir = os_path.abspath(logs_dir)

    # Load environment and configurations
    env = pyfinbot.loadEnv(config_path, project_dir=MODULE_DIR, instance=instance, logs_dir=logs_dir)
    _logger.info(f"Starting {env.project_name_text}.")

    try:
        # Load data from an Excel sheet into the version 1 database
        loadDataFromExcel(env, MODULE_DIR + "/example_transactions.xlsx", 1)
    except Exception as e:
        raise
    finally:
        close()


if __name__ == "__main__":
    main()
