"""AppConfig.

Reads and writes the settings saved in one project's catalog: the
research name, the project folder, the file naming template, and the
active AI provider. Non-secret settings only. The API key is never
stored here; it lives in the OS keyring and is accessed through
AIProviderClient.

All database access goes through CatalogRepository, the app's SQLite
layer, so AppConfig never runs SQL itself.
"""

from backend.pipeline import naming

# Interface languages the app offers. English is the default. The
# choice is the same for every project, so it is saved in the project
# list (see projects.py), not in a project's catalog.
LANGUAGES = ("en", "es")


class AppConfig:
    """Manages research settings and active AI provider config."""

    def __init__(self, catalog_repo):
        """Set up AppConfig with the repository it reads and writes through.

        Args:
            catalog_repo (CatalogRepository): The app's database layer.
        """
        self.db = catalog_repo

    def get_settings(self):
        """Read the current app settings.

        Returns:
            dict: {
                'research_name': str,
                'target_directory': str,
                'naming_template': str, e.g. '{date}_{topic}',
                'active_provider': str or None,
                'active_model': str or None
            }
            Text fields are empty strings before the first setup.
        """
        config = self.db.get_app_config() or {}
        provider = self.db.get_active_provider() or {}
        return {
            "research_name": config.get("research_name", ""),
            "target_directory": config.get("target_directory", ""),
            "naming_template": config.get("naming_template",
                                          naming.DEFAULT_TEMPLATE),
            "active_provider": provider.get("provider_name"),
            "active_model": provider.get("model"),
        }

    def update_settings(self, research_name, target_directory):
        """Save research_name and target_directory.

        Args:
            research_name (str): Name of the current research project.
            target_directory (str): Path to the archive folder.
        """
        self.db.save_app_config(research_name, target_directory)

    def update_naming_template(self, template):
        """Save the file naming template. Only new files use it.

        Args:
            template (str): One of naming.METHOD_TEMPLATES or a custom one.

        Raises:
            ValueError: If naming.validate_template() finds a problem.
        """
        problem = naming.validate_template(template)
        if problem:
            raise ValueError("invalid naming template: " +
                             problem["reason"])
        self.db.save_naming_template(template)

    def set_active_provider(self, provider_name, model):
        """Mark a provider as active and store its model name.

        Args:
            provider_name (str): e.g. 'gemini'.
            model (str): e.g. 'gemini-2.5-flash'.
        """
        self.db.set_active_provider(provider_name, model)

    def set_password_hash(self, password_hash):
        """Store the app-lock password hash in app_config.

        Planned for task S2-8 (app lock password).

        Args:
            password_hash (str): Hash of the user's password.
        """
        pass

    def get_password_hash(self):
        """Return the stored password hash, or None if no password is set.

        Planned for task S2-8 (app lock password).

        Returns:
            str or None
        """
        pass
