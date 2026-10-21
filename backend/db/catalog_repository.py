"""CatalogRepository.

The single place in the codebase that reads from and writes to the database.
All other modules call methods here instead of running SQL directly.
"""

from backend.db.schema import get_connection
from backend.models.document import Document, LOCKED_FIELDS


class CatalogRepository:
    """Owns all database reads and writes for documents and activity_log."""

    def add_document(self, doc):
        """Insert a new document row and log the 'classified' event.

        Args:
            doc (Document): The document to save.

        Returns:
            Document: The same document with its id set from the new row.
        """
        pass

    def get_all_documents(self, filters=None):
        """Return all documents, optionally filtered.

        Args:
            filters (dict, optional): Keys: media_type, source, status, search.

        Returns:
            list[Document]: Matching documents.
        """
        pass

    def get_by_status(self, status):
        """Return all documents with the given status.

        Args:
            status (str): 'Classified' or 'Manual Review'.

        Returns:
            list[Document]: Matching documents.
        """
        pass

    def update_document(self, doc_id, fields):
        """Update editable fields on a document.

        Rejects any attempt to change original_filename or filename with a
        ValueError, which the route will translate into a 400 response.

        Args:
            doc_id (int): The document's primary key.
            fields (dict): Field names and new values.

        Returns:
            Document: The updated document.

        Raises:
            ValueError: If fields contains a locked field name.
            KeyError: If doc_id does not exist.
        """
        pass

    def get_dashboard_stats(self):
        """Return aggregate data for the dashboard.

        Returns:
            dict: {
                'documents_classified': int,
                'needs_manual_review': int,
                'sources_tracked': int,
                'media_type_breakdown': {type: count, ...},
                'recent_activity': [{'filename': str, 'action': str,
                                     'timestamp': str}, ...]
            }
        """
        pass
