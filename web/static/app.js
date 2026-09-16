'use strict';
const app = document.querySelector('#app');
const modal = document.querySelector('#modal');
let user = null, page = 'dashboard', selectedStore = sessionStorage.getItem('store') || '', timer = null, currentDoc = null, previewUrl = null, catalogOffset = 0;
const labels = {received:'Загружена',retry_pending:'В очереди',processing:'Распознаём',needs_review:'Нужна проверка',recognized:'Распознана',confirmed:'Проверена',error:'Ошибка',matched:'Совпадение',manual:'Подтверждено',not_found:'Выберите товар',pending:'Ожидает'};
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const money = value => value == null ? '—' : Number(value).toLocaleString('ru-RU',{minimumFractionDigits:2,maximumFractionDigits:2});
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
function authView(signup=false) {
  clearTimeout(timer); user=null; page='auth';
  app.innerHTML=`<div class="auth-layout"><section class="auth-story"><div class="brand"><span class="mark">≡</span>Накладная</div><h1>От фото<br>до порядка<br>в вашей 1С.</h1><p>Распознайте накладную, сверьте товары с каталогом магазина и сохраните готовый Excel.</p><div class="flow"><span>01 &nbsp; Фото или скан документа</span><span>02 &nbsp; Точные названия из вашей базы</span><span>03 &nbsp; Проверка и выгрузка в Excel</span></div></section><section class="auth-panel"><div class="auth-box"><div class="eyebrow">Рабочее пространство магазина</div><h2>${signup?'Подключить магазин':'С возвращением'}</h2><p class="muted">${signup?'Создайте отдельный аккаунт для вашего магазина.':'Войдите, чтобы продолжить работу с накладными.'}</p><form id="auth-form" data-signup="${signup}">${signup?'<div class="field"><label for="store-name">Название магазина</label><input id="store-name" name="store_name" required minlength="2" maxlength="255" autocomplete="organization" placeholder="Например, Магазин у дома"></div>':''}<div class="field"><label for="username">Логин</label><input id="username" name="username" required minlength="3" maxlength="100" pattern="[a-zA-Z0-9_.@\-]+" autocomplete="username" placeholder="Латинские буквы или email"></div><div class="field"><label for="password">Пароль</label><input id="password" type="password" name="password" required ${signup?'minlength="10"':''} maxlength="72" autocomplete="${signup?'new-password':'current-password'}">${signup?'<small>От 10 символов</small>':''}</div><div id="auth-error" role="alert"></div><button class="btn primary" type="submit">${signup?'Создать магазин':'Войти в аккаунт'} <span>→</span></button></form><div class="auth-switch">${signup?'Уже есть аккаунт?':'Первый раз здесь?'} <button class="link" data-action="auth-switch" data-signup="${!signup}">${signup?'Войти':'Подключить магазин'}</button></div><p class="auth-note">Документы и каталог доступны только сотрудникам вашего магазина.</p></div></section></div>`;
}
function shell() {
  const admin=['super_admin','store_admin'].includes(user.role);
  app.innerHTML=`<div class="shell"><aside class="sidebar"><div><div class="brand"><span class="mark">≡</span>Накладная</div><small>Порядок начинается с документа</small></div><nav class="nav" aria-label="Основное меню"><button data-page="dashboard"><span class="nav-icon">◫</span>Обзор</button><button data-page="documents"><span class="nav-icon">▤</span>Накладные</button><button data-page="products"><span class="nav-icon">▦</span>Каталог 1С</button>${admin?'<button data-page="users"><span class="nav-icon">♧</span>Команда</button><button data-page="settings"><span class="nav-icon">⚙</span>Настройки</button>':''}</nav><div class="sidebar-bottom"><small>Ваш аккаунт</small><span>${esc(user.full_name || user.username)}</span><button data-action="logout">Выйти из аккаунта ↗</button></div></aside><div class="workspace"><header class="topbar"><span id="store-label">Рабочее пространство</span><div class="actions">${user.role==='super_admin'?'<select id="store-select" class="store-select" aria-label="Выбрать магазин"><option value="">Выберите магазин</option></select>':''}<button class="btn small" data-action="logout" aria-label="Выйти">Выйти</button><span class="avatar">${esc(user.username.slice(0,2).toUpperCase())}</span></div></header><main id="content" class="content"></main></div></div>`;
  api('/stores/').then(stores=>{const store=stores.find(s=>s.id===(Number(selectedStore)||user.store_id));document.querySelector('#store-label').textContent=store?.name || 'Выберите магазин';const select=document.querySelector('#store-select');if(select){for(const s of stores){const o=new Option(s.name,s.id);select.add(o);}select.value=selectedStore;}}).catch(e=>toast(e.message));
}
const head=(title,subtitle,actions='')=>`<div class="page-head"><div><div class="eyebrow">Ваш магазин · каждый день проще</div><h1>${esc(title)}</h1><p>${esc(subtitle)}</p></div><div class="actions">${actions}</div></div>`;
const empty=(title,text,button='')=>`<div class="empty"><div class="symbol">▤</div><h3>${esc(title)}</h3><p>${esc(text)}</p>${button}</div>`;
async function navigate(next) {
  clearTimeout(timer);page=next;currentDoc=null;
  document.querySelectorAll('[data-page]').forEach(b=>b.classList.toggle('active',b.dataset.page===next));
  const content=document.querySelector('#content');content.innerHTML='<p class="loading">Загрузка…</p>';
  if(user.role==='super_admin' && !selectedStore){content.innerHTML=head('Магазины','Выберите магазин в верхнем меню, чтобы открыть его рабочее пространство.');return;}
  try {await ({dashboard:dashboard,documents:documents,products:products,users:users,settings:settings}[next] || dashboard)();}
  catch(e){if(page!=='auth')content.innerHTML=`<div class="error">${esc(e.message)}</div>`;}
}
async function dashboard() {
  const data=await api('/stats/dashboard');
  document.querySelector('#content').innerHTML=head('Рабочий день без ручного ввода','Все накладные и товары магазина — в одном месте.','<button class="btn primary" data-action="upload">＋ Новая накладная</button>')+`<div class="metrics">${[['Все накладные',data.documents,'В вашем пространстве'],['Ждут проверки',data.needs_review,'Сверьте перед выгрузкой'],['Проверены',data.confirmed,'Готовы к Excel'],['Товары в каталоге',data.catalog,'Названия из вашей 1С']].map(([title,value,note])=>`<div class="metric"><strong>${title}</strong><div class="value">${value}</div><p>${note}</p></div>`).join('')}</div><div class="hero"><div><div class="eyebrow">От документа к результату</div><h2>Фотографируйте накладную.<br>Остальное — здесь.</h2><p>Распознавание через Mistral и сопоставление с вашим каталогом. Вы проверяете результат и получаете Excel для загрузки в 1С.</p><button class="btn primary" data-action="${data.catalog?'upload':'catalog-import'}">${data.catalog?'Загрузить накладную →':'Начать с каталога →'}</button></div><div class="steps"><div class="step"><b>1</b><span>Загрузите каталог товаров из 1С</span></div><div class="step"><b>2</b><span>Добавьте фото или PDF накладной</span></div><div class="step"><b>3</b><span>Проверьте товары и скачайте Excel</span></div></div></div><div class="card"><div class="card-title"><h3>Последние накладные</h3><button class="btn small" data-page="documents">Все документы →</button></div><div id="recent"></div></div>`;
  const docs=await api('/documents/?limit=5');document.querySelector('#recent').innerHTML=documentTable(docs.items);
}
function documentTable(items) {return items.length?`<div class="table-wrap"><table><thead><tr><th>Документ</th><th>Поставщик</th><th>Статус</th><th>Строк</th><th>Добавлен</th><th></th></tr></thead><tbody>${items.map(d=>`<tr><td><b>Накладная #${d.id}</b></td><td>${esc(d.supplier || 'Не указан')}</td><td>${badge(d.status)}</td><td>${d.total_items}</td><td>${date(d.created_at)}</td><td><button class="btn small" data-action="document" data-id="${d.id}">Открыть →</button></td></tr>`).join('')}</tbody></table></div>`:empty('Здесь появятся ваши накладные','Загрузите первый документ — фото с телефона или скан в PDF.','<button class="btn" data-action="upload">Загрузить документ</button>');}
async function documents() {const data=await api('/documents/?limit=200');document.querySelector('#content').innerHTML=head('Накладные','Загрузка, распознавание и проверка перед выгрузкой.','<button class="btn primary" data-action="upload">＋ Новая накладная</button>')+`<div class="card">${documentTable(data.items)}</div>`;if(data.items.some(d=>['processing','retry_pending'].includes(d.status)))timer=setTimeout(()=>{if(page==='documents')documents().catch(e=>toast(e.message));},3000);}
function uploadModal() {openModal('Новая накладная',`<form id="upload-form"><div class="file-drop"><label for="invoice-file">Фото с телефона или скан документа</label><input id="invoice-file" name="file" type="file" accept="image/jpeg,image/png,image/webp,application/pdf" required><small>JPG, PNG, WebP или PDF · до 20 МБ · до 30 страниц</small></div><div class="field"><label for="supplier">Поставщик (необязательно)</label><input id="supplier" name="supplier" maxlength="500" placeholder="Название поставщика"></div><p class="muted">Файл отправляется в Mistral для распознавания. Результат можно проверить и исправить перед выгрузкой.</p><div class="form-error" role="alert"></div><button class="btn primary" type="submit">Загрузить и распознать →</button></form>`);}
async function showDocument(id) {
  clearTimeout(timer);page='detail';currentDoc=Number(id);
  const data=await api(`/documents/${id}`), d=data.document, items=data.items;
  if(currentDoc!==Number(id))return;
  const busy=['processing','retry_pending'].includes(d.status);
  const total=items.reduce((sum,i)=>sum+Number(i.total || 0),0);
  document.querySelector('#content').innerHTML=head(`Накладная #${id}`,`${d.supplier || 'Поставщик не указан'} · ${date(d.created_at)}`,'<button class="btn" data-page="documents">← К списку</button>')+`${d.error_message?`<div class="error">${esc(d.error_message)}</div>`:''}${busy?'<div class="notice">Распознаём документ через Mistral. Можно закрыть страницу — обработка продолжится на сервере.</div>':''}<div class="split"><aside class="card preview"><div class="card-title"><h3>Оригинал</h3>${badge(d.status)}</div><div class="card-body" id="preview"><p class="muted">Загружаем документ…</p></div></aside><section class="card"><div class="card-title"><div><h3>Проверьте товары</h3><small class="muted">Название в Excel будет точно как в каталоге 1С</small></div><span class="badge">${items.length} строк</span></div>${items.length?`<div class="table-wrap"><table class="review-table"><thead><tr><th>Товар из каталога / в накладной</th><th>Кол-во</th><th>Цена</th><th>Сумма</th><th></th></tr></thead><tbody>${items.map(i=>`<tr data-row="${i.id}"><td><button class="product-button" data-action="choose-product" data-id="${i.id}">${esc(i.product_name || i.ocr_text)}</button><span class="ocr">В документе: ${esc(i.ocr_text)}</span>${badge(i.match_status)}</td><td><input aria-label="Количество, строка ${i.row_number}" data-quantity type="number" min="0.001" step="0.001" value="${esc(i.quantity ?? '')}"></td><td><input aria-label="Цена, строка ${i.row_number}" data-price type="number" min="0" step="0.01" value="${esc(i.price ?? '')}"></td><td class="number">${money(i.total)}</td><td><button class="btn small" data-action="save-row" data-id="${i.id}">Сохранить</button></td></tr>`).join('')}</tbody></table></div><div class="review-footer"><span>Итого: <b class="number">${money(total)}</b></span><div class="actions"><button class="btn" data-action="confirm" data-id="${id}">✓ Всё проверено</button><button class="btn primary" data-action="export" data-id="${id}" ${d.status!=='confirmed'?'disabled':''}>Скачать Excel ↓</button></div></div>`:empty(busy?'Документ обрабатывается':'Документ готов к распознаванию',busy?'Товары появятся здесь после обработки.':'Запустите OCR, чтобы получить строки накладной.',!busy?`<button class="btn primary" data-action="process" data-id="${id}">${d.status==='error'?'Повторить распознавание':'Распознать документ'}</button>`:'')}</section></div><p class="muted">Сначала выберите товары для спорных строк, сохраните исправления и нажмите «Всё проверено». Excel предназначен для загрузки через обработку импорта вашей конфигурации 1С.</p>`;
  const image=await request(`/documents/${id}/image`);const blob=await image.blob();
  if(previewUrl)URL.revokeObjectURL(previewUrl);previewUrl=URL.createObjectURL(blob);
  if(currentDoc===Number(id)){const preview=document.querySelector('#preview');preview.innerHTML=d.file_type==='.pdf'?`<iframe title="Оригинал накладной" src="${previewUrl}"></iframe>`:`<img alt="Оригинал накладной" src="${previewUrl}">`;}
  if(busy)timer=setTimeout(()=>{if(currentDoc===Number(id))showDocument(id).catch(e=>toast(e.message));},3000);
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
async function users(){const data=await api('/users/');document.querySelector('#content').innerHTML=head('Команда магазина','Каждый сотрудник входит под своим аккаунтом.','<button class="btn primary" data-action="add-user">＋ Добавить сотрудника</button>')+`<div class="card"><div class="table-wrap"><table><thead><tr><th>Сотрудник</th><th>Логин</th><th>Роль</th><th>Статус</th></tr></thead><tbody>${data.map(u=>`<tr><td>${esc(u.full_name || '—')}</td><td>${esc(u.username)}</td><td>${esc({super_admin:'Владелец сервиса',store_admin:'Администратор',operator:'Оператор'}[u.role])}</td><td>${u.is_active?'Активен':'Отключён'}</td></tr>`).join('')}</tbody></table></div></div>`;}
function userModal(){openModal('Новый сотрудник',`<form id="user-form"><div class="field"><label>Имя<input name="full_name" maxlength="255" required></label></div><div class="field"><label>Логин<input name="username" minlength="3" maxlength="100" pattern="[a-zA-Z0-9_.@\-]+" required autocomplete="off"></label></div><div class="field"><label>Пароль<input name="password" type="password" minlength="10" maxlength="72" required autocomplete="new-password"></label></div><div class="field"><label>Роль<select name="role"><option value="operator">Оператор: накладные и Excel</option><option value="store_admin">Администратор: каталог и команда</option></select></label></div><div class="form-error" role="alert"></div><button class="btn primary" type="submit">Создать аккаунт</button></form>`);}
async function settings(){const data=await api('/settings/');document.querySelector('#content').innerHTML=head('Настройки','Подключение распознавания и правила работы магазина.')+`<div class="card"><div class="card-title"><h3>Mistral OCR</h3>${badge(data.ocr_configured?'confirmed':'error')}</div><div class="card-body"><p>${data.ocr_configured?'Распознавание настроено на сервере.':'Владелец сервиса должен добавить ключ Mistral на сервере.'}</p><p class="muted">До ${data.max_upload_mb} МБ и ${data.max_pages} страниц на документ. Неуверенные совпадения требуют ручной проверки.</p><p class="notice">${esc(data.export_note)}</p></div></div>`;}

document.addEventListener('click',async event=>{
  const button=event.target.closest('button');if(!button || button.disabled)return;
  if(button.dataset.page){await navigate(button.dataset.page);return;}
  const action=button.dataset.action,id=button.dataset.id;if(!action)return;
  try {
    if(action==='close'){closeModal();return;}
    if(action==='auth-switch'){authView(button.dataset.signup==='true');return;}
    if(action==='upload'){uploadModal();return;}
    if(action==='catalog-import'){catalogModal();return;}
    if(action==='add-user'){userModal();return;}
    if(action==='pick-product'){document.querySelector('#match-form [name=product_id]').value=id;document.querySelectorAll('.result').forEach(b=>b.classList.toggle('selected',b===button));return;}
    button.disabled=true;
    if(action==='logout'){await api('/auth/logout',{method:'POST'});selectedStore='';sessionStorage.removeItem('store');authView();}
    if(action==='document')await showDocument(id);
    if(action==='process'){await api(`/documents/${id}/process`,{method:'POST'});await showDocument(id);}
    if(action==='confirm'){if(document.querySelector('[data-dirty]'))throw new Error('Сначала сохраните изменённые строки');await api(`/documents/${id}/confirm`,{method:'POST'});toast('Накладная проверена. Можно скачать Excel.');await showDocument(id);}
    if(action==='export'){if(document.querySelector('[data-dirty]'))throw new Error('Сначала сохраните исправления и подтвердите накладную заново');await download(`/documents/${id}/export`,`invoice-${id}.xlsx`);}
    if(action==='template')await download('/products/template','catalog-template.xlsx');
    if(action==='choose-product')await chooseProduct(id);
    if(action==='save-row'){const row=button.closest('[data-row]');const quantity=row.querySelector('[data-quantity]').value,price=row.querySelector('[data-price]').value;if(!quantity || !price)throw new Error('Заполните количество и цену');await api(`/documents/${currentDoc}/items/${id}`,{method:'PUT',body:JSON.stringify({quantity,price})});toast('Строка сохранена');await showDocument(currentDoc);}
    if(action==='catalog-next'){catalogOffset+=50;await products();}
    if(action==='catalog-prev'){catalogOffset=Math.max(0,catalogOffset-50);await products();}
  }catch(e){toast(e.message);}finally{button.disabled=false;}
});
document.addEventListener('submit',async event=>{
  event.preventDefault();const form=event.target,button=form.querySelector('[type=submit]');const data=new FormData(form);if(button)button.disabled=true;
  const error=form.querySelector('.form-error') || document.querySelector('#auth-error');if(error)error.innerHTML='';
  try {
    if(form.id==='auth-form'){const signup=form.dataset.signup==='true';const result=await api(`/auth/${signup?'signup':'login'}`,{method:'POST',body:JSON.stringify(Object.fromEntries(data))});user=result.user;selectedStore='';sessionStorage.removeItem('store');shell();await navigate('dashboard');}
    if(form.id==='upload-form'){const doc=await api('/documents/upload',{method:'POST',body:data});closeModal();try{await api(`/documents/${doc.id}/process`,{method:'POST'});}catch(e){toast(e.message);}await showDocument(doc.id);}
    if(form.id==='catalog-form'){const result=await api('/products/import',{method:'POST',body:data});closeModal();toast(`Загружено товаров: ${result.imported}`);catalogOffset=0;await navigate('products');}
    if(form.id==='catalog-search'){catalogOffset=0;await products(data.get('search'));}
    if(form.id==='match-form'){if(!data.get('product_id'))throw new Error('Выберите товар из списка');await api(`/documents/${currentDoc}/items/${form.dataset.item}`,{method:'PUT',body:JSON.stringify({product_id:Number(data.get('product_id')),create_alias:data.has('create_alias')})});closeModal();toast('Товар выбран');await showDocument(currentDoc);}
    if(form.id==='user-form'){await api('/auth/register',{method:'POST',body:JSON.stringify({...Object.fromEntries(data),store_id:Number(selectedStore)||user.store_id})});closeModal();toast('Аккаунт сотрудника создан');await users();}
  }catch(e){if(error){error.className='error form-error';error.textContent=e.message;}else toast(e.message);}finally{if(button)button.disabled=false;}
});
let searchTimer=null;
document.addEventListener('input',event=>{
  if(event.target.matches('[data-quantity],[data-price]'))event.target.closest('[data-row]').dataset.dirty='true';
  if(event.target.id==='product-search'){clearTimeout(searchTimer);const value=event.target.value;searchTimer=setTimeout(async()=>{try{const result=await api('/products/?limit=20&search='+encodeURIComponent(value));if(document.querySelector('#product-search')?.value===value)renderCandidates(result.items);}catch(e){toast(e.message);}},250);}
});
document.addEventListener('change',async event=>{if(event.target.id==='store-select'){selectedStore=event.target.value;sessionStorage.setItem('store',selectedStore);document.querySelector('#store-label').textContent=event.target.selectedOptions[0].textContent;await navigate('dashboard');}});
(async()=>{localStorage.removeItem('token');try{user=await api('/auth/me');shell();await navigate('dashboard');}catch{authView();}})();
