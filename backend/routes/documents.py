"""Document routes.

Endpoints:
    GET  /documents                 List all documents, with optional filters.
    GET  /documents/<id>            Get a single document by id.
    PATCH /documents/<id>           Update editable fields on a document.
    GET  /documents/export          Download the catalog as a file
                                    (default: csv).
"""

import csv
import io

from flask import Blueprint, Response, jsonify, request

from backend.routes import error_response, get_repo

documents_bp = Blueprint("documents", __name__)

# Worksheet columns in the same order as the catalog table:
# (header shown in the file, Document attribute).
EXPORT_COLUMNS = (
    ("Original Filename", "original_filename"),
    ("Filename", "filename"),
    ("Media Type", "media_type"),
    ("Source", "source"),
    ("Date", "document_date"),
    ("Summary", "summary"),
    ("Status", "status"),
)


def read_filters():
    """Collect the optional filter query params from the request.

    Returns:
        dict: Only the filters that were sent.
    """
    filters = {}
    for name in ("media_type", "source", "status", "search"):
        value = request.args.get(name)
        if value:
            filters[name] = value
    return filters


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
    documents = get_repo().get_all_documents(read_filters())
    return jsonify([doc.to_dict() for doc in documents]), 200


@documents_bp.route("/documents/export", methods=["GET"])
def export_documents():
    """Export the catalog as a downloadable file.

    Query params (all optional):
        Same filters as GET /documents.
        format (str): 'csv' (default). Other formats are not supported yet.

    Returns:
        200: The worksheet file as a download.
        400: If an unsupported format is requested.
    """
    file_format = request.args.get("format", "csv").lower()
    if file_format != "csv":
        return error_response("unsupported_format",
                              "Only csv export is supported.", 400)

    documents = get_repo().get_all_documents(read_filters())

    # Write the CSV into memory, then send it as the response body.
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([header for header, attribute in EXPORT_COLUMNS])
    for doc in documents:
        writer.writerow([getattr(doc, attribute) or ""
                         for header, attribute in EXPORT_COLUMNS])

    # Content-Disposition tells the browser to save it as a file.
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition":
                 "attachment; filename=cataloga_worksheet.csv"},
    )


@documents_bp.route("/documents/<int:doc_id>", methods=["GET"])
def get_document(doc_id):
    """Return a single document by id.

    Args:
        doc_id (int): The document's primary key.

    Returns:
        200: JSON object for the document.
        404: If the id does not exist.
    """
    doc = get_repo().get_document(doc_id)
    if doc is None:
        return error_response("not_found",
                              "Document {} does not exist.".format(doc_id),
                              404)
    return jsonify(doc.to_dict()), 200


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
        400: If the body is not a JSON object, or has a locked or
             invalid field.
        404: If the id does not exist.
    """
    # silent=True returns None instead of raising on a bad body.
    fields = request.get_json(silent=True)
    if not isinstance(fields, dict):
        return error_response("invalid_body",
                              "The request body must be a JSON object.", 400)
    try:
        doc = get_repo().update_document(doc_id, fields)
    except ValueError as error:
        return error_response("invalid_field", str(error), 400)
    except KeyError:
        return error_response("not_found",
                              "Document {} does not exist.".format(doc_id),
                              404)
    return jsonify(doc.to_dict()), 200
