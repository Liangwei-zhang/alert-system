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
        self.assertIn("普通订阅用户现在可以只维护一份离线优先草稿。", app_response.text)
        self.assertIn('"publicApiBaseUrl": "https://public.stockpy.local"', app_response.text)
        self.assertIn('"adminApiBaseUrl": "https://admin.stockpy.local"', app_response.text)
        self.assertIn("/v1/auth/send-code", app_response.text)
        self.assertIn("订阅登录", app_response.text)
        self.assertIn("本地订阅草稿", app_response.text)
        self.assertIn("POST /v1/account/start-subscription", app_response.text)
        self.assertIn("restore-remote-draft", app_response.text)
        self.assertIn("start-subscription-button", app_response.text)

        platform_response = self.client.get("/platform")
        self.assertEqual(platform_response.status_code, 200)
        self.assertIn("无需前端工作区，也能完成研究与交易查询。", platform_response.text)
        self.assertIn("/v1/search/symbols", platform_response.text)
        self.assertIn("/v1/trades/*", platform_response.text)
        self.assertIn("platform-portfolio-form", platform_response.text)
        self.assertIn("platform-update-watchlist-form", platform_response.text)
        self.assertIn("platform-update-portfolio-form", platform_response.text)
        self.assertIn("app-confirm-trade", platform_response.text)
        self.assertIn("app-adjust-trade", platform_response.text)
        self.assertIn("public-confirm-trade", platform_response.text)
        self.assertIn("platform-endpoint-matrix", platform_response.text)
        self.assertIn("platform-endpoint-console-form", platform_response.text)

        admin_response = self.client.get("/admin")
        self.assertEqual(admin_response.status_code, 200)
        self.assertIn('data-page="dashboard"', admin_response.text)
        self.assertIn("管理控制台 | Stock-Py", admin_response.text)
        self.assertIn("./js/admin-live.js", admin_response.text)
        self.assertIn("./js/api-maps.js", admin_response.text)

        admin_people_response = self.client.get("/admin/people.html")
        self.assertEqual(admin_people_response.status_code, 200)
        self.assertIn('data-page="people"', admin_people_response.text)

        admin_app_script_response = self.client.get("/admin/js/admin-app.js")
        self.assertEqual(admin_app_script_response.status_code, 200)
        self.assertIn("renderAdminCapabilityCoverage", admin_app_script_response.text)
        self.assertIn("topbar-endpoint-search", admin_app_script_response.text)
        self.assertIn("data-module-target", admin_app_script_response.text)
        self.assertIn('const ADMIN_UI_BUILD = "2026-04-07-r2"', admin_app_script_response.text)

        admin_api_maps_script_response = self.client.get("/admin/js/api-maps.js")
        self.assertEqual(admin_api_maps_script_response.status_code, 200)
        self.assertIn("data-admin-console-select", admin_api_maps_script_response.text)
        self.assertIn("focusConsole", admin_api_maps_script_response.text)


if __name__ == "__main__":
    unittest.main()