#!/usr/bin/env python3
"""Get Global Workflows.

Requires:
    1. A GCP Service Account key with appropriate permissions

Example:
    ./fs_get_workflows.py --cred-json xxxxxx.json
"""

import argparse
from typing import List, Dict, Any

from fstools import FsTools


def main() -> None:
    """Main entry point for listing global workflows."""
    arg_parser = argparse.ArgumentParser(
        description='Get Global Workflows List'
    )
    arg_parser.add_argument(
        '--cred-json',
        dest='cred_json',
        required=True,
        help='GCP Service Account Key JSON file path'
    )

    args = arg_parser.parse_args()

    db = FsTools(args.cred_json)

    labels: List[str] = []
    filter_out = [
        'Feedback', 'weekdayCheckIn', 'tos', 'onboarding', 'top', 'high',
        'shout', 'follow', 'manager', 'passcode', 'Covid', 'never',
        'reports', 'demo'
    ]

    workflow_docs = db.db.collection('globalWorkflows').stream()

    for workflow in workflow_docs:
        # Skip workflows with filtered labels
        if any(substring in workflow.id for substring in filter_out):
            continue

        workflow_data = db.get_doc_by_id('globalWorkflows', workflow.id)
        if workflow_data and 'states' in workflow_data:
            label = workflow_data['states']['main']['mobileFlow']['label']
            labels.append(label)

    # Remove duplicates while preserving order
    unique_labels = list(dict.fromkeys(labels))

    print(labels)
    print(unique_labels)


if __name__ == '__main__':
    main()
