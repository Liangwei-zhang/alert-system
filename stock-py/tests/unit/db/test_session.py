import unittest

from sqlalchemy.pool import NullPool

from infra.core.config import Settings
from infra.db import session as session_module


class SessionEngineConfigTest(unittest.TestCase):
    def tearDown(self) -> None:
        session_module._engine = None
        session_module._session_factory = None

    def test_build_database_url_keeps_direct_url_unchanged(self) -> None:
        settings = Settings(
            DATABASE_URL="postgresql+asyncpg://user:password@postgres:5432/stock",
            DATABASE_POOL_MODE="direct",
        )

        self.assertEqual(
            session_module.build_database_url(settings),
            "postgresql+asyncpg://user:password@postgres:5432/stock",
        )

    def test_build_engine_uses_null_pool_for_pgbouncer(self) -> None:
        settings = Settings(
            DATABASE_URL="postgresql+asyncpg://user:password@pgbouncer:6432/stock",
            DATABASE_POOL_MODE="pgbouncer",
        )

        engine = session_module.build_engine(settings)

        self.assertIs(engine.sync_engine.pool.__class__, NullPool)
        self.assertIn(
            "prepared_statement_cache_size=0",
            engine.url.render_as_string(hide_password=False),
        )


if __name__ == "__main__":
    unittest.main()
