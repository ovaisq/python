#!/usr/bin/env python3
"""Get all users for a given org ID and save in a tab-separated CSV.

Requires:
    1. A GCP Service Account key with appropriate permissions
    2. A valid Worklete Org ID

Example:
    ./fs_get_org_user_list.py --cred-json xxxxxx.json --org-id ZQO3tY6eMPV1NsJUmncI
"""

import argparse
import csv
import time
from typing import List

from fstools import FsTools


def main() -> None:
    """Main entry point for exporting org users to CSV."""
    arg_parser = argparse.ArgumentParser(
        description='Get list of users for a given Org and save in CSV'
    )
    arg_parser.add_argument(
        '--org-id',
        dest='org_id',
        required=True,
        help='Organization ID (e.g., NQO35YIeMPV1NsJCmncWi). '
             'Single value or comma-separated list'
    )
    arg_parser.add_argument(
        '--cred-json',
        dest='fs_cred_json',
        required=True,
        help='GCP Service Account Key JSON file path'
    )

    args = arg_parser.parse_args()

    db = FsTools(args.fs_cred_json)
    org = db.get_doc_by_id('orgs', args.org_id)

    if not org:
        print(f'No users found for Org ID {args.org_id}')
        return

    epoch = str(int(time.time()))
    csv_filename = f'{epoch}_{args.org_id}_users.csv'

    fieldnames = [
        'Org_Name',
        'User_Id',
        'User_FirstName',
        'User_LastName',
        'User_MobilePhone',
        'User_Email',
        'Employee_Id',
        'Manager_Id',
        'Manager',
        'Status'
    ]

    org_name = org['name']
    print(f'Getting a list of users for\t[Org Name: {org_name}]\t[Org ID: {args.org_id}]')

    user_docs = db.get_docs_by_filter('users', 'orgId', args.org_id).stream()

    doc_ids: List[str] = []

    with open(csv_filename, 'w', newline='') as csvfile:
        writer = csv.DictWriter(
            csvfile,
            fieldnames=fieldnames,
            dialect='excel',
            delimiter='\t',
            quoting=csv.QUOTE_ALL
        )
        writer.writeheader()

        for user_doc in user_docs:
            user_data = user_doc.to_dict()

            try:
                # User has logged in
                writer.writerow({
                    'Org_Name': org_name,
                    'User_Id': user_data.get('id'),
                    'User_LastName': user_data.get('lastName'),
                    'User_MobilePhone': user_data.get('mobilePhone'),
                    'User_Email': user_data.get('email'),
                    'Employee_Id': user_data.get('employeeId'),
                    'Manager_Id': user_data.get('managerId'),
                    'Manager': user_data.get('manager'),
                    'Status': 'user_has_logged_in',
                })
            except (KeyError, TypeError):
                # User hasn't logged in
                writer.writerow({
                    'Org_Name': org_name,
                    'User_Id': user_doc.id,
                    'User_LastName': user_data.get('lastName'),
                    'User_MobilePhone': user_data.get('mobilePhone'),
                    'User_Email': user_data.get('email'),
                    'Employee_Id': '',
                    'Manager_Id': user_data.get('managerId'),
                    'Manager': user_data.get('manager'),
                    'Status': 'user_never_logged_in',
                })

            doc_ids.append(user_doc.id)

    print(f'{len(doc_ids)} users in the org')


if __name__ == '__main__':
    main()
