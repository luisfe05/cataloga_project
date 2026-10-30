"""AppConfig."""

from backend.pipeline import archive_rules, naming

# The language is global, so it lives in projects.json, not in a catalog.
LANGUAGES = ("en", "es")


class AppConfig:
    """Manages research settings and active AI provider config."""

    def __init__(self, catalog_repo):
        """Set up AppConfig with the repository it reads and writes through."""
        self.db = catalog_repo

    def get_settings(self):
        """Read the current app settings."""
        config = self.db.get_app_config() or {}
        provider = self.db.get_active_provider() or {}
        return {
            "research_name": config.get("research_name", ""),
            "target_directory": config.get("target_directory", ""),
            "naming_template": config.get("naming_template",
                                          naming.DEFAULT_TEMPLATE),
            "stamp_date_order": self.db.stamp_date_order(),
            "industry": config.get("industry") or "",
            "categories": archive_rules.categories_from_text(
                config.get("categories")),
            "active_provider": provider.get("provider_name"),
            "active_model": provider.get("model"),
        }

    def update_settings(self, research_name, target_directory):
        """Save research_name and target_directory."""
        self.db.save_app_config(research_name, target_directory)

    def update_naming_template(self, template):
        """Save the file naming template. Only new files use it."""
        problem = naming.validate_template(template)
        if problem:
            raise ValueError("invalid naming template: " +
                             problem["reason"])
        self.db.save_naming_template(template)

    def update_categories(self, industry, categories):
        """Save the industry and the checked category list."""
        self.db.save_industry(industry)
        self.db.save_categories(categories)

    def set_active_provider(self, provider_name, model):
        """Mark a provider as active and store its model name."""
        self.db.set_active_provider(provider_name, model)

    def set_password_hash(self, password_hash):
        """Store the app-lock password hash in app_config."""
        pass

    def get_password_hash(self):
        """Return the stored password hash, or None if no password is set."""
        pass
