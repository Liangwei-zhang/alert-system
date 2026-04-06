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
            DATABASE_URL="postgresql+asyncpg://user:password@postgres:5432/stock_py",
            DATABASE_POOL_MODE="direct",
        )

        self.assertEqual(
            session_module.build_database_url(settings),
            "postgresql+asyncpg://user:password@postgres:5432/stock_py",
        )
        self.assertEqual(session_module.build_connect_args(settings), {})

    def test_build_engine_uses_null_pool_for_pgbouncer(self) -> None:
        settings = Settings(
            DATABASE_URL=(
                "postgresql+asyncpg://user:password@pgbouncer:6432/stock_py"
                "?prepared_statement_cache_size=25&statement_cache_size=100"
            ),
            DATABASE_POOL_MODE="pgbouncer",
        )

        engine = session_module.build_engine(settings)

        self.assertIs(engine.sync_engine.pool.__class__, NullPool)
        rendered_url = engine.url.render_as_string(hide_password=False)
        self.assertIn("prepared_statement_cache_size=0", rendered_url)
        self.assertNotIn("statement_cache_size=100", rendered_url)
        connect_args = session_module.build_connect_args(settings)
        self.assertEqual(connect_args["statement_cache_size"], 0)
        self.assertIn("prepared_statement_name_func", connect_args)
        prepared_statement_name_func = connect_args["prepared_statement_name_func"]
        self.assertTrue(callable(prepared_statement_name_func))

        statement_name_one = prepared_statement_name_func()
        statement_name_two = prepared_statement_name_func()

        self.assertNotEqual(statement_name_one, statement_name_two)
        self.assertTrue(statement_name_one.startswith("__asyncpg_"))
        self.assertTrue(statement_name_one.endswith("__"))


if __name__ == "__main__":
    unittest.main()
