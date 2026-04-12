const { defineConfig } = require('@playwright/test');

module.exports = defineConfig({
    testDir: './tests/playwright',
    timeout: 30_000,
    expect: {
        timeout: 10_000,
    },
    reporter: [
        ['list'],
        ['html', { outputFolder: 'playwright-report', open: 'never' }],
    ],
    use: {
        browserName: 'chromium',
        headless: true,
        viewport: { width: 1440, height: 1080 },
        trace: 'retain-on-failure',
        screenshot: 'only-on-failure',
        video: 'retain-on-failure',
    },
    webServer: {
        command: 'python3 -m http.server 4173',
        port: 4173,
        reuseExistingServer: !process.env.CI,
        timeout: 30_000,
    },
});