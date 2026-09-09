// Django owns persisted records and all financial totals. This state is a display cache.
let state = JSON.parse(document.getElementById('initial-state').textContent);
let editingInvoice = null, currentFilter = 'all', previewId = null;
const $ = id => document.getElementById(id);
const field = (form, name) => $(form).elements.namedItem(name);
const today = () => new Date().toLocaleDateString('en-CA');
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
// Integer hundredths keep even the unsaved preview free of floating-point money arithmetic.
function cents(value) {
  const match = String(value || '0').match(/^(\d+)(?:\.(\d{0,2}))?$/);
  if (!match) throw new Error('Enter a non-negative number with at most two decimal places.');
  return BigInt(match[1]) * 100n + BigInt((match[2] || '').padEnd(2, '0'));
}
function decimal(value) { return `${value / 100n}.${String(value % 100n).padStart(2, '0')}`; }
function money(value) {
  const amount = cents(value), whole = String(amount / 100n).replace(/\B(?=(\d{3})+(?!\d))/g, ',');
  return `${state.settings.currency === 'USD' ? '$' : 'R'}${whole}.${String(amount % 100n).padStart(2, '0')}`;
}
function reportError(error) { alert(error.message || String(error)); }
async function api(url, method = 'GET', data) {
  const options = {method, headers: {'X-CSRFToken': document.querySelector('#csrfForm input').value}};
  if (data instanceof FormData) options.body = data;
  else if (data !== undefined) { options.headers['Content-Type'] = 'application/json'; options.body = JSON.stringify(data); }
  const response = await fetch(url, options);
  if (response.redirected && response.url.includes('/accounts/login/')) { location.href = response.url; throw new Error('Please log in again.'); }
  const result = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(result.errors ? JSON.stringify(result.errors) : `Request failed (${response.status}).`);
  return result;
}
async function refresh() { state = await api('/api/state/'); render(); syncSidebar(); }
function closeModal(id) { $(id).classList.remove('open'); }
function showPage(id) {
  document.documentElement.classList.toggle('dashboard-view', id === 'dashboard');
  document.querySelectorAll('.page').forEach(p => p.classList.toggle('active', p.id === id));
  document.querySelectorAll('.nav button[data-page]').forEach(b => b.classList.toggle('active', b.dataset.page === id));
  $('pageTitle').textContent = {dashboard:'Dashboard',invoices:'Invoices',create:'Create Invoice',customers:'Customers',payments:'Payments',reports:'Reports',profile:'Business Profile',settings:'Settings'}[id];
  $('nav').classList.remove('open');
  if (id === 'reports') renderReports();
}
document.querySelectorAll('.nav button[data-page]').forEach(b => b.onclick = () => b.dataset.page === 'create' ? newInvoice() : showPage(b.dataset.page));
$('menu').onclick = () => $('nav').classList.toggle('open');
const statusOf = invoice => invoice.status;
function invoiceRow(i, compact = false) {
  const c = state.customers.find(c => c.id === i.customer) || {};
  const actions = `<button class="icon-btn" title="Preview" onclick="previewInvoice(${i.id})">◉</button>` + (compact ? '' :
    `<button class="icon-btn" title="Edit" onclick="editInvoice(${i.id})">✎</button><button class="icon-btn" title="Duplicate" onclick="duplicateInvoice(${i.id})">⧉</button>` +
    (['Unpaid','Overdue'].includes(i.status) ? `<button class="icon-btn" title="Record payment" onclick="openPayment(${i.id})">R</button>` : '') +
    (i.status === 'Draft' ? `<button class="icon-btn" title="Mark sent / unpaid" onclick="invoiceAction(${i.id},'sent')">Send</button>` : '') +
    (['Draft','Unpaid','Overdue'].includes(i.status) && cents(i.amount_paid) === 0n ? `<button class="icon-btn" title="Cancel invoice" onclick="invoiceAction(${i.id},'cancel')">Cancel</button>` : '') +
    `<button class="icon-btn" title="Delete" onclick="deleteInvoice(${i.id})">×</button>`);
  return `<tr><td><b>${esc(i.number)}</b></td><td>${esc(c.business || c.name)}</td><td>${esc(i.date)}</td><td>${esc(i.due)}</td><td>${money(i.total)}</td>${compact ? '' : `<td>${money(i.balance_due)}</td>`}<td><span class="status ${i.status.toLowerCase()}">${i.status}</span></td><td><div class="actions">${actions}</div></td></tr>`;
}
const empty = (columns, message) => `<tr><td colspan="${columns}" class="empty">${message}</td></tr>`;
function cards(values) { return values.map(([label, value, note]) => `<div class="stat"><div class="label">${esc(label)}</div><strong>${esc(value)}</strong><span>${esc(note || '')}</span></div>`).join(''); }
function render() {
  const s = state.summary;
  $('stats').innerHTML = cards([['Total invoices',s.invoice_count,'All invoices created'],['Total paid',money(s.received),'Payments received'],['Total outstanding',money(s.outstanding),'Awaiting payment'],['Overdue invoices',money(s.overdue),'Requires attention']]);
  $('recentBody').innerHTML = state.invoices.slice(-5).reverse().map(i => invoiceRow(i,true)).join('') || empty(7, '<div class="recent-empty"><div class="recent-empty-icon">▤</div><h4>No invoices yet</h4><p>Create your first invoice and start tracking payments.</p><button class="btn" onclick="newInvoice()">Create Invoice</button></div>');
  renderInvoices(); renderCustomers(); renderPayments();
  if ($('reports').classList.contains('active')) renderReports();
  fillSelects();
}
let invoiceRequest = 0, customerRequest = 0, paymentRequest = 0, reportRequest = 0;
async function renderInvoices() {
  const sequence = ++invoiceRequest;
  try {
    const query = new URLSearchParams({q:$('invoiceSearch').value, status:currentFilter === 'all' ? '' : currentFilter, start:$('invoiceStart').value, end:$('invoiceEnd').value});
    const result = await api('/api/invoices/?' + query);
    if (sequence === invoiceRequest) $('invoiceBody').innerHTML = result.invoices.reverse().map(i => invoiceRow(i)).join('') || empty(8,'No matching invoices.');
  } catch (e) { reportError(e); }
}
async function renderCustomers() {
  const sequence = ++customerRequest;
  try {
    const result = await api('/api/customers/?q=' + encodeURIComponent($('customerSearch').value));
    if (sequence !== customerRequest) return;
    $('customerBody').innerHTML = result.customers.map(c => `<tr><td><b>${esc(c.name)}</b></td><td>${esc(c.business)}</td><td>${esc(c.email)}</td><td>${esc(c.phone)}</td><td>${esc(c.address)}</td><td><div class="actions"><button class="icon-btn" title="View history" onclick="customerHistory(${c.id})">◉</button><button class="icon-btn" title="Edit" onclick="openCustomer(${c.id})">✎</button><button class="icon-btn" title="Delete" onclick="deleteCustomer(${c.id})">×</button></div></td></tr>`).join('') || empty(6,'No matching customers.');
  } catch (e) { reportError(e); }
}
async function renderPayments() {
  const sequence = ++paymentRequest;
  try {
    const query = new URLSearchParams({q:$('paymentSearch').value,method:$('paymentMethod').value,start:$('paymentStart').value,end:$('paymentEnd').value});
    const result = await api('/api/payments/?' + query);
    if (sequence !== paymentRequest) return;
    $('paymentBody').innerHTML = result.payments.reverse().map(p => {
      const i = state.invoices.find(i => i.id === p.invoice) || {}, c = state.customers.find(c => c.id === i.customer) || {};
      return `<tr><td>${esc(p.date)}</td><td>${esc(i.number)}</td><td>${esc(c.business || c.name)}</td><td>${esc(p.method)}<br><small>${esc(p.reference)}</small></td><td><b>${money(p.amount)}</b></td></tr>`;
    }).join('') || empty(5,'No matching payments.');
  } catch (e) { reportError(e); }
}
async function renderReports() {
  const sequence = ++reportRequest;
  try {
    const s = await api('/api/reports/?' + new URLSearchParams({start:$('reportStart').value,end:$('reportEnd').value}));
    if (sequence !== reportRequest) return;
    $('reportStats').innerHTML = cards([['Total invoiced',money(s.invoiced)],['Revenue / collected',money(s.received)],['Outstanding',money(s.outstanding)],['Overdue',money(s.overdue)],['Invoice count',s.invoice_count],['Payment count',s.payment_count],['Paid invoices',s.counts.Paid],['Unpaid invoices',s.counts.Unpaid],['Overdue invoices',s.counts.Overdue]]);
    const max = s.monthly.reduce((m,x) => cents(x.amount) > m ? cents(x.amount) : m, 1n);
    $('chart').innerHTML = s.monthly.map(m => `<div class="bar" title="${money(m.amount)}" style="height:${cents(m.amount)*100n/max}%"><span>${esc(m.month)}</span></div>`).join('') || '<p>No payments in this period.</p>';
    $('topCustomers').innerHTML = '<h3>Top customers by invoiced value</h3>' + (s.top_customers.map(c => `<p>${esc(c.name)} <b>${money(c.total)}</b></p>`).join('') || '<p>No invoiced customers in this period.</p>');
  } catch (e) { reportError(e); }
}
function debounce(fn) { let timer; return () => {clearTimeout(timer);timer=setTimeout(fn,200);}; }
['invoiceSearch','invoiceStart','invoiceEnd'].forEach(id => $(id).oninput=debounce(renderInvoices));
$('customerSearch').oninput=debounce(renderCustomers);
['paymentSearch','paymentStart','paymentEnd','paymentMethod'].forEach(id => $(id).oninput=debounce(renderPayments));
document.querySelectorAll('.filter').forEach(b => b.onclick=()=>{document.querySelectorAll('.filter').forEach(x=>x.classList.remove('on'));b.classList.add('on');currentFilter=b.dataset.filter;renderInvoices();});
function fillSelects() {
  const selected=$('invoiceCustomer').value, paidSelected=field('paymentForm','invoice').value;
  $('invoiceCustomer').innerHTML='<option value="">Select customer</option>'+state.customers.map(c=>`<option value="${c.id}">${esc(c.business||c.name)}</option>`).join('');
  $('invoiceCustomer').value=selected;
  field('paymentForm','invoice').innerHTML=state.invoices.filter(i=>['Unpaid','Overdue'].includes(i.status)).map(i=>`<option value="${i.id}">${esc(i.number)} — ${money(i.balance_due)}</option>`).join('');
  if (paidSelected) field('paymentForm','invoice').value=paidSelected;
}
function openCustomer(id) {
  const c=state.customers.find(c=>c.id===id);
  $('customerForm').reset();
  ['id','name','business','email','phone','address','vat_number','notes'].forEach(k=>field('customerForm',k).value=c?.[k]||'');
  $('customerTitle').textContent=c?'Edit Customer':'Add Customer';$('customerModal').classList.add('open');
}
// Disable submitting buttons while a write is pending, preventing accidental double clicks.
function bindForm(id, save) {
  $(id).onsubmit=async e=>{e.preventDefault();const buttons=[...$(id).querySelectorAll('button')];buttons.forEach(b=>b.disabled=true);try{await save();}catch(e){reportError(e);}finally{buttons.forEach(b=>b.disabled=false);}};
}
bindForm('customerForm',async()=>{const d=Object.fromEntries(new FormData($('customerForm'))),id=d.id;d.company_name=d.business;await api('/api/customers/'+(id?id+'/':''),'POST',d);await refresh();closeModal('customerModal');});
async function deleteCustomer(id) { if(confirm('Delete this customer?'))try{await api(`/api/customers/${id}/`,'DELETE');await refresh();}catch(e){reportError(e);} }
async function customerHistory(id) {
  try {
    const c=await api(`/api/customers/${id}/`);
    const dialog=document.createElement('div');dialog.className='modal open';
    dialog.innerHTML=`<div class="dialog wide"><div class="dialog-head"><h2>${esc(c.business||c.name)}</h2><button class="close">×</button></div><p>${esc(c.email)} · ${esc(c.phone)}</p><p>${esc(c.address)}</p><p>VAT: ${esc(c.vat_number)}</p><p>${esc(c.notes)}</p><h3>Invoice history</h3><div class="table-wrap"><table><thead><tr><th>Invoice</th><th>Customer</th><th>Date</th><th>Due</th><th>Total</th><th>Status</th><th>Preview</th></tr></thead><tbody>${c.invoices.map(i=>invoiceRow(i,true)).join('')||empty(7,'No invoices yet.')}</tbody></table></div></div>`;
    dialog.querySelector('.close').onclick=()=>dialog.remove();document.body.append(dialog);
    dialog.querySelectorAll('.icon-btn').forEach(b=>b.addEventListener('click',()=>dialog.remove()));
  }catch(e){reportError(e);}
}
function newInvoice() {
  editingInvoice=null;$('invoiceForm').reset();fillSelects();$('invoiceFormTitle').textContent='Create Invoice';
  $('invoiceNo').value='Assigned when saved';$('invoiceDate').value=today();
  const due=new Date();due.setDate(due.getDate()+30);$('dueDate').value=due.toLocaleDateString('en-CA');
  $('taxRate').value=state.settings.vat;$('discount').value='0';$('bankDetails').value=state.profile.banking;
  $('invoiceNotes').value='';$('invoiceTerms').value=state.settings.terms;$('lines').innerHTML='';addLine();showPage('create');
}
function addLine(item={description:'',quantity:'1',price:'0'}) {
  const row=document.createElement('div');row.className='line-row';
  row.innerHTML=`<input class="desc" required placeholder="Product or service" value="${esc(item.description)}"><input class="qty" aria-label="Quantity" type="number" min=".01" step=".01" required value="${esc(item.quantity)}"><input class="unit" aria-label="Unit price" type="number" min="0" step=".01" required value="${esc(item.price)}"><span class="line-total"></span><button type="button" class="remove" aria-label="Remove item">×</button>`;
  row.querySelectorAll('input').forEach(x=>x.oninput=calculate);row.querySelector('button').onclick=()=>{row.remove();calculate();};$('lines').append(row);calculate();
}
function calculate() {
  try {
    let sub=0n;
    document.querySelectorAll('.line-row').forEach(row=>{const value=(cents(row.querySelector('.qty').value)*cents(row.querySelector('.unit').value)+50n)/100n;sub+=value;row.querySelector('.line-total').textContent=money(decimal(value));});
    const vat=(sub*cents($('taxRate').value)+5000n)/10000n,discount=cents($('discount').value),total=sub+vat-discount;
    $('subtotal').textContent=money(decimal(sub));$('tax').textContent=money(decimal(vat));$('discountView').textContent=money(decimal(discount));$('total').textContent=total<0n?'Discount exceeds total':money(decimal(total));
  } catch(e) { $('total').textContent='Check amounts'; }
}
$('taxRate').oninput=$('discount').oninput=calculate;
let savingInvoice=false;
async function storeInvoice(status) {
  if(savingInvoice || !$('invoiceForm').reportValidity())return;
  savingInvoice=true;
  try {
    const data={customer:$('invoiceCustomer').value,issue_date:$('invoiceDate').value,due_date:$('dueDate').value,status,tax_rate:$('taxRate').value,discount:$('discount').value,banking:$('bankDetails').value,notes:$('invoiceNotes').value,terms:$('invoiceTerms').value,
      items:[...document.querySelectorAll('.line-row')].map(r=>({description:r.querySelector('.desc').value,quantity:r.querySelector('.qty').value,unit_price:r.querySelector('.unit').value}))};
    await api('/api/invoices/'+(editingInvoice?editingInvoice+'/':''),'POST',data);editingInvoice=null;await refresh();showPage('invoices');
  }catch(e){reportError(e);}finally{savingInvoice=false;}
}
bindForm('invoiceForm',()=>storeInvoice('Unpaid'));
function saveDraft(){storeInvoice('Draft');}
function editInvoice(id){const i=state.invoices.find(i=>i.id===id);editingInvoice=id;showPage('create');fillSelects();$('invoiceFormTitle').textContent='Edit Invoice';$('invoiceNo').value=i.number;$('invoiceCustomer').value=i.customer;$('invoiceDate').value=i.date;$('dueDate').value=i.due;$('taxRate').value=i.taxRate;$('discount').value=i.discount;$('bankDetails').value=i.banking;$('invoiceNotes').value=i.notes;$('invoiceTerms').value=i.terms;$('lines').innerHTML='';i.items.forEach(addLine);calculate();}
async function invoiceAction(id,action){try{const i=await api(`/api/invoices/${id}/${action}/`,'POST',{});await refresh();if(action==='duplicate')editInvoice(i.id);}catch(e){reportError(e);}}
function duplicateInvoice(id){invoiceAction(id,'duplicate');}
async function deleteInvoice(id){if(confirm('Delete this invoice? Invoices with recorded payments must be retained.'))try{await api(`/api/invoices/${id}/`,'DELETE');await refresh();}catch(e){reportError(e);}}
function paymentAmount(){const i=state.invoices.find(i=>String(i.id)===field('paymentForm','invoice').value);field('paymentForm','amount').value=i?.balance_due||'';}
function openPayment(id){$('paymentForm').reset();fillSelects();if(id)field('paymentForm','invoice').value=id;if(!field('paymentForm','invoice').options.length)return alert('There are no unpaid invoices.');field('paymentForm','date').value=today();paymentAmount();$('paymentModal').classList.add('open');}
field('paymentForm','invoice').onchange=paymentAmount;
bindForm('paymentForm',async()=>{const d=Object.fromEntries(new FormData($('paymentForm')));await api('/api/payments/','POST',{...d,payment_date:d.date,payment_method:d.method});await refresh();closeModal('paymentModal');});
async function previewInvoice(id){
  try{
    const response=await fetch(`/invoices/${id}/print/`);if(!response.ok)throw new Error('Unable to load invoice.');
    const doc=new DOMParser().parseFromString(await response.text(),'text/html'),paper=doc.getElementById('invoicePaper');if(!paper)throw new Error('Please log in again.');
    $('invoicePaper').innerHTML=paper.innerHTML;previewId=id;
    const i=state.invoices.find(i=>i.id===id),c=state.customers.find(c=>c.id===i.customer),p=state.profile;
    const subject=encodeURIComponent(`Invoice ${i.number} from ${p.name}`),body=encodeURIComponent(`Hello ${c.name},\n\nInvoice ${i.number}: ${money(i.total)}. Outstanding balance: ${money(i.balance_due)}.\nPlease see the invoice PDF (attach it after Print / Save PDF).\n\nRegards,\n${p.name}`);
    $('emailBtn').onclick=()=>location.href=`mailto:${encodeURIComponent(c.email)}?subject=${subject}&body=${body}`;
    $('whatsappBtn').onclick=()=>window.open(`https://wa.me/${c.phone.replace(/\D/g,'')}?text=${body}`,'_blank','noopener');
    $('previewModal').classList.add('open');
  }catch(e){reportError(e);}
}
function printCurrentInvoice(){if(previewId)window.open(`/invoices/${previewId}/print/`,'_blank','noopener');}
function loadForms(){Object.entries(state.profile).forEach(([k,v])=>{const f=field('profileForm',k);if(f&&f.type!=='file')f.value=v;});Object.entries(state.settings).forEach(([k,v])=>{const f=field('settingsForm',k);if(f)f.value=v;});$('logoView').innerHTML=state.profile.logo?`<img src="${esc(state.profile.logo)}?v=${Date.now()}" alt="Business logo">`:'LOGO';}
bindForm('profileForm',async()=>{const data=new FormData($('profileForm'));data.set('business_name',data.get('name'));data.set('registration_number',data.get('registration'));data.set('vat_number',data.get('vat'));if(!$('logo').files.length)data.delete('logo');await api('/api/profile/','POST',data);await refresh();loadForms();alert('Business profile saved.');});
bindForm('settingsForm',async()=>{const d=Object.fromEntries(new FormData($('settingsForm')));await api('/api/settings/','POST',{invoice_prefix:d.prefix,next_invoice_number:d.next,default_currency:d.currency,default_tax_rate:d.vat,payment_terms:d.terms});await refresh();loadForms();alert('Settings saved.');});
$('logo').onchange=()=>{const file=$('logo').files[0];if(file){const image=document.createElement('img'),url=URL.createObjectURL(file);image.src=url;image.onload=()=>URL.revokeObjectURL(url);$('logoView').replaceChildren(image);}};
function syncSidebar(){const p=state.profile;$('sidebarBusiness').textContent=p.name;$('sidebarEmail').textContent=p.email||'Simple invoicing for your SME';$('welcomeName').textContent=p.name;$('sidebarAvatar').innerHTML=p.logo?`<img src="${esc(p.logo)}?v=${Date.now()}" alt="Business logo">`:`<div class="avatar-fallback">${esc(p.name.split(/\s+/).slice(0,2).map(x=>x[0]).join('').toUpperCase())}</div>`;$('sideInvoices').textContent=state.summary.invoice_count;$('sideOutstanding').textContent=money(state.summary.outstanding);}
loadForms();render();syncSidebar();
