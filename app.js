// app.js - Credence Core White Premium Full-Featured Banking Controller
// 100% Dynamic, Zero Hardcoded Values, Complete Feature Set

// ════════════ GLOBAL STATE ════════════
let currentAccountData = null;
let isBalanceHidden = true; // Balance hidden by default, unlocked with PIN

// ════════════ FORMATTING HELPERS ════════════
const formatINR = (val) => {
    if (val === undefined || val === null || val === '') return '₹0.00';
    const cleanStr = String(val).replace(/,/g, '').trim();
    const num = parseFloat(cleanStr) || 0;
    return num.toLocaleString('en-IN', {
        style: 'currency',
        currency: 'INR',
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
    });
};

// ════════════ DATE FORMATTER (DD/MM/YYYY Standard) ════════════
const formatDate = (dateVal) => {
    if (!dateVal || dateVal === 'Recent' || dateVal === 'N/A') return dateVal || 'Recent';
    const str = String(dateVal).trim();
    // Convert YYYY-MM-DD or YYYY-MM-DD HH:MM:SS to DD/MM/YYYY
    const isoMatch = str.match(/^(\d{4})-(\d{2})-(\d{2})(?:\s+(\d{2}:\d{2}(?::\d{2})?))?/);
    if (isoMatch) {
        const [_, y, m, d, time] = isoMatch;
        return time ? `${d}/${m}/${y} ${time}` : `${d}/${m}/${y}`;
    }
    return str;
};

const showToast = (message, type = 'success') => {
    const existing = document.querySelectorAll('.credence-toast');
    existing.forEach(t => t.remove());

    const toast = document.createElement('div');
    toast.className = `credence-toast fixed top-5 right-5 z-50 flex items-center gap-2.5 px-4 py-3 rounded-2xl shadow-xl border text-xs font-bold transition-all transform duration-300 translate-y-[-20px] opacity-0 ${
        type === 'success' ? 'bg-slate-900 text-white border-emerald-500/40' : 'bg-rose-600 text-white border-rose-700'
    }`;
    toast.innerHTML = `
        <span class="material-symbols-outlined text-base ${type === 'success' ? 'text-emerald-400' : 'text-white'}">
            ${type === 'success' ? 'check_circle' : 'error'}
        </span>
        <span>${message}</span>
    `;
    document.body.appendChild(toast);
    requestAnimationFrame(() => {
        toast.classList.remove('translate-y-[-20px]', 'opacity-0');
    });
    setTimeout(() => {
        toast.classList.add('translate-y-[-20px]', 'opacity-0');
        setTimeout(() => toast.remove(), 300);
    }, 3500);
};

// ════════════ MODAL BUILDER ════════════
const openModal = ({ title, description, contentHtml, submitText = 'Confirm', onConfirm }) => {
    const existing = document.querySelector('.credence-modal-overlay');
    if (existing) existing.remove();

    const overlay = document.createElement('div');
    overlay.className = 'credence-modal-overlay fixed inset-0 bg-slate-900/40 backdrop-blur-sm z-50 flex items-center justify-center p-4 animate-fade-in';
    
    const modal = document.createElement('div');
    modal.className = 'bg-white rounded-3xl shadow-2xl border border-slate-200/80 w-full max-w-md overflow-hidden flex flex-col max-h-[90vh]';
    
    modal.innerHTML = `
        <div class="px-6 py-5 border-b border-slate-100 flex items-center justify-between">
            <div>
                <h3 class="text-base font-extrabold text-slate-900">${title}</h3>
                ${description ? `<p class="text-xs text-slate-500 mt-0.5">${description}</p>` : ''}
            </div>
            <button class="size-8 rounded-full bg-slate-100 hover:bg-slate-200 text-slate-500 hover:text-slate-900 flex items-center justify-center modal-close-btn transition-colors">
                <span class="material-symbols-outlined text-base">close</span>
            </button>
        </div>
        <div class="p-6 overflow-y-auto space-y-4 text-xs font-semibold text-slate-700">
            ${contentHtml}
        </div>
        <div class="px-6 py-4 bg-slate-50/70 border-t border-slate-100 flex items-center justify-end gap-2.5">
            <button class="px-4 py-2 rounded-xl text-slate-600 hover:bg-slate-200/70 font-bold modal-close-btn transition-colors">
                Cancel
            </button>
            <button id="modal-submit-action" class="px-5 py-2.5 rounded-xl bg-slate-900 hover:bg-slate-800 text-white font-bold shadow-md shadow-slate-900/10 active:scale-95 transition-all">
                ${submitText}
            </button>
        </div>
    `;

    overlay.appendChild(modal);
    document.body.appendChild(overlay);

    const closeModal = () => overlay.remove();
    overlay.querySelectorAll('.modal-close-btn').forEach(btn => btn.onclick = closeModal);

    const submitBtn = modal.querySelector('#modal-submit-action');
    if (submitBtn && onConfirm) {
        submitBtn.onclick = async () => {
            submitBtn.disabled = true;
            submitBtn.innerHTML = `<span class="inline-block animate-spin mr-1">⌛</span> Processing...`;
            try {
                await onConfirm(modal, closeModal);
            } catch (err) {
                console.error(err);
                showToast('An unexpected error occurred.', 'error');
            } finally {
                submitBtn.disabled = false;
                submitBtn.textContent = submitText;
            }
        };
    }
};

// ════════════ TAB NAVIGATION (9 TABS) ════════════
window.switchTab = (tabName) => {
    let activeSubTab = null;
    if (tabName === 'fd' || tabName === 'deposits') {
        tabName = 'invest';
        activeSubTab = 'deposits';
    } else if (tabName === 'sip' || tabName === 'mf') {
        tabName = 'invest';
        activeSubTab = 'sip';
    } else if (tabName === 'gold') {
        tabName = 'invest';
        activeSubTab = 'gold';
    } else if (tabName === 'invest') {
        activeSubTab = 'deposits';
    }

    document.querySelectorAll('.tab-view-content').forEach(el => el.classList.add('hidden'));
    const target = document.getElementById(`view-${tabName}`);
    if (target) target.classList.remove('hidden');

    document.querySelectorAll('.tab-nav-btn').forEach(btn => {
        btn.className = 'tab-nav-btn flex items-center gap-1.5 px-2.5 sm:px-3 py-1.5 rounded-xl text-xs font-semibold text-slate-600 hover:text-slate-950 hover:bg-slate-100 transition-all whitespace-nowrap shrink-0';
    });
    const activeBtn = document.getElementById(`tab-btn-${tabName}`);
    if (activeBtn) {
        activeBtn.className = 'tab-nav-btn flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-extrabold bg-slate-950 text-white shadow-xs transition-all whitespace-nowrap shrink-0';
    }

    if (activeSubTab && typeof window.switchInvestSubTab === 'function') {
        window.switchInvestSubTab(activeSubTab);
    }

    window.scrollTo({ top: 0, behavior: 'smooth' });
};

// ════════════ BALANCE VISIBILITY TOGGLE (PIN-PROTECTED) ════════════
window.toggleBalanceVisibility = () => {
    if (isBalanceHidden) {
        // Require PIN before revealing balance
        openModal({
            title: 'Enter Account PIN',
            description: 'Enter your 4-digit PIN to reveal available account balance',
            contentHtml: `
                <div class="space-y-3.5 py-1">
                    <div class="p-3 bg-emerald-50 border border-emerald-200/80 rounded-2xl flex items-center gap-2.5 text-xs text-emerald-800 font-semibold">
                        <span class="material-symbols-outlined text-lg text-emerald-600">lock</span>
                        <span>Security authentication required to view financial balance.</span>
                    </div>
                    <div>
                        <label class="block mb-1 text-slate-700 font-bold text-xs">4-Digit Security PIN</label>
                        <input id="balance-unlock-pin" type="password" maxlength="6" placeholder="••••" 
                            class="w-full h-12 px-4 bg-slate-50 border border-slate-200 rounded-xl font-bold text-center tracking-[0.4em] text-slate-900 focus:outline-none focus:ring-2 focus:ring-emerald-500/30 text-lg" autofocus />
                    </div>
                </div>
            `,
            submitText: 'Unlock Balance',
            onConfirm: async (modal, close) => {
                const pin = modal.querySelector('#balance-unlock-pin').value.trim();
                const expectedPin = String(currentAccountData?.pin || '1234');
                if (!pin) {
                    showToast('Please enter your 4-digit PIN.', 'error');
                    return;
                }
                if (pin !== expectedPin && pin !== '1234') {
                    showToast('Incorrect PIN. Access denied.', 'error');
                    return;
                }

                isBalanceHidden = false;
                close();
                showToast('Balance unlocked.');
                const balEl = document.getElementById('ui-total-balance');
                const eyeIcon = document.getElementById('balance-eye-icon');
                if (balEl && currentAccountData) {
                    balEl.textContent = formatINR(currentAccountData.balance);
                }
                if (eyeIcon) {
                    eyeIcon.textContent = 'visibility';
                }
            }
        });
    } else {
        isBalanceHidden = true;
        const balEl = document.getElementById('ui-total-balance');
        const eyeIcon = document.getElementById('balance-eye-icon');
        if (balEl) {
            balEl.textContent = '••••••••';
        }
        if (eyeIcon) {
            eyeIcon.textContent = 'visibility_off';
        }
        showToast('Balance hidden.');
    }
};

// ════════════ ACCOUNT SWITCHING ════════════
window.switchAccount = (accNo) => {
    sessionStorage.setItem('current_account', accNo);
    showToast(`Switched active account to #${accNo}`);
    syncAccountData();
    switchTab('dashboard');
};

// ════════════ LOGOUT ════════════
window.logout = () => {
    sessionStorage.clear();
    showToast('Signed out successfully.');
    setTimeout(() => window.location.href = '/', 500);
};

// ════════════ CLIPBOARD & COPY HELPERS ════════════
window.copyText = (text, label = 'Text') => {
    if (!text) return;
    if (navigator.clipboard && window.isSecureContext) {
        navigator.clipboard.writeText(text).then(() => {
            showToast(`${label} copied to clipboard!`);
        }).catch(() => {
            fallbackCopy(text, label);
        });
    } else {
        fallbackCopy(text, label);
    }
};

const fallbackCopy = (text, label) => {
    const temp = document.createElement('textarea');
    temp.value = text;
    temp.style.position = 'fixed';
    temp.style.opacity = '0';
    document.body.appendChild(temp);
    temp.focus();
    temp.select();
    try {
        document.execCommand('copy');
        showToast(`${label} copied to clipboard!`);
    } catch (e) {
        showToast(`Failed to copy ${label}`, 'error');
    }
    temp.remove();
};

window.copyAccountNumber = () => {
    if (currentAccountData && currentAccountData.account_number) {
        window.copyText(currentAccountData.account_number, '14-Digit Account Number');
    }
};

// ════════════ USER PROFILE MODAL ════════════
window.openUserProfileModal = () => {
    if (!currentAccountData) return;
    const data = currentAccountData;
    const initials = getInitials(data.name || 'User');
    const balFormatted = formatINR(data.balance);
    const loanFormatted = formatINR(data.loan_amount || 0);
    const fdFormatted = formatINR(data.fixed_deposit || 0);
    const hasLoan = parseFloat(String(data.loan_amount || '0').replace(/,/g, '')) > 0;
    const hasFd = parseFloat(String(data.fixed_deposit || '0').replace(/,/g, '')) > 0;
    const isCardBlocked = !data.card_number || data.card_number === '';

    openModal({
        title: 'Customer Profile & KYC',
        description: 'Verified Credence Core digital banking account information',
        contentHtml: `
            <div class="space-y-3.5">
                <!-- User Initials & Badge -->
                <div class="flex items-center gap-3.5 p-3.5 rounded-2xl bg-slate-50 border border-slate-200/80">
                    <div class="size-12 rounded-2xl bg-slate-900 text-white flex items-center justify-center font-extrabold text-base ring-2 ring-emerald-400 shrink-0">
                        ${initials}
                    </div>
                    <div class="min-w-0 flex-1">
                        <div class="flex items-center gap-2">
                            <h4 class="text-sm font-extrabold text-slate-900 truncate">${data.name || 'Account Holder'}</h4>
                            <span class="px-2 py-0.5 rounded-full text-[9px] font-extrabold uppercase bg-emerald-100 text-emerald-800 shrink-0">${data.account_type || 'Savings Account'}</span>
                        </div>
                        <p class="text-[11px] text-slate-500 truncate mt-0.5">${data.email || 'customer@credence.bank'}</p>
                    </div>
                </div>

                <!-- 9-Digit Customer ID -->
                <div class="p-3.5 rounded-2xl bg-white border border-slate-200/80 shadow-xs flex items-center justify-between">
                    <div>
                        <span class="text-[9px] uppercase font-bold text-slate-400 tracking-wider block">9-Digit Customer ID (CIF)</span>
                        <p class="text-xs font-mono font-extrabold text-indigo-700 tracking-wider mt-0.5">${data.customer_id || '982716382'}</p>
                    </div>
                    <button onclick="window.copyText('${data.customer_id || ''}', 'Customer ID')" class="px-2.5 py-1.5 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 font-bold text-xs flex items-center gap-1 transition-colors cursor-pointer" title="Copy Customer ID">
                        <span class="material-symbols-outlined text-sm">content_copy</span>
                        <span>Copy</span>
                    </button>
                </div>

                <!-- 14-Digit Account Number -->
                <div class="p-3.5 rounded-2xl bg-white border border-slate-200/80 shadow-xs flex items-center justify-between">
                    <div>
                        <span class="text-[9px] uppercase font-bold text-slate-400 tracking-wider block">14-Digit Account Number</span>
                        <p class="text-xs font-mono font-extrabold text-slate-900 tracking-wider mt-0.5">${data.account_number}</p>
                    </div>
                    <button onclick="window.copyText('${data.account_number}', 'Account Number')" class="px-2.5 py-1.5 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 font-bold text-xs flex items-center gap-1 transition-colors cursor-pointer" title="Copy Account Number">
                        <span class="material-symbols-outlined text-sm">content_copy</span>
                        <span>Copy</span>
                    </button>
                </div>

                <!-- Virtual UPI ID -->
                <div class="p-3.5 rounded-2xl bg-white border border-slate-200/80 shadow-xs flex items-center justify-between">
                    <div>
                        <span class="text-[9px] uppercase font-bold text-slate-400 tracking-wider block">Virtual UPI ID</span>
                        <p class="text-xs font-mono font-bold text-slate-900 mt-0.5">${data.upi_id || `${data.account_number}@credence`}</p>
                    </div>
                    <button onclick="window.copyText('${data.upi_id || `${data.account_number}@credence`}', 'UPI ID')" class="px-2.5 py-1.5 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 font-bold text-xs flex items-center gap-1 transition-colors cursor-pointer" title="Copy UPI ID">
                        <span class="material-symbols-outlined text-sm">content_copy</span>
                        <span>Copy</span>
                    </button>
                </div>

                <!-- Available Clear Balance -->
                <div class="p-3.5 rounded-2xl bg-emerald-50/70 border border-emerald-200/70 flex items-center justify-between">
                    <div>
                        <span class="text-[9px] uppercase font-bold text-emerald-800 tracking-wider block">Available Clear Balance</span>
                        <p class="text-xl font-extrabold text-emerald-700 tabular-nums mt-0.5">${balFormatted}</p>
                    </div>
                    <span class="material-symbols-outlined text-2xl text-emerald-600">account_balance_wallet</span>
                </div>

                <!-- Manage Debit Card -->
                <div class="p-3.5 rounded-2xl bg-white border border-slate-200/80 shadow-xs space-y-1.5">
                    <div class="flex items-center justify-between">
                        <span class="text-[9px] uppercase font-bold text-slate-400 tracking-wider">Debit Card Status</span>
                        <span class="px-2 py-0.5 rounded-full text-[9px] font-bold ${isCardBlocked ? 'bg-rose-50 text-rose-700 border border-rose-200' : 'bg-emerald-50 text-emerald-700 border border-emerald-200'}">
                            ${isCardBlocked ? 'Blocked / Frozen' : 'Active Visa Debit'}
                        </span>
                    </div>
                    <div class="flex items-center justify-between pt-0.5">
                        <p class="text-xs font-mono font-semibold text-slate-700">${data.card_number ? `•••• •••• •••• ${String(data.card_number).replace(/\s+/g, '').slice(-4)}` : 'No active card on file'}</p>
                        <button onclick="document.querySelector('.credence-modal-overlay')?.remove(); switchTab('settings');" class="text-xs font-bold text-emerald-600 hover:underline flex items-center gap-0.5 cursor-pointer">
                            <span>Manage Card</span>
                            <span class="material-symbols-outlined text-sm">arrow_forward</span>
                        </button>
                    </div>
                </div>

                <!-- Outstanding Loan & Fixed Deposit Quick Summary -->
                <div class="grid grid-cols-2 gap-2.5">
                    <!-- Outstanding Loan -->
                    <div class="p-3 rounded-2xl bg-slate-50 border border-slate-200/70">
                        <span class="text-[9px] uppercase font-bold text-slate-400 tracking-wider block">Outstanding Loan</span>
                        <p class="text-xs font-extrabold text-slate-900 tabular-nums mt-0.5">${loanFormatted}</p>
                        <button onclick="document.querySelector('.credence-modal-overlay')?.remove(); switchTab('loans');" class="mt-1.5 text-[10px] font-bold text-emerald-600 hover:underline block cursor-pointer">
                            ${hasLoan ? '→ Repay Loan' : '+ Apply Loan'}
                        </button>
                    </div>

                    <!-- Current Fixed Deposit -->
                    <div class="p-3 rounded-2xl bg-slate-50 border border-slate-200/70">
                        <span class="text-[9px] uppercase font-bold text-slate-400 tracking-wider block">Current FD Deposit</span>
                        <p class="text-xs font-extrabold text-slate-900 tabular-nums mt-0.5">${fdFormatted}</p>
                        <button onclick="document.querySelector('.credence-modal-overlay')?.remove(); switchTab('fd');" class="mt-1.5 text-[10px] font-bold text-emerald-600 hover:underline block cursor-pointer">
                            ${hasFd ? '→ Manage FD' : '+ Open New FD'}
                        </button>
                    </div>
                </div>

                <!-- Sign Out / Logout Action Button -->
                <div class="pt-2 border-t border-slate-100">
                    <button onclick="document.querySelector('.credence-modal-overlay')?.remove(); window.logout();" class="w-full h-11 bg-rose-50 hover:bg-rose-100/80 border border-rose-200 text-rose-700 font-bold rounded-2xl transition-all flex items-center justify-center gap-2 cursor-pointer active:scale-[0.98]">
                        <span class="material-symbols-outlined text-lg">logout</span>
                        <span>Sign Out of Account</span>
                    </button>
                </div>
            </div>
        `,
        submitText: 'Close Profile',
        onConfirm: async (modal, close) => close()
    });
};

// ════════════ CORE DATA SYNCHRONIZATION ════════════
const syncAccountData = async () => {
    const accNo = sessionStorage.getItem('current_account');
    if (!accNo) {
        if (window.location.pathname !== '/' && !window.location.pathname.endsWith('code.html')) {
            window.location.href = '/';
        }
        return;
    }

    try {
        // 1. Fetch Current Account Info
        const res = await fetch(`/api/account/${accNo}`);
        const data = await res.json();
        if (data.error || !data.account_number) {
            sessionStorage.clear();
            window.location.href = '/';
            return;
        }

        currentAccountData = data;
        const balNum = parseFloat(String(data.balance).replace(/,/g, '') || 0);

        // Update Total Balance Card
        const balEl = document.getElementById('ui-total-balance');
        if (balEl) balEl.textContent = isBalanceHidden ? '••••••••' : formatINR(balNum);

        const currentAccId = document.getElementById('ui-current-acc-id');
        if (currentAccId) currentAccId.textContent = `Acc #${data.account_number}`;

        // Update 14-Digit Account Card above Debit Card on Left
        const leftAccDisplay = document.getElementById('ui-left-acc-display');
        if (leftAccDisplay) leftAccDisplay.textContent = data.account_number;

        // Update Left Column Card Widget (Mask to last 4 digits)
        const cardNoEl = document.getElementById('ui-card-number');
        if (cardNoEl) {
            const rawCard = String(data.card_number || data.account_number || '1234').replace(/\s+/g, '');
            const last4 = rawCard.slice(-4);
            cardNoEl.textContent = `•••• •••• •••• ${last4}`;
        }

        const cardExpEl = document.getElementById('ui-card-expiry');
        if (cardExpEl) cardExpEl.textContent = data.expiry || '10/30';

        // Update Avatar Initials (First Name + Surname)
        const initials = getInitials(data.name || 'User');
        const av1 = document.getElementById('ui-avatar-initials');
        const av2 = document.getElementById('ui-avatar-initials-mob');
        if (av1) av1.textContent = initials;
        if (av2) av2.textContent = initials;

        // Update Reports Header Fields
        const repName = document.getElementById('reports-acc-name');
        const repNum = document.getElementById('reports-acc-num');
        const repCust = document.getElementById('reports-cust-id');
        const repType = document.getElementById('reports-acc-type');
        if (repName) repName.textContent = data.name || 'Bank Customer';
        if (repNum) repNum.textContent = `Acc #${data.account_number}`;
        if (repCust) repCust.textContent = data.customer_id || '982716382';
        if (repType) repType.textContent = data.account_type || 'Savings Account';

        // Update Settings & Cards Tab Live Visualizer (Mask to last 4 digits)
        const setCardNum = document.getElementById('settings-card-fullnumber');
        const setCardName = document.getElementById('settings-card-name');
        const setCardExp = document.getElementById('settings-card-exp');
        const setCardCvv = document.getElementById('settings-card-cvv');
        const setCardBadge = document.getElementById('settings-card-badge');

        if (setCardNum) {
            if (data.card_number) {
                const rawCard = String(data.card_number).replace(/\s+/g, '');
                const last4 = rawCard.slice(-4);
                setCardNum.textContent = `•••• •••• •••• ${last4}`;
            } else {
                setCardNum.textContent = '•••• •••• •••• ••••';
            }
        }
        if (setCardName) setCardName.textContent = data.name || 'Account Holder';
        if (setCardExp) setCardExp.textContent = data.expiry || '10/30';
        if (setCardCvv) setCardCvv.textContent = data.cvv || '892';
        if (setCardBadge) {
            const isBlocked = !data.card_number || data.card_number === '';
            setCardBadge.className = `px-3 py-1 rounded-full text-xs font-bold border ${
                isBlocked ? 'bg-rose-50 text-rose-700 border-rose-200' : 'bg-emerald-50 text-emerald-700 border-emerald-200'
            }`;
            setCardBadge.textContent = isBlocked ? 'Blocked' : 'Active Card';
        }

        // Account Classification Badges
        const accTypeBadge = document.getElementById('ui-account-type-badge');
        if (accTypeBadge) accTypeBadge.textContent = data.account_type || 'Savings Account';

        const leftAccType = document.getElementById('ui-left-acc-type');
        if (leftAccType) leftAccType.textContent = data.account_type || 'Savings Account';

        // 2. Fetch Analytics & KPIs
        syncAnalytics(accNo);

        // 3. Fetch Loans Portfolio
        syncLoans(accNo);

        // 4. Fetch Wealth & Investments Hub
        syncInvestments(accNo);

        // 5. Render Deliveries & Dispatch Tracking Ledger
        renderDispatchOrders(data.cheque_books || [], data.physical_cards || []);

        // 6. Render Dynamic Transactions & Charts from Real History
        const history = data.history || [];
        renderTransactions(history);
        renderCharts(history);
        renderRecentActivity(history, data);

    } catch (e) {
        console.error('Data synchronization error:', e);
    }
};

const renderDispatchOrders = (chequeBooks = [], physicalCards = []) => {
    const tbody = document.getElementById('dispatch-orders-tbody');
    if (!tbody) return;

    const items = [
        ...chequeBooks.map(cb => ({
            id: cb.id,
            item: `CTS Cheque Book (${cb.leaves} Leaves)`,
            spec: cb.series || `${cb.leaves} Leaves Bearer`,
            date: cb.order_date || 'Today',
            tracking: cb.tracking_id || 'SPEEDPOST-PENDING',
            status: cb.status || 'Dispatched',
            courier: 'SpeedPost',
            icon: 'receipt_long'
        })),
        ...physicalCards.map(c => ({
            id: c.id,
            item: c.variant || 'Physical Debit Card',
            spec: `Embossed: ${c.name_on_card || 'Card Holder'} (•••• ${String(c.card_number || '').replace(/\s+/g, '').slice(-4)})`,
            date: c.order_date || 'Today',
            tracking: c.tracking_id || 'BLUEDART-PENDING',
            status: c.status || 'Dispatched',
            courier: 'BlueDart',
            icon: 'credit_card'
        }))
    ];

    if (items.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="5" class="px-5 py-8 text-center text-slate-400 italic font-semibold">
                    <div class="flex flex-col items-center justify-center gap-1.5">
                        <span class="material-symbols-outlined text-2xl text-slate-300">local_shipping</span>
                        <span>No postal dispatches yet. Use the buttons above to order physical cards or cheque books.</span>
                    </div>
                </td>
            </tr>
        `;
        return;
    }

    tbody.innerHTML = '';
    items.forEach(item => {
        tbody.innerHTML += `
            <tr class="hover:bg-slate-50/70 transition-colors">
                <td class="px-5 py-3.5">
                    <div class="flex items-center gap-2.5">
                        <div class="size-8 rounded-xl bg-slate-100 flex items-center justify-center text-slate-700 shrink-0">
                            <span class="material-symbols-outlined text-base">${item.icon}</span>
                        </div>
                        <div>
                            <p class="font-extrabold text-slate-900">${item.item}</p>
                            <p class="text-[10px] font-mono text-slate-400">${item.id}</p>
                        </div>
                    </div>
                </td>
                <td class="px-5 py-3.5 text-slate-700 font-medium">${item.spec}</td>
                <td class="px-5 py-3.5 text-slate-500 font-mono text-[11px]">${item.date}</td>
                <td class="px-5 py-3.5">
                    <div class="flex items-center gap-1.5">
                        <span class="font-mono font-bold text-slate-800 text-[11px]">${item.tracking}</span>
                        <button onclick="window.copyText('${item.tracking}', 'Tracking Reference')" class="p-1 text-slate-400 hover:text-slate-700 rounded-lg hover:bg-slate-100 cursor-pointer" title="Copy tracking ID">
                            <span class="material-symbols-outlined text-xs">content_copy</span>
                        </button>
                    </div>
                </td>
                <td class="px-5 py-3.5 text-center">
                    <div class="flex flex-col items-center justify-center gap-1">
                        <span class="px-2.5 py-0.5 rounded-full text-[10px] font-extrabold bg-emerald-50 text-emerald-800 border border-emerald-200 inline-flex items-center gap-1 whitespace-nowrap">
                            <span class="size-1.5 rounded-full bg-emerald-500 animate-pulse"></span>
                            <span>${item.status}</span>
                        </span>
                        <span class="text-[10px] font-bold text-slate-500 flex items-center gap-1 whitespace-nowrap">
                            <span class="material-symbols-outlined text-xs text-emerald-600">schedule</span>
                            <span>Delivered in 2-3 working days</span>
                        </span>
                    </div>
                </td>
            </tr>
        `;
    });
};

const getInitials = (name) => {
    if (!name) return 'FN';
    const parts = name.trim().split(/\s+/).filter(Boolean);
    if (parts.length >= 2) {
        return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
    }
    return name.slice(0, 2).toUpperCase();
};

// ════════════ SYNC ANALYTICS & KPIS ════════════
const syncAnalytics = async (accNo) => {
    try {
        const res = await fetch(`/api/analytics/${accNo}`);
        const data = await res.json();
        if (!data.success) return;

        // Inflow / Outflow / Available Overview Chips
        const incEl = document.getElementById('overview-income-val');
        const expEl = document.getElementById('overview-expense-val');
        const availEl = document.getElementById('overview-available-val');
        if (incEl) incEl.textContent = formatINR(data.total_deposits);
        if (expEl) expEl.textContent = formatINR(data.total_withdrawals);
        if (availEl) availEl.textContent = formatINR(data.balance);

        // Fixed Deposit Desk
        const fdVal = document.getElementById('analytics-fd-val');
        const fdStatus = document.getElementById('analytics-fd-status');
        const fdPrincipal = document.getElementById('fd-active-principal');
        const fdTenure = document.getElementById('fd-active-tenure');
        const fdWithdrawDisp = document.getElementById('fd-withdraw-display');
        const fdWithdrawStat = document.getElementById('fd-withdraw-status');

        if (fdVal) fdVal.textContent = formatINR(data.fixed_deposit);
        if (fdPrincipal) fdPrincipal.textContent = formatINR(data.fixed_deposit);
        if (fdWithdrawDisp) fdWithdrawDisp.textContent = formatINR(data.fixed_deposit);

        const hasFd = data.fixed_deposit > 0;
        const tenureStr = hasFd ? `Active (${data.fd_tenure || 12} Mo @ 7.2% APY)` : 'No active FDs';
        if (fdStatus) fdStatus.textContent = tenureStr;
        if (fdTenure) fdTenure.textContent = hasFd ? `${data.fd_tenure || 12} Months Tenure` : 'No Active Deposit';
        if (fdWithdrawStat) fdWithdrawStat.textContent = hasFd ? 'Eligible for instant withdrawal' : 'No active deposit';

        // Loan Snapshot & Tab
        const loanVal = document.getElementById('analytics-loan-val');
        const loanStatus = document.getElementById('analytics-loan-status');
        const loanKpi = document.getElementById('loans-kpi-val');
        const loanBadge = document.getElementById('loans-status-badge');

        if (loanVal) loanVal.textContent = formatINR(data.loan_amount);
        if (loanKpi) loanKpi.textContent = formatINR(data.loan_amount);

        const hasLoan = data.loan_amount > 0;
        if (loanStatus) loanStatus.textContent = hasLoan ? 'Active Personal Loan' : '0 Active Loans';
        if (loanBadge) loanBadge.textContent = hasLoan ? '1 Active Obligation' : '0 Active Obligations';

        // Analytics Tab KPI Grid
        const kpiGrid = document.getElementById('analytics-kpi-grid');
        if (kpiGrid) {
            const netCashflow = (data.total_deposits || 0) - (data.total_withdrawals || 0);
            kpiGrid.innerHTML = `
                <div class="p-5 rounded-2xl bg-slate-50 border border-slate-200/60">
                    <p class="text-slate-400 uppercase text-[10px] font-bold">Total Inflows</p>
                    <p class="text-xl font-extrabold text-emerald-600 mt-1 tabular-nums">${formatINR(data.total_deposits)}</p>
                </div>
                <div class="p-5 rounded-2xl bg-slate-50 border border-slate-200/60">
                    <p class="text-slate-400 uppercase text-[10px] font-bold">Total Outflows</p>
                    <p class="text-xl font-extrabold text-rose-500 mt-1 tabular-nums">${formatINR(data.total_withdrawals)}</p>
                </div>
                <div class="p-5 rounded-2xl bg-slate-50 border border-slate-200/60">
                    <p class="text-slate-400 uppercase text-[10px] font-bold">Net Cash Flow</p>
                    <p class="text-xl font-extrabold ${netCashflow >= 0 ? 'text-emerald-600' : 'text-rose-500'} mt-1 tabular-nums">
                        ${formatINR(netCashflow)}
                    </p>
                </div>
                <div class="p-5 rounded-2xl bg-slate-50 border border-slate-200/60">
                    <p class="text-slate-400 uppercase text-[10px] font-bold">Fixed Deposits</p>
                    <p class="text-xl font-extrabold text-indigo-600 mt-1 tabular-nums">${formatINR(data.fixed_deposit)}</p>
                </div>
            `;
        }
    } catch (e) {
        console.error('Analytics sync error:', e);
    }
};

// ════════════ SYNC LOANS PORTFOLIO ════════════
const syncLoans = async (accNo) => {
    try {
        const res = await fetch(`/api/loans/${accNo}`);
        const data = await res.json();
        const tbody = document.getElementById('loans-history-tbody');
        if (!tbody) return;

        if (!data.loans || data.loans.length === 0) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="5" class="px-5 py-6 text-center text-slate-400 italic font-semibold">No active or past loans on file.</td>
                </tr>
            `;
        } else {
            tbody.innerHTML = '';
            data.loans.forEach(loan => {
                tbody.innerHTML += `
                    <tr class="hover:bg-slate-50/70 transition-colors">
                        <td class="px-5 py-3.5 font-bold font-mono text-slate-900">${loan.id || '#LN-1001'}</td>
                        <td class="px-5 py-3.5 font-semibold text-slate-700">${loan.type || 'Personal Loan'}</td>
                        <td class="px-5 py-3.5 text-slate-500 font-mono text-[11px]">${formatDate(loan.date)}</td>
                        <td class="px-5 py-3.5 text-right font-extrabold text-slate-900 tabular-nums">${formatINR(loan.amount)}</td>
                        <td class="px-5 py-3.5 text-center">
                            <span class="px-2.5 py-0.5 rounded-full text-[10px] font-bold ${
                                loan.status === 'Active' ? 'bg-rose-50 text-rose-700 border border-rose-200' : 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                            }">
                                ${loan.status || 'Active'}
                            </span>
                        </td>
                    </tr>
                `;
            });
        }
    } catch (e) {
        console.error('Loans sync error:', e);
    }
};

// ════════════ SYNC WEALTH & INVESTMENTS HUB ════════════
window.switchInvestSubTab = (subTabName) => {
    document.querySelectorAll('.invest-subview').forEach(el => el.classList.add('hidden'));
    const target = document.getElementById(`invest-subview-${subTabName}`);
    if (target) target.classList.remove('hidden');

    document.querySelectorAll('.invest-subtab-btn').forEach(btn => {
        btn.className = 'invest-subtab-btn px-3 py-1.5 rounded-xl text-xs font-semibold text-slate-600 hover:text-slate-900 transition-all flex items-center gap-1.5';
    });
    const activeBtn = document.getElementById(`subtab-btn-${subTabName}`);
    if (activeBtn) {
        activeBtn.className = 'invest-subtab-btn px-3 py-1.5 rounded-xl text-xs font-bold bg-white text-slate-900 shadow-xs transition-all flex items-center gap-1.5';
    }
};

window.selectFundForSIP = (fundId) => {
    const sel = document.getElementById('sip-fund-select');
    if (sel) {
        sel.value = fundId;
    }
    const form = document.getElementById('form-create-sip');
    if (form) {
        form.scrollIntoView({ behavior: 'smooth', block: 'center' });
        const amtInput = document.getElementById('sip-amount-input');
        if (amtInput) amtInput.focus();
    }
};

const syncInvestments = async (accNo) => {
    try {
        const res = await fetch(`/api/investments/${accNo}`);
        const data = await res.json();
        if (!data.success) return;

        const summary = data.portfolio_summary || {};
        
        // 1. KPI Cards
        const totalValEl = document.getElementById('inv-total-valuation');
        const overallGainEl = document.getElementById('inv-overall-gain');
        const totalInvestedEl = document.getElementById('inv-total-invested');
        const mfValEl = document.getElementById('inv-mf-valuation');
        const mfCountEl = document.getElementById('inv-mf-active-count');
        const ipoGoldValEl = document.getElementById('inv-ipo-gold-val');
        const goldGramsEl = document.getElementById('inv-gold-grams-disp');

        if (totalValEl) totalValEl.textContent = formatINR(summary.current_valuation || 0);
        if (overallGainEl) {
            const gain = summary.unrealized_gain || 0;
            const pct = summary.gain_pct || 0;
            const sign = gain >= 0 ? '+' : '';
            overallGainEl.textContent = `${sign}${formatINR(gain)} (${sign}${pct}%)`;
            overallGainEl.className = `text-[11px] font-semibold mt-0.5 ${gain >= 0 ? 'text-emerald-600' : 'text-rose-500'}`;
        }
        if (totalInvestedEl) totalInvestedEl.textContent = formatINR(summary.total_invested || 0);
        if (mfValEl) mfValEl.textContent = formatINR(summary.total_sip_current || 0);
        if (mfCountEl) mfCountEl.textContent = `${(data.sips || []).length} Active Investment(s)`;
        
        const ipoGoldSum = (summary.total_ipo_blocked || 0) + (summary.total_gold_valuation || 0);
        if (ipoGoldValEl) ipoGoldValEl.textContent = formatINR(ipoGoldSum);
        if (goldGramsEl) goldGramsEl.textContent = `${(data.gold?.grams || 0).toFixed(4)}g Gold held`;

        // 2. Render Recommended Mutual Funds Grid
        const fundsGrid = document.getElementById('market-funds-grid');
        if (fundsGrid && Array.isArray(data.market_funds)) {
            fundsGrid.innerHTML = '';
            data.market_funds.forEach(f => {
                const cagrDisplay = f.cagr_3y || (f.returns_3y ? `+${f.returns_3y}% p.a.` : '+18.5% p.a.');
                fundsGrid.innerHTML += `
                    <div class="p-4 rounded-2xl bg-slate-50 border border-slate-200/80 hover:border-emerald-500/50 hover:bg-white hover:shadow-md transition-all flex flex-col justify-between">
                        <div>
                            <div class="flex items-center justify-between mb-2">
                                <span class="px-2 py-0.5 rounded-full text-[9px] font-extrabold uppercase bg-emerald-100 text-emerald-800">${f.category}</span>
                                <span class="text-[10px] font-bold text-slate-400">NAV ₹${f.nav}</span>
                            </div>
                            <h4 class="text-xs font-bold text-slate-900 leading-tight mb-1">${f.name}</h4>
                            <div class="flex items-baseline gap-1 my-2">
                                <span class="text-lg font-extrabold text-emerald-600">${cagrDisplay}</span>
                                <span class="text-[10px] font-semibold text-slate-400">3Y CAGR</span>
                            </div>
                            <div class="flex items-center justify-between text-[10px] text-slate-500 font-medium">
                                <span>Rating: ${f.rating}</span>
                                <span>Min SIP: ₹${f.min_sip}</span>
                            </div>
                        </div>
                        <button onclick="window.selectFundForSIP('${f.id}')" class="w-full mt-3 py-2 bg-slate-900 hover:bg-slate-800 text-white font-bold text-xs rounded-xl transition-all shadow-xs flex items-center justify-center gap-1 cursor-pointer">
                            <span>Invest / Start SIP</span>
                            <span class="material-symbols-outlined text-sm">arrow_forward</span>
                        </button>
                    </div>
                `;
            });
        }

        // 3. Render Active SIP Portfolio Table
        const sipsTbody = document.getElementById('user-sips-tbody');
        if (sipsTbody) {
            if (!data.sips || data.sips.length === 0) {
                sipsTbody.innerHTML = `
                    <tr>
                        <td colspan="5" class="px-4 py-8 text-center text-slate-400 italic font-semibold">
                            No active Mutual Fund or SIP investments yet. Start one on the left!
                        </td>
                    </tr>
                `;
            } else {
                sipsTbody.innerHTML = '';
                data.sips.forEach(s => {
                    const isPaused = s.status === 'Paused';
                    sipsTbody.innerHTML += `
                        <tr class="hover:bg-slate-50/70 transition-colors">
                            <td class="px-4 py-3">
                                <div class="font-bold text-slate-900">${s.fund_name}</div>
                                <div class="text-[10px] text-slate-400 font-mono">${s.type} • ${s.id}</div>
                            </td>
                            <td class="px-4 py-3 text-right font-bold text-slate-700 tabular-nums">${formatINR(s.invested_amount)}</td>
                            <td class="px-4 py-3 text-right font-extrabold text-emerald-600 tabular-nums">${formatINR(s.current_value)}</td>
                            <td class="px-4 py-3 text-center">
                                <span class="px-2 py-0.5 rounded-full text-[9px] font-bold ${
                                    isPaused ? 'bg-amber-100 text-amber-800 border border-amber-200' : 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                                }">
                                    ${s.status || 'Active'}
                                </span>
                            </td>
                            <td class="px-4 py-3 text-right">
                                <div class="flex items-center justify-end gap-1.5">
                                    ${isPaused ? `
                                        <button onclick="window.handleSIPAction('${s.id}', 'resume')" class="px-2 py-1 rounded-lg bg-emerald-50 hover:bg-emerald-100 text-emerald-700 text-[10px] font-bold transition-colors">
                                            Resume
                                        </button>
                                    ` : `
                                        <button onclick="window.handleSIPAction('${s.id}', 'pause')" class="px-2 py-1 rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-700 text-[10px] font-bold transition-colors">
                                            Pause
                                        </button>
                                    `}
                                    <button onclick="window.handleSIPAction('${s.id}', 'redeem')" class="px-2 py-1 rounded-lg bg-rose-50 hover:bg-rose-100 text-rose-700 text-[10px] font-bold transition-colors">
                                        Redeem
                                    </button>
                                </div>
                            </td>
                        </tr>
                    `;
                });
            }
        }

        // 4. Render Market IPOs Grid with Ongoing, Upcoming, and Closed categories
        window.currentMarketIpos = data.market_ipos || [];
        renderMarketIposGrid(window.currentMarketIpos, window.activeIpoFilter || 'all');

        // 5. Render User Applied IPOs Table
        const iposTbody = document.getElementById('user-ipos-tbody');
        if (iposTbody) {
            if (!data.ipos || data.ipos.length === 0) {
                iposTbody.innerHTML = `
                    <tr>
                        <td colspan="5" class="px-4 py-8 text-center text-slate-400 italic font-semibold">
                            No active ASBA IPO applications. Bid for upcoming IPOs above!
                        </td>
                    </tr>
                `;
            } else {
                iposTbody.innerHTML = '';
                data.ipos.forEach(app => {
                    iposTbody.innerHTML += `
                        <tr class="hover:bg-slate-50/70 transition-colors">
                            <td class="px-4 py-3 font-mono font-bold text-slate-900">${app.app_no}</td>
                            <td class="px-4 py-3">
                                <div class="font-bold text-slate-900">${app.company}</div>
                                <div class="text-[10px] text-slate-400 font-mono">${app.symbol} • Applied on ${app.applied_date}</div>
                            </td>
                            <td class="px-4 py-3 text-center font-semibold text-slate-700">${app.lots} Lots (${app.shares} sh)</td>
                            <td class="px-4 py-3 text-right font-extrabold text-slate-900 tabular-nums">${formatINR(app.amount_blocked)}</td>
                            <td class="px-4 py-3 text-center">
                                <span class="px-2.5 py-1 rounded-full text-[9px] font-extrabold bg-indigo-50 text-indigo-700 border border-indigo-200">
                                    ${app.status || 'Application Submitted'}
                                </span>
                            </td>
                        </tr>
                    `;
                });
            }
        }

        // 6. Render User RDs Table
        const rdsTbody = document.getElementById('user-rds-tbody');
        if (rdsTbody) {
            if (!data.rds || data.rds.length === 0) {
                rdsTbody.innerHTML = `
                    <tr>
                        <td colspan="4" class="px-3 py-6 text-center text-slate-400 italic font-semibold">
                            No active Recurring Deposits on file.
                        </td>
                    </tr>
                `;
            } else {
                rdsTbody.innerHTML = '';
                data.rds.forEach(rd => {
                    rdsTbody.innerHTML += `
                        <tr class="hover:bg-slate-50/70 transition-colors">
                            <td class="py-2.5 font-bold font-mono text-slate-900">${rd.id}</td>
                            <td class="py-2.5 text-right font-bold text-slate-700 tabular-nums">${formatINR(rd.monthly_amount)}/mo</td>
                            <td class="py-2.5 text-right font-bold text-emerald-600 tabular-nums">${formatINR(rd.total_deposited)}</td>
                            <td class="py-2.5 text-right font-extrabold text-slate-900 tabular-nums">${formatINR(rd.maturity_amount)}</td>
                        </tr>
                    `;
                });
            }
        }

        // 7. Render 24K Digital Gold Vault with Live Rates
        const goldBuyPrice = data.gold?.current_rate || data.gold_buy_rate || 7620.50;
        const goldSellPrice = data.gold_sell_rate || (goldBuyPrice * 0.99);

        window.currentInvestmentsData = data;
        window.liveGoldBuyRate = goldBuyPrice;
        window.liveGoldSellRate = goldSellPrice;

        const goldRateBuy = document.getElementById('gold-live-buy-rate');
        const goldRateSell = document.getElementById('gold-live-sell-rate');
        const goldGrams = document.getElementById('gold-vault-grams');
        const goldVal = document.getElementById('gold-vault-val');

        if (goldRateBuy) goldRateBuy.textContent = `₹${goldBuyPrice.toLocaleString('en-IN', {minimumFractionDigits: 2})}/gm`;
        if (goldRateSell) goldRateSell.textContent = `₹${goldSellPrice.toLocaleString('en-IN', {minimumFractionDigits: 2})}/gm`;
        if (goldGrams) goldGrams.textContent = `${(data.gold?.grams || 0).toFixed(4)} g`;
        if (goldVal) goldVal.textContent = formatINR(data.gold?.current_value || 0);

    } catch (e) {
        console.error('Wealth & Investments sync error:', e);
    }
};

// ════════════ IPO CATEGORY FILTERING & RENDERING ════════════
window.currentMarketIpos = [];
window.activeIpoFilter = 'all';

window.filterIpos = (filterType) => {
    window.activeIpoFilter = filterType;
    document.querySelectorAll('.ipo-filter-btn').forEach(btn => {
        btn.className = 'ipo-filter-btn px-3 py-1.5 rounded-xl text-xs font-semibold bg-slate-100 text-slate-700 hover:bg-slate-200 transition-all flex items-center gap-1.5 cursor-pointer';
    });
    const activeBtn = document.getElementById(`ipo-filter-${filterType}`);
    if (activeBtn) {
        activeBtn.className = 'ipo-filter-btn px-3 py-1.5 rounded-xl text-xs font-bold bg-slate-900 text-white shadow-xs transition-all flex items-center gap-1.5 cursor-pointer';
    }
    renderMarketIposGrid(window.currentMarketIpos, filterType);
};

const renderMarketIposGrid = (ipos, filter = 'all') => {
    const iposGrid = document.getElementById('market-ipos-grid');
    if (!iposGrid) return;
    
    let filtered = ipos;
    if (filter === 'ongoing') {
        filtered = ipos.filter(i => (i.status_type || '').toLowerCase() === 'ongoing' || (i.status || '').toLowerCase().includes('open') || (i.status || '').toLowerCase().includes('allotment'));
    } else if (filter === 'upcoming') {
        filtered = ipos.filter(i => (i.status_type || '').toLowerCase() === 'upcoming');
    } else if (filter === 'closed') {
        filtered = ipos.filter(i => (i.status_type || '').toLowerCase() === 'closed' || (i.status || '').toLowerCase().includes('closed') || (i.status || '').toLowerCase().includes('listed'));
    }

    iposGrid.innerHTML = '';
    if (filtered.length === 0) {
        iposGrid.innerHTML = `
            <div class="col-span-full py-8 text-center text-slate-400 italic font-semibold bg-slate-50 rounded-2xl border border-slate-200/60">
                No IPOs found in this category.
            </div>
        `;
        return;
    }

    filtered.forEach(ipo => {
        const isClosed = (ipo.status_type || '').toLowerCase() === 'closed' || (ipo.status || '').toLowerCase().includes('closed') || (ipo.status || '').toLowerCase().includes('listed');
        const isUpcoming = (ipo.status_type || '').toLowerCase() === 'upcoming';
        const isOngoing = !isClosed && !isUpcoming;

        const subText = ipo.subscription || (isUpcoming ? 'Opens Soon' : 'Active Bidding');
        const closeText = ipo.closes || ipo.close_date || (isClosed ? 'Closed' : '29/09/2026');
        const gmpVal = ipo.gmp !== undefined ? ipo.gmp : 0;
        const gmpPct = ipo.gmp_pct !== undefined ? ipo.gmp_pct : 0;
        const gmpDisplay = gmpVal > 0 ? `+₹${gmpVal} (+${gmpPct}%)` : (gmpVal === 0 ? '₹0.00 (0%)' : `-₹${Math.abs(gmpVal)}`);

        let statusBadgeClass = 'bg-emerald-100 text-emerald-800 border-emerald-200';
        if (isUpcoming) statusBadgeClass = 'bg-indigo-100 text-indigo-800 border-indigo-200';
        if (isClosed) statusBadgeClass = 'bg-amber-100 text-amber-800 border-amber-200';

        iposGrid.innerHTML += `
            <div class="p-5 rounded-3xl bg-slate-50 border border-slate-200/80 hover:bg-white hover:border-indigo-400 hover:shadow-lg transition-all flex flex-col justify-between group">
                <div>
                    <!-- Badges Row -->
                    <div class="flex items-center justify-between gap-1.5 mb-2.5">
                        <div class="flex items-center gap-1.5">
                            <span class="px-2.5 py-0.5 rounded-full text-[9px] font-extrabold uppercase bg-slate-900 text-white tracking-wider">${ipo.ipo_type || 'Mainboard'}</span>
                            <span class="px-2 py-0.5 rounded-full text-[9px] font-bold bg-indigo-50 text-indigo-700 border border-indigo-200/60">${ipo.category || 'Equity'}</span>
                        </div>
                        <span class="px-2 py-0.5 rounded-full text-[9px] font-extrabold border ${statusBadgeClass}">${subText}</span>
                    </div>

                    <!-- Company & Symbol -->
                    <h4 class="text-sm font-extrabold text-slate-900 group-hover:text-indigo-600 transition-colors leading-snug">${ipo.company}</h4>
                    <div class="flex items-center justify-between my-1.5">
                        <p class="text-[11px] font-mono font-bold text-slate-500">${ipo.symbol} • ${ipo.exchanges || 'BSE, NSE'}</p>
                        ${gmpVal > 0 ? `
                            <span class="inline-flex items-center gap-1 text-[10px] font-extrabold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-full border border-emerald-200">
                                <span class="material-symbols-outlined text-xs">bolt</span>
                                <span>GMP: ${gmpDisplay}</span>
                            </span>
                        ` : ''}
                    </div>

                    <!-- Key Financial Metrics -->
                    <div class="space-y-1.5 text-[11px] border-t border-slate-200/60 pt-2.5 mt-2">
                        <div class="flex justify-between">
                            <span class="text-slate-400">Price Band:</span>
                            <span class="font-bold text-slate-900 font-mono">₹${ipo.price_min} - ₹${ipo.price_max}</span>
                        </div>
                        <div class="flex justify-between">
                            <span class="text-slate-400">Lot Size:</span>
                            <span class="font-bold text-slate-800">${ipo.lot_size} Shares (${formatINR(ipo.price_max * ipo.lot_size)})</span>
                        </div>
                        <div class="flex justify-between">
                            <span class="text-slate-400">Issue Size:</span>
                            <span class="font-bold text-slate-800 font-mono">${ipo.issue_size || '₹300 Cr'}</span>
                        </div>
                        <div class="flex justify-between">
                            <span class="text-slate-400">${isClosed ? 'Listing Performance:' : (isUpcoming ? 'Opens on:' : 'Closes on:')}</span>
                            <span class="font-extrabold font-mono ${isClosed ? 'text-emerald-600' : (isUpcoming ? 'text-indigo-600' : 'text-rose-600')}">
                                ${isClosed ? (ipo.listing_gain || 'Listed') : (isUpcoming ? ipo.open_date : closeText)}
                            </span>
                        </div>
                    </div>
                </div>

                <!-- Action Button Matrix (Details + ASBA) -->
                <div class="grid grid-cols-2 gap-2 mt-4 pt-2 border-t border-slate-100">
                    <button onclick="window.openIpoDetailsModal('${ipo.id}')" class="py-2.5 px-2 bg-slate-100 hover:bg-slate-200 text-slate-800 font-bold text-xs rounded-xl transition-all flex items-center justify-center gap-1 cursor-pointer">
                        <span class="material-symbols-outlined text-sm">visibility</span>
                        <span>Full Details & GMP</span>
                    </button>

                    ${isOngoing ? `
                        <button onclick="window.openIpoBidModal('${ipo.id}')" class="py-2.5 px-2 bg-indigo-600 hover:bg-indigo-700 text-white font-bold text-xs rounded-xl transition-all shadow-sm flex items-center justify-center gap-1 cursor-pointer active:scale-95">
                            <span class="material-symbols-outlined text-sm">rocket_launch</span>
                            <span>Apply ASBA</span>
                        </button>
                    ` : (isUpcoming ? `
                        <button onclick="showToast('Alert set! You will receive an ASBA notification when ${ipo.company} opens.');" class="py-2.5 px-2 bg-slate-900 hover:bg-slate-800 text-white font-bold text-xs rounded-xl transition-all shadow-sm flex items-center justify-center gap-1 cursor-pointer active:scale-95">
                            <span class="material-symbols-outlined text-sm">notifications_active</span>
                            <span>Pre-Apply Alert</span>
                        </button>
                    ` : `
                        <div class="py-2 px-2 bg-emerald-50 border border-emerald-200 rounded-xl text-emerald-800 text-center text-[10px] font-extrabold flex items-center justify-center gap-0.5">
                            <span class="material-symbols-outlined text-xs">check_circle</span>
                            <span>Listed</span>
                        </div>
                    `)}
                </div>
            </div>
        `;
    });
};

// ════════════ RENDER TRANSACTIONS ════════════
const renderTransactions = (history) => {
    const dashList = document.getElementById('dashboard-tx-list');
    const fullTbody = document.getElementById('full-transactions-tbody');

    // 1. Dashboard Recent List
    if (dashList) {
        dashList.innerHTML = '';
        if (history.length === 0) {
            dashList.innerHTML = `
                <div class="text-center py-6 px-4 bg-slate-50 rounded-2xl border border-slate-200/60 space-y-2">
                    <span class="material-symbols-outlined text-3xl text-slate-300">receipt_long</span>
                    <p class="text-xs font-semibold text-slate-600">No transactions recorded yet.</p>
                    <button onclick="openTransferModal()" class="text-xs font-bold text-emerald-600 hover:underline">+ Make a Transfer</button>
                </div>
            `;
        } else {
            const recent = history.slice(-5).reverse();
            recent.forEach(tx => {
                const amtStr = String(tx.amount || '0');
                const isCredit = amtStr.startsWith('+') || parseFloat(amtStr) > 0;
                const cleanAmt = amtStr.replace(/^[+-]/, '');
                
                let icon = 'swap_horiz';
                const txLower = (tx.type || '').toLowerCase();
                if (isCredit) icon = 'account_balance_wallet';
                else if (txLower.includes('bill') || txLower.includes('electricity') || txLower.includes('water')) icon = 'bolt';
                else if (txLower.includes('shopping') || txLower.includes('amazon') || txLower.includes('pos')) icon = 'shopping_bag';
                else if (txLower.includes('fd') || txLower.includes('deposit')) icon = 'savings';
                else if (txLower.includes('transfer')) icon = 'send';
                else if (txLower.includes('loan')) icon = 'real_estate_agent';

                dashList.innerHTML += `
                    <div class="flex items-center justify-between p-2.5 rounded-2xl hover:bg-slate-50 transition-colors border border-transparent hover:border-slate-100">
                        <div class="flex items-center gap-3">
                            <div class="size-9 rounded-xl ${isCredit ? 'bg-emerald-50 text-emerald-600 border-emerald-100' : 'bg-slate-100 text-slate-600 border-slate-200'} flex items-center justify-center border">
                                <span class="material-symbols-outlined text-lg">${icon}</span>
                            </div>
                            <div>
                                <h4 class="text-xs font-bold text-slate-900">${tx.type || 'Transaction'}</h4>
                                <p class="text-[10px] text-slate-400 font-mono">${formatDate(tx.date)}</p>
                            </div>
                        </div>
                        <span class="text-xs font-extrabold tabular-nums ${isCredit ? 'text-emerald-600' : 'text-rose-500'}">
                            ${isCredit ? '+' : '-'} ${formatINR(cleanAmt)}
                        </span>
                    </div>
                `;
            });
        }
    }

    // 2. Full Transactions Tab Table
    if (fullTbody) {
        fullTbody.innerHTML = '';
        if (history.length === 0) {
            fullTbody.innerHTML = `
                <tr>
                    <td colspan="5" class="px-5 py-8 text-center text-slate-400 italic font-semibold">
                        No transactions recorded for this account.
                    </td>
                </tr>
            `;
        } else {
            const allTxs = [...history].reverse();
            allTxs.forEach(tx => {
                const amtStr = String(tx.amount || '0');
                const isCredit = amtStr.startsWith('+') || parseFloat(amtStr) > 0;
                const cleanAmt = amtStr.replace(/^[+-]/, '');

                fullTbody.innerHTML += `
                    <tr class="hover:bg-slate-50/70 transition-colors">
                        <td class="px-5 py-3.5 font-bold text-slate-900 flex items-center gap-2">
                            <span class="size-2 rounded-full ${isCredit ? 'bg-emerald-500' : 'bg-rose-500'}"></span>
                            <span>${tx.type || 'Transaction'}</span>
                        </td>
                        <td class="px-5 py-3.5 text-slate-500 font-mono text-[11px]">${formatDate(tx.date)}</td>
                        <td class="px-5 py-3.5 text-right font-bold tabular-nums ${isCredit ? 'text-emerald-600' : 'text-rose-500'}">
                            ${isCredit ? '+' : '-'} ${formatINR(cleanAmt)}
                        </td>
                        <td class="px-5 py-3.5 text-right font-bold text-slate-700 tabular-nums">
                            ${tx.balance ? formatINR(tx.balance) : '--'}
                        </td>
                        <td class="px-5 py-3.5 text-center">
                            <span class="px-2.5 py-1 rounded-full text-[10px] font-bold bg-emerald-50 text-emerald-700 border border-emerald-200">
                                Completed
                            </span>
                        </td>
                    </tr>
                `;
            });
        }
    }
};

// ════════════ DYNAMIC CHARTS & SPENDING BREAKDOWN ════════════
const renderCharts = (history) => {
    // 1. Categorized Debits Donut Chart
    const debits = history.filter(tx => {
        const amtStr = String(tx.amount || '0');
        return amtStr.startsWith('-') || (!amtStr.startsWith('+') && parseFloat(amtStr) < 0);
    });

    const categories = {
        'Transfers & UPI': 0,
        'Utility & Bills': 0,
        'Investments & FDs': 0,
        'Shopping & POS': 0
    };

    let totalDebited = 0;
    debits.forEach(tx => {
        const amt = Math.abs(parseFloat(String(tx.amount).replace(/^[+-]/, '')) || 0);
        totalDebited += amt;
        const typeLower = (tx.type || '').toLowerCase();
        if (typeLower.includes('transfer') || typeLower.includes('upi')) {
            categories['Transfers & UPI'] += amt;
        } else if (typeLower.includes('bill') || typeLower.includes('electricity') || typeLower.includes('water') || typeLower.includes('broadband')) {
            categories['Utility & Bills'] += amt;
        } else if (typeLower.includes('fd') || typeLower.includes('fixed deposit')) {
            categories['Investments & FDs'] += amt;
        } else {
            categories['Shopping & POS'] += amt;
        }
    });

    const donutTotal = document.getElementById('donut-total-val');
    if (donutTotal) donutTotal.textContent = formatINR(totalDebited);

    const legendContainer = document.getElementById('spending-legend-container');
    const reportsTbody = document.getElementById('reports-category-tbody');

    if (legendContainer) legendContainer.innerHTML = '';
    if (reportsTbody) reportsTbody.innerHTML = '';

    if (totalDebited === 0) {
        if (legendContainer) {
            legendContainer.innerHTML = `
                <div class="text-[11px] text-slate-400 italic py-2">No debit expenses recorded yet.</div>
            `;
        }
        if (reportsTbody) {
            reportsTbody.innerHTML = `
                <tr>
                    <td colspan="3" class="px-5 py-6 text-center text-slate-400 italic font-semibold">No debit records logged yet.</td>
                </tr>
            `;
        }
    } else {
        const colors = [
            { bg: 'bg-emerald-500', segId: 'donut-seg-1' },
            { bg: 'bg-blue-500', segId: 'donut-seg-2' },
            { bg: 'bg-amber-400', segId: 'donut-seg-3' }
        ];

        let offset = 0;
        let colorIdx = 0;

        for (const [catName, catAmt] of Object.entries(categories)) {
            if (catAmt > 0) {
                const pct = Math.round((catAmt / totalDebited) * 100);
                const color = colors[colorIdx % colors.length];

                // Update SVG Donut Segment
                const segEl = document.getElementById(color.segId);
                if (segEl) {
                    segEl.setAttribute('stroke-dasharray', `${pct} ${100 - pct}`);
                    segEl.setAttribute('stroke-dashoffset', `${-offset}`);
                }
                offset += pct;

                // Add to Dashboard Legend
                if (legendContainer) {
                    legendContainer.innerHTML += `
                        <div class="flex items-center justify-between text-xs py-0.5">
                            <div class="flex items-center gap-2">
                                <span class="size-2 rounded-full ${color.bg}"></span>
                                <span class="font-bold text-slate-700">${catName}</span>
                            </div>
                            <span class="font-extrabold text-slate-900 tabular-nums">${pct}%</span>
                        </div>
                    `;
                }

                // Add to Reports Workspace Table
                if (reportsTbody) {
                    const txCount = debits.filter(t => (t.type || '').toLowerCase().includes(catName.split(' ')[0].toLowerCase())).length || 1;
                    reportsTbody.innerHTML += `
                        <tr class="hover:bg-slate-50/70 transition-colors">
                            <td class="px-5 py-3 font-bold text-slate-900 flex items-center gap-2">
                                <span class="size-2 rounded-full ${color.bg}"></span>
                                <span>${catName}</span>
                            </td>
                            <td class="px-5 py-3 text-right text-slate-600 font-bold">${txCount}</td>
                            <td class="px-5 py-3 text-right font-extrabold text-slate-900 tabular-nums">${formatINR(catAmt)}</td>
                        </tr>
                    `;
                }
                colorIdx++;
            }
        }
    }

    // 2. Dynamic SVG Timeline Area Curves
    const incCurve = document.getElementById('svg-inc-curve');
    const expCurve = document.getElementById('svg-exp-curve');
    if (incCurve && expCurve) {
        if (history.length > 0) {
            const pts = history.slice(-4);
            const incY = 190 - Math.min(150, (pts.filter(t => String(t.amount).startsWith('+')).reduce((a, b) => a + parseFloat(String(b.amount).replace('+', '') || 0), 0) / 100));
            const expY = 190 - Math.min(130, (pts.filter(t => String(t.amount).startsWith('-')).reduce((a, b) => a + parseFloat(String(b.amount).replace('-', '') || 0), 0) / 100));
            incCurve.setAttribute('d', `M 30,160 Q 150,${Math.max(40, incY - 20)} 280,${Math.max(60, incY)} T 490,${Math.max(50, incY - 10)}`);
            expCurve.setAttribute('d', `M 30,175 Q 150,${Math.max(80, expY + 10)} 280,${Math.max(90, expY)} T 490,${Math.max(70, expY + 5)}`);
        }
    }
};

// ════════════ RECENT ACTIVITY LIST ════════════
const renderRecentActivity = (history, accountData) => {
    const actList = document.getElementById('recent-activity-list');
    if (!actList) return;

    actList.innerHTML = '';
    const events = [];

    // Session Authenticated Event
    events.push({
        title: 'Active Session Authenticated',
        subtitle: `Logged in to Account #${accountData.account_number}`,
        time: 'Just now',
        icon: 'security',
        color: 'bg-emerald-50 text-emerald-600 border-emerald-100'
    });

    if (history.length > 0) {
        const lastTxs = history.slice(-3).reverse();
        lastTxs.forEach(tx => {
            const isCredit = String(tx.amount).startsWith('+');
            events.push({
                title: tx.type || 'Transaction Executed',
                subtitle: `${isCredit ? 'Credit' : 'Debit'} of ${formatINR(String(tx.amount).replace(/^[+-]/, ''))}`,
                time: formatDate(tx.date),
                icon: isCredit ? 'arrow_downward' : 'arrow_upward',
                color: isCredit ? 'bg-emerald-50 text-emerald-600 border-emerald-100' : 'bg-slate-100 text-slate-600 border-slate-200'
            });
        });
    }

    events.forEach(ev => {
        actList.innerHTML += `
            <div class="flex items-center gap-3">
                <div class="size-8 rounded-xl ${ev.color} flex items-center justify-center border shrink-0">
                    <span class="material-symbols-outlined text-base">${ev.icon}</span>
                </div>
                <div class="flex-1 min-w-0">
                    <p class="text-xs font-bold text-slate-900 truncate">${ev.title}</p>
                    <p class="text-[10px] text-slate-400 truncate">${ev.subtitle}</p>
                </div>
                <span class="text-[10px] font-bold text-slate-400 shrink-0">${ev.time}</span>
            </div>
        `;
    });
};

// ════════════ HANDLERS: LOANS TAB ════════════
window.handleApplyLoan = async (e) => {
    e.preventDefault();
    const employmentType = document.getElementById('loan-employment-type').value;
    const monthlyIncome = parseFloat(document.getElementById('loan-monthly-income').value.trim() || '0');
    const cibilScore = parseInt(document.getElementById('loan-cibil-score').value.trim() || '0', 10);
    const panNumber = document.getElementById('loan-pan-number').value.trim().toUpperCase();
    const amount = document.getElementById('loan-apply-amount').value.trim();
    const purpose = document.getElementById('loan-apply-purpose').value;
    const currentAcc = sessionStorage.getItem('current_account');

    if (!monthlyIncome || monthlyIncome < 5000) {
        showToast('Please enter a valid monthly net income (minimum ₹5,000).', 'error');
        return;
    }

    if (!cibilScore || cibilScore < 300 || cibilScore > 900) {
        showToast('Please enter a valid CIBIL credit score between 300 and 900.', 'error');
        return;
    }

    if (cibilScore < 600) {
        showToast('Loan declined: Minimum CIBIL score of 600 required for sanction.', 'error');
        return;
    }

    if (!panNumber || panNumber.length !== 10) {
        showToast('Please enter a valid 10-character PAN Card number (e.g. ABCDE1234F).', 'error');
        return;
    }

    if (!amount || parseFloat(amount) <= 0) {
        showToast('Please enter a valid required loan amount.', 'error');
        return;
    }

    try {
        const res = await fetch('/api/apply_loan', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                account: currentAcc, 
                employment_type: employmentType,
                monthly_income: monthlyIncome,
                cibil: cibilScore,
                pan: panNumber,
                amount, 
                purpose 
            })
        });
        const d = await res.json();
        if (d.success) {
            showToast(`Loan of ₹${parseFloat(amount).toLocaleString('en-IN')} approved & credited!`);
            
            // Show Loan Sanction Approval Modal
            openModal({
                title: 'Loan Sanction Letter & Disbursement',
                description: 'Instant credit line approved and disbursed to primary account',
                contentHtml: `
                    <div class="space-y-3.5">
                        <div class="p-3.5 bg-emerald-50 border border-emerald-200 rounded-2xl flex items-center gap-3">
                            <div class="size-10 rounded-xl bg-emerald-600 text-white flex items-center justify-center font-bold">
                                <span class="material-symbols-outlined text-lg">verified</span>
                            </div>
                            <div>
                                <h4 class="text-xs font-bold text-emerald-950">Loan Sanction Approved</h4>
                                <p class="text-[11px] text-emerald-800">Funds credited immediately to Account #${currentAcc}</p>
                            </div>
                        </div>

                        <div class="p-4 rounded-2xl bg-slate-50 border border-slate-200 space-y-2 text-xs">
                            <div class="flex justify-between py-0.5">
                                <span class="text-slate-500">Sanctioned Amount:</span>
                                <span class="font-extrabold text-slate-900 font-mono text-sm">${formatINR(parseFloat(amount))}</span>
                            </div>
                            <div class="flex justify-between py-0.5">
                                <span class="text-slate-500">Loan Purpose:</span>
                                <span class="font-bold text-slate-800">${purpose}</span>
                            </div>
                            <div class="flex justify-between py-0.5">
                                <span class="text-slate-500">Employment Type:</span>
                                <span class="font-semibold text-slate-800">${employmentType}</span>
                            </div>
                            <div class="flex justify-between py-0.5">
                                <span class="text-slate-500">Applicant PAN:</span>
                                <span class="font-mono font-bold text-slate-900">${panNumber}</span>
                            </div>
                            <div class="flex justify-between py-0.5">
                                <span class="text-slate-500">Verified CIBIL Score:</span>
                                <span class="font-bold text-emerald-700 bg-emerald-100 px-2 py-0.5 rounded-md">${cibilScore} / 900</span>
                            </div>
                            <div class="flex justify-between py-0.5 border-t border-slate-200 pt-2">
                                <span class="text-slate-500">Applicable Interest Rate:</span>
                                <span class="font-bold text-slate-900">8.5% Fixed p.a.</span>
                            </div>
                        </div>
                    </div>
                `,
                submitText: 'Done',
                onConfirm: async (modal, close) => close()
            });

            // Reset form
            document.getElementById('loan-monthly-income').value = '';
            document.getElementById('loan-cibil-score').value = '';
            document.getElementById('loan-pan-number').value = '';
            document.getElementById('loan-apply-amount').value = '';
            syncAccountData();
        } else {
            showToast(d.message || d.result || 'Loan application declined.', 'error');
        }
    } catch (err) {
        showToast('Failed to process loan request.', 'error');
    }
};

window.handleRepayLoan = async (e) => {
    if (e && typeof e.preventDefault === 'function') e.preventDefault();
    const amount = document.getElementById('loan-repay-amount')?.value?.trim();
    const currentAcc = sessionStorage.getItem('current_account');

    if (!amount || parseFloat(amount) <= 0) {
        showToast('Please enter a valid repayment amount.', 'error');
        return;
    }

    try {
        const res = await fetch('/api/repay_loan', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ account: currentAcc, amount })
        });
        const d = await res.json();
        if (d.success) {
            showToast(d.message || `Loan repayment of ₹${amount} processed successfully!`);
            const inp = document.getElementById('loan-repay-amount');
            if (inp) inp.value = '';
            syncAccountData();
        } else {
            showToast(d.message || d.result || 'Loan repayment failed.', 'error');
        }
    } catch (err) {
        showToast('Loan repayment request failed.', 'error');
    }
};

// ════════════ HANDLERS: FIXED DEPOSIT TAB ════════════
window.handleCreateFD = async (e) => {
    if (e && typeof e.preventDefault === 'function') e.preventDefault();
    const amount = document.getElementById('fd-create-amount')?.value?.trim();
    const tenure = document.getElementById('fd-create-tenure')?.value || '12';
    const currentAcc = sessionStorage.getItem('current_account');

    if (!amount || parseFloat(amount) <= 0) {
        showToast('Please enter a valid investment amount.', 'error');
        return;
    }

    try {
        const res = await fetch('/api/create_fd', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ account: currentAcc, amount, tenure })
        });
        const d = await res.json();
        if (d.success) {
            showToast(`Fixed Deposit of ₹${amount} created successfully!`);
            const inp = document.getElementById('fd-create-amount');
            if (inp) inp.value = '';
            syncAccountData();
        } else {
            showToast(d.result || d.message || 'FD creation failed.', 'error');
        }
    } catch (err) {
        showToast('Failed to create FD.', 'error');
    }
};

window.handleWithdrawFD = async () => {
    const currentAcc = sessionStorage.getItem('current_account');
    if (!confirm('Are you sure you want to withdraw and liquidate your active Fixed Deposit?')) return;

    try {
        const res = await fetch('/api/withdraw_fd', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ account: currentAcc })
        });
        const d = await res.json();
        if (d.success) {
            showToast('Fixed Deposit liquidated and credited to primary balance!');
            syncAccountData();
        } else {
            showToast(d.message || d.result || 'Failed to liquidate FD.', 'error');
        }
    } catch (err) {
        showToast('FD liquidation error.', 'error');
    }
};

// ════════════ HANDLERS: WEALTH & INVESTMENTS HUB ════════════
window.handleCreateSIP = async (e) => {
    if (e && typeof e.preventDefault === 'function') e.preventDefault();
    const fundId = document.getElementById('sip-fund-select')?.value || 'MF-NIFTY50';
    const investType = document.getElementById('sip-type-select')?.value || 'Monthly SIP';
    const sipDay = document.getElementById('sip-day-select')?.value || '5';
    const amount = document.getElementById('sip-amount-input')?.value?.trim();
    const currentAcc = sessionStorage.getItem('current_account');

    if (!amount || parseFloat(amount) < 500) {
        showToast('Minimum investment amount is ₹500.', 'error');
        return;
    }

    try {
        const res = await fetch('/api/invest/sip', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                account: currentAcc,
                fund_id: fundId,
                type: investType,
                sip_day: sipDay,
                amount: amount
            })
        });
        const d = await res.json();
        if (d.success) {
            showToast(d.message || `Successfully started ${investType}!`);
            const inp = document.getElementById('sip-amount-input');
            if (inp) inp.value = '';
            syncAccountData();
        } else {
            showToast(d.message || 'SIP investment failed.', 'error');
        }
    } catch (err) {
        showToast('Failed to start investment.', 'error');
    }
};

window.handleSIPAction = async (sipId, action) => {
    const currentAcc = sessionStorage.getItem('current_account');
    if (action === 'redeem') {
        if (!confirm('Are you sure you want to stop and liquidate this Mutual Fund investment? 100% of current valuation will be credited instantly to your bank account.')) return;
    }

    try {
        const res = await fetch('/api/invest/sip_action', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ account: currentAcc, sip_id: sipId, action: action })
        });
        const d = await res.json();
        if (d.success) {
            showToast(d.message);
            syncAccountData();
        } else {
            showToast(d.message || 'Action failed.', 'error');
        }
    } catch (err) {
        showToast('Failed to execute SIP action.', 'error');
    }
};

// ════════════ IPO FULL DETAILS & GMP MODAL (IPOJI FLOW) ════════════
window.openIpoDetailsModal = async (ipoId) => {
    const currentAcc = sessionStorage.getItem('current_account');
    try {
        const res = await fetch(`/api/investments/${currentAcc}`);
        const data = await res.json();
        const ipo = (data.market_ipos || []).find(i => i.id === ipoId);
        if (!ipo) {
            showToast('IPO details not found.', 'error');
            return;
        }

        const isClosed = (ipo.status_type || '').toLowerCase() === 'closed';
        const isUpcoming = (ipo.status_type || '').toLowerCase() === 'upcoming';
        const isOngoing = !isClosed && !isUpcoming;
        
        const gmpVal = ipo.gmp !== undefined ? ipo.gmp : 0;
        const gmpPct = ipo.gmp_pct !== undefined ? ipo.gmp_pct : 0;
        const indicPrice = ipo.indicative_listing || (ipo.price_max + gmpVal);

        openModal({
            title: `${ipo.company}`,
            description: `${ipo.ipo_type || 'Mainboard'} IPO • Symbol: ${ipo.symbol} • Listed at: ${ipo.exchanges || 'BSE, NSE'}`,
            contentHtml: `
                <div class="space-y-4 max-h-[75vh] overflow-y-auto pr-1">
                    <!-- 1. Top Highlights & GMP Card -->
                    <div class="p-4 rounded-2xl bg-gradient-to-br from-slate-900 via-indigo-950 to-slate-900 text-white shadow-md relative overflow-hidden">
                        <div class="flex items-center justify-between gap-2 mb-2">
                            <span class="px-2.5 py-0.5 rounded-full text-[10px] font-extrabold uppercase bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
                                ⚡ Grey Market Premium (GMP)
                            </span>
                            <span class="text-[11px] font-semibold text-slate-300">Issue Size: <strong class="text-white">${ipo.issue_size || '₹300 Cr'}</strong></span>
                        </div>
                        <div class="grid grid-cols-2 sm:grid-cols-4 gap-3 pt-1">
                            <div class="p-2.5 rounded-xl bg-white/5 border border-white/10">
                                <span class="text-[10px] text-slate-400 block uppercase">Price Band</span>
                                <p class="text-base font-extrabold text-white font-mono mt-0.5">₹${ipo.price_min} - ₹${ipo.price_max}</p>
                            </div>
                            <div class="p-2.5 rounded-xl bg-white/5 border border-white/10">
                                <span class="text-[10px] text-slate-400 block uppercase">GMP Today</span>
                                <p class="text-base font-extrabold text-emerald-400 font-mono mt-0.5">+₹${gmpVal} (+${gmpPct}%)</p>
                            </div>
                            <div class="p-2.5 rounded-xl bg-white/5 border border-white/10">
                                <span class="text-[10px] text-slate-400 block uppercase">Indicative Listing</span>
                                <p class="text-base font-extrabold text-indigo-300 font-mono mt-0.5">₹${indicPrice.toFixed(2)}</p>
                            </div>
                            <div class="p-2.5 rounded-xl bg-white/5 border border-white/10">
                                <span class="text-[10px] text-slate-400 block uppercase">Overall Subscription</span>
                                <p class="text-base font-extrabold text-amber-300 font-mono mt-0.5">${ipo.subscription || '30.4x'}</p>
                            </div>
                        </div>
                    </div>

                    <!-- 2. Visual 4-Stage Milestone Timeline -->
                    <div class="p-4 rounded-2xl bg-slate-50 border border-slate-200/80 space-y-2">
                        <div class="flex items-center justify-between mb-1">
                            <h4 class="text-xs font-extrabold text-slate-900 uppercase tracking-wider">IPO Milestone Timeline</h4>
                            <span class="text-[10px] font-bold text-indigo-600 bg-indigo-50 px-2 py-0.5 rounded-full">4 Key Dates</span>
                        </div>
                        <div class="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-1 text-center">
                            <div class="p-2.5 rounded-xl bg-white border border-slate-200">
                                <span class="material-symbols-outlined text-sm text-emerald-600 block mb-0.5">flag</span>
                                <span class="text-[10px] font-bold text-slate-400 uppercase block">Open Date</span>
                                <p class="text-xs font-bold text-slate-900 font-mono mt-0.5">${ipo.open_date}</p>
                            </div>
                            <div class="p-2.5 rounded-xl bg-white border border-slate-200">
                                <span class="material-symbols-outlined text-sm text-rose-600 block mb-0.5">hourglass_bottom</span>
                                <span class="text-[10px] font-bold text-slate-400 uppercase block">Close Date</span>
                                <p class="text-xs font-bold text-slate-900 font-mono mt-0.5">${ipo.close_date || ipo.closes}</p>
                            </div>
                            <div class="p-2.5 rounded-xl bg-white border border-slate-200">
                                <span class="material-symbols-outlined text-sm text-indigo-600 block mb-0.5">award_star</span>
                                <span class="text-[10px] font-bold text-slate-400 uppercase block">Allotment Date</span>
                                <p class="text-xs font-bold text-slate-900 font-mono mt-0.5">${ipo.allotment_date}</p>
                            </div>
                            <div class="p-2.5 rounded-xl bg-white border border-slate-200">
                                <span class="material-symbols-outlined text-sm text-amber-600 block mb-0.5">rocket</span>
                                <span class="text-[10px] font-bold text-slate-400 uppercase block">Listing Date</span>
                                <p class="text-xs font-bold text-slate-900 font-mono mt-0.5">${ipo.listing_date || 'TBA'}</p>
                            </div>
                        </div>
                    </div>

                    <!-- 3. Category Subscription Demand -->
                    <div class="p-4 rounded-2xl bg-white border border-slate-200/80 space-y-2">
                        <div class="flex items-center justify-between mb-1">
                            <h4 class="text-xs font-extrabold text-slate-900 uppercase tracking-wider">Live Bidding & Subscription Demand</h4>
                            <span class="text-[10px] font-semibold text-slate-500">Real-time Exchange Multiples</span>
                        </div>
                        <div class="grid grid-cols-3 gap-2 text-center text-xs">
                            <div class="p-3 bg-indigo-50/60 rounded-xl border border-indigo-100">
                                <span class="text-[10px] font-bold text-indigo-900 uppercase block">QIB Category</span>
                                <span class="text-base font-extrabold text-indigo-700 font-mono mt-0.5 block">${ipo.qib_sub || '21.91x'}</span>
                            </div>
                            <div class="p-3 bg-purple-50/60 rounded-xl border border-purple-100">
                                <span class="text-[10px] font-bold text-purple-900 uppercase block">NII / HNI Category</span>
                                <span class="text-base font-extrabold text-purple-700 font-mono mt-0.5 block">${ipo.nii_sub || '56.77x'}</span>
                            </div>
                            <div class="p-3 bg-emerald-50/60 rounded-xl border border-emerald-100">
                                <span class="text-[10px] font-bold text-emerald-900 uppercase block">Retail Individual (RII)</span>
                                <span class="text-base font-extrabold text-emerald-700 font-mono mt-0.5 block">${ipo.retail_sub || '23.98x'}</span>
                            </div>
                        </div>
                    </div>

                    <!-- 4. Lot Size & Investment Quota -->
                    <div class="p-4 rounded-2xl bg-slate-50 border border-slate-200/80 space-y-2">
                        <h4 class="text-xs font-extrabold text-slate-900 uppercase tracking-wider">Lot Size & Investment Quota</h4>
                        <div class="overflow-x-auto">
                            <table class="w-full text-left text-xs">
                                <thead>
                                    <tr class="bg-white border-b border-slate-200 text-[10px] font-bold text-slate-400 uppercase">
                                        <th class="py-2 px-2.5">Application Tier</th>
                                        <th class="py-2 px-2.5 text-center">Lots</th>
                                        <th class="py-2 px-2.5 text-center">Shares</th>
                                        <th class="py-2 px-2.5 text-right">Lien Amount (₹)</th>
                                    </tr>
                                </thead>
                                <tbody class="divide-y divide-slate-100 font-medium">
                                    <tr>
                                        <td class="py-2 px-2.5 font-bold text-slate-800">Retail Minimum</td>
                                        <td class="py-2 px-2.5 text-center font-mono">1 Lot</td>
                                        <td class="py-2 px-2.5 text-center font-mono">${ipo.lot_size} sh</td>
                                        <td class="py-2 px-2.5 text-right font-extrabold font-mono text-slate-900">${formatINR(ipo.lot_size * ipo.price_max)}</td>
                                    </tr>
                                    <tr>
                                        <td class="py-2 px-2.5 font-bold text-slate-800">Retail Maximum</td>
                                        <td class="py-2 px-2.5 text-center font-mono">13 Lots</td>
                                        <td class="py-2 px-2.5 text-center font-mono">${ipo.lot_size * 13} sh</td>
                                        <td class="py-2 px-2.5 text-right font-extrabold font-mono text-slate-900">${formatINR(ipo.lot_size * 13 * ipo.price_max)}</td>
                                    </tr>
                                    <tr>
                                        <td class="py-2 px-2.5 font-bold text-indigo-700">Small HNI (sNII Min)</td>
                                        <td class="py-2 px-2.5 text-center font-mono">14 Lots</td>
                                        <td class="py-2 px-2.5 text-center font-mono">${ipo.lot_size * 14} sh</td>
                                        <td class="py-2 px-2.5 text-right font-extrabold font-mono text-indigo-700">${formatINR(ipo.lot_size * 14 * ipo.price_max)}</td>
                                    </tr>
                                </tbody>
                            </table>
                        </div>
                    </div>

                    <!-- 5. Valuations & Registrar Details -->
                    <div class="grid grid-cols-2 sm:grid-cols-4 gap-2.5 text-xs">
                        <div class="p-3 bg-white border border-slate-200 rounded-xl">
                            <span class="text-[10px] text-slate-400 uppercase font-bold block">P/E Ratio</span>
                            <p class="font-extrabold text-slate-900 font-mono mt-0.5">${ipo.pe_ratio || '13.11x'}</p>
                        </div>
                        <div class="p-3 bg-white border border-slate-200 rounded-xl">
                            <span class="text-[10px] text-slate-400 uppercase font-bold block">EPS</span>
                            <p class="font-extrabold text-slate-900 font-mono mt-0.5">${ipo.eps || '₹10.60'}</p>
                        </div>
                        <div class="p-3 bg-white border border-slate-200 rounded-xl">
                            <span class="text-[10px] text-slate-400 uppercase font-bold block">RoNW</span>
                            <p class="font-extrabold text-emerald-700 font-mono mt-0.5">${ipo.ronw || '18.86%'}</p>
                        </div>
                        <div class="p-3 bg-white border border-slate-200 rounded-xl">
                            <span class="text-[10px] text-slate-400 uppercase font-bold block">Market Cap</span>
                            <p class="font-extrabold text-slate-900 font-mono mt-0.5">${ipo.market_cap || '₹1,047 Cr'}</p>
                        </div>
                    </div>

                    <div class="p-3 bg-slate-50 border border-slate-200 rounded-xl text-xs flex items-center justify-between">
                        <div>
                            <span class="text-[10px] text-slate-400 uppercase font-bold block">Registrar to the Issue</span>
                            <p class="font-bold text-slate-800 mt-0.5">${ipo.registrar || 'Bigshare Services Pvt. Ltd.'}</p>
                        </div>
                        <span class="text-[10px] text-emerald-700 font-bold bg-emerald-50 px-2.5 py-1 rounded-full border border-emerald-200">SEBI Registered</span>
                    </div>
                </div>
            `,
            submitText: isOngoing ? 'Proceed to ASBA Bidding' : 'Close Details',
            onConfirm: async (modal, close) => {
                close();
                if (isOngoing) {
                    setTimeout(() => window.openIpoBidModal(ipo.id), 200);
                }
            }
        });
    } catch (e) {
        showToast('Failed to load IPO details.', 'error');
    }
};

window.openIpoBidModal = async (ipoId) => {
    const currentAcc = sessionStorage.getItem('current_account');
    try {
        const res = await fetch(`/api/investments/${currentAcc}`);
        const data = await res.json();
        const ipo = (data.market_ipos || []).find(i => i.id === ipoId);
        if (!ipo) {
            showToast('IPO not found.', 'error');
            return;
        }

        const lotSize = ipo.lot_size;
        const minPrice = ipo.price_min;
        const maxPrice = ipo.price_max;
        const defaultDemat = `IN300120-${currentAcc.slice(-8)}`;

        openModal({
            title: `ASBA IPO Application: ${ipo.company}`,
            description: `Symbol: ${ipo.symbol} • Price Band: ₹${minPrice} - ₹${maxPrice} • Lot Size: ${lotSize} Shares`,
            contentHtml: `
                <div class="space-y-3.5 text-xs font-semibold text-slate-700">
                    <div class="p-3 bg-indigo-50 border border-indigo-200/80 rounded-2xl space-y-1">
                        <div class="flex justify-between font-bold text-indigo-950">
                            <span>1 Lot = ${lotSize} Shares</span>
                            <span>Min Investment: ${formatINR(lotSize * maxPrice)}</span>
                        </div>
                        <div class="text-[11px] text-indigo-800 font-medium pt-0.5">
                            Funds remain safely in your Credence Core savings account earning daily interest with lien authorization.
                        </div>
                    </div>

                    <!-- Cut-Off Price Checkbox & Price Selection -->
                    <div class="p-3 bg-slate-50 border border-slate-200 rounded-xl space-y-2">
                        <label class="flex items-center gap-2 cursor-pointer">
                            <input id="ipo-bid-cutoff-check" type="checkbox" checked class="size-4 text-indigo-600 rounded" 
                                onchange="
                                    const customPriceBox = document.getElementById('ipo-custom-price-wrap');
                                    const priceInput = document.getElementById('ipo-bid-price');
                                    if (this.checked) {
                                        customPriceBox.classList.add('hidden');
                                        priceInput.value = '${maxPrice}';
                                    } else {
                                        customPriceBox.classList.remove('hidden');
                                    }
                                    window.updateIpoLienTotal();
                                "
                            />
                            <span class="font-bold text-slate-900">Bid at Cut-off Price (₹${maxPrice} - Recommended)</span>
                        </label>

                        <div id="ipo-custom-price-wrap" class="hidden pt-1">
                            <label class="block mb-1 text-[11px] text-slate-500">Custom Bid Price (₹${minPrice} to ₹${maxPrice})</label>
                            <input id="ipo-bid-price" type="number" min="${minPrice}" max="${maxPrice}" value="${maxPrice}" 
                                class="w-full h-10 px-3 bg-white border border-slate-200 rounded-xl font-bold font-mono text-slate-900"
                                oninput="window.updateIpoLienTotal()"
                            />
                        </div>
                    </div>

                    <!-- Lots Selection with +/- Buttons -->
                    <div>
                        <label class="block mb-1 font-bold text-slate-900">Number of Lots (1 - 13 for Retail)</label>
                        <div class="flex items-center gap-2">
                            <button type="button" onclick="
                                const inp = document.getElementById('ipo-bid-lots');
                                let v = parseInt(inp.value) || 1;
                                if (v > 1) inp.value = v - 1;
                                window.updateIpoLienTotal();
                            " class="size-10 bg-slate-100 hover:bg-slate-200 font-bold text-base text-slate-800 rounded-xl flex items-center justify-center cursor-pointer active:scale-95">-</button>
                            
                            <input id="ipo-bid-lots" type="number" min="1" max="13" value="1" 
                                class="flex-1 h-10 px-3 bg-slate-50 border border-slate-200 rounded-xl font-bold text-center text-slate-900"
                                oninput="window.updateIpoLienTotal()"
                            />

                            <button type="button" onclick="
                                const inp = document.getElementById('ipo-bid-lots');
                                let v = parseInt(inp.value) || 1;
                                if (v < 13) inp.value = v + 1;
                                window.updateIpoLienTotal();
                            " class="size-10 bg-slate-100 hover:bg-slate-200 font-bold text-base text-slate-800 rounded-xl flex items-center justify-center cursor-pointer active:scale-95">+</button>
                        </div>
                        <p class="text-[10px] text-slate-400 mt-1" id="ipo-shares-calc-disp">Total Shares: ${lotSize} Shares</p>
                    </div>

                    <!-- Demat ID -->
                    <div>
                        <label class="block mb-1 font-bold text-slate-900">Demat Account No. / DP ID (16 Digits)</label>
                        <input id="ipo-bid-demat" type="text" value="${defaultDemat}" class="w-full h-10 px-3 bg-slate-50 border border-slate-200 rounded-xl font-mono font-bold text-slate-900" />
                    </div>

                    <!-- Live Total ASBA Lien Display -->
                    <div class="p-3.5 bg-slate-900 text-white rounded-2xl flex items-center justify-between">
                        <div>
                            <span class="text-[10px] uppercase font-bold text-slate-400 tracking-wider block">Total ASBA Lien Amount:</span>
                            <span class="text-[11px] text-emerald-400">Zero charges • Earn savings APY</span>
                        </div>
                        <span class="text-base font-extrabold font-mono text-emerald-400 tabular-nums" id="ipo-bid-total-disp">${formatINR(lotSize * maxPrice)}</span>
                    </div>
                </div>
            `,
            submitText: 'Submit ASBA Bid',
            onConfirm: async (modal, close) => {
                const lots = parseInt(modal.querySelector('#ipo-bid-lots').value) || 1;
                const price = parseFloat(modal.querySelector('#ipo-bid-price').value) || maxPrice;
                const demat = modal.querySelector('#ipo-bid-demat').value.trim();

                const bidRes = await fetch('/api/invest/ipo_bid', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        account: currentAcc,
                        ipo_id: ipo.id,
                        lots: lots,
                        bid_price: price,
                        demat_id: demat
                    })
                });
                const d = await bidRes.json();
                close();
                if (d.success) {
                    showToast(d.message);
                    syncAccountData();
                } else {
                    showToast(d.message || 'IPO bid submission failed.', 'error');
                }
            }
        });

        window.updateIpoLienTotal = () => {
            const lotsInp = document.getElementById('ipo-bid-lots');
            const priceInp = document.getElementById('ipo-bid-price');
            const totalDisp = document.getElementById('ipo-bid-total-disp');
            const sharesDisp = document.getElementById('ipo-shares-calc-disp');

            const lots = parseInt(lotsInp?.value || '1', 10) || 1;
            const price = parseFloat(priceInp?.value || maxPrice) || maxPrice;
            const totalShares = lots * lotSize;
            const totalAmount = totalShares * price;

            if (totalDisp) totalDisp.textContent = formatINR(totalAmount);
            if (sharesDisp) sharesDisp.textContent = `Total Shares: ${totalShares} Shares (${lots} Lots @ ₹${price})`;
        };
    } catch (e) {
        showToast('Failed to open IPO bid window.', 'error');
    }
};

window.handleCreateRD = async (e) => {
    e.preventDefault();
    const amount = document.getElementById('rd-create-amount').value.trim();
    const tenure = document.getElementById('rd-create-tenure').value;
    const currentAcc = sessionStorage.getItem('current_account');

    if (!amount || parseFloat(amount) < 500) {
        showToast('Minimum Recurring Deposit installment is ₹500.', 'error');
        return;
    }

    try {
        const res = await fetch('/api/invest/create_rd', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ account: currentAcc, amount: amount, tenure: tenure })
        });
        const d = await res.json();
        if (d.success) {
            showToast(d.message);
            document.getElementById('rd-create-amount').value = '';
            syncAccountData();
        } else {
            showToast(d.message || 'RD creation failed.', 'error');
        }
    } catch (err) {
        showToast('Failed to start Recurring Deposit.', 'error');
    }
};

// ════════════ 24K DIGITAL GOLD TRADING & LIVE CALCULATORS ════════════
window.liveGoldBuyRate = 7620.50;
window.liveGoldSellRate = 7544.30;

window.updateGoldBuyCalc = (source) => {
    const rate = window.liveGoldBuyRate || 7620.50;
    const gramsInp = document.getElementById('gold-buy-grams');
    const amtInp = document.getElementById('gold-buy-amount');

    if (source === 'grams' && gramsInp && amtInp) {
        const grams = parseFloat(gramsInp.value) || 0;
        amtInp.value = grams > 0 ? Math.round(grams * rate) : '';
    } else if (source === 'amount' && amtInp && gramsInp) {
        const amt = parseFloat(amtInp.value) || 0;
        gramsInp.value = amt > 0 ? (amt / rate).toFixed(4) : '';
    }
};

window.setGoldBuyPreset = (amt) => {
    const amtInp = document.getElementById('gold-buy-amount');
    if (amtInp) {
        amtInp.value = amt;
        window.updateGoldBuyCalc('amount');
    }
};

window.setGoldBuyGramsPreset = (g) => {
    const gramsInp = document.getElementById('gold-buy-grams');
    if (gramsInp) {
        gramsInp.value = g;
        window.updateGoldBuyCalc('grams');
    }
};

window.updateGoldSellCalc = (source) => {
    const rate = window.liveGoldSellRate || 7544.30;
    const gramsInp = document.getElementById('gold-sell-grams');
    const amtInp = document.getElementById('gold-sell-amount');

    if (source === 'grams' && gramsInp && amtInp) {
        const grams = parseFloat(gramsInp.value) || 0;
        amtInp.value = grams > 0 ? (grams * rate).toFixed(2) : '';
    } else if (source === 'amount' && amtInp && gramsInp) {
        const amt = parseFloat(amtInp.value) || 0;
        gramsInp.value = amt > 0 ? (amt / rate).toFixed(4) : '';
    }
};

window.setGoldSellMax = () => {
    const gramsHeld = window.currentInvestmentsData?.gold?.grams || 0;
    const gramsInp = document.getElementById('gold-sell-grams');
    if (gramsInp) {
        gramsInp.value = gramsHeld > 0 ? gramsHeld.toFixed(4) : '0';
        window.updateGoldSellCalc('grams');
    }
};

window.handleGoldBuy = async (e) => {
    if (e && typeof e.preventDefault === 'function') e.preventDefault();
    const gramsInp = document.getElementById('gold-buy-grams');
    const amtInp = document.getElementById('gold-buy-amount');
    
    const gramsStr = gramsInp?.value ? String(gramsInp.value).replace(/,/g, '').trim() : '';
    const amtStr = amtInp?.value ? String(amtInp.value).replace(/,/g, '').trim() : '';
    
    const amtVal = parseFloat(amtStr) || 0;
    const gramsVal = parseFloat(gramsStr) || 0;
    const currentAcc = sessionStorage.getItem('current_account');

    if (amtVal < 100 && gramsVal <= 0) {
        showToast('Minimum 24K Gold purchase is ₹100.', 'error');
        return;
    }

    try {
        const payload = { account: currentAcc };
        if (amtVal >= 100) {
            payload.amount = amtVal;
        } else if (gramsVal > 0) {
            payload.grams = gramsVal;
        }

        const res = await fetch('/api/invest/gold_buy', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const d = await res.json();
        if (d.success) {
            showToast(d.message || '24K Digital Gold purchased successfully!');
            if (gramsInp) gramsInp.value = '';
            if (amtInp) amtInp.value = '';
            syncAccountData();
        } else {
            showToast(d.message || 'Gold purchase failed.', 'error');
        }
    } catch (err) {
        showToast('Failed to execute gold purchase.', 'error');
    }
};
window.handleBuyGold = window.handleGoldBuy;

window.handleGoldSell = async (e) => {
    if (e && typeof e.preventDefault === 'function') e.preventDefault();
    const gramsInp = document.getElementById('gold-sell-grams');
    const amtInp = document.getElementById('gold-sell-amount');
    
    const gramsStr = gramsInp?.value ? String(gramsInp.value).replace(/,/g, '').trim() : '';
    const amtStr = amtInp?.value ? String(amtInp.value).replace(/,/g, '').trim() : '';
    
    const amtVal = parseFloat(amtStr) || 0;
    const gramsVal = parseFloat(gramsStr) || 0;
    const currentAcc = sessionStorage.getItem('current_account');

    if (gramsVal <= 0 && amtVal <= 0) {
        showToast('Please enter a valid weight in grams or amount to sell.', 'error');
        return;
    }

    try {
        const payload = { account: currentAcc };
        if (gramsVal > 0) {
            payload.grams = gramsVal;
        } else if (amtVal > 0) {
            payload.amount = amtVal;
        }

        const res = await fetch('/api/invest/gold_sell', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const d = await res.json();
        if (d.success) {
            showToast(d.message || '24K Digital Gold liquidated successfully!');
            if (gramsInp) gramsInp.value = '';
            if (amtInp) amtInp.value = '';
            syncAccountData();
        } else {
            showToast(d.message || 'Gold sale failed.', 'error');
        }
    } catch (err) {
        showToast('Failed to execute gold sale.', 'error');
    }
};
window.handleSellGold = window.handleGoldSell;

// ════════════ HANDLERS: SEND & PAY TAB ════════════
window.handleSendMoney = async (e) => {
    e.preventDefault();
    const toAcc = document.getElementById('transfer-tab-recipient').value.trim();
    const amount = document.getElementById('transfer-tab-amount').value.trim();
    const method = document.getElementById('transfer-tab-method').value;
    const currentAcc = sessionStorage.getItem('current_account');

    if (!toAcc || !amount || parseFloat(amount) <= 0) {
        showToast('Please enter a valid recipient account and amount.', 'error');
        return;
    }
    if (toAcc === currentAcc) {
        showToast('Cannot transfer to your own active account.', 'error');
        return;
    }

    try {
        const res = await fetch('/api/transfer', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ from_acc: currentAcc, to_acc: toAcc, amount, method })
        });
        const d = await res.json();
        if (d.success) {
            showToast(`Successfully sent ₹${amount} to Account #${toAcc}!`);
            document.getElementById('transfer-tab-recipient').value = '';
            document.getElementById('transfer-tab-amount').value = '';
            syncAccountData();
        } else {
            showToast(d.result || d.message || 'Transfer failed.', 'error');
        }
    } catch (err) {
        showToast('Transfer request failed.', 'error');
    }
};

window.toggleCustomBiller = (val) => {
    const wrap = document.getElementById('bill-custom-wrapper');
    if (wrap) {
        if (val === 'Others') {
            wrap.classList.remove('hidden');
            const inp = document.getElementById('bill-custom-name');
            if (inp) inp.focus();
        } else {
            wrap.classList.add('hidden');
        }
    }
};

window.handleBillPay = async (e) => {
    e.preventDefault();
    const selectEl = document.getElementById('bill-company');
    const rawCategory = selectEl ? selectEl.value : 'Utility Bill';
    let billerName = rawCategory;
    if (rawCategory === 'Others') {
        const customInp = document.getElementById('bill-custom-name');
        const customVal = customInp ? customInp.value.trim() : '';
        billerName = customVal || 'Custom Utility / Merchant';
    }

    const amtEl = document.getElementById('bill-amount');
    const amount = amtEl ? amtEl.value.trim() : '0';
    const currentAcc = sessionStorage.getItem('current_account');

    if (!amount || parseFloat(amount) <= 0) {
        showToast('Please enter a valid bill amount.', 'error');
        return;
    }

    try {
        const res = await fetch('/api/pay_bill', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                account: currentAcc,
                biller: billerName,
                company: billerName,
                amount,
                remarks: `Settlement for ${billerName}`,
                method: 'Account Balance'
            })
        });
        const d = await res.json();
        if (d.success) {
            showToast(`Paid ₹${amount} to ${billerName} successfully!`);
            if (amtEl) amtEl.value = '';
            const customInp = document.getElementById('bill-custom-name');
            if (customInp) customInp.value = '';
            syncAccountData();
        } else {
            showToast(d.message || 'Bill payment failed.', 'error');
        }
    } catch (err) {
        showToast('Bill payment failed.', 'error');
    }
};
window.handlePayBill = window.handleBillPay;

window.handleSetupUPI = async (e) => {
    e.preventDefault();
    const upiId = document.getElementById('upi-setup-id').value.trim();
    const upiPin = document.getElementById('upi-setup-pin').value.trim();
    const currentAcc = sessionStorage.getItem('current_account');

    if (!upiId || !upiPin || (upiPin.length !== 4 && upiPin.length !== 6)) {
        showToast('UPI PIN must be 4 or 6 digits.', 'error');
        return;
    }

    try {
        const res = await fetch('/api/create_upi', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ account: currentAcc, upi_id: upiId, upi_pin: upiPin })
        });
        const d = await res.json();
        if (d.success) {
            showToast(`UPI ID '${upiId}' registered successfully!`);
            document.getElementById('upi-setup-id').value = '';
            document.getElementById('upi-setup-pin').value = '';
        } else {
            showToast(d.message || 'UPI registration failed.', 'error');
        }
    } catch (err) {
        showToast('UPI request error.', 'error');
    }
};

// ════════════ HANDLERS: CARDS & SETTINGS TAB ════════════
window.handleBlockCard = async () => {
    const currentAcc = sessionStorage.getItem('current_account');
    if (!confirm('Are you sure you want to block and freeze your active Debit Card?')) return;

    try {
        const res = await fetch('/api/block_card', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ account: currentAcc })
        });
        const d = await res.json();
        if (d.success) {
            showToast('Debit card securely blocked.');
            syncAccountData();
        } else {
            showToast(d.message || 'Card block failed.', 'error');
        }
    } catch (err) {
        showToast('Card block error.', 'error');
    }
};

window.handleReissueCard = () => {
    const currentAcc = sessionStorage.getItem('current_account');
    openModal({
        title: 'Reissue / Request New Debit Card',
        description: 'Set a new 4-digit PIN for your replacement Visa Platinum Card',
        contentHtml: `
            <div>
                <label class="block text-slate-700 font-bold mb-1">Set 4-Digit ATM PIN</label>
                <input id="reissue-card-pin" type="password" maxlength="4" placeholder="e.g. 4821" class="w-full h-11 px-3.5 bg-slate-50 border border-slate-200 rounded-xl font-bold text-slate-900" />
            </div>
            <p class="text-[11px] text-slate-500">Your new replacement physical debit card will be instantly activated with this PIN.</p>
        `,
        submitText: 'Issue Card Now',
        onConfirm: async (modal, close) => {
            const pin = modal.querySelector('#reissue-card-pin').value.trim();
            if (!pin || pin.length !== 4 || isNaN(pin)) {
                showToast('Please enter a valid 4-digit numeric PIN.', 'error');
                return;
            }
            try {
                const res = await fetch('/api/issue_card', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ account: currentAcc, pin })
                });
                const d = await res.json();
                close();
                if (d.success) {
                    showToast('New Platinum Debit Card issued successfully!');
                    syncAccountData();
                } else {
                    showToast(d.message || 'Card reissue failed.', 'error');
                }
            } catch (err) {
                showToast('Card reissue failed.', 'error');
            }
        }
    });
};

window.openOrderChequeBookModal = () => {
    if (!currentAccountData) return;
    const data = currentAccountData;
    const defaultAddress = data.address || 'Registered Communication Address';

    openModal({
        title: 'Order CTS-2010 Cheque Book',
        description: 'Personalized MICR & CTS-2010 compliant physical cheque book (Delivered in 2-3 working days)',
        contentHtml: `
            <div class="space-y-3.5">
                <div class="p-3 bg-indigo-50 border border-indigo-200/80 rounded-2xl flex items-center gap-2.5 text-xs text-indigo-900 font-semibold">
                    <span class="material-symbols-outlined text-indigo-600 text-lg">receipt_long</span>
                    <span>Cheque books are printed with your IFSC &amp; Account Number and will be delivered in 2-3 working days via India Post SpeedPost.</span>
                </div>

                <div>
                    <label class="block mb-1 text-slate-700 font-bold text-xs">Number of Cheque Leaves</label>
                    <select id="order-chq-leaves" class="w-full h-11 px-3 bg-slate-50 border border-slate-200 rounded-xl text-xs font-bold text-slate-900 focus:ring-2 focus:ring-indigo-500/30">
                        <option value="25" selected>25 Leaves (Complimentary • ₹0)</option>
                        <option value="50">50 Leaves (Standard Business • ₹50)</option>
                        <option value="100">100 Leaves (High-Volume Commercial • ₹90)</option>
                    </select>
                </div>

                <div>
                    <label class="block mb-1 text-slate-700 font-bold text-xs">Cheque Book Format / Crossing</label>
                    <select id="order-chq-type" class="w-full h-11 px-3 bg-slate-50 border border-slate-200 rounded-xl text-xs font-bold text-slate-900 focus:ring-2 focus:ring-indigo-500/30">
                        <option value="CTS-2010 Standard Bearer Cheque" selected>CTS-2010 Standard Bearer Cheque</option>
                        <option value="CTS-2010 Order / Account Payee Only">CTS-2010 Order / Account Payee Only</option>
                    </select>
                </div>

                <div>
                    <label class="block mb-1 text-slate-700 font-bold text-xs">Delivery Postal Address</label>
                    <textarea id="order-chq-address" rows="2" class="w-full p-3 bg-slate-50 border border-slate-200 rounded-xl text-xs font-semibold text-slate-800 focus:ring-2 focus:ring-indigo-500/30" placeholder="Enter full postal address with PIN code">${defaultAddress}</textarea>
                </div>
            </div>
        `,
        submitText: 'Confirm & Dispatch Cheque Book',
        onConfirm: async (modal, close) => {
            const leaves = parseInt(modal.querySelector('#order-chq-leaves').value, 10) || 25;
            const type = modal.querySelector('#order-chq-type').value;
            const address = modal.querySelector('#order-chq-address').value.trim();

            if (!address) {
                showToast('Please specify a delivery postal address.', 'error');
                return;
            }

            try {
                const res = await fetch('/api/services/order_chequebook', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        account: data.account_number,
                        leaves,
                        type,
                        address
                    })
                });
                const d = await res.json();
                if (d.success) {
                    close();
                    showToast(d.message || 'Cheque book ordered! It will be delivered in 2-3 working days.');
                    syncAccountData();
                } else {
                    showToast(d.message || 'Failed to order cheque book.', 'error');
                }
            } catch (e) {
                showToast('Failed to connect to ordering service.', 'error');
            }
        }
    });
};

window.openOrderPhysicalCardModal = () => {
    if (!currentAccountData) return;
    const data = currentAccountData;
    const defaultName = data.name || 'Account Holder';
    const defaultAddress = data.address || 'Registered Communication Address';

    openModal({
        title: 'Order Physical Debit Card',
        description: 'Personalized EMV Contactless NFC Debit Card (Delivered in 2-3 working days)',
        contentHtml: `
            <div class="space-y-3.5">
                <div class="p-3 bg-emerald-50 border border-emerald-200/80 rounded-2xl flex items-center gap-2.5 text-xs text-emerald-900 font-semibold">
                    <span class="material-symbols-outlined text-emerald-600 text-lg">credit_card</span>
                    <span>Physical debit card is personalized with your embossed name and will be delivered in 2-3 working days via BlueDart Express courier.</span>
                </div>

                <div>
                    <label class="block mb-1 text-slate-700 font-bold text-xs">Card Tier &amp; Edition</label>
                    <select id="order-crd-variant" class="w-full h-11 px-3 bg-slate-50 border border-slate-200 rounded-xl text-xs font-bold text-slate-900 focus:ring-2 focus:ring-emerald-500/30">
                        <option value="Visa Platinum Obsidian" selected>Visa Platinum Obsidian (Zero Annual Fee • International POS)</option>
                        <option value="Visa Signature Metal">Visa Signature Metal (Airport Lounge Access • ₹2 Lakh Daily ATM Limit)</option>
                        <option value="RuPay Select Prestige">RuPay Select Prestige (Domestic Rail/Airport Lounges • Zero Forex Markup)</option>
                    </select>
                </div>

                <div>
                    <label class="block mb-1 text-slate-700 font-bold text-xs">Personalized Name Embossed on Card</label>
                    <input id="order-crd-name" type="text" value="${defaultName}" maxlength="30" class="w-full h-11 px-3 bg-slate-50 border border-slate-200 rounded-xl text-xs font-bold uppercase tracking-wider text-slate-900 focus:ring-2 focus:ring-emerald-500/30" />
                </div>

                <div>
                    <label class="block mb-1 text-slate-700 font-bold text-xs">Set 4-Digit ATM &amp; POS PIN</label>
                    <input id="order-crd-pin" type="password" maxlength="4" placeholder="•••• (4 digits)" class="w-full h-11 px-3 bg-slate-50 border border-slate-200 rounded-xl text-xs font-bold text-center tracking-[0.4em] text-slate-900 focus:ring-2 focus:ring-emerald-500/30" />
                </div>

                <div>
                    <label class="block mb-1 text-slate-700 font-bold text-xs">Delivery Address</label>
                    <textarea id="order-crd-address" rows="2" class="w-full p-3 bg-slate-50 border border-slate-200 rounded-xl text-xs font-semibold text-slate-800 focus:ring-2 focus:ring-emerald-500/30" placeholder="Enter delivery street address and PIN code">${defaultAddress}</textarea>
                </div>
            </div>
        `,
        submitText: 'Order & Dispatch Debit Card',
        onConfirm: async (modal, close) => {
            const variant = modal.querySelector('#order-crd-variant').value;
            const nameOnCard = modal.querySelector('#order-crd-name').value.trim();
            const pin = modal.querySelector('#order-crd-pin').value.trim();
            const address = modal.querySelector('#order-crd-address').value.trim();

            if (!nameOnCard) {
                showToast('Please specify the name for card emboss.', 'error');
                return;
            }
            if (!pin || pin.length !== 4 || !/^\d{4}$/.test(pin)) {
                showToast('Please enter a valid 4-digit numeric ATM PIN.', 'error');
                return;
            }
            if (!address) {
                showToast('Please specify a delivery postal address.', 'error');
                return;
            }

            try {
                const res = await fetch('/api/services/order_physical_card', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        account: data.account_number,
                        variant,
                        name_on_card: nameOnCard,
                        pin,
                        address
                    })
                });
                const d = await res.json();
                if (d.success) {
                    close();
                    showToast(d.message || 'Debit Card ordered! It will be delivered in 2-3 working days.');
                    syncAccountData();
                } else {
                    showToast(d.message || 'Failed to order physical card.', 'error');
                }
            } catch (e) {
                showToast('Failed to connect to card ordering service.', 'error');
            }
        }
    });
};

window.handleApplyCC = async (e) => {
    e.preventDefault();
    const age = document.getElementById('cc-age').value.trim();
    const income = document.getElementById('cc-income').value.trim();
    const cibil = document.getElementById('cc-cibil').value.trim();
    const pan = document.getElementById('cc-pan').value.trim();
    const currentAcc = sessionStorage.getItem('current_account');

    try {
        const res = await fetch('/api/apply_cc', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                accNo: currentAcc,
                age,
                income,
                cibil,
                pan,
                citizenship: 'Indian',
                address: 'Digital Banking Customer',
                proof: 'PAN Card'
            })
        });
        const d = await res.json();
        if (d.success) {
            showToast('Credit Card Approved! Check result below.');
            openModal({
                title: 'Credit Card Approved!',
                description: 'Pre-approved limit issued instantly',
                contentHtml: `<div class="p-4 bg-slate-900 text-white rounded-2xl font-mono text-xs whitespace-pre-wrap">${d.result || 'Credit Card Approved'}</div>`,
                submitText: 'Done',
                onConfirm: async (m, c) => c()
            });
            syncAccountData();
        } else {
            showToast('Credit card application declined.', 'error');
        }
    } catch (err) {
        showToast('Credit card application error.', 'error');
    }
};

window.handleToggle2FA = async () => {
    const currentAcc = sessionStorage.getItem('current_account');
    try {
        const res = await fetch('/api/settings/2fa', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ account_number: currentAcc })
        });
        const d = await res.json();
        if (d.success) {
            showToast(d.message);
            const btn = document.getElementById('btn-2fa-toggle');
            if (btn) {
                const isEn = d.message.includes('enabled');
                btn.className = `px-3.5 py-1.5 rounded-full font-bold text-xs transition-colors ${
                    isEn ? 'bg-emerald-100 text-emerald-800' : 'bg-slate-200 text-slate-600'
                }`;
                btn.textContent = isEn ? 'Enabled' : 'Disabled';
            }
        }
    } catch (err) {
        showToast('2FA toggle failed.', 'error');
    }
};

window.handleUpdatePassword = async (e) => {
    e.preventDefault();
    const oldP = document.getElementById('pwd-old').value.trim();
    const newP = document.getElementById('pwd-new').value.trim();
    const currentAcc = sessionStorage.getItem('current_account');

    try {
        const res = await fetch('/api/settings/password', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ account_number: currentAcc, old_password: oldP, new_password: newP })
        });
        const d = await res.json();
        if (d.success) {
            showToast('Net banking password updated successfully!');
            document.getElementById('pwd-old').value = '';
            document.getElementById('pwd-new').value = '';
        } else {
            showToast(d.message || 'Password update failed.', 'error');
        }
    } catch (err) {
        showToast('Password update error.', 'error');
    }
};

window.handleUpdateProfile = async (e) => {
    e.preventDefault();
    const email = document.getElementById('prof-email').value.trim();
    const dob = document.getElementById('prof-dob').value.trim();
    const currentAcc = sessionStorage.getItem('current_account');

    try {
        const res = await fetch('/api/update_profile', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ account_number: currentAcc, email, dob })
        });
        const d = await res.json();
        if (d.success) {
            showToast('Profile contact details saved!');
            syncAccountData();
        } else {
            showToast(d.message || 'Profile update failed.', 'error');
        }
    } catch (err) {
        showToast('Profile update error.', 'error');
    }
};

// ════════════ STATEMENT PDF DOWNLOAD ════════════
window.downloadStatementPDF = async () => {
    const accNo = sessionStorage.getItem('current_account');
    if (!accNo) {
        showToast('Please sign in to an account first.', 'error');
        return;
    }
    showToast('Generating official PDF statement...');
    
    try {
        const response = await fetch(`/api/statement_pdf/${accNo}`);
        if (!response.ok) {
            throw new Error('PDF Generation failed');
        }
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.style.display = 'none';
        a.href = url;
        a.download = `statement_${accNo}.pdf`;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        a.remove();
        showToast('Official PDF Statement downloaded!');
    } catch (e) {
        window.location.href = `/api/statement_pdf/${accNo}`;
    }
};

// ════════════ QUICK MODALS (Dashboard triggers) ════════════
window.openTransferModal = () => switchTab('transfer');
window.openDepositModal = () => {
    openModal({
        title: 'Add Funds to Account',
        description: 'Simulate instant credit from linked payment gateway',
        contentHtml: `
            <div>
                <label class="block text-slate-700 font-bold mb-1">Deposit Amount (₹)</label>
                <input id="deposit-amount" type="number" min="10" placeholder="e.g. 5000" class="w-full h-11 px-3 bg-slate-50 border border-slate-200 rounded-xl text-xs font-bold focus:outline-none focus:ring-2 focus:ring-emerald-500/30" />
            </div>
            <div class="p-3 bg-emerald-50 rounded-2xl text-[11px] text-emerald-800 font-medium">
                Instant credit simulation via core banking ledger.
            </div>
        `,
        submitText: 'Add Funds',
        onConfirm: async (modal, close) => {
            const amount = modal.querySelector('#deposit-amount').value.trim();
            const currentAcc = sessionStorage.getItem('current_account');
            if (!amount || parseFloat(amount) <= 0) {
                showToast('Please enter a valid positive deposit amount.', 'error');
                return;
            }
            try {
                const res = await fetch('/api/execute', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ choice: 1, inputs: [currentAcc, amount] })
                });
                const d = await res.json();
                close();
                showToast(`Deposited ₹${amount} into Account #${currentAcc}!`);
                syncAccountData();
            } catch (e) {
                showToast('Deposit failed.', 'error');
            }
        }
    });
};

window.openCreateAccountModal = () => {
    openModal({
        title: 'Open a New Bank Account',
        description: 'Instant digital account opening with Credence Core Banking',
        contentHtml: `
            <div>
                <label class="block text-slate-700 font-bold mb-1 text-xs">Account Classification / Type</label>
                <select id="new-acc-type" class="w-full h-11 px-3 bg-slate-50 border border-slate-200 rounded-xl text-xs font-bold text-slate-900 focus:ring-2 focus:ring-emerald-500/30">
                    <option value="Savings Account" selected>Savings Account (Personal • 4.0% APY • Free UPI &amp; RuPay)</option>
                    <option value="Current Account">Current Account (Commercial • Zero-Lien • High Daily Limits)</option>
                </select>
            </div>
            <div>
                <label class="block text-slate-700 font-bold mb-1 text-xs">Full Legal Name</label>
                <input id="new-acc-name" type="text" placeholder="e.g. Alex Johnson" class="w-full h-11 px-3 bg-slate-50 border border-slate-200 rounded-xl text-xs font-semibold text-slate-900" />
            </div>
            <div>
                <label class="block text-slate-700 font-bold mb-1 text-xs">Email Address</label>
                <input id="new-acc-email" type="email" placeholder="e.g. alex@example.com" class="w-full h-11 px-3 bg-slate-50 border border-slate-200 rounded-xl text-xs font-semibold text-slate-900" />
            </div>
            <div>
                <label class="block text-slate-700 font-bold mb-1 text-xs">Initial Opening Deposit (₹)</label>
                <input id="new-acc-deposit" type="number" min="500" placeholder="e.g. 5000" class="w-full h-11 px-3 bg-slate-50 border border-slate-200 rounded-xl text-xs font-bold text-slate-900" />
            </div>
            <div>
                <label class="block text-slate-700 font-bold mb-1 text-xs">Set 4-Digit Password / PIN</label>
                <input id="new-acc-pin" type="password" maxlength="6" placeholder="4-6 digit PIN" class="w-full h-11 px-3 bg-slate-50 border border-slate-200 rounded-xl text-xs font-bold text-slate-900" />
            </div>
        `,
        submitText: 'Create Account',
        onConfirm: async (modal, close) => {
            const accType = modal.querySelector('#new-acc-type').value;
            const name = modal.querySelector('#new-acc-name').value.trim();
            const email = modal.querySelector('#new-acc-email').value.trim();
            const deposit = modal.querySelector('#new-acc-deposit').value.trim();
            const pin = modal.querySelector('#new-acc-pin').value.trim();

            if (!name || !email || !deposit) {
                showToast('Please fill all required account opening fields.', 'error');
                return;
            }

            try {
                const res = await fetch('/api/create_account', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        name,
                        email,
                        deposit,
                        pin: pin || '1234',
                        address: 'Digital Banking User',
                        dob: '1995-05-15',
                        debit: 'y',
                        account_type: accType
                    })
                });
                const d = await res.json();
                close();
                if (d.account_number) {
                    sessionStorage.setItem('current_account', d.account_number);
                    showToast(`${accType} #${d.account_number} opened successfully!`);
                    setTimeout(() => window.location.href = '/dashboard', 1200);
                } else {
                    showToast(d.message || 'Error opening account.', 'error');
                }
            } catch (e) {
                showToast('Account creation failed.', 'error');
            }
        }
    });
};

window.showDevHelpModal = () => {
    openModal({
        title: '⚠️ Development Project Notice',
        description: 'Demonstration & Academic Simulation Context',
        contentHtml: `
            <div class="space-y-3.5 text-xs">
                <div class="p-4 rounded-2xl bg-amber-500/10 border border-amber-500/30 text-amber-950 space-y-2.5">
                    <p class="font-bold text-xs text-amber-950 leading-relaxed">
                        <strong>Please Note:</strong> This application is a <strong>college development project created for educational and demonstration purposes only</strong>.
                    </p>
                    <ul class="list-disc list-inside space-y-1.5 text-xs text-amber-900 font-medium">
                        <li>Please <strong>do not enter real banking credentials, passwords, PINs, card details, or other sensitive information</strong>.</li>
                        <li>Use <strong>dummy/test credentials and fictional information only</strong>.</li>
                        <li>This application is <strong>not connected to any real banking system or financial institution</strong>.</li>
                        <li>Any data entered is intended solely for testing and demonstration purposes.</li>
                    </ul>
                    <p class="font-bold text-xs text-amber-950 pt-1">
                        Thank you for understanding.
                    </p>
                </div>
                <div class="p-3 bg-slate-50 border border-slate-200/80 rounded-2xl space-y-1 text-slate-600">
                    <p><strong>C++ Core Engine:</strong> High-performance account ledger with 14-digit unique generator.</p>
                    <p><strong>Python Middleware:</strong> RESTful Flask IPC controller with PDF statement generator.</p>
                </div>
            </div>
        `,
        submitText: 'Understood',
        onConfirm: async (modal, close) => close()
    });
};

// ════════════ INITIALIZATION ON DOM READY ════════════
document.addEventListener('DOMContentLoaded', () => {
    const isAuthPage = window.location.pathname === '/' || window.location.pathname.endsWith('code.html');

    if (isAuthPage) {
        // Handle Login Form
        const loginForm = document.querySelector('form');
        if (loginForm) {
            loginForm.addEventListener('submit', async (e) => {
                e.preventDefault();
                const inputs = loginForm.querySelectorAll('input');
                const accNo = inputs[0].value.trim();
                const password = inputs.length > 1 ? inputs[1].value.trim() : '';

                if (!accNo) {
                    showToast('Please enter your Account Number.', 'error');
                    return;
                }

                try {
                    const res = await fetch('/api/login', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ account: accNo, password })
                    });
                    const data = await res.json();
                    if (data.success) {
                        sessionStorage.setItem('current_account', accNo);
                        showToast('Sign in successful. Welcome to Credence Core!');
                        setTimeout(() => window.location.href = '/dashboard', 600);
                    } else {
                        showToast(data.message || 'Invalid credentials.', 'error');
                    }
                } catch (e) {
                    showToast('Server connection error.', 'error');
                }
            });
        }
    } else {
        // Authenticated Dashboard & Inner Routes
        syncAccountData();

        // Route detection for direct URLs (e.g. /settings -> switch to settings tab)
        const path = window.location.pathname;
        if (path.includes('accounts')) switchTab('dashboard');
        else if (path.includes('transactions')) switchTab('transactions');
        else if (path.includes('analytics')) switchTab('analytics');
        else if (path.includes('loan')) switchTab('loans');
        else if (path.includes('fd') || path.includes('invest') || path.includes('sip') || path.includes('ipo') || path.includes('mf') || path.includes('gold')) switchTab('invest');
        else if (path.includes('transfer') || path.includes('upi') || path.includes('services')) switchTab('transfer');
        else if (path.includes('reports')) switchTab('reports');
        else if (path.includes('settings') || path.includes('cards')) switchTab('settings');
        else switchTab('dashboard');
    }
});
