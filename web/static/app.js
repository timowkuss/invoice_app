const API = '/api';
let token = localStorage.getItem('token');
let currentUser = null;

// ============================================================
// Auth
// ============================================================
async function api(url, options = {}) {
    const headers = { 'Content-Type': 'application/json', ...options.headers };
    if (token) headers['Authorization'] = `Bearer ${token}`;
    const res = await fetch(API + url, { ...options, headers });
    if (res.status === 401) { logout(); return null; }
    if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || 'Error');
    }
    return res.json();
}

async function login() {
    const username = document.getElementById('login-user').value;
    const password = document.getElementById('login-pass').value;
    try {
        const data = await api('/auth/login', {
            method: 'POST',
            body: JSON.stringify({ username, password }),
        });
        token = data.token;
        currentUser = data.user;
        localStorage.setItem('token', token);
        showApp();
    } catch (e) {
        document.getElementById('login-error').textContent = e.message;
    }
}

function logout() {
    token = null;
    currentUser = null;
    localStorage.removeItem('token');
    showLogin();
}

function showLogin() {
    document.getElementById('page-login').classList.add('active');
    document.querySelectorAll('.page:not(#page-login)').forEach(p => p.classList.remove('active'));
    document.getElementById('page-login').innerHTML = `
        <div class="login-container">
            <h1>📋 Invoice App</h1>
            <div class="form-group">
                <label>Пользователь</label>
                <input type="text" id="login-user" value="admin">
            </div>
            <div class="form-group">
                <label>Пароль</label>
                <input type="password" id="login-pass" value="admin">
            </div>
            <div id="login-error" style="color:red;margin-bottom:12px"></div>
            <button class="btn btn-primary btn-block" onclick="login()">Войти</button>
        </div>`;
}

async function showApp() {
    try {
        currentUser = await api('/auth/me');
    } catch { showLogin(); return; }
    document.getElementById('user-info').textContent = currentUser.full_name || currentUser.username;
    document.getElementById('page-login').classList.remove('active');
    showPage('dashboard');
}

// ============================================================
// Navigation
// ============================================================
function showPage(page) {
    document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
    const el = document.getElementById('page-' + page);
    if (el) el.classList.add('active');
    document.querySelectorAll('.nav-links a').forEach(a => {
        a.classList.toggle('active', a.dataset.page === page);
    });
    const loaders = {
        dashboard: loadDashboard,
        documents: loadDocuments,
        products: loadProducts,
        users: loadUsers,
        stores: loadStores,
        aliases: loadAliases,
        'ai-stats': loadAiStats,
        settings: loadSettings,
    };
    if (loaders[page]) loaders[page]();
}

function toggleSidebar() {
    document.getElementById('sidebar').classList.toggle('open');
}

// ============================================================
// Dashboard
// ============================================================
async function loadDashboard() {
    const el = document.getElementById('page-dashboard');
    try {
        const data = await api('/stats/dashboard?period=month');
        el.innerHTML = `
            <h1 style="margin-bottom:24px">Dashboard</h1>
            <div class="dashboard-grid">
                <div class="stat-card"><h3>Сегодня</h3><div class="value">${data.today_count}</div></div>
                <div class="stat-card"><h3>За месяц</h3><div class="value">${data.period_count}</div></div>
                <div class="stat-card"><h3>Требуют проверки</h3><div class="value warning">${data.needs_review}</div></div>
                <div class="stat-card"><h3>Отправлено в 1С</h3><div class="value success">${data.sent_to_1c}</div></div>
                <div class="stat-card"><h3>Ошибок</h3><div class="value danger">${data.errors}</div></div>
                <div class="stat-card"><h3>Mistral запросов</h3><div class="value">${data.ai_requests}</div></div>
            </div>`;
    } catch (e) { el.innerHTML = `<p>Ошибка: ${e.message}</p>`; }
}

// ============================================================
// Documents
// ============================================================
async function loadDocuments() {
    const el = document.getElementById('page-documents');
    try {
        const data = await api('/documents/');
        const items = data.items || [];
        el.innerHTML = `
            <div class="card-header"><h2>Накладные</h2>
                <button class="btn btn-primary" onclick="showUploadModal()">+ Загрузить</button>
            </div>
            <div class="card-body">
                <table>
                    <thead><tr>
                        <th>№</th><th>Поставщик</th><th>Статус</th><th>Товаров</th><th>Дата</th><th></th>
                    </tr></thead>
                    <tbody>
                        ${items.map(d => `<tr>
                            <td>#${d.id}</td>
                            <td>${d.supplier || '—'}</td>
                            <td><span class="badge badge-${d.status}">${d.status}</span></td>
                            <td>${d.total_items}</td>
                            <td>${d.created_at ? new Date(d.created_at).toLocaleDateString() : '—'}</td>
                            <td><button class="btn btn-sm btn-outline" onclick="showDocument(${d.id})">Открыть</button></td>
                        </tr>`).join('')}
                    </tbody>
                </table>
                ${items.length === 0 ? '<p style="text-align:center;padding:40px;color:#999">Нет документов</p>' : ''}
            </div>`;
    } catch (e) { el.innerHTML = `<p>Ошибка: ${e.message}</p>`; }
}

async function showDocument(id) {
    const el = document.getElementById('page-document-detail');
    document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
    el.classList.add('active');
    try {
        const data = await api(`/documents/${id}`);
        const doc = data.document;
        const items = data.items || [];
        el.innerHTML = `
            <div style="margin-bottom:16px">
                <button class="btn btn-outline" onclick="showPage('documents')">← Назад</button>
                <span class="badge badge-${doc.status}" style="margin-left:12px">${doc.status}</span>
                ${doc.status === 'needs_review' || doc.status === 'recognized' ?
                    `<button class="btn btn-success" style="margin-left:12px" onclick="confirmDocument(${doc.id})">✔ Подтвердить</button>` : ''}
            </div>
            <div class="doc-layout">
                <div class="doc-image">
                    <img src="/api/documents/${doc.id}/image" alt="Накладная"
                         onerror="this.style.display='none'">
                </div>
                <div>
                    <div class="card" style="margin-bottom:16px">
                        <div class="card-body">
                            <p><strong>Поставщик:</strong> ${doc.supplier || '—'}</p>
                            <p><strong>Номер:</strong> ${doc.document_number || '—'}</p>
                            <p><strong>Дата:</strong> ${doc.document_date || '—'}</p>
                            <p><strong>Статус:</strong> <span class="badge badge-${doc.status}">${doc.status}</span></p>
                        </div>
                    </div>
                    <div class="card">
                        <div class="card-header"><h2>Товары (${items.length})</h2></div>
                        <div class="card-body" style="overflow-x:auto">
                            <table>
                                <thead><tr><th>№</th><th>Распознано</th><th>Товар 1С</th><th>Кол-во</th><th>Цена</th><th>Статус</th><th></th></tr></thead>
                                <tbody>
                                    ${items.map(i => `<tr>
                                        <td>${i.row_number}</td>
                                        <td>${i.ocr_text || i.product_name || '—'}</td>
                                        <td>${i.product_name || 'Не найдено'}</td>
                                        <td>${i.quantity || '—'}</td>
                                        <td>${i.price || '—'}</td>
                                        <td><span class="badge badge-${i.match_status}">${i.match_status}</span></td>
                                        <td><button class="btn btn-sm btn-outline" onclick="editItem(${doc.id},${i.id})">Изменить</button></td>
                                    </tr>`).join('')}
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>
            </div>`;
    } catch (e) { el.innerHTML = `<p>Ошибка: ${e.message}</p>`; }
}

async function confirmDocument(id) {
    await api(`/documents/${id}/confirm`, { method: 'POST' });
    showDocument(id);
}

// ============================================================
// Upload
// ============================================================
function showUploadModal() {
    openModal('Загрузить накладную', `
        <div class="form-group">
            <label>Поставщик</label>
            <input type="text" id="upload-supplier" placeholder="Название поставщика">
        </div>
        <div class="form-group">
            <label>Файл</label>
            <input type="file" id="upload-file" accept="image/*,.pdf">
        </div>
        <button class="btn btn-primary btn-block" onclick="uploadDocument()">Загрузить</button>
    `);
}

async function uploadDocument() {
    const file = document.getElementById('upload-file').files[0];
    const supplier = document.getElementById('upload-supplier').value;
    if (!file) return alert('Выберите файл');
    const formData = new FormData();
    formData.append('file', file);
    formData.append('supplier', supplier);
    try {
        const res = await fetch(API + '/documents/upload', {
            method: 'POST',
            headers: { 'Authorization': `Bearer ${token}` },
            body: formData,
        });
        const doc = await res.json();
        closeModal();
        showDocument(doc.id);
        await api(`/documents/${doc.id}/process`, { method: 'POST' });
        showDocument(doc.id);
    } catch (e) { alert('Ошибка: ' + e.message); }
}

// ============================================================
// Edit Item
// ============================================================
async function editItem(docId, itemId) {
    const data = await api(`/documents/${docId}`);
    const item = data.items.find(i => i.id === itemId);
    if (!item) return;

    openModal('Изменить строку', `
        <div class="form-group">
            <label>Распознано:</label>
            <p>${item.ocr_text || item.product_name}</p>
        </div>
        <div class="form-group">
            <label>Поиск товара:</label>
            <input type="text" id="edit-search" onkeyup="searchProductsForEdit(this.value)" placeholder="Введите название...">
            <div id="edit-search-results" style="max-height:200px;overflow-y:auto;margin-top:8px"></div>
        </div>
        <input type="hidden" id="edit-product-id" value="${item.product_id || ''}">
        <div class="form-group"><label>Количество</label><input type="number" id="edit-qty" value="${item.quantity || ''}"></div>
        <div class="form-group"><label>Цена</label><input type="number" id="edit-price" value="${item.price || ''}"></div>
        <div class="form-group">
            <label><input type="checkbox" id="edit-alias"> Запомнить для будущих накладных</label>
        </div>
        <button class="btn btn-primary btn-block" onclick="saveItem(${docId},${itemId})">Сохранить</button>
    `);
}

let editSearchTimeout;
function searchProductsForEdit(query) {
    clearTimeout(editSearchTimeout);
    if (query.length < 2) return;
    editSearchTimeout = setTimeout(async () => {
        const products = await api(`/matching/search?q=${encodeURIComponent(query)}`);
        const el = document.getElementById('edit-search-results');
        el.innerHTML = products.map(p => `
            <div style="padding:8px;cursor:pointer;border:1px solid #e2e8f0;border-radius:4px;margin-bottom:4px"
                 onclick="selectProduct(${p.id},'${p.name.replace(/'/g,"\\'")}')">
                <strong>${p.name}</strong><br>
                <small>${p.article || ''} ${p.barcode || ''}</small>
            </div>
        `).join('') || '<p style="color:#999;padding:8px">Не найдено</p>';
    }, 300);
}

function selectProduct(id, name) {
    document.getElementById('edit-product-id').value = id;
    document.getElementById('edit-search').value = name;
    document.getElementById('edit-search-results').innerHTML = '';
}

async function saveItem(docId, itemId) {
    const productId = document.getElementById('edit-product-id').value;
    const qty = document.getElementById('edit-qty').value;
    const price = document.getElementById('edit-price').value;
    const createAlias = document.getElementById('edit-alias').checked;

    const params = new URLSearchParams();
    if (productId) params.set('product_id', productId);
    if (qty) params.set('quantity', qty);
    if (price) params.set('price', price);
    params.set('create_alias', createAlias);

    await api(`/documents/${docId}/items/${itemId}?${params}`, { method: 'PUT' });
    closeModal();
    showDocument(docId);
}

// ============================================================
// Products, Users, Stores, Aliases, AI Stats, Settings
// ============================================================
async function loadProducts() {
    const el = document.getElementById('page-products');
    const data = await api('/products/');
    const items = data.items || [];
    el.innerHTML = `
        <div class="card-header"><h2>Каталог товаров</h2></div>
        <div class="card-body">
            <table>
                <thead><tr><th>ID</th><th>Название</th><th>Артикул</th><th>Штрихкод</th><th>Ед.</th><th>Цена</th></tr></thead>
                <tbody>
                    ${items.map(p => `<tr>
                        <td>${p.id}</td><td>${p.name}</td><td>${p.article || '—'}</td>
                        <td>${p.barcode || '—'}</td><td>${p.unit || '—'}</td><td>${p.price || '—'}</td>
                    </tr>`).join('')}
                </tbody>
            </table>
        </div>`;
}

async function loadUsers() {
    const el = document.getElementById('page-users');
    const data = await api('/users/');
    el.innerHTML = `
        <div class="card-header"><h2>Пользователи</h2></div>
        <div class="card-body">
            <table>
                <thead><tr><th>ID</th><th>Имя</th><th>Логин</th><th>Роль</th><th>Telegram</th><th>Статус</th></tr></thead>
                <tbody>
                    ${(data || []).map(u => `<tr>
                        <td>${u.id}</td><td>${u.full_name || '—'}</td><td>${u.username}</td>
                        <td>${u.role}</td><td>${u.telegram_chat_id || '—'}</td>
                        <td>${u.is_active ? '✅' : '❌'}</td>
                    </tr>`).join('')}
                </tbody>
            </table>
        </div>`;
}

async function loadStores() {
    const el = document.getElementById('page-stores');
    const data = await api('/stores/');
    el.innerHTML = `
        <div class="card-header"><h2>Магазины</h2></div>
        <div class="card-body">
            <table>
                <thead><tr><th>ID</th><th>Название</th><th>Код</th><th>ИНН</th><th>Статус</th></tr></thead>
                <tbody>
                    ${(data || []).map(s => `<tr>
                        <td>${s.id}</td><td>${s.name}</td><td>${s.code}</td>
                        <td>${s.inn || '—'}</td><td>${s.is_active ? '✅' : '❌'}</td>
                    </tr>`).join('')}
                </tbody>
            </table>
        </div>`;
}

async function loadAliases() {
    const el = document.getElementById('page-aliases');
    const data = await api('/matching/aliases');
    el.innerHTML = `
        <div class="card-header"><h2>Синонимы (Aliases)</h2></div>
        <div class="card-body">
            <table>
                <thead><tr><th>OCR текст</th><th>Нормализованный</th><th>Product ID</th><th>Использований</th><th></th></tr></thead>
                <tbody>
                    ${(data || []).map(a => `<tr>
                        <td>${a.ocr_text}</td><td>${a.normalized_text}</td>
                        <td>${a.product_id}</td><td>${a.usage_count}</td>
                        <td><button class="btn btn-sm btn-danger" onclick="deleteAlias(${a.id})">Удалить</button></td>
                    </tr>`).join('')}
                </tbody>
            </table>
        </div>`;
}

async function deleteAlias(id) {
    if (!confirm('Удалить синоним?')) return;
    await api(`/matching/aliases/${id}`, { method: 'DELETE' });
    loadAliases();
}

async function loadAiStats() {
    const el = document.getElementById('page-ai-stats');
    const data = await api('/stats/ai-usage');
    const s = data.stats || {};
    el.innerHTML = `
        <h1 style="margin-bottom:24px">Mistral Статистика</h1>
        <div class="dashboard-grid">
            <div class="stat-card"><h3>Запросов</h3><div class="value">${s.total_requests || 0}</div></div>
            <div class="stat-card"><h3>Токенов</h3><div class="value">${s.total_tokens || 0}</div></div>
            <div class="stat-card"><h3>Стоимость</h3><div class="value">$${(s.total_cost || 0).toFixed(4)}</div></div>
            <div class="stat-card"><h3>Ошибок</h3><div class="value danger">${s.errors || 0}</div></div>
        </div>`;
}

async function loadSettings() {
    const el = document.getElementById('page-settings');
    const data = await api('/settings/');
    el.innerHTML = `
        <h1 style="margin-bottom:24px">Настройки</h1>
        <div class="card"><div class="card-body">
            ${Object.entries(data || {}).map(([k, v]) => `
                <div class="form-group">
                    <label>${k}</label>
                    <input type="text" id="setting-${k}" value="${v.value}">
                </div>
            `).join('')}
            <button class="btn btn-primary" onclick="saveSettings()">Сохранить</button>
        </div></div>`;
}

async function saveSettings() {
    const inputs = document.querySelectorAll('[id^="setting-"]');
    for (const input of inputs) {
        const key = input.id.replace('setting-', '');
        let value = input.value;
        if (!isNaN(value) && value !== '') value = Number(value);
        await api('/settings/', {
            method: 'PUT',
            body: JSON.stringify({ key, value }),
        });
    }
    alert('Настройки сохранены');
}

// ============================================================
// Modal
// ============================================================
function openModal(title, content) {
    document.getElementById('modal-title').textContent = title;
    document.getElementById('modal-content').innerHTML = content;
    document.getElementById('modal-overlay').classList.add('active');
}

function closeModal() {
    document.getElementById('modal-overlay').classList.remove('active');
}

// ============================================================
// Init
// ============================================================
if (token) { showApp(); } else { showLogin(); }
