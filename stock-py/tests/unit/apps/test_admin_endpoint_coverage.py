import re
import unittest
from pathlib import Path


class AdminEndpointCoverageTest(unittest.TestCase):
    def test_admin_frontend_endpoint_catalog_matches_backend_routes(self) -> None:
        root = Path(__file__).resolve().parents[3]
        backend_routes = self._collect_backend_admin_routes(root)
        frontend_routes = self._collect_frontend_endpoint_catalog(root)

        missing_in_frontend = sorted(backend_routes - frontend_routes)
        extra_in_frontend = sorted(frontend_routes - backend_routes)

        self.assertEqual(
            missing_in_frontend,
            [],
            msg=f"Frontend endpoint catalog is missing backend routes: {missing_in_frontend}",
        )
        self.assertEqual(
            extra_in_frontend,
            [],
            msg=f"Frontend endpoint catalog has non-backend routes: {extra_in_frontend}",
        )

    @staticmethod
    def _collect_backend_admin_routes(root: Path) -> set[tuple[str, str]]:
        routes: set[tuple[str, str]] = set()
        routers_dir = root / "apps" / "admin_api" / "routers"

        prefix_pattern = re.compile(
            r"APIRouter\((?:.|\n)*?prefix\s*=\s*['\"]([^'\"]+)['\"]",
            re.S,
        )
        route_pattern = re.compile(
            r"@router\.(get|post|put|patch|delete)\((?:\n\s*)?['\"]([^'\"]*)['\"]"
        )

        for file_path in routers_dir.glob("*.py"):
            source = file_path.read_text(encoding="utf-8")
            prefix_match = prefix_pattern.search(source)
            prefix = prefix_match.group(1) if prefix_match else ""

            for method, path in route_pattern.findall(source):
                full_path = AdminEndpointCoverageTest._join_path(prefix, path)
                routes.add((method.upper(), full_path))

        return routes

    @staticmethod
    def _collect_frontend_endpoint_catalog(root: Path) -> set[tuple[str, str]]:
        source = (root / "frontend" / "admin" / "js" / "api-maps.js").read_text(
            encoding="utf-8"
        )
        endpoint_pattern = re.compile(
            r'endpoint\("(GET|POST|PUT|PATCH|DELETE)",\s*"([^\"]+)"'
        )
        return {(method, path) for method, path in endpoint_pattern.findall(source)}

    @staticmethod
    def _join_path(prefix: str, path: str) -> str:
        if not path:
            return prefix
        if path.startswith("/"):
            return f"{prefix}{path}"
        return f"{prefix}/{path}"


if __name__ == "__main__":
    unittest.main()
