// Stock-py API Configuration
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
    return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(value);
}

function formatPercent(value) {
    const sign = value >= 0 ? '+' : '';
    return `${sign}${value.toFixed(2)}%`;
}

function formatNumber(value) {
    return new Intl.NumberFormat('en-US').format(value);
}

function formatDate(dateStr) {
    return new Date(dateStr).toLocaleDateString('en-US', { 
        year: 'numeric', month: 'short', day: 'numeric' 
    });
}

// Update page with data
function updateElement(id, value) {
    const el = document.getElementById(id);
    if (el) el.textContent = value;
}

// Show notification/toast
function showToast(message, type = 'info') {
    // Simple implementation - can be enhanced
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