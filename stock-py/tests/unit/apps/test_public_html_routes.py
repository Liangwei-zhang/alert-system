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
        app_response = self.client.get("/app")
        self.assertEqual(app_response.status_code, 200)
        self.assertIn("text/html", app_response.headers["content-type"])
        self.assertIn("/v1/auth/send-code", app_response.text)
        self.assertIn("当前离线草稿模式，登录后可一键同步到后台。", app_response.text)
        self.assertIn("开始订阅 (本地同步)", app_response.text)
        self.assertIn("通知中心", app_response.text)
        self.assertIn("浏览器推送", app_response.text)
        self.assertIn("sendPushTest()", app_response.text)
        self.assertIn("/app/sw.js", app_response.text)

        app_notifications_response = self.client.get("/app/notifications")
        self.assertEqual(app_notifications_response.status_code, 200)
        self.assertIn("通知中心", app_notifications_response.text)
        self.assertIn("notificationScopeCount('all')", app_notifications_response.text)

        platform_response = self.client.get("/platform")
        self.assertEqual(platform_response.status_code, 200)
        self.assertIn("策略驾驶舱", platform_response.text)
        self.assertIn("你当前看到的是稳定版桌面端", platform_response.text)
        self.assertIn("/next/platform/", platform_response.text)
        self.assertIn("/ui-versions/", platform_response.text)
        self.assertIn("Desktop Workbench", platform_response.text)
        self.assertIn("Desktop Access", platform_response.text)
        self.assertIn("Desktop Launchpad", platform_response.text)
        self.assertIn("桌面端验证码登录", platform_response.text)
        self.assertIn("Execution Relay", platform_response.text)
        self.assertIn("Research Relay", platform_response.text)
        self.assertIn("命令面板", platform_response.text)
        self.assertIn("platform-deck-tradingagents.js", platform_response.text)
        self.assertIn("platform-deck-workspace.js", platform_response.text)
        self.assertIn("platform-deck.js", platform_response.text)

        platform_execution_response = self.client.get("/platform/execution?symbol=NVDA", follow_redirects=False)
        self.assertEqual(platform_execution_response.status_code, 307)
        self.assertEqual(
            platform_execution_response.headers["location"],
            "/platform/?mode=execution&section=exit-desk-panel&symbol=NVDA",
        )

        admin_response = self.client.get("/admin")
        self.assertEqual(admin_response.status_code, 200)
        self.assertIn('data-page="dashboard"', admin_response.text)
        self.assertIn("管理控制台 | Stock-Py", admin_response.text)
        self.assertIn("./js/admin-live.js", admin_response.text)
        self.assertIn("./js/api-maps.js", admin_response.text)

        admin_people_response = self.client.get("/admin/people.html")
        self.assertEqual(admin_people_response.status_code, 200)
        self.assertIn('data-page="people"', admin_people_response.text)

        admin_people_clean_response = self.client.get("/admin/people")
        self.assertEqual(admin_people_clean_response.status_code, 200)
        self.assertIn('data-page="people"', admin_people_clean_response.text)

        admin_runtime_clean_response = self.client.get("/admin/runtime")
        self.assertEqual(admin_runtime_clean_response.status_code, 200)
        self.assertIn('data-page="runtime"', admin_runtime_clean_response.text)

        admin_app_script_response = self.client.get("/admin/js/admin-app.js")
        self.assertEqual(admin_app_script_response.status_code, 200)
        self.assertIn("renderAdminCapabilityCoverage", admin_app_script_response.text)
        self.assertIn("topbar-endpoint-search", admin_app_script_response.text)
        self.assertIn("data-module-target", admin_app_script_response.text)
        self.assertIn('const ADMIN_UI_BUILD = "2026-04-07-r2"', admin_app_script_response.text)
        self.assertIn('href: adminRoute("people")', admin_app_script_response.text)
        self.assertIn('href: adminRoute("runtime")', admin_app_script_response.text)
        self.assertIn('/next/admin/', admin_app_script_response.text)
        self.assertIn('/ui-versions/', admin_app_script_response.text)

        admin_api_maps_script_response = self.client.get("/admin/js/api-maps.js")
        self.assertEqual(admin_api_maps_script_response.status_code, 200)
        self.assertIn("data-admin-console-select", admin_api_maps_script_response.text)
        self.assertIn("focusConsole", admin_api_maps_script_response.text)

    def test_platform_javascript_assets_expose_desktop_workflow_entrypoints(self) -> None:
        workspace_script_response = self.client.get("/platform/js/platform-deck-workspace.js")
        self.assertEqual(workspace_script_response.status_code, 200)
        self.assertIn("openCommandPalette(initialQuery = '')", workspace_script_response.text)
        self.assertIn("handoffSelectedToBacktest()", workspace_script_response.text)
        self.assertIn("applySelectedResearchPreset()", workspace_script_response.text)
        self.assertIn("selectedResearchSummary()", workspace_script_response.text)
        self.assertIn("workspaceLaunchpadCards()", workspace_script_response.text)
        self.assertIn("applyWorkspaceFirstScreenState(options = {})", workspace_script_response.text)
        self.assertIn("runDeskAction(actionId)", workspace_script_response.text)

        tradingagents_script_response = self.client.get("/platform/js/platform-deck-tradingagents.js")
        self.assertEqual(tradingagents_script_response.status_code, 200)
        self.assertIn("submitTradingAgentsAnalysis()", tradingagents_script_response.text)
        self.assertIn("pollPendingTradingAgentsRuns(force = false)", tradingagents_script_response.text)

        platform_script_response = self.client.get("/platform/js/platform-deck.js")
        self.assertEqual(platform_script_response.status_code, 200)
        self.assertIn("sendAdminCode()", platform_script_response.text)
        self.assertIn("verifyAdminCode()", platform_script_response.text)
        self.assertIn("refreshAdminSession(options = {})", platform_script_response.text)
        self.assertIn("triggerBacktestRefresh()", platform_script_response.text)
        self.assertIn("const routeMode = String(params.get('mode') || '').trim().toLowerCase();", platform_script_response.text)
        self.assertIn("const routeSection = String(params.get('section') || '').trim();", platform_script_response.text)
        self.assertIn("const routeSymbol = String(params.get('symbol') || '').trim().toUpperCase();", platform_script_response.text)
        self.assertIn("window.platformDeck = platformDeck", platform_script_response.text)


if __name__ == "__main__":
    unittest.main()