#!/usr/bin/env python3
"""Transforms customer supplied XLSX to Worklete-Dashboard friendly data format.

This script:
1. Reads user supplied XLSX
2. Reads Worklete's Master Roster Google Sheet
3. Transforms data from user supplied XLSX into a
   Worklete Master Roster Google Sheet compliant format

Goal is to help the CS team shorten the time, and remove user errors,
from the updating of the user rosters.
"""

import argparse
import csv
import io
import logging
import pickle
import sys
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd
import openpyxl_dictreader
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# Constants
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
DEFAULT_SHEET_RANGE = 'A1:AA1000'
TOKEN_FILE = 'token.pickle'

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def transform_sheehan(reader_obj: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Transform Sheehan organization data to Worklete format.

    Sorts by location and job title, then transforms each row to the
    standardized format with user_id, name fields, and organizational data.

    Args:
        reader_obj: List of dictionaries from the XLSX file

    Returns:
        List of transformed dictionaries in Worklete format
    """
    sorted_list = sorted(
        reader_obj,
        key=lambda row: (row['Loc'], row['Job Title']),
        reverse=False
    )

    list_of_dicts = []
    for row in sorted_list:
        full_name = row["Name"].strip().split(',')
        last_name_orig = full_name[0]
        first_name_orig = full_name[1]
        last_name_new = last_name_orig.replace(' ', '').replace('-', '').replace('.', '').replace('\'', '')
        first_name_new = first_name_orig.strip().split(' ')[0]
        user_id_val = first_name_new + last_name_new

        new_csv = {
            'user_id': user_id_val.replace('-', ''),
            'first_name': first_name_new,
            'last_name': last_name_new,
            'location_id': row['Loc'],
            'email': row['Email'],
            'job_title': row['Job Title'],
            'team': row['Org Level 1']
        }
        list_of_dicts.append(new_csv)

    return list_of_dicts


def transform_cbre(reader_obj: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Transform CBRE organization data to Worklete format.

    Sorts by job title, then transforms each row to the standardized format.

    Args:
        reader_obj: List of dictionaries from the XLSX file

    Returns:
        List of transformed dictionaries in Worklete format
    """
    sorted_list = sorted(
        reader_obj,
        key=lambda row: row['Job Title'],
        reverse=False
    )

    list_of_dicts = []
    for row in sorted_list:
        new_csv = {
            'user_id': row['Email ID'],
            'first_name': row['First Name'],
            'last_name': row['Last Name'],
            'location_id': 'Microsoft',
            'email': row['Email ID'],
            'job_title': row['Job Title'],
            'team': row['Group'],
            'supervisor': row['Supervisor Name']
        }
        list_of_dicts.append(new_csv)

    return list_of_dicts


# Organization transformer mapping
ORG_TRANSFORMERS = {
    'sheehan': transform_sheehan,
    'cbre': transform_cbre,
}


def read_google_sheet(user_cred_json: str, spread_sheet_id: str, sheet_range: str) -> List[Dict[str, Any]]:
    """Read Google Sheet and return data as list of dictionaries.

    Args:
        user_cred_json: Path to Google credentials JSON file
        spread_sheet_id: Google Sheet ID
        sheet_range: Range of cells to read (e.g., 'A1:AA1000')

    Returns:
        List of dictionaries representing sheet rows
    """
    creds = None

    if Path(TOKEN_FILE).exists():
        with open(TOKEN_FILE, 'rb') as token:
            creds = pickle.load(token)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(user_cred_json, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, 'wb') as token:
            pickle.dump(creds, token)

    service = build('sheets', 'v4', credentials=creds)
    sheet = service.spreadsheets()

    result_input = sheet.values().get(
        spreadsheetId=spread_sheet_id,
        range=sheet_range
    ).execute()
    values_input = result_input.get('values', [])

    if not values_input:
        logger.warning('No data found in Google Sheet.')

    df = pd.DataFrame(values_input[1:], columns=values_input[0])
    a_csv = csv.DictReader(io.StringIO(df.to_csv(index=False)))
    return list(a_csv)


def parse_arguments() -> argparse.Namespace:
    """Parse command line arguments.

    Returns:
        Parsed arguments namespace
    """
    arg_parser = argparse.ArgumentParser(
        description="Transform Original Excel Spreadsheet to Worklete compliant version"
    )
    arg_parser.add_argument(
        '--orig-excel-file',
        dest='orig_excel_file',
        action='store',
        required=True,
        help="Original Excel Spreadsheet file name"
    )
    arg_parser.add_argument(
        '--google-sheet-id',
        dest='spread_sheet_id',
        action='store',
        required=True,
        help="Google Sheet ID"
    )
    arg_parser.add_argument(
        '--google-cred-json',
        dest='google_cred_json',
        action='store',
        required=True,
        help="Google User Credentials JSON file"
    )
    arg_parser.add_argument(
        '--org-name',
        dest='org_name',
        action='store',
        required=True,
        help="All lower case org name e.g. sheehan"
    )

    return arg_parser.parse_args()


def find_new_users(user_data: List[Dict[str, Any]],
                   google_sheet_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Find users that exist in user_data but not in google_sheet_data.

    A user is considered new if both their email and user_id don't exist
    in the Google Sheet.

    Args:
        user_data: List of user dictionaries from XLSX
        google_sheet_data: List of user dictionaries from Google Sheet

    Returns:
        List of new user dictionaries
    """
    emails = {user['email'] for user in google_sheet_data}
    userids = {user['user_id'] for user in google_sheet_data}

    diff_list = []
    for user in user_data:
        if user['email'] not in emails and user['user_id'] not in userids:
            diff_list.append(user)

    return diff_list


def main() -> None:
    """Main entry point for the transform script."""
    args = parse_arguments()

    orig_xlsx = Path(args.orig_excel_file)
    spread_sheet_id = args.spread_sheet_id
    sheet_range = DEFAULT_SHEET_RANGE
    google_cred_json = args.google_cred_json
    org_name = args.org_name.lower()

    # Validate input file exists
    if not orig_xlsx.exists():
        logger.error(f"Input file not found: {orig_xlsx}")
        sys.exit(1)

    # Validate credentials file exists
    if not Path(google_cred_json).exists():
        logger.error(f"Credentials file not found: {google_cred_json}")
        sys.exit(1)

    # Validate organization name
    if org_name not in ORG_TRANSFORMERS:
        logger.error(f"Unknown org name: [{org_name}]. Supported: {list(ORG_TRANSFORMERS.keys())}")
        sys.exit(1)

    # Generate output filename
    ux_timestamp = int(pd.Timestamp.now().timestamp())
    new_xlsx = Path(f"{ux_timestamp}_{org_name}_difference_{orig_xlsx.name}")

    # Read Google Sheet data
    logger.info("Reading Google Sheet...")
    google_sheet_csv = read_google_sheet(google_cred_json, spread_sheet_id, sheet_range)

    # Read and transform XLSX data
    try:
        reader = openpyxl_dictreader.DictReader(str(orig_xlsx), 'Sheet1')
    except Exception as e:
        logger.error(f"Failed to read XLSX file: {e}")
        sys.exit(1)

    # Apply organization-specific transformation
    transformer = ORG_TRANSFORMERS[org_name]
    list_dicts = transformer(reader)

    logger.info(f"Users in Google Sheet: {len(google_sheet_csv)}")
    logger.info(f"Users in Excel Sheet: {len(list_dicts)}")

    # Find new users
    diff_list = find_new_users(list_dicts, google_sheet_csv)
    logger.info(f"New Users Found: {len(diff_list)}")

    # Write new users to XLSX spreadsheet
    df = pd.DataFrame.from_dict(diff_list)
    df.to_excel(new_xlsx, index=False)

    logger.info(f"Orig XLSX file: {orig_xlsx}")
    logger.info(f"New XLSX file: {new_xlsx}")


if __name__ == "__main__":
    main()
