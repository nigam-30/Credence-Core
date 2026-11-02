import re

with open('app.js', 'r', encoding='utf-8') as f:
    js = f.read()

# 1. Add escapeHtml and fetch interceptor near top
top_helper = """// Centralized XSS Sanitization & Fetch Interceptor (Phase 6.2 Hardening)
function escapeHtml(str) {
    if (str === null || str === undefined) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}
window.escapeHtml = escapeHtml;

// Global Fetch Interceptor for central session expiration and CSRF management
const _originalFetch = window.fetch;
window.fetch = async function(...args) {
    const response = await _originalFetch.apply(this, args);
    if (response.status === 401) {
        const url = String(args[0] || '');
        if (!url.includes('/api/login') && !url.includes('/api/mfa/verify') && !url.includes('/api/demo_login') && !url.includes('/api/account/verify_pin')) {
            showToast('Your session has expired. Please sign in again.', 'error');
            sessionStorage.clear();
            setTimeout(() => {
                if (window.location.pathname !== '/' && window.location.pathname !== '/index') {
                    window.location.href = '/?auth_required=true';
                }
            }, 1000);
        }
    }
    return response;
};
"""

if 'escapeHtml' not in js:
    # Insert right after GLOBAL STATE comment
    js = re.sub(r'(let currentAccountData = null;)', top_helper + r'\n\1', js, count=1)

# 2. Patch toggleBalanceVisibility
old_pin_verify = """                const pin = modal.querySelector('#balance-unlock-pin').value.trim();
                const expectedPin = String(currentAccountData?.pin || '1234');
                if (!pin) {
                    showToast('Please enter your 4-digit PIN.', 'error');
                    return;
                }
                if (pin !== expectedPin && pin !== '1234') {
                    showToast('Incorrect PIN. Access denied.', 'error');
                    return;
                }"""

new_pin_verify = """                const pin = modal.querySelector('#balance-unlock-pin').value.trim();
                if (!pin) {
                    showToast('Please enter your 4-digit PIN.', 'error');
                    return;
                }
                if (pin.length !== 4 && pin.length !== 6) {
                    showToast('PIN must be 4 or 6 digits.', 'error');
                    return;
                }
                try {
                    const res = await fetch('/api/account/verify_pin', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'X-CSRF-Token': getCsrfToken()
                        },
                        body: JSON.stringify({ pin })
                    });
                    const data = await res.json();
                    if (!res.ok || !data.success) {
                        showToast(data.message || 'Incorrect PIN. Access denied.', 'error');
                        return;
                    }
                } catch (err) {
                    showToast('PIN verification service unavailable. Please try again.', 'error');
                    return;
                }"""

js = js.replace(old_pin_verify.replace('\n', '\r\n'), new_pin_verify.replace('\n', '\r\n'))
js = js.replace(old_pin_verify, new_pin_verify)

# 3. Patch window.logout
old_logout = """window.logout = () => {
    sessionStorage.clear();
    showToast('Signed out successfully.');
    setTimeout(() => window.location.href = '/', 500);
};"""

new_logout = """window.logout = async () => {
    try {
        await fetch('/api/logout', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRF-Token': getCsrfToken()
            }
        });
    } catch (e) {
        // Fall through to clear local session
    }
    sessionStorage.clear();
    showToast('Signed out successfully.');
    setTimeout(() => window.location.href = '/', 500);
};"""

js = js.replace(old_logout.replace('\n', '\r\n'), new_logout.replace('\n', '\r\n'))
js = js.replace(old_logout, new_logout)

# 4. Patch new account modal: pin: pin || '1234'
old_acc_pin = "pin: pin || '1234',"
new_acc_pin = "pin: pin,"
js = js.replace(old_acc_pin, new_acc_pin)

# 5. Patch card format fallback '1234'
js = js.replace("data.account_number || '1234'", "data.account_number || ''")

with open('app.js', 'w', encoding='utf-8') as f:
    f.write(js)

print("app.js patched successfully.")
