#!/usr/bin/env python3
"""Get AWS costs, store them in SQLite database

    https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ce/client/get_cost_and_usage.html
"""

import argparse
import boto3
import configparser
import datetime
import json
import logging
import pathlib
import sqlite3
import sys
import time
from typing import Dict, Any, Tuple, Optional


def aws_account_id() -> str:
    """Get AWS account number.
    
    Returns:
        str: AWS account ID
    """
    sts = boto3.client("sts")
    account_id = sts.get_caller_identity()["Account"]
    return account_id


def read_config(file_path: str) -> configparser.RawConfigParser:
    """Read configuration file.
    
    Args:
        file_path: Path to config file
        
    Returns:
        configparser.RawConfigParser: Configuration object
        
    Raises:
        FileNotFoundError: If config file doesn't exist
    """
    if pathlib.Path(file_path).exists():
        config_obj = configparser.RawConfigParser()
        config_obj.read(file_path)
        return config_obj
    else:
        raise FileNotFoundError(f"Config file {file_path} not found.")


def sqlite_connection(p_config: configparser.RawConfigParser) -> Tuple[Any, Any, str]:
    """Connect to SQLite database.
    
    Args:
        p_config: Configuration object containing database settings
        
    Returns:
        Tuple[connection, cursor, table_name]: SQLite connection, cursor, and table name
        
    Raises:
        sqlite3.Error: If connection fails
        ValueError: If configuration values are missing or invalid
    """
    # Get configuration values
    db_path = p_config.get('sqlitedb', 'db_path')
    table_name = p_config.get('sqlitedb', 'tablename')
    
    # Validate that required fields are not empty
    if not db_path:
        raise ValueError("Missing required database configuration: db_path")
    
    try:
        sqlite_conn = sqlite3.connect(db_path)
        sqlite_cur = sqlite_conn.cursor()
        return sqlite_conn, sqlite_cur, table_name
    except sqlite3.Error as e:
        logging.error(f"Error connecting to SQLite: {e}")
        raise


def db_write(table_name: str, dataobject: Dict[str, Any], sqlite_cursor: Any) -> None:
    """Write data to database table.
    
    Args:
        table_name: Name of the table to insert data into
        dataobject: Dictionary containing data to insert
        sqlite_cursor: SQLite cursor object
        
    Raises:
        sqlite3.Error: If database operation fails
    """
    cols = ', '.join(dataobject.keys())
    placeholders = ', '.join(['?' for _ in dataobject.values()])
    query = f"INSERT INTO {table_name} ({cols}) VALUES ({placeholders})"
    try:
        sqlite_cursor.execute(query, tuple(dataobject.values()))
        sqlite_cursor.connection.commit()
    except sqlite3.Error as e:
        logging.error(f"Unable to execute query or commit for table {table_name} - {e}")
        raise


def fetch_aws_costs(
    start_date: datetime.date, 
    end_date: datetime.date,
    granularity: str = 'DAILY',
    metrics: Optional[list] = None,
    group_by: Optional[list] = None
) -> Dict[str, Any]:
    """Fetch AWS cost and usage data.
    
    Args:
        start_date: Start date for cost data
        end_date: End date for cost data (exclusive)
        granularity: Granularity of data (DAILY, MONTHLY, etc.)
        metrics: List of metrics to retrieve
        group_by: List of dimensions to group by
        
    Returns:
        dict: AWS cost and usage response
    """
    if metrics is None:
        metrics = ['AmortizedCost', 'BlendedCost', 'UnblendedCost']
        
    if group_by is None:
        group_by = [
            {'Type': 'DIMENSION', 'Key': 'SERVICE'},
            {'Type': 'DIMENSION', 'Key': 'USAGE_TYPE'}
        ]
    
    boto_client = boto3.client('ce')  # AWS cost explorer
    time_period = {
        'Start': str(start_date),
        'End': str(end_date)  # exclusive
    }
    
    response = boto_client.get_cost_and_usage(
        TimePeriod=time_period,
        Granularity=granularity,
        Metrics=metrics,
        GroupBy=group_by
    )
    
    return json.loads(json.dumps(response))


def process_and_store_costs(
    response: Dict[str, Any],
    table_name: str,
    account_id: str,
    timestamp: int,
    sqlite_cursor: Any
) -> None:
    """Process AWS cost response and store in database.
    
    Args:
        response: AWS cost and usage response
        table_name: Name of the database table
        account_id: AWS account ID
        timestamp: Timestamp for the data collection
        sqlite_cursor: SQLite cursor object
    """
    EXCLUDED_KEY = {'Tax'}
    
    for groups_key in response['ResultsByTime']:
        time_period = groups_key['TimePeriod']['Start']
        for aws_service_key_name in groups_key['Groups']:
            if aws_service_key_name['Keys'][0] not in EXCLUDED_KEY:
                aws_service = aws_service_key_name['Keys'][0]
                usage_type = aws_service_key_name['Keys'][1]
                for cost_type in ['AmortizedCost', 'BlendedCost', 'UnblendedCost']:
                    amount_usd = aws_service_key_name['Metrics'][cost_type]['Amount']
                    db_object = {
                        'timestamp': timestamp,
                        'account_id': account_id,
                        'time_period': time_period,
                        'aws_service': aws_service,
                        'cost_type': cost_type,
                        'usage_type': usage_type,
                        'amount': amount_usd
                    }
                    db_write(table_name, db_object, sqlite_cursor)


def create_table_if_not_exists(table_name: str, sqlite_cursor: Any) -> None:
    """Create the costs table if it doesn't exist.
    
    Args:
        table_name: Name of the table to create
        sqlite_cursor: SQLite cursor object
    """
    create_table_sql = f"""
    CREATE TABLE IF NOT EXISTS {table_name} (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp INTEGER NOT NULL,
        account_id TEXT NOT NULL,
        time_period TEXT NOT NULL,
        aws_service TEXT NOT NULL,
        cost_type TEXT NOT NULL,
        usage_type TEXT NOT NULL,
        amount REAL NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """
    try:
        sqlite_cursor.execute(create_table_sql)
        sqlite_cursor.connection.commit()
    except sqlite3.Error as e:
        logging.error(f"Error creating table {table_name} - {e}")
        raise


def parse_arguments() -> argparse.Namespace:
    """Parse command line arguments.
    
    Returns:
        argparse.Namespace: Parsed arguments
    """
    parser = argparse.ArgumentParser(description='Track AWS costs and store in SQLite')
    parser.add_argument(
        '--start-date',
        type=str,
        help='Start date in YYYY-MM-DD format (default: 2023-09-01)'
    )
    parser.add_argument(
        '--end-date',
        type=str,
        help='End date in YYYY-MM-DD format (default: start_date + 30 days)'
    )
    parser.add_argument(
        '--config',
        type=str,
        default='setup.config',
        help='Path to configuration file (default: setup.config)'
    )
    return parser.parse_args()


def main() -> None:
    """Main function to orchestrate AWS cost tracking."""
    # Setup logging
    logging.basicConfig(level=logging.INFO)
    
    # Parse command line arguments
    args = parse_arguments()
    
    # Determine date range
    if args.start_date:
        try:
            start_date = datetime.datetime.strptime(args.start_date, '%Y-%m-%d').date()
        except ValueError:
            logging.error("Invalid start date format. Use YYYY-MM-DD")
            sys.exit(1)
    else:
        start_date = datetime.date(2023, 9, 1)  # Default start date
        
    if args.end_date:
        try:
            end_date = datetime.datetime.strptime(args.end_date, '%Y-%m-%d').date()
        except ValueError:
            logging.error("Invalid end date format. Use YYYY-MM-DD")
            sys.exit(1)
    else:
        end_date = start_date + datetime.timedelta(days=30)  # Default 30 days
    
    timestamp = int(time.time())
    
    try:
        # Get AWS account ID
        account_id = aws_account_id()
        logging.info(f"Processing AWS account: {account_id}")
        
        # Read configuration
        p_config = read_config(args.config)
        
        # Connect to database and get table name
        sqlite_conn, sqlite_cur, table_name = sqlite_connection(p_config)
        
        # Create table if it doesn't exist
        create_table_if_not_exists(table_name, sqlite_cur)
        
        # Fetch AWS costs
        logging.info(f"Fetching costs from {start_date} to {end_date}")
        response = fetch_aws_costs(start_date, end_date)
        
        # Process and store costs
        process_and_store_costs(response, table_name, account_id, timestamp, sqlite_cur)
        
        # Close database connection
        sqlite_cur.close()
        sqlite_conn.close()
        
        logging.info("Successfully completed AWS cost tracking")
        
    except Exception as e:
        logging.error(f"Error in AWS cost tracking: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()