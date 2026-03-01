#!/usr/bin/env python3
"""
Copy user data from a source user to target users.

This script copies profile data and subcollection documents from a source
user to multiple target users.
"""

import random
import time
from typing import Dict, Any, List

from fstools import FsTools

# Firebase service account key path
CRED_JSON = '/Users/username/Downloads/company-mobile-firebase-adminsdk-xxxxx-xxxxx.json'

# Source user IDs to copy from
SRC_DOC_IDS = [
    '1QnoP7LCdSzl4VFndG1g', '3oh4lGZnwc9AJqHntky0', '70XIa2ZWMy826EY5QFTG',
    '7iMC1b76lMrKSOcptJOV', '9pp2oyIPy1PyX42JlhiX', 'JHvF156AZw0yE1N8AqK1',
    'KiMEkpj1QBl6UFSHHgJJ', 'ZDLGxDCPxslINZHqGba6', 'oqFJguw5SVLLiwncfQNQ',
    'qZif2p5iNIdoG4tCywEu'
]

# Target user IDs to update
DOC_IDS: List[str] = []


def merge_user_data(
    orig_data: Dict[str, Any],
    source_data: Dict[str, Any],
    doc_id: str
) -> Dict[str, Any]:
    """Merge source user data into original user data.

    Args:
        orig_data: Original user document data.
        source_data: Source user document data to copy from.
        doc_id: Target document ID.

    Returns:
        Merged user data dictionary.
    """
    merged = orig_data.copy()
    merged.update({
        'lastSignedIn': source_data.get('lastSignedIn'),
        'appVersion': source_data.get('appVersion'),
        'iv': source_data.get('iv', ''),
        'hasPin': source_data.get('hasPin', ''),
        'deviceModel': source_data.get('deviceModel'),
        'workflowsLastProcessedAt': source_data.get('workflowsLastProcessedAt'),
        'id': doc_id,
        'deviceName': doc_id,
        'fcmTokens': source_data.get('fcmTokens'),
        'employeePin': source_data.get('employeePin', ''),
        'platform': source_data.get('platform'),
    })
    return merged


def build_context_data(
    user_data: Dict[str, Any],
    doc_id: str
) -> Dict[str, Any]:
    """Build context data for subcollection documents.

    Args:
        user_data: User document data.
        doc_id: Target document ID.

    Returns:
        Context data dictionary.
    """
    return {
        'employee': {
            'id': doc_id,
            'managerId': user_data.get('managerId'),
            'appVersion': user_data.get('appVersion'),
            'companyName': user_data.get('companyName'),
            'deactivatedAt': '',
            'debug': user_data.get('debug'),
            'deviceModel': user_data.get('deviceModel'),
            'deviceName': user_data.get('deviceName'),
            'email': user_data.get('email'),
            'employeeId': user_data.get('employeeId'),
            'employeePin': None,
            'firstName': user_data.get('firstName'),
            'fullName': user_data.get('fullName'),
            'hasPin': user_data.get('hasPin'),
            'inviteCode': user_data.get('inviteCode'),
            'iv': user_data.get('iv'),
            'jobTitle': user_data.get('jobTitle'),
            'language': user_data.get('language'),
            'lastName': user_data.get('lastName'),
            'location': user_data.get('location'),
            'manager': user_data.get('manager'),
            'mdm': False,
            'mobilePhone': user_data.get('mobilePhone'),
            'orgId': user_data.get('orgId'),
            'passwordAdmin': user_data.get('passwordAdmin'),
            'platform': 'ios',
            'role': user_data.get('role'),
            'startDate': '2020-08-04',
            'team': user_data.get('team'),
            'timeZone': '',
        }
    }


def main() -> None:
    """Main entry point for copying user data."""
    db = FsTools(CRED_JSON)

    for doc_id in DOC_IDS:
        src_doc_id = random.choice(SRC_DOC_IDS)

        source_user_data = db.get_doc_by_id('users', src_doc_id)
        if not source_user_data:
            print(f'Source user {src_doc_id} not found, skipping')
            continue

        user_collections = db.db.collection('users').document(src_doc_id).collections()
        orig_user_data = db.get_doc_by_id('users', doc_id)

        if not orig_user_data:
            print(f'Target user {doc_id} not found, skipping')
            continue

        print(f'Updating {doc_id} with {src_doc_id}')

        # Update user document
        merged_data = merge_user_data(orig_user_data, source_user_data, doc_id)
        print(f'\tUpdating {doc_id}')
        db.set_doc_data('users', doc_id, merged_data)

        # Wait for update to propagate
        while db.get_doc_by_id('users', doc_id) != merged_data:
            print(f'Waiting for update: {doc_id}')
            time.sleep(5)

        # Copy subcollection documents
        for user_collection in user_collections:
            for user_doc in user_collection.stream():
                user_doc_id = user_doc.id
                parts = user_doc_id.split('.')

                if len(parts) > 2:
                    parts[1] = doc_id
                    new_user_doc_id = '.'.join(parts)
                    new_wf_id = '.'.join(parts[:-1])
                else:
                    new_user_doc_id = user_doc_id
                    new_wf_id = user_doc.to_dict().get('workflowInstanceId', '')

                user_doc_data = user_doc.to_dict()
                user_doc_data.update({
                    'context': build_context_data(merged_data, doc_id),
                    'id': new_user_doc_id,
                    'workflowInstanceId': new_wf_id,
                })

                print(f'\tAdding to {new_user_doc_id}')
                db.db.collection('users').document(doc_id).collection(user_collection.id).document(new_user_doc_id).set(user_doc_data)

                # Wait for document to be created
                while True:
                    created_doc = db.db.collection('users').document(doc_id).collection(user_collection.id).document(new_user_doc_id).get()
                    if created_doc.exists and created_doc.to_dict() == user_doc_data:
                        break
                    print(f'Waiting for document: {doc_id}')
                    time.sleep(5)


if __name__ == '__main__':
    main()
