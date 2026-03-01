#!/usr/bin/env python3
"""
Firebase/Firestore utility module for common database operations.

Usage:
    from fstools import FsTools
    db = FsTools(cred_json_path)
"""

import firebase_admin
from firebase_admin import credentials, firestore
from typing import Any, Dict, List, Optional


class FsTools:
    """Firebase Firestore helper class for common database operations."""

    def __init__(self, cred_json: str) -> None:
        """Initialize Firebase admin client with service account credentials.

        Args:
            cred_json: Path to the Firebase service account JSON key file.
        """
        self.cred = credentials.Certificate(cred_json)
        firebase_admin.initialize_app(self.cred)
        self.db = firestore.client()

    def get_doc_by_id(self, collection: str, doc_id: str) -> Optional[Dict[str, Any]]:
        """Fetch document data by ID from a collection.

        Args:
            collection: Name of the collection.
            doc_id: Document ID to fetch.

        Returns:
            Document data as dictionary, or None if document doesn't exist.
        """
        doc = self.db.collection(collection).document(doc_id).get()
        return doc.to_dict() if doc.exists else None

    def get_docs_by_filter(
        self, collection: str, field: str, value: Any
    ) -> firestore.Query:
        """Get documents from a collection filtered by field value.

        Args:
            collection: Name of the collection.
            field: Field name to filter on.
            value: Value to match.

        Returns:
            Firestore Query object (call .stream() to iterate results).
        """
        return self.db.collection(collection).where(field, '==', value)

    def set_doc_data(
        self, collection: str, doc_id: str, doc_data: Dict[str, Any]
    ) -> None:
        """Create or update a document in a collection.

        Args:
            collection: Name of the collection.
            doc_id: Document ID to set.
            doc_data: Dictionary of document data.
        """
        self.db.collection(collection).document(doc_id).set(doc_data)

    def get_subcollection(self, doc_id: str, collection: str, subcollection: str) -> firestore.CollectionReference:
        """Get a subcollection reference for a given document.

        Args:
            doc_id: Parent document ID.
            collection: Parent collection name.
            subcollection: Subcollection name (e.g., 'actions', 'history').

        Returns:
            Firestore CollectionReference object.
        """
        return self.db.collection(collection).document(doc_id).collection(subcollection)

    def delete_document(self, collection_path: str) -> None:
        """Delete a document from a collection.

        Args:
            collection_path: Full path to the document (e.g., 'orgs/org123' or
                           'users/user123/actions/action456').
        """
        self.db.document(collection_path).delete()

    def delete_user_subcollection_doc(
        self, user_id: str, subcollection: str, doc_id: str
    ) -> None:
        """Delete a document from a user's subcollection.

        Args:
            user_id: User document ID.
            subcollection: Subcollection name ('actions' or 'history').
            doc_id: Document ID to delete.
        """
        self.delete_document(f'users/{user_id}/{subcollection}/{doc_id}')
