// Stock-py Common Functions
const API_BASE = '/api/v1';

// Auth functions
const auth = {
    getToken: () => localStorage.getItem('stock_token'),
    setToken: (token) => localStorage.setItem('stock_token', token),
    removeToken: () => localStorage.removeItem('stock_token'),
    headers: () => {
        const token = auth.getToken();
        return token ? { 'Authorization': `Bearer ${token}` } : {};
    },
    isLoggedIn: () => !!auth.getToken()
};

// API helper functions
async function apiGet(endpoint) {
    const response = await fetch(`${API_BASE}${endpoint}`, {
        headers: { 'Content-Type': 'application/json', ...auth.headers() }
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return response.json();
}

async function apiPost(endpoint, data) {
    const response = await fetch(`${API_BASE}${endpoint}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...auth.headers() },
        body: JSON.stringify(data)
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return response.json();
}

async function apiDelete(endpoint) {
    const response = await fetch(`${API_BASE}${endpoint}`, {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json', ...auth.headers() }
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return response.json();
}

// Format helpers
function formatCurrency(value) {
    return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(value || 0);
}

function formatPercent(value) {
    if (!value) return '-';
    const sign = value >= 0 ? '+' : '';
    return `${sign}${value.toFixed(2)}%`;
}

function formatNumber(value) {
    return new Intl.NumberFormat('en-US').format(value || 0);
}

function formatDate(dateStr) {
    if (!dateStr) return '-';
    return new Date(dateStr).toLocaleDateString('en-US', { 
        year: 'numeric', month: 'short', day: 'numeric' 
    });
}

function formatDateTime(dateStr) {
    if (!dateStr) return '-';
    return new Date(dateStr).toLocaleString('en-US', { 
        year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit'
    });
}

// Show notification/toast
function showToast(message, type = 'info') {
    console.log(`[${type}] ${message}`);
}

// Check auth on page load
function requireAuth() {
    if (!auth.isLoggedIn()) {
        window.location.href = 'login.html';
    }
}

// Logout
function logout() {
    auth.removeToken();
    window.location.href = 'login.html';
}

// Common navigation to be added to pages
const NAV_LINKS = [
    { href: 'dashboard.html', icon: 'home', label: 'Dashboard' },
    { href: 'watchlist.html', icon: 'star', label: 'Watchlist' },
    { href: 'portfolio.html', icon: 'package', label: 'Portfolio' },
    { href: 'signals.html', icon: 'flash', label: 'Signals' },
    { href: 'notifications.html', icon: 'bell', label: 'Notifications' },
    { href: 'settings.html', icon: 'settings', label: 'Settings' }
];
