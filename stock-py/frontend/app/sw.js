self.LOCAL_NOTIFICATION_DB = 'stockpy.local.notifications';
self.LOCAL_NOTIFICATION_STORE = 'notifications';
self.LOCAL_NOTIFICATION_MAX = 500;

function idbRequest(request) {
    return new Promise((resolve, reject) => {
        request.onsuccess = () => resolve(request.result);
        request.onerror = () => reject(request.error || new Error('IndexedDB request failed'));
    });
}

function idbTransactionDone(transaction) {
    return new Promise((resolve, reject) => {
        transaction.oncomplete = () => resolve();
        transaction.onerror = () => reject(transaction.error || new Error('IndexedDB transaction failed'));
        transaction.onabort = () => reject(transaction.error || new Error('IndexedDB transaction aborted'));
    });
}

function openLocalNotificationDb() {
    return new Promise((resolve, reject) => {
        if (!('indexedDB' in self)) {
            reject(new Error('IndexedDB is not available in service worker'));
            return;
        }

        const request = self.indexedDB.open(self.LOCAL_NOTIFICATION_DB, 1);
        request.onupgradeneeded = () => {
            const db = request.result;
            if (!db.objectStoreNames.contains(self.LOCAL_NOTIFICATION_STORE)) {
                db.createObjectStore(self.LOCAL_NOTIFICATION_STORE, { keyPath: 'id' });
            }
        };
        request.onsuccess = () => resolve(request.result);
        request.onerror = () => reject(request.error || new Error('Failed to open local notification DB'));
    });
}

function normalizeNotificationRecord(payload) {
    const value = payload && typeof payload === 'object' ? payload : {};
    const metadata = value.metadata && typeof value.metadata === 'object' && !Array.isArray(value.metadata)
        ? value.metadata
        : {};
    const notificationId = String(
        value.notification_id || value.notificationId || metadata.notification_id || '',
    ).trim();
    const fallbackId = self.crypto?.randomUUID
        ? self.crypto.randomUUID()
        : `local-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
    const id = String(value.id || notificationId || fallbackId);

    return {
        id,
        notification_id: notificationId || null,
        type: String(value.type || value.notification_type || metadata.notification_type || 'push').trim() || 'push',
        title: String(value.title || 'StockPy 通知'),
        body: String(value.body || ''),
        is_read: Boolean(value.is_read),
        ack_required: Boolean(value.ack_required || metadata.ack_required),
        acknowledged_at: value.acknowledged_at || null,
        opened_at: value.opened_at || null,
        created_at: value.created_at || new Date().toISOString(),
        metadata,
        url: String(value.url || '/app/notifications'),
        tag: String(value.tag || `notification-${id}`),
    };
}

async function persistLocalNotification(payload) {
    const db = await openLocalNotificationDb();
    try {
        const transaction = db.transaction(self.LOCAL_NOTIFICATION_STORE, 'readwrite');
        const store = transaction.objectStore(self.LOCAL_NOTIFICATION_STORE);

        const incoming = normalizeNotificationRecord(payload);
        const existing = await idbRequest(store.get(incoming.id));
        const merged = existing && typeof existing === 'object'
            ? { ...existing, ...incoming, id: incoming.id }
            : incoming;

        if (existing && typeof existing === 'object') {
            merged.is_read = Boolean(existing.is_read);
            merged.opened_at = existing.opened_at || merged.opened_at || null;
            merged.acknowledged_at = existing.acknowledged_at || merged.acknowledged_at || null;
        }

        store.put(merged);

        const all = await idbRequest(store.getAll());
        if (Array.isArray(all) && all.length > self.LOCAL_NOTIFICATION_MAX) {
            const sorted = [...all].sort((a, b) => {
                const aTime = Date.parse(a?.created_at || '') || 0;
                const bTime = Date.parse(b?.created_at || '') || 0;
                return bTime - aTime;
            });
            const stale = sorted.slice(self.LOCAL_NOTIFICATION_MAX);
            for (const item of stale) {
                if (item?.id) {
                    store.delete(item.id);
                }
            }
        }

        await idbTransactionDone(transaction);
        return merged;
    } finally {
        db.close();
    }
}

async function broadcastIncomingNotification(notification) {
    const clients = await self.clients.matchAll({ type: 'window', includeUncontrolled: true });
    for (const client of clients) {
        client.postMessage({
            type: 'stockpy:notification-created',
            notification,
        });
    }
}

self.addEventListener('install', (event) => {
    event.waitUntil(self.skipWaiting());
});

self.addEventListener('activate', (event) => {
    event.waitUntil(self.clients.claim());
});

self.addEventListener('push', (event) => {
    event.waitUntil((async () => {
        let payload = {};
        try {
            payload = event.data ? event.data.json() : {};
        } catch (_error) {
            payload = {
                title: 'StockPy 通知',
                body: event.data ? event.data.text() : '',
            };
        }

        let stored = normalizeNotificationRecord(payload);
        try {
            stored = await persistLocalNotification(payload);
            await broadcastIncomingNotification(stored);
        } catch (_error) {
            // Keep notification UX available even if local persistence is temporarily unavailable.
        }

        const notificationId =
            stored.notification_id ||
            stored.id ||
            stored?.metadata?.notification_id ||
            null;
        const target = new URL(stored.url || '/app/notifications', self.location.origin);
        if (notificationId && !target.searchParams.get('notification_id')) {
            target.searchParams.set('notification_id', String(notificationId));
        }

        await self.registration.showNotification(stored.title || 'StockPy 通知', {
            body: stored.body || '',
            tag: stored.tag || 'stockpy-notification',
            data: {
                url: target.href,
                notification_id: notificationId,
                metadata: stored.metadata || {},
            },
            renotify: true,
        });
    })());
});

self.addEventListener('notificationclick', (event) => {
    event.notification.close();
    const targetUrl = new URL(
        event.notification.data?.url || '/app/notifications',
        self.location.origin,
    ).href;

    event.waitUntil(
        self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then(async (clients) => {
            for (const client of clients) {
                try {
                    const clientUrl = new URL(client.url);
                    if (clientUrl.origin !== self.location.origin || !clientUrl.pathname.startsWith('/app/')) {
                        continue;
                    }
                    if ('focus' in client) {
                        await client.focus();
                    }
                    if ('navigate' in client && client.url !== targetUrl) {
                        await client.navigate(targetUrl);
                    }
                    return;
                } catch (_error) {
                    continue;
                }
            }
            if (self.clients.openWindow) {
                return self.clients.openWindow(targetUrl);
            }
            return undefined;
        })
    );
});