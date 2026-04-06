// Login form handling
document.getElementById('login-form')?.addEventListener('submit', async function(e) {
    e.preventDefault();
    
    const email = document.getElementById('email')?.value;
    const password = document.getElementById('password')?.value;
    
    if (!email || !password) {
        showToast('Please enter email and password', 'error');
        return;
    }
    
    try {
        const response = await fetch('/api/v1/auth/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, password })
        });
        
        if (response.ok) {
            const data = await response.json();
            if (data.access_token) {
                localStorage.setItem('stock_token', data.access_token);
                window.location.href = 'pages/dashboard.html';
            }
        } else {
            showToast('Invalid credentials', 'error');
        }
    } catch (e) {
        showToast('Login failed: ' + e.message, 'error');
    }
});

// Register form handling
document.getElementById('register-form')?.addEventListener('submit', async function(e) {
    e.preventDefault();
    
    const email = document.getElementById('email')?.value;
    const password = document.getElementById('password')?.value;
    const confirmPassword = document.getElementById('confirm-password')?.value;
    
    if (!email || !password) {
        showToast('Please fill in all fields', 'error');
        return;
    }
    
    if (password !== confirmPassword) {
        showToast('Passwords do not match', 'error');
        return;
    }
    
    try {
        const response = await fetch('/api/v1/auth/register', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, password })
        });
        
        if (response.ok) {
            showToast('Registration successful! Please login.', 'success');
            setTimeout(() => {
                window.location.href = 'login.html';
            }, 1500);
        } else {
            const data = await response.json();
            showToast(data.detail || 'Registration failed', 'error');
        }
    } catch (e) {
        showToast('Registration failed: ' + e.message, 'error');
    }
});