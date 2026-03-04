// auth.js - Authentication handling for Club Kinawa Coding Lab

// Detect if we're running under /lab subpath
const isLabSubpath = window.location.pathname.startsWith('/lab');
const API_BASE = isLabSubpath ? '/api' : '/api';
const LAB_BASE = isLabSubpath ? '/lab' : '';

// Check if user is logged in
function isLoggedIn() {
    return !!localStorage.getItem('auth_token');
}

// Get auth token
function getToken() {
    return localStorage.getItem('auth_token');
}

// Get current user
function getCurrentUser() {
    const user = localStorage.getItem('current_user');
    return user ? JSON.parse(user) : null;
}

// Login
async function login(username, pin) {
    try {
        const response = await fetch(`${API_BASE}/auth/login`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ username, pin }),
                credentials: 'same-origin'
        });

        const data = await response.json();

        if (data.success) {
            localStorage.setItem('auth_token', data.token);
            localStorage.setItem('current_user', JSON.stringify(data.user));
            return { success: true };
        } else {
            return { success: false, error: data.error };
        }
    } catch (error) {
        return { success: false, error: 'Network error. Please try again.' };
    }
}

// Logout
async function logout() {
    const token = getToken();
    if (token) {
        try {
            await fetch(`${API_BASE}/auth/logout`, {
                credentials: "same-origin",
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${token}`
                }
            });
        } catch (e) {
            // Ignore errors on logout
        }
    }
    localStorage.removeItem('auth_token');
    localStorage.removeItem('current_user');
    window.location.href = '/lab/login';
}

// API request helper with auth
async function apiRequest(url, options = {}) {
    const token = getToken();
    if (!token) {
        window.location.href = '/lab/login';
        return null;
    }

    const headers = {
        'Authorization': `Bearer ${token}`,
        ...options.headers
    };

    if (options.body && typeof options.body === 'object') {
        headers['Content-Type'] = 'application/json';
        options.body = JSON.stringify(options.body);
    }

    const response = await fetch(`${API_BASE}${url}`, {
        credentials: "same-origin",
        ...options,
        headers
    });

    if (response.status === 401) {
        localStorage.removeItem('auth_token');
        window.location.href = '/lab/login';
        return null;
    }

    return response.json();
}

// Redirect to login if not authenticated
function requireAuth() {
    if (!isLoggedIn()) {
        window.location.href = '/lab/login';
        return false;
    }
    return true;
}

// Initialize auth on page load
document.addEventListener('DOMContentLoaded', () => {
    // Handle login form
    const loginBtn = document.getElementById('login-btn');
    if (loginBtn) {
        loginBtn.addEventListener('click', async () => {
            const username = document.getElementById('username').value.trim();
            const pin = document.getElementById('pin').value.trim();
            const errorDiv = document.getElementById('error-message');

            if (!username || !pin) {
                errorDiv.textContent = 'Please enter both username and PIN.';
                return;
            }

            if (!/^\d{4}$/.test(pin)) {
                errorDiv.textContent = 'PIN must be exactly 4 digits.';
                return;
            }

            loginBtn.disabled = true;
            loginBtn.textContent = 'Logging in...';

            const result = await login(username, pin);

            if (result.success) {
                window.location.href = '/lab/projects';
            } else {
                errorDiv.textContent = result.error || 'Login failed.';
                loginBtn.disabled = false;
                loginBtn.textContent = 'Log In';
            }
        });

        // Allow Enter key to submit
        document.getElementById('pin').addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                loginBtn.click();
            }
        });
    }

    // Handle logout button
    const logoutBtn = document.getElementById('logout-btn');
    if (logoutBtn) {
        logoutBtn.addEventListener('click', logout);
    }

    // Display username if logged in
    const usernameDisplay = document.getElementById('username-display');
    if (usernameDisplay) {
        const user = getCurrentUser();
        if (user) {
            usernameDisplay.textContent = user.username;
        }
    }
});