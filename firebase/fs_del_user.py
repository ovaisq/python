#!/usr/bin/env python3
"""
Delete users by ID or last name from an organization.

Usage:
    Modify user_ids list and run the script.
"""

from fstools import FsTools

# Firebase service account key path
# Update this to your actual key file path
CRED_JSON = '/Users/username/Downloads/stage1-company-local-dev-xxxxx-xxxxx.json'

# Organization and user IDs to delete
ORG_ID = 'NQO35YIeMPV1NsJCmncW'
USER_IDS = ['02ftdZNORPc36GKgIEWy', '03Lik5shyZcfVzEAUWD2', '04XEQRHSsxa7b9geD1yT']


def main() -> None:
    """Delete users by ID or last name."""
    db = FsTools(CRED_JSON)

    user_docs = db.get_docs_by_filter('users', 'orgId', ORG_ID).stream()

    for user_doc in user_docs:
        user_data = user_doc.to_dict()

        # Delete by last name match
        if user_data.get('lastName') in USER_IDS:
            print(f'Deleting by Last Name: {user_data["lastName"]}')
            db.delete_document(f'users/{user_doc.id}')
            print(f'\t{user_data["lastName"]} {user_doc.id} DELETED')

        # Delete by document ID match
        if user_doc.id in USER_IDS:
            print(f'Deleting User ID: {user_doc.id}')
            db.delete_document(f'users/{user_doc.id}')
            print(f'\t{user_doc.id} DELETED')


if __name__ == '__main__':
    main()
