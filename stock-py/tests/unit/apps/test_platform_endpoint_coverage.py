import re
import unittest
from pathlib import Path


class PlatformEndpointCoverageTest(unittest.TestCase):
    def test_platform_endpoint_catalog_matches_public_user_routes(self) -> None:
        root = Path(__file__).resolve().parents[3]
        backend_routes = self._collect_backend_platform_routes(root)
        frontend_routes = self._collect_frontend_platform_catalog(root)

        missing_in_frontend = sorted(backend_routes - frontend_routes)
        extra_in_frontend = sorted(frontend_routes - backend_routes)

        self.assertEqual(
            missing_in_frontend,
            [],
            msg=f"Platform endpoint catalog is missing backend routes: {missing_in_frontend}",
        )
        self.assertEqual(
            extra_in_frontend,
            [],
            msg=f"Platform endpoint catalog has non-backend routes: {extra_in_frontend}",
        )

    @staticmethod
    def _collect_backend_platform_routes(root: Path) -> set[tuple[str, str]]:
        routes: set[tuple[str, str]] = set()
        routers_dir = root / "apps" / "public_api" / "routers"
        router_files = (
            "auth.py",
            "account.py",
            "watchlist.py",
            "portfolio.py",
            "search.py",
            "notifications.py",
            "trades.py",
        )

        prefix_pattern = re.compile(
            r"APIRouter\((?:.|\n)*?prefix\s*=\s*['\"]([^'\"]+)['\"]",
            re.S,
        )
        route_pattern = re.compile(
            r"@router\.(get|post|put|patch|delete)\((?:\n\s*)?['\"]([^'\"]*)['\"]"
        )

        for file_name in router_files:
            source = (routers_dir / file_name).read_text(encoding="utf-8")
            prefix_match = prefix_pattern.search(source)
            prefix = prefix_match.group(1) if prefix_match else ""

            for method, path in route_pattern.findall(source):
                route_path = PlatformEndpointCoverageTest._join_path(prefix, path)
                full_path = PlatformEndpointCoverageTest._join_path("/v1", route_path)
                routes.add((method.upper(), full_path))

        return routes

    @staticmethod
    def _collect_frontend_platform_catalog(root: Path) -> set[tuple[str, str]]:
        source = (root / "apps" / "public_api" / "ui_shell.py").read_text(encoding="utf-8")
        script_match = re.search(r'_PLATFORM_SCRIPT\s*=\s*"""(.*?)"""', source, re.S)
        if not script_match:
            raise AssertionError("Could not locate _PLATFORM_SCRIPT block in ui_shell.py")

        script = script_match.group(1)
        endpoint_pattern = re.compile(
            r'endpoint\("(GET|POST|PUT|PATCH|DELETE)",\s*"([^\"]+)"'
        )
        return {(method, path) for method, path in endpoint_pattern.findall(script)}

    @staticmethod
    def _join_path(prefix: str, path: str) -> str:
        normalized_prefix = str(prefix or "").rstrip("/")
        normalized_path = str(path or "").strip()

        if not normalized_path:
            return normalized_prefix or "/"
        if normalized_path.startswith("/"):
            return f"{normalized_prefix}{normalized_path}" if normalized_prefix else normalized_path
        return f"{normalized_prefix}/{normalized_path}" if normalized_prefix else f"/{normalized_path}"


if __name__ == "__main__":
    unittest.main()
