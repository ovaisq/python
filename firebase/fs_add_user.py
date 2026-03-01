#!/usr/bin/env python3
"""Add users to an organization.

Requires fstools.py

Example:
    ./fs_add_user.py --cred-json srvc_act_key.json --org-id <org id>

Output:
    Manager Document g84ZEOA7QVo9XFldvbea created
    User Document I36ezlfYbkvq7dVCr5n2 created
"""

import argparse
import random
from typing import Dict, Any

from fstools import FsTools


def rand_employee_id() -> str:
    """Generate random employee ID (numeric or alphanumeric).

    Returns:
        Random employee ID string.
    """
    num = random.randrange(1, 3)
    if num == 1:
        return rand_alpha_nums(6)
    return str(random.randrange(100000, 999999))


def rand_alpha_nums(numchars: int) -> str:
    """Generate random alphanumeric string.

    Args:
        numchars: Number of characters in the result.

    Returns:
        Random alphanumeric string.
    """
    alphanum_str = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
    return ''.join(random.sample(alphanum_str, numchars))


def build_user_demographics(
    role: str,
    company_name: str,
    org_id: str,
    manager: str = '',
    manager_id: str = ''
) -> Dict[str, Any]:
    """Build user demographics data for a user document.

    Args:
        role: User role ('manager' or 'employee').
        company_name: Organization name.
        org_id: Organization ID.
        manager: Manager's full name (for employees).
        manager_id: Manager's document ID (for employees).

    Returns:
        Dictionary containing user demographics.
    """
    team = 'QA'
    location = 'California'

    first_name = f'QA_F_{rand_alpha_nums(8)}'
    last_name = f'QA_L_{rand_alpha_nums(8)}'
    full_name = f'{first_name} {last_name}'

    if role == 'manager':
        job_title = 'Manager'
        manager = ''
        manager_id = ''
    else:
        job_title = 'Employee'

    return {
        'companyName': company_name,
        'deactivatedAt': '',
        'debug': False,
        'email': '',
        'employeeId': rand_employee_id(),
        'employeePin': 'ACCCBbBCBA==',
        'externalId': '',
        'fcmTokens': [],
        'firstName': first_name,
        'fullName': full_name,
        'inviteCode': '',
        'jobTitle': job_title,
        'language': '',
        'lastName': last_name,
        'location': location,
        'manager': manager,
        'managerId': manager_id,
        'mdm': False,
        'mobilePhone': '+1',
        'orgId': org_id,
        'passwordAdmin': False,
        'platform': '',
        'role': role,
        'startDate': '',
        'team': team,
        'timeZone': '',
    }


def main() -> None:
    """Main entry point for adding users to an organization."""
    arg_parser = argparse.ArgumentParser(
        description='Add users to a given organization'
    )
    arg_parser.add_argument(
        '--org-id',
        dest='org_id',
        required=True,
        help='Organization ID (e.g., NQO35YIeMPV1NsJCmncWi)'
    )
    arg_parser.add_argument(
        '--cred-json',
        dest='fs_cred_json',
        required=True,
        help='GCP Service Account Key JSON file path'
    )
    arg_parser.add_argument(
        '--num-users',
        dest='num_users',
        type=int,
        default=1,
        help='Number of employee users to add (plus 1 manager)'
    )

    args = arg_parser.parse_args()

    db = FsTools(args.fs_cred_json)

    org = db.get_doc_by_id('orgs', args.org_id)
    if not org:
        print(f'Error: Organization {args.org_id} not found')
        return

    company_name = org['name']

    manager_doc_id = rand_alpha_nums(20)
    manager_data = build_user_demographics(
        role='manager',
        company_name=company_name,
        org_id=args.org_id
    )

    db.set_doc_data('users', manager_doc_id, manager_data)
    print(f'Manager Document {manager_doc_id} created')

    manager_name = manager_data['fullName']

    for _ in range(args.num_users):
        employee_doc_id = rand_alpha_nums(20)
        employee_data = build_user_demographics(
            role='employee',
            company_name=company_name,
            org_id=args.org_id,
            manager=manager_name,
            manager_id=manager_doc_id
        )
        db.set_doc_data('users', employee_doc_id, employee_data)
        print(f'User Document {employee_doc_id} created')


if __name__ == '__main__':
    main()
