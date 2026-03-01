#!/usr/bin/env python3
"""Delete all data for a given organization.

Requires:
    1. A GCP Service Account key with appropriate permissions
    2. A valid Worklete Org ID

Example:
    ./fs_clean_demo_bug.py --cred-json xxxxxx.json --org-id ZQO3tY6eMPV1NsJUmncI
"""

import argparse
import time
from random import randrange
from typing import List

from fstools import FsTools


def delete_with_rate_limit(
    items: List, delete_func, item_type: str, org_name: str
) -> int:
    """Delete items with rate limiting to avoid API quota issues.

    Args:
        items: List of items to delete.
        delete_func: Function to call for each item (receives item.id).
        item_type: Human-readable type name for logging.
        org_name: Organization name for logging.

    Returns:
        Number of items deleted.
    """
    counter = 0
    for item in items:
        counter += 1
        if counter > 100:
            sleep_for = randrange(1, 10)
            print(f'Sleeping for {sleep_for} seconds')
            time.sleep(sleep_for)
            counter = 0
        print(f'{counter}: Deleting {item_type} {item.id} for ORG {org_name}')
        delete_func(item.id)
    return counter


def main() -> None:
    """Main entry point for cleaning demo organization data."""
    arg_parser = argparse.ArgumentParser(
        description='Delete all data for a given organization'
    )
    arg_parser.add_argument(
        '--org-id',
        dest='org_id',
        required=True,
        help='Organization ID to clean'
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

    org_name = org['name']
    print(f'Getting a list of users for\t[Org Name: {org_name}]\t[Org ID: {args.org_id}]')

    # Fetch all collections for the org
    user_docs = db.get_docs_by_filter('users', 'orgId', args.org_id).stream()
    m_notification_docs = db.get_docs_by_filter('mobileNotifications', 'orgId', args.org_id).stream()
    org_config_docs = db.get_docs_by_filter('orgConfigs', 'org_id', args.org_id).stream()
    workflow_docs = db.get_docs_by_filter('workflows', 'orgId', args.org_id).stream()
    trendagg_docs = db.get_docs_by_filter('trendAggregates', 'orgId', args.org_id).stream()
    trendevent_docs = db.get_docs_by_filter('trendEvents', 'orgId', args.org_id).stream()

    # Delete mobile notifications
    delete_with_rate_limit(
        list(m_notification_docs),
        lambda doc_id: db.delete_document(f'mobileNotifications/{doc_id}'),
        'mobileNotification',
        org_name
    )

    # Delete user subcollections and users
    for user_doc in user_docs:
        actions = db.get_subcollection(user_doc.id, 'users', 'actions').stream()
        history = db.get_subcollection(user_doc.id, 'users', 'history').stream()

        delete_with_rate_limit(
            list(actions),
            lambda doc_id: db.delete_user_subcollection_doc(user_doc.id, 'actions', doc_id),
            'action',
            org_name
        )
        delete_with_rate_limit(
            list(history),
            lambda doc_id: db.delete_user_subcollection_doc(user_doc.id, 'history', doc_id),
            'history',
            org_name
        )

        print(f'Deleting user doc {user_doc.id} for ORG {org_name}')
        db.delete_document(f'users/{user_doc.id}')

    # Delete workflows
    delete_with_rate_limit(
        list(workflow_docs),
        lambda doc_id: db.delete_document(f'workflows/{doc_id}'),
        'workflow',
        org_name
    )

    # Delete org configs
    for org_config_doc in org_config_docs:
        print(f'Deleting orgConfigs {org_config_doc.id} for ORG {org_name}')
        db.delete_document(f'orgConfigs/{org_config_doc.id}')

    # Delete trend aggregates
    delete_with_rate_limit(
        list(trendagg_docs),
        lambda doc_id: db.delete_document(f'trendAggregates/{doc_id}'),
        'trendAggregates',
        org_name
    )

    # Delete trend events
    delete_with_rate_limit(
        list(trendevent_docs),
        lambda doc_id: db.delete_document(f'trendEvents/{doc_id}'),
        'trendEvents',
        org_name
    )

    # Delete org document
    print(f'Deleting ORG {args.org_id} for ORG {org_name}')
    db.delete_document(f'orgs/{args.org_id}')


if __name__ == '__main__':
    main()
