'use strict';
const app = document.querySelector('#app');
const modal = document.querySelector('#modal');
let user = null, page = 'dashboard', selectedStore = sessionStorage.getItem('store') || '', timer = null, currentDoc = null, previewUrl = null, catalogOffset = 0;
const labels = {received:'Загружена',retry_pending:'В очереди',processing:'Распознаём',needs_review:'Нужна проверка',recognized:'Распознана',confirmed:'Проверена',success:'Успешно',timeout:'Тайм-аут',error:'Ошибка',matched:'Совпадение',manual:'Подтверждено',not_found:'Выберите товар',pending:'Ожидает'};
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const money = value => value == null ? '—' : Number(value).toLocaleString('ru-RU',{minimumFractionDigits:2,maximumFractionDigits:2});
const integer = value => Number(value || 0).toLocaleString('ru-RU');
const usd = value => Number(value || 0).toLocaleString('en-US',{style:'currency',currency:'USD',minimumFractionDigits:4,maximumFractionDigits:6});
const dateTime = value => value ? new Date(value).toLocaleString('ru-RU') : '—';
const badge = status => `<span class="badge ${esc(status)}">${esc(labels[status] || status)}</span>`;
const date = value => value ? new Date(value).toLocaleDateString('ru-RU') : '—';
function toast(message) {const el=document.querySelector('#toast');el.textContent=message;el.classList.add('visible');setTimeout(()=>el.classList.remove('visible'),4500);}
async function request(path, options={}) {
  const headers = {...options.headers};
  if (!(options.body instanceof FormData) && options.body) headers['Content-Type']='application/json';
  if (selectedStore) headers['X-Store-ID']=selectedStore;
  const res=await fetch('/api'+path,{...options,headers,credentials:'same-origin'});
  if (!res.ok) {
    const data=await res.json().catch(()=>({}));
    let message=data.detail;
    if (Array.isArray(message)) message=message.map(e=>`${e.loc.at(-1)}: ${e.msg}`).join('; ');
    if (typeof message==='object') message=message.message;
    if (res.status===401 && !path.startsWith('/auth/')) authView();
    throw new Error(message || 'Не удалось выполнить запрос');
  }
  return res;
}
async function api(path,options) {return (await request(path,options)).json();}
async function download(path,filename) {
  const blob=await (await request(path)).blob();const url=URL.createObjectURL(blob);
  const a=document.createElement('a');a.href=url;a.download=filename;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
}
function openModal(title,content) {document.querySelector('#modal-content').innerHTML=`<div class="modal-head"><h2>${esc(title)}</h2><button class="modal-close" data-action="close" aria-label="Закрыть">×</button></div>${content}`;modal.showModal();}
function closeModal(){modal.close();}
function authView(mode='login') {
  clearTimeout(timer); user=null; page='auth';
  const token=new URLSearchParams(location.search).get('reset_token') || '';
  const forms={
    login:`<h2>С возвращением</h2><p class="muted">Войдите по email, который вам выдал администратор.</p><form id="auth-form"><div class="field"><label for="email">Email</label><input id="email" type="email" name="email" required maxlength="254" autocomplete="email" placeholder="name@example.com"></div><div class="field"><label for="password">Пароль</label><input id="password" type="password" name="password" required maxlength="72" autocomplete="current-password"></div><div id="auth-error" role="alert"></div><button class="btn primary" type="submit">Войти в аккаунт <span>→</span></button></form><div class="auth-switch"><button class="link" data-action="forgot-password">Забыли пароль?</button></div>`,
    forgot:`<h2>Восстановление пароля</h2><p class="muted">Укажите email аккаунта. Мы отправим одноразовую ссылку.</p><form id="forgot-form"><div class="field"><label for="email">Email</label><input id="email" type="email" name="email" required maxlength="254" autocomplete="email" placeholder="name@example.com"></div><div id="auth-error" role="alert"></div><button class="btn primary" type="submit">Отправить ссылку <span>→</span></button></form><div class="auth-switch"><button class="link" data-action="back-login">Вернуться ко входу</button></div>`,
    reset:`<h2>Новый пароль</h2><p class="muted">Придумайте новый пароль длиной не менее 10 символов.</p><form id="reset-form"><input type="hidden" name="token" value="${esc(token)}"><div class="field"><label for="password">Новый пароль</label><input id="password" type="password" name="password" required minlength="10" maxlength="72" autocomplete="new-password"></div><div class="field"><label for="password-confirm">Повторите пароль</label><input id="password-confirm" type="password" name="password_confirm" required minlength="10" maxlength="72" autocomplete="new-password"></div><div id="auth-error" role="alert"></div><button class="btn primary" type="submit">Сохранить пароль <span>→</span></button></form>`
  };
  const current=mode==='reset' && !token?'login':mode;
  app.innerHTML=`<div class="auth-layout"><section class="auth-story"><div class="brand"><span class="mark">≡</span>Накладная</div><h1>От фото<br>до порядка<br>в вашей 1С.</h1><p>Распознайте накладную, сверьте товары с каталогом магазина и сохраните готовый Excel.</p><div class="flow"><span>01 &nbsp; Фото или скан документа</span><span>02 &nbsp; Точные названия из вашей базы</span><span>03 &nbsp; Проверка и выгрузка в Excel</span></div></section><section class="auth-panel"><div class="auth-box"><div class="eyebrow">Рабочее пространство магазина</div>${forms[current] || forms.login}<p class="auth-note">Аккаунты создаёт администратор сервиса.</p></div></section></div>`;
}
function shell() {
  const accountAdmin=user.role==='super_admin',storeAdmin=['super_admin','store_admin'].includes(user.role);
  app.innerHTML=`<div class="shell"><aside class="sidebar"><div><div class="brand"><span class="mark">≡</span>Накладная</div><small>Порядок начинается с документа</small></div><nav class="nav" aria-label="Основное меню"><button data-page="dashboard"><span class="nav-icon">◫</span>Обзор</button><button data-page="documents"><span class="nav-icon">▤</span>Накладные</button><button data-page="products"><span class="nav-icon">▦</span>Каталог 1С</button>${accountAdmin?'<button data-page="usage"><span class="nav-icon">◎</span>Статистика</button><button data-page="users"><span class="nav-icon">♧</span>Аккаунты</button>':''}${storeAdmin?'<button data-page="settings"><span class="nav-icon">⚙</span>Настройки</button>':''}</nav><div class="sidebar-bottom"><small>Ваш аккаунт</small><span>${esc(user.full_name || user.email)}</span><button data-action="logout">Выйти из аккаунта ↗</button></div></aside><div class="workspace"><header class="topbar"><span id="store-label">Рабочее пространство</span><div class="actions">${accountAdmin?'<button class="btn small" data-action="add-store">＋ Магазин</button><select id="store-select" class="store-select" aria-label="Выбрать магазин"><option value="">Выберите магазин</option></select>':''}<button class="btn small" data-action="logout" aria-label="Выйти">Выйти</button><span class="avatar">${esc(user.email.slice(0,2).toUpperCase())}</span></div></header><main id="content" class="content"></main></div></div>`;
  api('/stores/').then(stores=>{const store=stores.find(s=>s.id===(Number(selectedStore)||user.store_id));document.querySelector('#store-label').textContent=store?.name || 'Выберите магазин';const select=document.querySelector('#store-select');if(select){for(const s of stores){const o=new Option(s.name,s.id);select.add(o);}select.value=selectedStore;}}).catch(e=>toast(e.message));
}
const head=(title,subtitle,actions='')=>`<div class="page-head"><div><div class="eyebrow">Ваш магазин · каждый день проще</div><h1>${esc(title)}</h1><p>${esc(subtitle)}</p></div><div class="actions">${actions}</div></div>`;
const empty=(title,text,button='')=>`<div class="empty"><div class="symbol">▤</div><h3>${esc(title)}</h3><p>${esc(text)}</p>${button}</div>`;
async function navigate(next) {
  clearTimeout(timer);page=next;currentDoc=null;
  document.querySelectorAll('[data-page]').forEach(b=>b.classList.toggle('active',b.dataset.page===next));
  const content=document.querySelector('#content');content.innerHTML='<p class="loading">Загрузка…</p>';
  if(user.role==='super_admin' && !selectedStore && next!=='usage'){content.innerHTML=head('Магазины','Создайте магазин или выберите существующий, чтобы управлять его аккаунтами.','<button class="btn primary" data-action="add-store">＋ Новый магазин</button>');return;}
  try {await ({dashboard:dashboard,documents:documents,products:products,usage:usage,users:users,settings:settings}[next] || dashboard)();}
  catch(e){if(page!=='auth')content.innerHTML=`<div class="error">${esc(e.message)}</div>`;}
}
async function dashboard() {
  const data=await api('/stats/dashboard');
  document.querySelector('#content').innerHTML=head('Рабочий день без ручного ввода','Все накладные и товары магазина — в одном месте.','<button class="btn primary" data-action="upload">＋ Новая накладная</button>')+`<div class="metrics">${[['Все накладные',data.documents,'В вашем пространстве'],['Ждут проверки',data.needs_review,'Сверьте перед выгрузкой'],['Проверены',data.confirmed,'Готовы к Excel'],['Товары в каталоге',data.catalog,'Названия из вашей 1С']].map(([title,value,note])=>`<div class="metric"><strong>${title}</strong><div class="value">${value}</div><p>${note}</p></div>`).join('')}</div><div class="hero"><div><div class="eyebrow">От документа к результату</div><h2>Фотографируйте накладную.<br>Остальное — здесь.</h2><p>Распознавание через Mistral и сопоставление с вашим каталогом. Вы проверяете результат и получаете Excel для загрузки в 1С.</p><button class="btn primary" data-action="${data.catalog?'upload':'catalog-import'}">${data.catalog?'Загрузить накладную →':'Начать с каталога →'}</button></div><div class="steps"><div class="step"><b>1</b><span>Загрузите каталог товаров из 1С</span></div><div class="step"><b>2</b><span>Добавьте фото или PDF накладной</span></div><div class="step"><b>3</b><span>Проверьте товары и скачайте Excel</span></div></div></div><div class="card"><div class="card-title"><h3>Последние накладные</h3><button class="btn small" data-page="documents">Все документы →</button></div><div id="recent"></div></div>`;
  const docs=await api('/documents/?limit=5');document.querySelector('#recent').innerHTML=documentTable(docs.items);
}
async function usage() {
  if(user.role!=='super_admin')throw new Error('Нужны права владельца сервиса');
  const data=await api('/stats/admin-ai-usage'),s=data.summary;
  const metrics=[
    ['Запросы Mistral',integer(s.total_requests),'Все попытки распознавания'],
    ['Успешно',integer(s.successful_requests),'Обработаны без ошибки'],
    ['Ошибки',integer(s.failed_requests),'Неуспешные попытки'],
    ['Страницы',integer(s.total_pages),'Основа расчёта расходов'],
    ['Стоимость',usd(s.total_cost),'Расчётная сумма']
  ];
  const storeRows=data.stores.map(row=>`<tr><td><b>${esc(row.store_name)}</b></td><td class="number">${integer(row.total_requests)}</td><td class="number">${integer(row.successful_requests)}</td><td class="number">${integer(row.failed_requests)}</td><td class="number">${integer(row.total_pages)}</td><td class="number">${usd(row.total_cost)}</td><td>${dateTime(row.last_request_at)}</td></tr>`).join('');
  const recentRows=data.recent.map(row=>`<tr><td>${dateTime(row.created_at)}</td><td>${esc(row.store_name || 'Удалённый магазин')}</td><td>${row.document_id?`#${integer(row.document_id)}`:'—'}</td><td>${badge(row.status)}</td><td class="number">${integer(row.pages)}</td><td class="number">${usd(row.cost)}</td><td class="number">${row.duration_ms==null?'—':`${integer(row.duration_ms)} мс`}</td></tr>`).join('');
  document.querySelector('#content').innerHTML=head('Статистика Mistral','Расходы и количество распознаваний по всем магазинам.')+
    `<div class="metrics usage-metrics">${metrics.map(([title,value,note])=>`<div class="metric"><strong>${title}</strong><div class="value">${value}</div><p>${note}</p></div>`).join('')}</div>`+
    `<div class="notice">Расчёт стоимости использует тариф ${usd(data.cost_per_1000_pages_usd)} за 1000 страниц из настройки MISTRAL_COST_PER_1000_PAGES_USD.</div>`+
    `<div class="card"><div class="card-title"><h3>По магазинам</h3><span class="muted">${integer(data.stores.length)} магазинов</span></div><div class="table-wrap"><table><thead><tr><th>Магазин</th><th>Запросы</th><th>Успешно</th><th>Ошибки</th><th>Страницы</th><th>Стоимость</th><th>Последний запрос</th></tr></thead><tbody>${storeRows}</tbody></table></div></div>`+
    `<div class="card"><div class="card-title"><h3>Последние обращения</h3><span class="muted">До 50 записей</span></div>${recentRows?`<div class="table-wrap"><table><thead><tr><th>Дата</th><th>Магазин</th><th>Накладная</th><th>Статус</th><th>Страницы</th><th>Стоимость</th><th>Время</th></tr></thead><tbody>${recentRows}</tbody></table></div>`:empty('Запросов пока нет','После первого распознавания здесь появится расход Mistral.')}</div>`;
}
function documentTable(items) {return items.length?`<div class="table-wrap"><table><thead><tr><th>Документ</th><th>Поставщик</th><th>Статус</th><th>Строк</th><th>Добавлен</th><th></th></tr></thead><tbody>${items.map(d=>`<tr><td><b>Накладная #${d.id}</b></td><td>${esc(d.supplier || 'Не указан')}</td><td>${badge(d.status)}</td><td>${d.total_items}</td><td>${date(d.created_at)}</td><td><button class="btn small" data-action="document" data-id="${d.id}">Открыть →</button></td></tr>`).join('')}</tbody></table></div>`:empty('Здесь появятся ваши накладные','Загрузите первый документ — фото с телефона или скан в PDF.','<button class="btn" data-action="upload">Загрузить документ</button>');}
async function documents() {const data=await api('/documents/?limit=200');document.querySelector('#content').innerHTML=head('Накладные','Загрузка, распознавание и проверка перед выгрузкой.','<button class="btn primary" data-action="upload">＋ Новая накладная</button>')+`<div class="card">${documentTable(data.items)}</div>`;if(data.items.some(d=>['processing','retry_pending'].includes(d.status)))timer=setTimeout(()=>{if(page==='documents')documents().catch(e=>toast(e.message));},3000);}
function uploadModal() {openModal('Новая накладная',`<form id="upload-form"><div class="file-drop"><label for="invoice-file">Фото с телефона или скан документа</label><input id="invoice-file" name="file" type="file" accept="image/jpeg,image/png,image/webp,application/pdf" required><small>JPG, PNG, WebP или PDF · до 20 МБ · до 30 страниц</small></div><div class="field"><label for="supplier">Поставщик (необязательно)</label><input id="supplier" name="supplier" maxlength="500" placeholder="Название поставщика"></div><p class="muted">Файл отправляется в Mistral для распознавания. Результат можно проверить и исправить перед выгрузкой.</p><div class="form-error" role="alert"></div><button class="btn primary" type="submit">Загрузить и распознать →</button></form>`);}
async function showDocument(id) {
  clearTimeout(timer);page='detail';currentDoc=Number(id);
  const data=await api(`/documents/${id}`), d=data.document, items=data.items;
  if(currentDoc!==Number(id))return;
  const busy=['processing','retry_pending'].includes(d.status);
  const editable=['needs_review','recognized','confirmed'].includes(d.status);
  const total=items.reduce((sum,i)=>sum+Number(i.total || 0),0);
  document.querySelector('#content').innerHTML=head(`Накладная #${id}`,`${d.supplier || 'Поставщик не указан'} · ${date(d.created_at)}`,'<button class="btn" data-page="documents">← К списку</button>')+`${d.error_message?`<div class="error">${esc(d.error_message)}</div>`:''}${busy?'<div class="notice">Распознаём документ через Mistral. Можно закрыть страницу — обработка продолжится на сервере.</div>':''}<div class="split"><aside class="card preview"><div class="card-title"><h3>Оригинал</h3>${badge(d.status)}</div><div class="card-body" id="preview"><p class="muted">Загружаем документ…</p></div></aside><section class="card"><div class="card-title"><div><h3>Проверьте товары</h3><small class="muted">Название в Excel будет точно как в каталоге 1С</small></div><div class="actions"><span class="badge">${items.length} строк</span>${editable?'<button class="btn small" data-action="add-row">＋ Добавить строку</button>':''}</div></div>${items.length?`<div class="table-wrap"><table class="review-table"><thead><tr><th>Товар из каталога / в накладной</th><th>Кол-во</th><th>Цена</th><th>Сумма</th><th></th></tr></thead><tbody>${items.map(i=>`<tr data-row="${i.id}"><td><button class="product-button" data-action="choose-product" data-id="${i.id}">${esc(i.product_name || i.ocr_text)}</button><span class="ocr">${i.ocr_text?`В документе: ${esc(i.ocr_text)}`:'Добавлено вручную'}</span>${badge(i.match_status)}</td><td><input aria-label="Количество, строка ${i.row_number}" data-quantity type="number" min="0.001" step="0.001" value="${esc(i.quantity ?? '')}"></td><td><input aria-label="Цена, строка ${i.row_number}" data-price type="number" min="0" step="0.01" value="${esc(i.price ?? '')}"></td><td class="number">${money(i.total)}</td><td><button class="btn small" data-action="save-row" data-id="${i.id}">Сохранить</button>${editable?` <button class="btn small danger" data-action="delete-row" data-id="${i.id}" aria-label="Удалить строку ${i.row_number}">Удалить</button>`:''}</td></tr>`).join('')}</tbody></table></div><div class="review-footer"><span>Итого: <b class="number">${money(total)}</b></span><div class="actions"><button class="btn" data-action="confirm" data-id="${id}">✓ Всё проверено</button><button class="btn primary" data-action="export" data-id="${id}" ${d.status!=='confirmed'?'disabled':''}>Скачать Excel ↓</button></div></div>`:editable?empty('В накладной нет строк','Добавьте товар из каталога кнопкой «Добавить строку».'):empty(busy?'Документ обрабатывается':'Документ готов к распознаванию',busy?'Товары появятся здесь после обработки.':'Запустите OCR, чтобы получить строки накладной.',!busy?`<button class="btn primary" data-action="process" data-id="${id}">${d.status==='error'?'Повторить распознавание':'Распознать документ'}</button>`:'')}</section></div><p class="muted">Сначала выберите товары для спорных строк, сохраните исправления и нажмите «Всё проверено». Excel предназначен для загрузки через обработку импорта вашей конфигурации 1С.</p>`;
  const image=await request(`/documents/${id}/image`);const blob=await image.blob();
  if(previewUrl)URL.revokeObjectURL(previewUrl);previewUrl=URL.createObjectURL(blob);
  if(currentDoc===Number(id)){const preview=document.querySelector('#preview');preview.innerHTML=d.file_type==='.pdf'?`<iframe title="Оригинал накладной" src="${previewUrl}"></iframe>`:`<img alt="Оригинал накладной" src="${previewUrl}">`;}
  if(busy)timer=setTimeout(()=>{if(currentDoc===Number(id))showDocument(id).catch(e=>toast(e.message));},3000);
}
function requireSavedRows() {
  if(document.querySelector('[data-dirty]'))throw new Error('Сначала сохраните изменённые строки');
}
async function addRow() {
  requireSavedRows();
  openModal('Добавить строку',`<form id="add-row-form" data-document="${currentDoc}"><div class="field"><label for="product-search">Товар из каталога</label><input id="product-search" placeholder="Название, артикул или штрихкод" autofocus></div><div id="product-results" class="search-results">Загружаем товары…</div><input type="hidden" name="product_id"><div class="form-grid"><div class="field"><label for="new-quantity">Количество</label><input id="new-quantity" name="quantity" type="number" required min="0.001" max="9999999" step="0.001" value="1"></div><div class="field"><label for="new-price">Цена</label><input id="new-price" name="price" type="number" required min="0" max="999999999" step="0.01"></div></div><div class="form-error" role="alert"></div><button class="btn primary" type="submit">Добавить строку</button></form>`);
  const data=await api('/products/?limit=20');
  if(document.querySelector('#add-row-form') && !document.querySelector('#product-search').value)renderCandidates(data.items);
}
function deleteRow(itemId) {
  requireSavedRows();
  const row=document.querySelector(`[data-row="${itemId}"]`);
  openModal('Удалить строку?',`<form id="delete-row-form" data-document="${currentDoc}" data-item="${itemId}"><p>Удалить «${esc(row.querySelector('.product-button').textContent)}» из накладной?</p><p class="muted">Итог будет пересчитан. Накладную потребуется проверить заново.</p><div class="form-error" role="alert"></div><div class="actions"><button class="btn" type="button" data-action="close">Отмена</button><button class="btn danger" type="submit">Удалить строку</button></div></form>`);
}
async function chooseProduct(itemId) {
  openModal('Выберите товар из 1С',`<form id="match-form" data-item="${itemId}"><div class="field"><label for="product-search">Поиск по названию, артикулу или штрихкоду</label><input id="product-search" placeholder="Например, Шадринское"></div><div id="product-results" class="search-results">Ищем подходящие товары…</div><input type="hidden" name="product_id" required><label class="check"><input type="checkbox" name="create_alias" checked>Запомнить это название для моего магазина</label><div class="form-error" role="alert"></div><div class="actions"><button class="btn primary" type="submit">Выбрать товар</button></div></form>`);
  const data=await api(`/documents/${currentDoc}/items/${itemId}/suggestions`);renderCandidates(data.items);
}
function renderCandidates(items){const el=document.querySelector('#product-results');if(el)el.innerHTML=items.length?items.map(p=>`<button type="button" class="result" data-action="pick-product" data-id="${p.id}"><b>${esc(p.name)}</b><small>Код: ${esc(p.one_c_id)} · ${esc(p.unit || '—')} · ${esc(p.barcode || p.article || '')}</small></button>`).join(''):'<p class="muted">Совпадений нет. Попробуйте одно слово или загрузите актуальный каталог из 1С.</p>';}
async function products(search='') {
  const data=await api(`/products/?limit=50&offset=${catalogOffset}${search?'&search='+encodeURIComponent(search):''}`);
  document.querySelector('#content').innerHTML=head('Каталог из 1С','Единые названия, коды и единицы измерения вашего магазина.',user.role!=='operator'?'<button class="btn primary" data-action="catalog-import">↑ Загрузить каталог</button>':'')+`<form id="catalog-search" class="toolbar"><input name="search" aria-label="Поиск товаров" placeholder="Поиск по названию, артикулу или штрихкоду" value="${esc(search)}"><button class="btn" type="submit">Найти</button><span class="muted">${data.total} товаров</span></form><div class="card">${data.items.length?`<div class="table-wrap"><table><thead><tr><th>Код 1С</th><th>Название в базе</th><th>Артикул</th><th>Штрихкод</th><th>Единица</th></tr></thead><tbody>${data.items.map(p=>`<tr><td>${esc(p.one_c_id)}</td><td><b>${esc(p.name)}</b></td><td>${esc(p.article || '—')}</td><td>${esc(p.barcode || '—')}</td><td>${esc(p.unit || '—')}</td></tr>`).join('')}</tbody></table></div>${!search?`<div class="pagination"><button class="btn small" data-action="catalog-prev" ${catalogOffset===0?'disabled':''}>← Назад</button><button class="btn small" data-action="catalog-next" ${catalogOffset+50>=data.total?'disabled':''}>Далее →</button></div>`:''}`:empty('Добавьте ваш каталог','Выгрузите номенклатуру из 1С в XLSX или CSV. Сайт будет использовать именно эти названия.','<button class="btn" data-action="template">Скачать шаблон ↓</button>')}</div><div class="notice">Например, «Молоко Шадринское 5% 1л» сопоставляется с «Шадринское Молоко 1л 5%». Товары с другой жирностью или объёмом требуют отдельного выбора.</div>`;
}
function catalogModal(){openModal('Загрузить каталог',`<p class="muted">Коды и названия должны точно совпадать с номенклатурой вашей 1С. Повторная загрузка обновляет товары по коду.</p><button class="btn" data-action="template">Скачать шаблон XLSX ↓</button><form id="catalog-form"><div class="field"><label for="catalog-file">Файл XLSX или CSV</label><input id="catalog-file" type="file" name="file" accept=".xlsx,.csv" required><small>До 10 МБ и 10 000 строк. Коды и штрихкоды храните как текст.</small></div><div class="form-error" role="alert"></div><button class="btn primary" type="submit">Импортировать каталог</button></form>`);}
async function users(){const data=await api('/users/');document.querySelector('#content').innerHTML=head('Аккаунты магазина','Только вы создаёте аккаунты. Клиенты входят по email и не могут регистрироваться сами.','<button class="btn primary" data-action="add-user">＋ Добавить аккаунт</button>')+`<div class="card"><div class="table-wrap"><table><thead><tr><th>Пользователь</th><th>Email</th><th>Роль</th><th>Статус</th><th>Telegram</th></tr></thead><tbody>${data.map(u=>`<tr><td>${esc(u.full_name || '—')}</td><td>${esc(u.email)}</td><td>${esc({super_admin:'Владелец сервиса',store_admin:'Администратор магазина',operator:'Оператор'}[u.role])}</td><td>${u.is_active?'Активен':'Отключён'}</td><td>${u.telegram_chat_id?`<span>${esc(u.telegram_chat_id)}</span> `:''}<button class="btn small" data-action="telegram-bind" data-id="${u.id}" data-chat="${esc(u.telegram_chat_id || '')}">${u.telegram_chat_id?'Изменить':'Подключить'}</button></td></tr>`).join('')}</tbody></table></div></div>`;}
function telegramModal(button){
  openModal('Telegram сотрудника',`<form id="telegram-form" data-user="${button.dataset.id}"><p>Попросите сотрудника отправить /id боту в личном чате и передать вам номер. Проверьте, что номер принадлежит выбранному сотруднику: привязка даёт доступ к накладным магазина.</p><div class="field"><label for="telegram-id">Telegram ID сотрудника</label><input id="telegram-id" name="chat_id" inputmode="numeric" pattern="[0-9]{1,16}" required value="${esc(button.dataset.chat)}"></div><div class="form-error" role="alert"></div><div class="actions"><button class="btn primary" type="submit">Сохранить привязку</button>${button.dataset.chat?`<button class="btn danger" type="button" data-action="telegram-unbind" data-id="${button.dataset.id}">Отключить Telegram</button>`:''}</div></form>`);
}
async function openLanding(){
  const id=new URLSearchParams(location.search).get('document');
  if(id && /^[1-9][0-9]*$/.test(id) && Number.isSafeInteger(Number(id))){
    try{await showDocument(id);}catch(e){toast(e.message);await navigate('documents');}
  }else await navigate('dashboard');
}
function userModal(){openModal('Новый аккаунт',`<form id="user-form"><div class="field"><label>Имя<input name="full_name" maxlength="255" required></label></div><div class="field"><label>Email<input name="email" type="email" maxlength="254" required autocomplete="off" placeholder="client@example.com"></label></div><div class="field"><label>Временный пароль<input name="password" type="password" minlength="10" maxlength="72" required autocomplete="new-password"></label><small>Клиент сможет заменить его через «Забыли пароль?»</small></div><div class="field"><label>Роль<select name="role"><option value="store_admin">Клиент магазина</option><option value="operator">Оператор: накладные и Excel</option></select></label></div><div class="form-error" role="alert"></div><button class="btn primary" type="submit">Создать аккаунт</button></form>`);}
function storeModal(){openModal('Новый магазин',`<form id="store-form"><div class="field"><label>Название магазина<input name="name" minlength="2" maxlength="255" required placeholder="Например, Магазин у дома"></label></div><div class="field"><label>Адрес<input name="address" maxlength="500"></label></div><div class="field"><label>Телефон<input name="phone" maxlength="50"></label></div><div class="field"><label>ИИН / БИН<input name="inn" maxlength="20"></label></div><div class="form-error" role="alert"></div><button class="btn primary" type="submit">Создать магазин</button></form>`);}
async function settings(){const data=await api('/settings/');document.querySelector('#content').innerHTML=head('Настройки','Подключение распознавания и правила работы магазина.')+`<div class="card"><div class="card-title"><h3>Mistral OCR</h3>${badge(data.ocr_configured?'confirmed':'error')}</div><div class="card-body"><p>${data.ocr_configured?'Распознавание настроено на сервере.':'Владелец сервиса должен добавить ключ Mistral на сервере.'}</p><p class="muted">До ${data.max_upload_mb} МБ и ${data.max_pages} страниц на документ. Неуверенные совпадения требуют ручной проверки.</p><p class="notice">${esc(data.export_note)}</p></div></div>`;}

document.addEventListener('click',async event=>{
  const button=event.target.closest('button');if(!button || button.disabled)return;
  if(button.dataset.page){await navigate(button.dataset.page);return;}
  const action=button.dataset.action,id=button.dataset.id;if(!action)return;
  try {
    if(action==='close'){closeModal();return;}
    if(action==='forgot-password'){authView('forgot');return;}
    if(action==='back-login'){authView();return;}
    if(action==='add-store'){storeModal();return;}
    if(action==='upload'){uploadModal();return;}
    if(action==='catalog-import'){catalogModal();return;}
    if(action==='add-user'){userModal();return;}
    if(action==='telegram-bind'){telegramModal(button);return;}
    if(action==='pick-product'){modal.querySelector('[name=product_id]').value=id;document.querySelectorAll('.result').forEach(b=>b.classList.toggle('selected',b===button));return;}
    button.disabled=true;
    if(action==='logout'){await api('/auth/logout',{method:'POST'});selectedStore='';sessionStorage.removeItem('store');authView();}
    if(action==='document')await showDocument(id);
    if(action==='process'){await api(`/documents/${id}/process`,{method:'POST'});await showDocument(id);}
    if(action==='confirm'){if(document.querySelector('[data-dirty]'))throw new Error('Сначала сохраните изменённые строки');await api(`/documents/${id}/confirm`,{method:'POST'});toast('Накладная проверена. Можно скачать Excel.');await showDocument(id);}
    if(action==='export'){if(document.querySelector('[data-dirty]'))throw new Error('Сначала сохраните исправления и подтвердите накладную заново');await download(`/documents/${id}/export`,`invoice-${id}.xlsx`);}
    if(action==='telegram-unbind'){await api(`/users/${id}/bind-telegram`,{method:'DELETE'});closeModal();toast('Telegram отключён');await users();}
    if(action==='template')await download('/products/template','catalog-template.xlsx');
    if(action==='add-row')await addRow();
    if(action==='delete-row')deleteRow(id);
    if(action==='choose-product'){requireSavedRows();await chooseProduct(id);}
    if(action==='save-row'){const row=button.closest('[data-row]');const pending=Array.from(document.querySelectorAll('[data-dirty]')).filter(r=>r!==row).map(r=>({id:r.dataset.row,quantity:r.querySelector('[data-quantity]').value,price:r.querySelector('[data-price]').value}));const quantity=row.querySelector('[data-quantity]').value,price=row.querySelector('[data-price]').value;if(!quantity || !price)throw new Error('Заполните количество и цену');await api(`/documents/${currentDoc}/items/${id}`,{method:'PUT',body:JSON.stringify({quantity,price})});toast('Строка сохранена');await showDocument(currentDoc);for(const edit of pending){const r=document.querySelector(`[data-row="${edit.id}"]`);if(r){r.querySelector('[data-quantity]').value=edit.quantity;r.querySelector('[data-price]').value=edit.price;r.dataset.dirty='true';}}}
    if(action==='catalog-next'){catalogOffset+=50;await products();}
    if(action==='catalog-prev'){catalogOffset=Math.max(0,catalogOffset-50);await products();}
  }catch(e){toast(e.message);}finally{button.disabled=false;}
});
document.addEventListener('submit',async event=>{
  event.preventDefault();const form=event.target,button=form.querySelector('[type=submit]');const data=new FormData(form);if(button)button.disabled=true;
  const error=form.querySelector('.form-error') || document.querySelector('#auth-error');if(error)error.innerHTML='';
  try {
    if(form.id==='auth-form'){const result=await api('/auth/login',{method:'POST',body:JSON.stringify(Object.fromEntries(data))});user=result.user;selectedStore='';sessionStorage.removeItem('store');shell();await openLanding();}
    if(form.id==='forgot-form'){const result=await api('/auth/forgot-password',{method:'POST',body:JSON.stringify(Object.fromEntries(data))});form.innerHTML=`<div class="notice">${esc(result.message)}</div>`;}
    if(form.id==='reset-form'){if(data.get('password')!==data.get('password_confirm'))throw new Error('Пароли не совпадают');await api('/auth/reset-password',{method:'POST',body:JSON.stringify({token:data.get('token'),password:data.get('password')})});history.replaceState({},'',location.pathname);authView();toast('Пароль изменён. Войдите с новым паролем.');}
    if(form.id==='store-form'){const created=await api('/stores/',{method:'POST',body:JSON.stringify(Object.fromEntries(data))});selectedStore=String(created.id);sessionStorage.setItem('store',selectedStore);closeModal();shell();await navigate('users');toast('Магазин создан. Теперь добавьте аккаунт клиента.');}
    if(form.id==='upload-form'){const doc=await api('/documents/upload',{method:'POST',body:data});closeModal();try{await api(`/documents/${doc.id}/process`,{method:'POST'});}catch(e){toast(e.message);}await showDocument(doc.id);}
    if(form.id==='catalog-form'){const result=await api('/products/import',{method:'POST',body:data});closeModal();toast(`Загружено товаров: ${result.imported}`);catalogOffset=0;await navigate('products');}
    if(form.id==='catalog-search'){catalogOffset=0;await products(data.get('search'));}
    if(form.id==='add-row-form'){
      if(!data.get('product_id'))throw new Error('Выберите товар из списка');
      await api(`/documents/${form.dataset.document}/items`,{method:'POST',body:JSON.stringify({product_id:Number(data.get('product_id')),quantity:data.get('quantity'),price:data.get('price')})});
      closeModal();toast('Строка добавлена. Проверьте накладную заново.');await showDocument(form.dataset.document);
    }
    if(form.id==='delete-row-form'){
      await api(`/documents/${form.dataset.document}/items/${form.dataset.item}`,{method:'DELETE'});
      closeModal();toast('Строка удалена. Итог пересчитан.');await showDocument(form.dataset.document);
    }
    if(form.id==='match-form'){if(!data.get('product_id'))throw new Error('Выберите товар из списка');await api(`/documents/${currentDoc}/items/${form.dataset.item}`,{method:'PUT',body:JSON.stringify({product_id:Number(data.get('product_id')),create_alias:data.has('create_alias')})});closeModal();toast('Товар выбран');await showDocument(currentDoc);}
    if(form.id==='telegram-form'){await api(`/users/${form.dataset.user}/bind-telegram?chat_id=${encodeURIComponent(data.get('chat_id'))}`,{method:'POST'});closeModal();toast('Telegram подключён');await users();}
    if(form.id==='user-form'){await api('/auth/register',{method:'POST',body:JSON.stringify({...Object.fromEntries(data),store_id:Number(selectedStore)||user.store_id})});closeModal();toast('Аккаунт сотрудника создан');await users();}
  }catch(e){if(error){error.className='error form-error';error.textContent=e.message;}else toast(e.message);}finally{if(button)button.disabled=false;}
});
let searchTimer=null;
document.addEventListener('input',event=>{
  if(event.target.matches('[data-quantity],[data-price]'))event.target.closest('[data-row]').dataset.dirty='true';
  if(event.target.id==='product-search'){clearTimeout(searchTimer);const value=event.target.value;searchTimer=setTimeout(async()=>{try{const result=await api('/products/?limit=20&search='+encodeURIComponent(value));if(document.querySelector('#product-search')?.value===value)renderCandidates(result.items);}catch(e){toast(e.message);}},250);}
});
document.addEventListener('change',async event=>{if(event.target.id==='store-select'){selectedStore=event.target.value;sessionStorage.setItem('store',selectedStore);document.querySelector('#store-label').textContent=event.target.selectedOptions[0].textContent;await navigate('dashboard');}});
(async()=>{localStorage.removeItem('token');const resetToken=new URLSearchParams(location.search).get('reset_token');if(resetToken){authView('reset');return;}try{user=await api('/auth/me');shell();await openLanding();}catch{authView();}})();
