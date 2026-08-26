/* ═══════════════════════════════════════════════════════════
   RABTA AI — Dashboard JavaScript
   API integration, CRUD, state management, modals
   ═══════════════════════════════════════════════════════════ */

const API_BASE = '';
let currentBusiness = null;
let currentPhone = null;
let editingProductIndex = null;
let deleteProductIndex = null;

/* ── Theme Toggle ── */
const themeToggle = document.getElementById('themeToggle');
const themeThumb = document.getElementById('themeThumb');
const html = document.documentElement;

function setTheme(theme) {
    html.setAttribute('data-theme', theme);
    themeThumb.textContent = theme === 'dark' ? '🌙' : '☀️';
    localStorage.setItem('rabta-theme', theme);
}

const savedTheme = localStorage.getItem('rabta-theme') || 'dark';
setTheme(savedTheme);

themeToggle.addEventListener('click', () => {
    const current = html.getAttribute('data-theme');
    setTheme(current === 'dark' ? 'light' : 'dark');
});

/* ── Login ── */
async function loginToDashboard() {
    const phone = document.getElementById('loginPhone').value.trim();
    if (!phone) {
        showToast('Please enter your business WhatsApp number.', 'error');
        return;
    }

    const cleanPhone = phone.replace(/[+\s\-]/g, '');

    try {
        const res = await fetch(`${API_BASE}/api/business/${cleanPhone}`);
        if (!res.ok) throw new Error('Business not found');
        const data = await res.json();

        currentBusiness = data;
        currentPhone = cleanPhone;
        localStorage.setItem('rabta-dash-phone', cleanPhone);

        showDashboard();
    } catch (err) {
        showToast('Business not found. Please onboard first.', 'error');
    }
}

// Auto-login if saved
const savedPhone = localStorage.getItem('rabta-dash-phone');
if (savedPhone) {
    document.getElementById('loginPhone').value = savedPhone;
    loginToDashboard();
}

function showDashboard() {
    document.getElementById('loginGate').style.display = 'none';
    document.getElementById('dashboardMain').style.display = 'grid';

    // Populate sidebar
    document.getElementById('sidebarBizName').textContent = currentBusiness.name || 'My Business';
    document.getElementById('sidebarBizPhone').textContent = '+' + currentPhone;

    // Populate overview stats
    const catalog = currentBusiness.raw_catalog || [];
    document.getElementById('statProductsVal').textContent = catalog.length;
    document.getElementById('statIndustryVal').textContent = currentBusiness.industry || '—';

    // Populate settings
    document.getElementById('settBizName').value = currentBusiness.name || '';
    document.getElementById('settBizPhone').value = '+' + currentPhone;
    document.getElementById('settOwnerPhone').value = currentBusiness.owner_phone || '';
    document.getElementById('settPolicies').value = currentBusiness.policies || '';

    // Render products
    renderProducts();
}

/* ── Tab Switching ── */
function switchTab(tabName, btnEl) {
    // Update panels
    document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
    const panel = document.getElementById('tab-' + tabName);
    if (panel) panel.classList.add('active');

    // Update sidebar
    document.querySelectorAll('.sidebar__item').forEach(i => i.classList.remove('active'));
    if (btnEl) btnEl.classList.add('active');

    // Close mobile sidebar
    document.getElementById('sidebar').classList.remove('open');
}

/* ── Mobile Sidebar ── */
function toggleMobileSidebar() {
    document.getElementById('sidebar').classList.toggle('open');
}

/* ══════════════════════════════════════════════
   Product CRUD
   ══════════════════════════════════════════════ */

function renderProducts() {
    const container = document.getElementById('productsContainer');
    const catalog = currentBusiness.raw_catalog || [];

    if (catalog.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <div class="empty-state__icon">📦</div>
                <div class="empty-state__title">No products yet</div>
                <div class="empty-state__desc">Add your first product to start selling with AI.</div>
                <button class="btn btn--primary" onclick="openProductModal()">+ Add First Product</button>
            </div>
        `;
        return;
    }

    let html = '<div class="products-grid">';
    catalog.forEach((item, index) => {
        html += `
            <div class="product-card" id="productCard${index}">
                <div class="product-card__category">${item.category || 'General'}</div>
                <div class="product-card__name">${escapeHtml(item.name)}</div>
                <div class="product-card__price">PKR ${Number(item.price).toLocaleString()}</div>
                ${item.details ? `<div class="text-muted" style="font-size:0.8125rem;">${escapeHtml(item.details)}</div>` : ''}
                <div class="product-card__actions">
                    <button class="btn btn--ghost btn--sm" onclick="openEditModal(${index})" title="Edit product">✏️ Edit</button>
                    <button class="btn btn--ghost btn--sm" onclick="openDeleteModal(${index})" style="color:var(--danger);" title="Delete product">🗑️ Delete</button>
                </div>
            </div>
        `;
    });
    html += '</div>';
    container.innerHTML = html;

    // Update stat
    document.getElementById('statProductsVal').textContent = catalog.length;
}

/* ── Product Modal ── */
function openProductModal() {
    editingProductIndex = null;
    document.getElementById('productModalTitle').textContent = 'Add Product';
    document.getElementById('modalSaveBtn').textContent = 'Add Product';
    document.getElementById('modalProdName').value = '';
    document.getElementById('modalProdPrice').value = '';
    document.getElementById('modalProdCategory').value = '';
    document.getElementById('modalProdDetails').value = '';
    document.getElementById('productModal').classList.add('active');
    setTimeout(() => document.getElementById('modalProdName').focus(), 200);
}

function openEditModal(index) {
    editingProductIndex = index;
    const item = currentBusiness.raw_catalog[index];
    document.getElementById('productModalTitle').textContent = 'Edit Product';
    document.getElementById('modalSaveBtn').textContent = 'Save Changes';
    document.getElementById('modalProdName').value = item.name || '';
    document.getElementById('modalProdPrice').value = item.price || '';
    document.getElementById('modalProdCategory').value = item.category || '';
    document.getElementById('modalProdDetails').value = item.details || '';
    document.getElementById('productModal').classList.add('active');
    setTimeout(() => document.getElementById('modalProdName').focus(), 200);
}

function closeProductModal() {
    document.getElementById('productModal').classList.remove('active');
    editingProductIndex = null;
}

async function saveProduct() {
    const name = document.getElementById('modalProdName').value.trim();
    const price = parseFloat(document.getElementById('modalProdPrice').value);
    const category = document.getElementById('modalProdCategory').value.trim() || 'General';
    const details = document.getElementById('modalProdDetails').value.trim();

    if (!name) { showToast('Product name is required.', 'error'); return; }
    if (!price || price <= 0) { showToast('Please enter a valid price.', 'error'); return; }

    const catalog = [...(currentBusiness.raw_catalog || [])];

    if (editingProductIndex !== null) {
        // Update existing
        catalog[editingProductIndex] = { name, price, category, details };
    } else {
        // Add new
        catalog.push({ name, price, category, details });
    }

    // Save to backend
    try {
        const res = await fetch(`${API_BASE}/api/business/${currentPhone}/catalog`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                items: catalog,
                policies: currentBusiness.policies || ''
            })
        });

        if (!res.ok) throw new Error('Failed to save product');

        currentBusiness.raw_catalog = catalog;
        renderProducts();
        closeProductModal();
        showToast(editingProductIndex !== null ? 'Product updated!' : 'Product added!', 'success');
    } catch (err) {
        showToast('Error saving product: ' + err.message, 'error');
    }
}

/* ── Delete Modal ── */
function openDeleteModal(index) {
    deleteProductIndex = index;
    const item = currentBusiness.raw_catalog[index];
    document.getElementById('deleteProductName').textContent = item.name;
    document.getElementById('deleteModal').classList.add('active');
}

function closeDeleteModal() {
    document.getElementById('deleteModal').classList.remove('active');
    deleteProductIndex = null;
}

async function confirmDelete() {
    if (deleteProductIndex === null) return;

    const catalog = [...(currentBusiness.raw_catalog || [])];
    catalog.splice(deleteProductIndex, 1);

    try {
        const res = await fetch(`${API_BASE}/api/business/${currentPhone}/catalog`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                items: catalog,
                policies: currentBusiness.policies || ''
            })
        });

        if (!res.ok) throw new Error('Failed to delete product');

        currentBusiness.raw_catalog = catalog;
        renderProducts();
        closeDeleteModal();
        showToast('Product deleted.', 'success');
    } catch (err) {
        showToast('Error deleting product: ' + err.message, 'error');
    }
}

/* ══════════════════════════════════════════════
   Settings
   ══════════════════════════════════════════════ */

async function saveSettings() {
    showToast('Settings saved! (Business info update coming in next release)', 'success');
}

async function savePolicies() {
    const policies = document.getElementById('settPolicies').value.trim();

    try {
        const catalog = currentBusiness.raw_catalog || [];
        const res = await fetch(`${API_BASE}/api/business/${currentPhone}/catalog`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ items: catalog, policies })
        });

        if (!res.ok) throw new Error('Failed to update policies');

        currentBusiness.policies = policies;
        showToast('Store policies updated! AI will use new policies.', 'success');
    } catch (err) {
        showToast('Error: ' + err.message, 'error');
    }
}

/* ══════════════════════════════════════════════
   AI Auto-Sense (Mock Implementation)
   ══════════════════════════════════════════════ */

let sensePlatform = '';
let senseResults = [];

function selectSensePlatform(platform) {
    sensePlatform = platform;
    const names = {
        instagram: 'Instagram',
        facebook: 'Facebook',
        tiktok: 'TikTok',
        whatsapp_catalog: 'WhatsApp Business'
    };
    document.getElementById('senseStep2Title').textContent = `Enter your ${names[platform]} profile URL`;

    const placeholders = {
        instagram: 'https://instagram.com/your_shop',
        facebook: 'https://facebook.com/your_page',
        tiktok: 'https://tiktok.com/@your_shop',
        whatsapp_catalog: 'https://wa.me/c/923001234567'
    };
    document.getElementById('senseUrl').placeholder = placeholders[platform] || '';

    goSenseStep(2);
}

function goSenseStep(step) {
    document.querySelectorAll('.sense-flow__step').forEach(s => s.classList.remove('active'));
    document.getElementById('senseStep' + step).classList.add('active');
}

async function startSenseScan() {
    const url = document.getElementById('senseUrl').value.trim();
    if (!url) {
        showToast('Please enter a profile URL.', 'error');
        return;
    }

    // Show scanning animation
    goSenseStep(3);

    // Mock AI scan — simulate delay & return mock products
    // In production, this would call POST /api/business/{phone}/auto-sense
    await new Promise(resolve => setTimeout(resolve, 3000));

    // Generate mock results based on industry
    const industry = currentBusiness.industry || 'General Retail';
    senseResults = generateMockSenseResults(industry);

    // Render results
    renderSenseResults();
    goSenseStep(4);
}

function generateMockSenseResults(industry) {
    const mockData = {
        'Pakistani Fabric & Fashion': [
            { name: 'Embroidered Chiffon Dupatta', price: 1800, confidence: 0.94 },
            { name: 'Lawn 3-Piece Unstitched', price: 4500, confidence: 0.91 },
            { name: 'Cotton Shalwar Kameez', price: 3200, confidence: 0.87 },
            { name: 'Bridal Lehenga Set', price: 45000, confidence: 0.82 },
            { name: 'Men\'s Wash & Wear Suit', price: 5500, confidence: 0.79 },
        ],
        'Restaurant & Food': [
            { name: 'Chicken Biryani (Full)', price: 850, confidence: 0.95 },
            { name: 'Mutton Karahi', price: 2200, confidence: 0.90 },
            { name: 'Seekh Kebab Platter', price: 650, confidence: 0.88 },
            { name: 'Special Naan', price: 80, confidence: 0.85 },
        ],
        'Electronics & Mobile': [
            { name: 'Samsung Galaxy A15 (128GB)', price: 42000, confidence: 0.93 },
            { name: 'iPhone 14 Pro Max (256GB)', price: 380000, confidence: 0.89 },
            { name: 'Earbuds Pro X', price: 4500, confidence: 0.84 },
        ],
    };

    return mockData[industry] || [
        { name: 'Product A', price: 1500, confidence: 0.90 },
        { name: 'Product B', price: 3000, confidence: 0.85 },
        { name: 'Product C', price: 750, confidence: 0.80 },
    ];
}

function renderSenseResults() {
    const container = document.getElementById('senseResults');
    let html = '';

    senseResults.forEach((item, i) => {
        const confPercent = Math.round(item.confidence * 100);
        const confColor = confPercent >= 90 ? 'var(--accent)' : confPercent >= 80 ? 'var(--warning)' : 'var(--text-muted)';

        html += `
            <div class="sense-result-card" id="senseResult${i}">
                <div class="sense-result-card__info">
                    <div class="sense-result-card__name">${escapeHtml(item.name)}</div>
                    <div class="sense-result-card__price">PKR ${item.price.toLocaleString()}</div>
                    <div class="sense-result-card__confidence" style="color: ${confColor};">
                        AI Confidence: ${confPercent}%
                    </div>
                </div>
                <div class="sense-result-card__actions">
                    <button class="btn btn--primary btn--sm" onclick="approveSenseProduct(${i})" title="Approve and add to catalog">✓</button>
                    <button class="btn btn--ghost btn--sm" onclick="skipSenseProduct(${i})" style="color:var(--danger);" title="Skip this product">✕</button>
                </div>
            </div>
        `;
    });

    container.innerHTML = html || '<p class="text-muted">No products found. Try a different profile.</p>';
}

async function approveSenseProduct(index) {
    const item = senseResults[index];
    if (!item) return;

    const catalog = [...(currentBusiness.raw_catalog || [])];
    catalog.push({ name: item.name, price: item.price, category: 'Auto-Sensed', details: '' });

    try {
        const res = await fetch(`${API_BASE}/api/business/${currentPhone}/catalog`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ items: catalog, policies: currentBusiness.policies || '' })
        });

        if (!res.ok) throw new Error('Failed to add product');

        currentBusiness.raw_catalog = catalog;
        renderProducts();
        
        // Remove from sense results UI
        const el = document.getElementById('senseResult' + index);
        if (el) {
            el.style.opacity = '0.3';
            el.style.pointerEvents = 'none';
            el.querySelector('.sense-result-card__name').textContent += ' ✓ Added';
        }

        showToast(`"${item.name}" added to your catalog!`, 'success');
    } catch (err) {
        showToast('Error: ' + err.message, 'error');
    }
}

function skipSenseProduct(index) {
    const el = document.getElementById('senseResult' + index);
    if (el) {
        el.style.opacity = '0.3';
        el.style.pointerEvents = 'none';
        el.querySelector('.sense-result-card__name').textContent += ' — Skipped';
    }
}

async function approveAllSenseProducts() {
    const catalog = [...(currentBusiness.raw_catalog || [])];
    let added = 0;

    senseResults.forEach((item, i) => {
        const el = document.getElementById('senseResult' + i);
        if (el && el.style.pointerEvents !== 'none') {
            catalog.push({ name: item.name, price: item.price, category: 'Auto-Sensed', details: '' });
            added++;
        }
    });

    if (added === 0) {
        showToast('No products left to approve.', 'warning');
        return;
    }

    try {
        const res = await fetch(`${API_BASE}/api/business/${currentPhone}/catalog`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ items: catalog, policies: currentBusiness.policies || '' })
        });

        if (!res.ok) throw new Error('Failed to add products');

        currentBusiness.raw_catalog = catalog;
        renderProducts();
        showToast(`${added} products imported to your catalog!`, 'success');

        // Dim all results
        document.querySelectorAll('.sense-result-card').forEach(el => {
            el.style.opacity = '0.3';
            el.style.pointerEvents = 'none';
        });
    } catch (err) {
        showToast('Error: ' + err.message, 'error');
    }
}

/* ══════════════════════════════════════════════
   Utilities
   ══════════════════════════════════════════════ */

function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

function showToast(message, type = 'success') {
    const container = document.getElementById('toastContainer');
    const toast = document.createElement('div');
    toast.className = `toast toast--${type}`;

    const icons = { success: '✓', error: '✕', warning: '⚠', info: 'ℹ' };
    toast.innerHTML = `<span style="font-weight:700;font-size:16px;">${icons[type] || '•'}</span> ${message}`;

    container.appendChild(toast);
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateX(40px)';
        toast.style.transition = 'all 0.3s var(--ease-out)';
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}

/* ── Close modals on overlay click ── */
document.getElementById('productModal').addEventListener('click', (e) => {
    if (e.target === document.getElementById('productModal')) closeProductModal();
});
document.getElementById('deleteModal').addEventListener('click', (e) => {
    if (e.target === document.getElementById('deleteModal')) closeDeleteModal();
});

/* ── Keyboard shortcuts ── */
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        closeProductModal();
        closeDeleteModal();
    }
});

/* ── Login on Enter key ── */
document.getElementById('loginPhone').addEventListener('keydown', (e) => {
    if (e.key === 'Enter') loginToDashboard();
});

/* ══════════════════════════════════════════════
   Visual Search — Customer Images
   ══════════════════════════════════════════════ */

async function loadUnmatchedImages() {
    if (!currentPhone) return;
    const container = document.getElementById('unmatchedImagesContainer');
    try {
        const res = await fetch(`${API_BASE}/api/visual-search/unmatched/${currentPhone}?limit=20`);
        if (!res.ok) throw new Error('Failed to fetch');
        const data = await res.json();

        if (!data.items || data.items.length === 0) {
            container.innerHTML = `
                <div class="empty-state">
                    <div class="empty-state__icon">📸</div>
                    <div class="empty-state__title">No unmatched images</div>
                    <div class="empty-state__desc">When customers send photos your AI can't match, they'll appear here.</div>
                </div>
            `;
            return;
        }

        let html = `<p class="text-muted" style="margin-bottom:16px; font-size:0.875rem;">${data.total_unmatched} images waiting for review</p>`;
        html += '<div style="display:grid; gap:16px;">';
        data.items.forEach(item => {
            const score = item.confidence_score !== null ? (item.confidence_score * 100).toFixed(0) + '%' : 'N/A';
            const tier = item.confidence_tier || 'unknown';
            const tierColor = tier === 'low' ? 'var(--warning)' : 'var(--danger)';
            html += `
                <div class="card card--flat" style="display:flex; gap:16px; padding:16px; align-items:center;">
                    <img src="${item.image_url}" alt="Customer image" style="width:80px; height:80px; object-fit:cover; border-radius:var(--radius-sm); background:var(--bg-surface-elevated);">
                    <div style="flex:1;">
                        <div style="font-size:0.8125rem; color:var(--text-muted);">From: ${item.customer_phone}</div>
                        <div style="font-size:0.875rem; font-weight:600; margin:2px 0;">Confidence: <span style="color:${tierColor};">${score} (${tier})</span></div>
                        ${item.ocr_text ? `<div style="font-size:0.8125rem; color:var(--text-muted);">OCR: "${escapeHtml(item.ocr_text.substring(0, 80))}"</div>` : ''}
                        <div style="font-size:0.75rem; color:var(--text-muted); margin-top:2px;">${item.created_at ? new Date(item.created_at).toLocaleDateString() : ''}</div>
                    </div>
                </div>
            `;
        });
        html += '</div>';
        container.innerHTML = html;
    } catch (err) {
        container.innerHTML = `<p class="text-muted" style="text-align:center; padding:48px 0;">Could not load images. ${err.message}</p>`;
    }
}

async function loadMatchStats() {
    if (!currentPhone) return;
    try {
        const res = await fetch(`${API_BASE}/api/visual-search/stats/${currentPhone}?days=30`);
        if (!res.ok) throw new Error('Failed to fetch');
        const data = await res.json();

        document.getElementById('statTotalSearches').textContent = data.total_searches || 0;
        document.getElementById('statHighMatchRate').textContent = (data.high_match_rate_pct || 0) + '%';
        document.getElementById('statAvgConfidence').textContent = data.avg_confidence_score !== null ? Number(data.avg_confidence_score).toFixed(2) : '—';

        const dist = data.distribution || {};
        document.getElementById('distHigh').textContent = dist.high || 0;
        document.getElementById('distMedium').textContent = dist.medium || 0;
        document.getElementById('distLow').textContent = dist.low || 0;
        document.getElementById('distNone').textContent = dist.none || 0;

        const alertEl = document.getElementById('matchHealthAlert');
        if (data.health_alert) {
            alertEl.innerHTML = `<div class="card card--flat" style="padding:16px; border-left:3px solid var(--warning); background:var(--bg-surface-elevated); margin-bottom:24px;">
                <strong>⚠️ Health Alert:</strong> ${escapeHtml(data.health_alert)}
            </div>`;
        } else {
            alertEl.innerHTML = '';
        }
    } catch (err) {
        document.getElementById('statTotalSearches').textContent = '—';
    }
}

/* ── Hook into tab switching to load data ── */
const originalSwitchTab = window.switchTab;
window.switchTab = function(tabName, btnEl) {
    originalSwitchTab(tabName, btnEl);
    if (tabName === 'visual-search') loadUnmatchedImages();
    if (tabName === 'match-stats') loadMatchStats();
};
