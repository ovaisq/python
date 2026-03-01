#!/usr/bin/env python3
"""
Export user action documents to files.

Exports action documents containing 'Risk' in the ID to JSON files.
"""

import json
from fstools import FsTools

# Firebase service account key path
CRED_JSON = '/Users/username/Downloads/prod-company-mobile-firebase-adminsdk-xxxxx-xxxxx.json'

# Source user document ID
SRC_DOC_ID = 'xxxxxxxxXXXXX'


def main() -> None:
    """Export action documents containing 'Risk' to files."""
    db = FsTools(CRED_JSON)

    actions = db.get_subcollection(SRC_DOC_ID, 'users', 'actions').stream()

    for action_doc in actions:
        if 'Risk' in action_doc.id:
            file_name = f'{action_doc.id}.doc'
            file_dict = json.dumps(str(action_doc.to_dict()))

            with open(file_name, 'w') as f:
                f.write(file_dict)

            print(file_name)


if __name__ == '__main__':
    main()
