import unittest

from infra.core.config import Settings


class SettingsProductionSafetyTest(unittest.TestCase):
    def test_production_rejects_default_secret(self) -> None:
        with self.assertRaisesRegex(ValueError, "SECRET_KEY"):
            Settings(
                ENVIRONMENT="production",
                SECRET_KEY="change-me-in-production",
                DEBUG=False,
                ALLOWED_ORIGINS=["https://app.stockpy.test"],
            )

    def test_production_rejects_debug_mode(self) -> None:
        with self.assertRaisesRegex(ValueError, "DEBUG"):
            Settings(
                ENVIRONMENT="production",
                SECRET_KEY="unit-test-secret",
                DEBUG=True,
                ALLOWED_ORIGINS=["https://app.stockpy.test"],
            )

    def test_production_rejects_wildcard_origins(self) -> None:
        with self.assertRaisesRegex(ValueError, "ALLOWED_ORIGINS"):
            Settings(
                ENVIRONMENT="production",
                SECRET_KEY="unit-test-secret",
                DEBUG=False,
                ALLOWED_ORIGINS=["*"],
            )

    def test_production_accepts_safe_settings(self) -> None:
        settings = Settings(
            ENVIRONMENT="production",
            SECRET_KEY="unit-test-secret",
            DEBUG=False,
            ALLOWED_ORIGINS=["https://app.stockpy.test"],
        )

        self.assertEqual(settings.environment, "production")


if __name__ == "__main__":
    unittest.main()
