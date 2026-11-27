const {defineConfig, devices} = require('@playwright/test');

module.exports = defineConfig({
    testDir: './tests',
    globalSetup: require.resolve('./global-setup'),
    timeout: 180_000,
    expect: {timeout: 15_000},
    fullyParallel: false,
    workers: 1,
    retries: process.env.CI ? 1 : 0,
    reporter: process.env.CI ? [['list'], ['html', {open: 'never'}]] : 'list',
    use: {
        baseURL: process.env.E2E_BASE_URL || 'http://localhost:8081',
        trace: 'retain-on-failure',
        video: 'retain-on-failure',
    },
    projects: [{name: 'chromium', use: {...devices['Desktop Chrome']}}],
});
