import unittest

from fastapi.testclient import TestClient

from apps.public_api import main as public_main


class PublicHtmlRoutesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(public_main.app)

    def tearDown(self) -> None:
        self.client.close()
        public_main.app.dependency_overrides.clear()

    def test_app_platform_and_admin_pages_render_python_html_shells(self) -> None:
        app_response = self.client.get(
            "/app",
            params={
                "public_api_base_url": "https://public.stockpy.local",
                "admin_api_base_url": "https://admin.stockpy.local",
            },
        )
        self.assertEqual(app_response.status_code, 200)
        self.assertIn("text/html", app_response.headers["content-type"])
        self.assertIn("Subscriber workflows stay inside stock-py now.", app_response.text)
        self.assertIn('"publicApiBaseUrl": "https://public.stockpy.local"', app_response.text)
        self.assertIn('"adminApiBaseUrl": "https://admin.stockpy.local"', app_response.text)
        self.assertIn("/v1/auth/send-code", app_response.text)

        platform_response = self.client.get("/platform")
        self.assertEqual(platform_response.status_code, 200)
        self.assertIn("Research and trade lookup without a frontend workspace.", platform_response.text)
        self.assertIn("/v1/search/symbols", platform_response.text)
        self.assertIn("/v1/trades/*", platform_response.text)

        admin_response = self.client.get("/admin")
        self.assertEqual(admin_response.status_code, 200)
        self.assertIn("Admin analytics and runtime control on the same deployment baseline.", admin_response.text)
        self.assertIn("/v1/admin/analytics/*", admin_response.text)
        self.assertIn("/v1/admin/runtime/*", admin_response.text)


if __name__ == "__main__":
    unittest.main()