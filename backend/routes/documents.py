"""Document routes.

Endpoints:
    GET  /documents                 List all documents, with optional filters.
    GET  /documents/<id>            Get a single document by id.
    PATCH /documents/<id>           Update editable fields on a document.
    GET  /documents/export          Download the catalog as a file (default: csv).
"""

from flask import Blueprint, jsonify, request

documents_bp = Blueprint("documents", __name__)


@documents_bp.route("/documents", methods=["GET"])
def list_documents():
    """Return all documents, filtered by optional query params.

    Query params (all optional):
        media_type (str): Filter by media type.
        source (str): Filter by source.
        status (str): Filter by status (Classified or Manual Review).
        search (str): Search across filename, source, and summary.

    Returns:
        200: JSON array of document objects.
    """
    pass


@documents_bp.route("/documents/export", methods=["GET"])
def export_documents():
    """Export the catalog as a downloadable file.

    Query params (all optional):
        Same filters as GET /documents.
        format (str): 'csv' (default) or 'xlsx'.

    Returns:
        200: The worksheet file as a download.
    """
    pass


@documents_bp.route("/documents/<int:doc_id>", methods=["GET"])
def get_document(doc_id):
    """Return a single document by id.

    Args:
        doc_id (int): The document's primary key.

    Returns:
        200: JSON object for the document.
        404: If the id does not exist.
    """
    pass


@documents_bp.route("/documents/<int:doc_id>", methods=["PATCH"])
def update_document(doc_id):
    """Update editable fields on a document.

    Locked fields (original_filename, filename) are rejected with 400.

    Args:
        doc_id (int): The document's primary key.

    Request body (JSON): Any combination of source, document_date,
                         summary, media_type, status.

    Returns:
        200: JSON of the updated document.
        400: If a locked field is included in the request body.
        404: If the id does not exist.
    """
    pass
