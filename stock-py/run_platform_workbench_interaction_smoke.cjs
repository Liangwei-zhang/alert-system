'use strict';

const fs = require('fs');
const path = require('path');
const vm = require('vm');
const { execFileSync } = require('child_process');

const FRONTEND_SCRIPT_FILES = [
    'frontend/platform/js/platform-deck-constants.js',
    'frontend/platform/js/platform-deck-utils.js',
    'frontend/platform/js/platform-deck-tradingagents.js',
    'frontend/platform/js/platform-deck-workspace.js',
    'frontend/platform/js/platform-deck.js',
];

function emit(payload) {
    process.stdout.write(`${JSON.stringify(payload)}\n`);
}

class SmokeFailure extends Error {
    constructor(step, message, details = {}) {
        super(message);
        this.name = 'SmokeFailure';
        this.step = step;
        this.details = {
            message,
            ...details,
        };
    }
}

function fail(step, message, details = {}) {
    throw new SmokeFailure(step, message, details);
}

function parseArgs(argv) {
    const options = {
        publicBaseUrl: 'http://127.0.0.1:8000',
        adminBaseUrl: 'http://127.0.0.1:8001',
        email: '',
        timeoutSeconds: 20,
        resetRateLimit: true,
    };

    for (let index = 0; index < argv.length; index += 1) {
        const arg = argv[index];
        if (arg === '--public-base-url') {
            options.publicBaseUrl = String(argv[index + 1] || '').trim() || options.publicBaseUrl;
            index += 1;
            continue;
        }
        if (arg === '--admin-base-url') {
            options.adminBaseUrl = String(argv[index + 1] || '').trim() || options.adminBaseUrl;
            index += 1;
            continue;
        }
        if (arg === '--email') {
            options.email = String(argv[index + 1] || '').trim();
            index += 1;
            continue;
        }
        if (arg === '--timeout') {
            const parsed = Number.parseFloat(String(argv[index + 1] || '').trim());
            if (Number.isFinite(parsed) && parsed > 0) {
                options.timeoutSeconds = parsed;
            }
            index += 1;
            continue;
        }
        if (arg === '--no-reset-rate-limit') {
            options.resetRateLimit = false;
            continue;
        }
        fail('args', `Unknown argument: ${arg}`);
    }

    return options;
}

function normalizeBaseUrl(value) {
    return String(value || '').trim().replace(/\/+$/, '');
}

function resolvePythonExecutable(repoRoot) {
    const venvPython = path.join(repoRoot, '.venv', 'bin', 'python');
    if (fs.existsSync(venvPython)) {
        return venvPython;
    }
    return process.env.PYTHON || 'python3';
}

function runPythonSnippet(repoRoot, pythonExecutable, code) {
    return execFileSync(pythonExecutable, ['-c', code], {
        cwd: repoRoot,
        encoding: 'utf8',
        stdio: ['ignore', 'pipe', 'pipe'],
    });
}

function lastNonEmptyLine(value) {
    const lines = String(value || '')
        .split(/\r?\n/)
        .map((line) => line.trim())
        .filter(Boolean);
    return lines.length ? lines[lines.length - 1] : '';
}

function resolveAdminEmail(repoRoot, pythonExecutable, preferredEmail) {
    if (preferredEmail) {
        return preferredEmail;
    }
    return lastNonEmptyLine(runPythonSnippet(
        repoRoot,
        pythonExecutable,
        [
            'import asyncio',
            'import run_platform_workbench_smoke as smoke',
            'print(asyncio.run(smoke.resolve_default_operator_email()))',
        ].join('\n')
    ));
}

function resetRateLimit(repoRoot, pythonExecutable, email) {
    const deleted = lastNonEmptyLine(runPythonSnippet(
        repoRoot,
        pythonExecutable,
        [
            'import asyncio',
            'from infra.cache.redis_client import get_redis, close_redis',
            `EMAIL = ${JSON.stringify(email)}`,
            'KEY = f"rate-limit:auth:send-code:{EMAIL.strip().lower()}"',
            'async def main():',
            '    client = await get_redis()',
            '    deleted = await client.delete(KEY)',
            '    print(deleted)',
            '    await close_redis()',
            'asyncio.run(main())',
        ].join('\n')
    ));
    const parsed = Number.parseInt(String(deleted || '').trim(), 10);
    return Number.isFinite(parsed) ? parsed : 0;
}

function createLocalStorage() {
    const values = new Map();
    return {
        getItem(key) {
            return values.has(key) ? values.get(key) : null;
        },
        setItem(key, value) {
            values.set(key, String(value));
        },
        removeItem(key) {
            values.delete(key);
        },
        clear() {
            values.clear();
        },
    };
}

function createDocument() {
    const elements = new Map();
    return {
        addEventListener() {},
        getElementById(id) {
            if (!elements.has(id)) {
                elements.set(id, {
                    id,
                    scrollIntoView() {},
                });
            }
            return elements.get(id);
        },
    };
}

function createFrontendHarness(repoRoot, publicBaseUrl, adminBaseUrl, timeoutSeconds) {
    const normalizedPublicBaseUrl = normalizeBaseUrl(publicBaseUrl);
    const normalizedAdminBaseUrl = normalizeBaseUrl(adminBaseUrl);
    const localStorage = createLocalStorage();
    const document = createDocument();
    const publicUrl = new URL(normalizedPublicBaseUrl);
    const query = new URLSearchParams({
        admin_api_base_url: normalizedAdminBaseUrl,
        public_api_base_url: normalizedPublicBaseUrl,
    });

    const fetchWithTimeout = (url, options = {}) => {
        const requestOptions = { ...options };
        if (!requestOptions.signal && typeof AbortSignal !== 'undefined' && typeof AbortSignal.timeout === 'function') {
            requestOptions.signal = AbortSignal.timeout(Math.ceil(timeoutSeconds * 1000));
        }
        return fetch(url, requestOptions);
    };

    const windowObject = {
        location: {
            search: `?${query.toString()}`,
            origin: publicUrl.origin,
            protocol: publicUrl.protocol,
            hostname: publicUrl.hostname,
            port: publicUrl.port,
            href: `${normalizedPublicBaseUrl}/platform/?${query.toString()}`,
        },
        navigator: {
            language: 'en-US',
        },
        lucide: null,
    };
    windowObject.window = windowObject;
    windowObject.localStorage = localStorage;
    windowObject.document = document;

    const intervalStub = () => 0;
    const timeoutStub = (callback) => {
        if (typeof callback === 'function') {
            callback();
        }
        return 0;
    };

    const context = vm.createContext({
        console,
        window: windowObject,
        document,
        localStorage,
        fetch: fetchWithTimeout,
        Headers,
        URLSearchParams,
        Intl,
        Date,
        Math,
        JSON,
        Promise,
        setInterval: intervalStub,
        clearInterval() {},
        setTimeout: timeoutStub,
        clearTimeout() {},
    });

    for (const relativePath of FRONTEND_SCRIPT_FILES) {
        const absolutePath = path.join(repoRoot, relativePath);
        const code = fs.readFileSync(absolutePath, 'utf8');
        vm.runInContext(code, context, { filename: relativePath });
    }

    const createDeck = () => {
        const deck = windowObject.platformDeck();
        deck.$nextTick = (callback) => {
            if (typeof callback === 'function') {
                callback();
            }
        };
        deck.$refs = {
            adminEmailInput: { focus() {}, select() {} },
            adminVerifyEmailInput: { focus() {}, select() {} },
            adminCodeInput: { focus() {}, select() {} },
        };
        return deck;
    };

    return {
        createDeck,
        localStorage,
    };
}

function summarizeLaunchpadCards(cards) {
    return cards.map((card) => ({
        id: card.id,
        title: card.title,
        status: card.status,
        actionId: card.actionId,
        secondaryActionId: card.secondaryActionId || '',
    }));
}

async function main() {
    const repoRoot = process.cwd();
    const options = parseArgs(process.argv.slice(2));
    const pythonExecutable = resolvePythonExecutable(repoRoot);
    const email = resolveAdminEmail(repoRoot, pythonExecutable, options.email);

    if (options.resetRateLimit) {
        const deleted = resetRateLimit(repoRoot, pythonExecutable, email);
        emit({
            step: 'reset_rate_limit',
            status: 'ok',
            email,
            deleted,
        });
    }

    const harness = createFrontendHarness(
        repoRoot,
        options.publicBaseUrl,
        options.adminBaseUrl,
        options.timeoutSeconds,
    );
    const deck = harness.createDeck();

    deck.loadConfig();
    if (deck.config.baseUrl !== normalizeBaseUrl(options.adminBaseUrl)) {
        fail('config', 'Admin base URL was not loaded into the desktop state.', {
            expected: normalizeBaseUrl(options.adminBaseUrl),
            actual: deck.config.baseUrl,
        });
    }
    if (deck.config.publicBaseUrl !== normalizeBaseUrl(options.publicBaseUrl)) {
        fail('config', 'Public base URL was not loaded into the desktop state.', {
            expected: normalizeBaseUrl(options.publicBaseUrl),
            actual: deck.config.publicBaseUrl,
        });
    }

    emit({
        step: 'config',
        status: 'ok',
        baseUrl: deck.config.baseUrl,
        publicBaseUrl: deck.config.publicBaseUrl,
        workspaceMode: deck.workspaceMode,
        activeDesktopSectionId: deck.activeDesktopSectionId,
    });

    deck.adminAuth.email = email;
    await deck.sendAdminCode();
    const verificationCode = String(deck.adminAuth.devCode || deck.adminAuth.code || '').trim();
    if (deck.adminAuth.statusType !== 'ok' || !/^\d{6}$/.test(verificationCode)) {
        fail('send_code_ui', 'Frontend sendAdminCode() did not produce a usable verification code.', {
            email,
            statusType: deck.adminAuth.statusType,
            statusMessage: deck.adminAuth.statusMessage,
            devCode: deck.adminAuth.devCode,
        });
    }
    if (deck.adminAuth.verifyEmail !== email) {
        fail('send_code_ui', 'Frontend sendAdminCode() did not synchronize the verify email.', {
            email,
            verifyEmail: deck.adminAuth.verifyEmail,
        });
    }

    emit({
        step: 'send_code_ui',
        status: 'ok',
        email,
        devCodeAvailable: Boolean(deck.adminAuth.devCode),
        verifyEmail: deck.adminAuth.verifyEmail,
    });

    await deck.verifyAdminCode();
    if (!deck.adminSessionReady()) {
        fail('verify_ui', 'Frontend verifyAdminCode() did not establish an admin session.', {
            email,
            statusType: deck.adminAuth.statusType,
            statusMessage: deck.adminAuth.statusMessage,
            tokenSource: deck.adminAuth.tokenSource,
        });
    }
    if (!deck.workspaceHasData()) {
        fail('verify_ui', 'Frontend verifyAdminCode() did not hydrate desktop data.', {
            watchlist: deck.watchlist.length,
            signalTape: deck.signalTape.length,
            rankings: deck.rankings.length,
            strategyHealth: deck.strategyHealth.length,
        });
    }
    if (!deck.workspaceAutoRouted) {
        fail('verify_ui', 'Frontend verifyAdminCode() did not trigger first-screen auto routing.', {
            workspaceMode: deck.workspaceMode,
            activeDesktopSectionId: deck.activeDesktopSectionId,
        });
    }

    const preferredRoute = deck.preferredDesktopRoute();
    if (deck.workspaceMode !== preferredRoute.mode || deck.activeDesktopSectionId !== preferredRoute.sectionId) {
        fail('verify_ui', 'Frontend first-screen state does not match preferredDesktopRoute().', {
            workspaceMode: deck.workspaceMode,
            activeDesktopSectionId: deck.activeDesktopSectionId,
            preferredRoute,
        });
    }
    if (deck.watchlist.length > 0) {
        if (deck.workspaceMode !== 'signals' || deck.activeDesktopSectionId !== 'watchlist-panel') {
            fail('verify_ui', 'Watchlist data is present but the desktop did not route to the watchlist panel.', {
                workspaceMode: deck.workspaceMode,
                activeDesktopSectionId: deck.activeDesktopSectionId,
                watchlist: deck.watchlist.length,
            });
        }
        if (!deck.selectedSymbol) {
            fail('verify_ui', 'Watchlist data loaded but no desktop focus symbol was selected.', {
                watchlist: deck.watchlist.length,
            });
        }
    }

    const persistedWorkspaceMode = harness.localStorage.getItem(deck.storageKeys.workspaceMode);
    const persistedWorkspaceSection = harness.localStorage.getItem(deck.storageKeys.workspaceSection);
    if (persistedWorkspaceMode !== deck.workspaceMode || persistedWorkspaceSection !== deck.activeDesktopSectionId) {
        fail('verify_ui', 'Auto-routed workspace state was not persisted to localStorage.', {
            persistedWorkspaceMode,
            persistedWorkspaceSection,
            workspaceMode: deck.workspaceMode,
            activeDesktopSectionId: deck.activeDesktopSectionId,
        });
    }

    const launchpadCards = summarizeLaunchpadCards(deck.workspaceLaunchpadCards());
    const accessCard = launchpadCards.find((card) => card.id === 'access');
    const syncCard = launchpadCards.find((card) => card.id === 'sync');
    if (!accessCard || accessCard.status !== '在线') {
        fail('launchpad', 'Launchpad access card did not switch to the online state after verify.', {
            launchpadCards,
        });
    }
    if (!syncCard || syncCard.status !== '已在线') {
        fail('launchpad', 'Launchpad sync card did not show an online state after loadAll().', {
            launchpadCards,
        });
    }

    emit({
        step: 'verify_ui',
        status: 'ok',
        email,
        workspaceMode: deck.workspaceMode,
        activeDesktopSectionId: deck.activeDesktopSectionId,
        preferredRoute,
        workspaceAutoRouted: deck.workspaceAutoRouted,
        watchlist: deck.watchlist.length,
        signalTape: deck.signalTape.length,
        rankings: deck.rankings.length,
        strategyHealth: deck.strategyHealth.length,
        selectedSymbol: deck.selectedSymbol,
    });

    emit({
        step: 'launchpad',
        status: 'ok',
        cards: launchpadCards,
    });

    const restoredDeck = harness.createDeck();
    restoredDeck.loadConfig();
    if (!restoredDeck.adminSessionReady()) {
        fail('restore_ui', 'A new frontend deck instance did not restore the persisted admin session.', {
            tokenSource: restoredDeck.adminAuth.tokenSource,
            refreshToken: Boolean(restoredDeck.adminAuth.refreshToken),
            hasSession: Boolean(restoredDeck.adminAuth.session),
        });
    }
    if (restoredDeck.workspaceMode !== deck.workspaceMode || restoredDeck.activeDesktopSectionId !== deck.activeDesktopSectionId) {
        fail('restore_ui', 'A new frontend deck instance did not restore the persisted workspace route.', {
            expectedMode: deck.workspaceMode,
            expectedSection: deck.activeDesktopSectionId,
            actualMode: restoredDeck.workspaceMode,
            actualSection: restoredDeck.activeDesktopSectionId,
        });
    }

    emit({
        step: 'restore_ui',
        status: 'ok',
        workspaceMode: restoredDeck.workspaceMode,
        activeDesktopSectionId: restoredDeck.activeDesktopSectionId,
        tokenSource: restoredDeck.adminAuth.tokenSource,
        adminEmail: restoredDeck.adminSessionEmail(),
    });

    await restoredDeck.logoutAdminSession();
    if (restoredDeck.adminSessionReady()) {
        fail('logout_ui', 'Frontend logoutAdminSession() did not clear the restored session.', {
            tokenSource: restoredDeck.adminAuth.tokenSource,
            statusMessage: restoredDeck.adminAuth.statusMessage,
        });
    }
    if (harness.localStorage.getItem(restoredDeck.storageKeys.token)) {
        fail('logout_ui', 'Frontend logoutAdminSession() did not remove the persisted access token.', {
            token: harness.localStorage.getItem(restoredDeck.storageKeys.token),
        });
    }
    if (harness.localStorage.getItem(restoredDeck.storageKeys.adminSession)) {
        fail('logout_ui', 'Frontend logoutAdminSession() did not remove the persisted admin session payload.', {
            adminSession: harness.localStorage.getItem(restoredDeck.storageKeys.adminSession),
        });
    }

    emit({
        step: 'logout_ui',
        status: 'ok',
        statusType: restoredDeck.statusType,
        statusMessage: restoredDeck.statusMessage,
        adminStatusMessage: restoredDeck.adminAuth.statusMessage,
    });
}

main().catch((error) => {
    emit({
        step: error.step || 'unexpected',
        status: 'failed',
        body: error.details || {
            message: error.message,
            stack: error.stack,
        },
    });
    process.exitCode = 1;
});