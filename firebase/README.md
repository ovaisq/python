# Firebase/Firestore Utilities

A collection of Python utilities for managing Firebase Firestore databases, specifically designed for user and organization management.

## Overview

This project provides a set of command-line tools and a reusable module (`fstools.py`) for common Firebase Firestore operations including:

- Adding users to organizations
- Deleting users by ID or last name
- Copying user data between accounts
- Retrieving documents and workflows
- Exporting user lists to CSV

## Requirements

- Python 3.7+
- Firebase Admin SDK
- Google Cloud Platform service account key (JSON)

## Installation

Install the required dependencies:

```bash
pip install firebase-admin
```

## Module: fstools.py

The `FsTools` class provides a high-level interface for common Firestore operations.

### Usage

```python
from fstools import FsTools

# Initialize with service account key
db = FsTools('path/to/service-account-key.json')

# Get a document by ID
user = db.get_doc_by_id('users', 'user123')

# Query documents by field value
users = db.get_docs_by_filter('users', 'orgId', 'org456')

# Create or update a document
db.set_doc_data('users', 'user123', {'name': 'John', 'email': 'john@example.com'})

# Delete a document
db.delete_document('users/user123')

# Get a subcollection reference
actions = db.get_subcollection('user123', 'users', 'actions')
```

### Available Methods

| Method | Description |
|--------|-------------|
| `get_doc_by_id(collection, doc_id)` | Fetch document data by ID |
| `get_docs_by_filter(collection, field, value)` | Query documents by field value |
| `set_doc_data(collection, doc_id, doc_data)` | Create or update a document |
| `get_subcollection(doc_id, collection, subcollection)` | Get subcollection reference |
| `delete_document(collection_path)` | Delete a document |
| `delete_user_subcollection_doc(user_id, subcollection, doc_id)` | Delete user subcollection document |

## Command-Line Tools

### fs_add_user.py

Add users (manager and employees) to an organization.

```bash
./fs_add_user.py --cred-json service-account-key.json --org-id NQO35YIeMPV1NsJCmncWi --num-users 5
```

**Options:**
- `--cred-json`: Path to GCP Service Account Key JSON file
- `--org-id`: Organization ID
- `--num-users`: Number of employee users to add (plus 1 manager)

### fs_del_user.py

Delete users by ID or last name.

```python
# Edit the script to specify users to delete
ORG_ID = 'NQO35YIeMPV1NsJCmncW'
USER_IDS = ['user_id_1', 'user_id_2', 'last_name_to_delete']
```

### fs_get_org_user_list.py

Export all users for an organization to a tab-separated CSV file.

```bash
./fs_get_org_user_list.py --cred-json service-account-key.json --org-id NQO35YIeMPV1NsJCmncWi
```

Output: `<timestamp>_<org-id>_users.csv`

### fs_get_workflows.py

Retrieve and list all global workflows (excluding filtered categories).

```bash
./fs_get_workflows.py --cred-json service-account-key.json
```

### fs_get_all_docs.py (fs_add_user.py)

Copy user data from source users to target users, including profile data and subcollection documents.

### fs_get_doc.py

Retrieve a specific document by collection and document ID.

### fs_get_org_user_list.py

Get a list of all users for a given organization.

## Configuration

Update the `CRED_JSON` path in each script to point to your Firebase service account key:

```python
CRED_JSON = '/path/to/your/service-account-key.json'
```

## Firebase Setup

1. Go to the [Firebase Console](https://console.firebase.google.com/)
2. Select your project
3. Navigate to **Project Settings** > **Service Accounts**
4. Click **Generate New Private Key**
5. Save the JSON file securely and update the paths in the scripts

## Data Structure

The tools expect the following Firestore structure:

- `orgs/{orgId}` - Organization documents
- `users/{userId}` - User documents
- `users/{userId}/actions/{actionId}` - User action subcollections
- `users/{userId}/history/{historyId}` - User history subcollections
- `globalWorkflows/{workflowId}` - Global workflow definitions

## Security Notes

- Never commit service account keys to version control
- Ensure proper IAM permissions on the service account
- Use separate service accounts for development and production

## License

MIT
