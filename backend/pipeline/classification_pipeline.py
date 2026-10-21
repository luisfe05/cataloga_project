"""ClassificationPipeline.

Orchestrates the full classification flow for a single file or a batch:
1. Send the file content to the AI provider for classification and summary.
2. Extract source and document date from the AI response.
3. Validate completeness: flag as Manual Review if any field is missing.
4. Generate a serial filename and move the file to the right subdirectory.
5. Hand the finished Document object to CatalogRepository for storage.
"""

from backend.models.document import Document


class ClassificationPipeline:
    """Runs the classify-summarize-organize-catalog flow."""

    def __init__(self, ai_client, catalog_repo, file_organizer):
        """Set up the pipeline with its three dependencies.

        Args:
            ai_client: An AIProviderClient instance for making AI calls.
            catalog_repo: A CatalogRepository instance for database writes.
            file_organizer: A FileOrganizer instance for renaming and moving files.
        """
        self.ai_client = ai_client
        self.db = catalog_repo
        self.file_organizer = file_organizer

    def classify_document(self, file_path):
        """Run the full pipeline on a single file.

        Args:
            file_path (str): Absolute path to the file to process.

        Returns:
            Document: The finished Document object, already saved to the database.
        """
        pass

    def generate_summary(self, text):
        """Request a content summary from the AI provider.

        Args:
            text (str): Extracted text content of the document.

        Returns:
            str: Summary, capped at 500 characters. Empty string if the AI fails.
        """
        pass

    def extract_metadata(self, text):
        """Ask the AI to pull source and document date from the document text.

        Args:
            text (str): Extracted text content of the document.

        Returns:
            dict: {'source': str or None, 'document_date': str or None}
        """
        pass

    def validate_completeness(self, document):
        """Check whether all expected fields were filled in.

        If any field is empty, calls document.mark_needs_review() with a list
        of the missing field names and sets status to 'Manual Review'.

        Args:
            document (Document): The document to validate.

        Returns:
            Document: The same document, possibly with status updated.
        """
        pass

    def process_batch(self, file_list):
        """Run classify_document on every file in a list.

        Args:
            file_list (list[str]): Absolute paths to the files to process.

        Returns:
            list[Document]: One Document per file processed.
        """
        pass
