"""AppConfig.

Reads and writes the app_config and ai_provider_config rows in the database.
Non-secret settings only. The API key is never stored here; it lives in the
OS keyring and is accessed through AIProviderClient.
"""

from backend.db.schema import get_connection


class AppConfig:
    """Manages research settings and active AI provider config."""

    def get_settings(self):
        """Read the current app settings from the database.

        Returns:
            dict: {
                'research_name': str,
                'target_directory': str,
                'active_provider': str or None,
                'active_model': str or None
            }
        """
        pass

    def update_settings(self, research_name, target_directory):
        """Write research_name and target_directory to app_config.

        If no row exists yet, inserts one. Otherwise updates the existing row.

        Args:
            research_name (str): Name of the current research project.
            target_directory (str): Path to the archive folder.
        """
        pass

    def set_active_provider(self, provider_name, model):
        """Mark a provider as active and store its model name.

        Deactivates any previously active provider first.

        Args:
            provider_name (str): e.g. 'gemini'.
            model (str): e.g. 'gemini-2.5-flash'.
        """
        pass

    def set_password_hash(self, password_hash):
        """Store the app-lock password hash in app_config.

        Args:
            password_hash (str): bcrypt or similar hash of the user's password.
        """
        pass

    def get_password_hash(self):
        """Return the stored password hash, or None if no password is set.

        Returns:
            str or None
        """
        pass
