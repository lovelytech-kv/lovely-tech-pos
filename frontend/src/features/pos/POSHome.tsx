import { useEffect, useMemo, useRef, useState } from 'react';
import { api, serverLogout } from '../../api/client';
import { money, moneyAdd, moneySub, moneyTimesQty, moneyPositive } from '../../services/money';
import { DashboardLayout } from '../../layouts/DashboardLayout';
import { RepairForm } from '../repairs/RepairForm';
import { RepairWorkspace } from '../repairs/RepairWorkspace';
import { Purchases } from '../purchases/Purchases';
import { DayEnd } from '../finance/DayEnd';
import { ReturnsWorkspace } from '../returns/ReturnsWorkspace';
import { WarrantyWorkspace } from '../warranty/WarrantyWorkspace';
import { SettingsPanel } from '../settings/SettingsPanel';
import { HomeDashboard } from '../home/HomeDashboard';
import { SalesHistory } from '../sales/SalesHistory';
import { UserManagement } from '../users/UserManagement';
import { moneyInputProps, intInputProps, signedIntInputProps } from '../../utils/numberInput';
import { toast } from '../../ui/toast';
import { useModal } from '../../ui/modals';
import { useShopProfile } from '../settings/ShopContext';

type User = { display_name:string; role:string; branch_id:string; username?:string };
type WarrantyDefault = { warranty_type:string; duration_value?:number|null; custom_rule?:string|null };
type Item = { item_id:string; item_code:string; description:string; sale_price:string|number|null; stock:string|number; brand?:string; model?:string; warranty_default?:WarrantyDefault|null; is_serialized?:boolean };
type CartLine = Item & { line_id:string; serial_number?:string; quantity:string; price:string; discount:string; serialized_unit_id?:string; warranty_override?:WarrantyDefault|null };
type DocType = 'SYSTEM_PRINTED' | 'MANUAL' | 'NO_PRINT';
const today = () => new Date().toISOString().slice(0,10);

const RECENT_KEY = 'ltpos_recent_items';
const DEFAULT_DOC_KEY = 'ltpos_default_doc_type';

function loadRecent(): Item[] {
  try {
    const raw = localStorage.getItem(RECENT_KEY);
    if (!raw) return [];
    const arr = JSON.parse(raw);
    if (!Array.isArray(arr)) return [];
    return arr.filter((x): x is Item => !!x && typeof x.item_id === 'string' && typeof x.item_code === 'string').slice(0, 10);
  } catch {
    return [];
  }
}

function saveRecent(items: Item[]): void {
  try {
    localStorage.setItem(RECENT_KEY, JSON.stringify(items.slice(0, 10)));
  } catch {
    // ignore storage errors
  }
}

function getDefaultDocType(): DocType {
  try {
    const v = localStorage.getItem(DEFAULT_DOC_KEY);
    if (v === 'SYSTEM_PRINTED' || v === 'MANUAL' || v === 'NO_PRINT') return v;
  } catch {
    // ignore storage errors
  }
  return 'SYSTEM_PRINTED';
}
function buildGenericReprintHTML(r: any): string {
  const title = String(r.document_type || 'Document');
  const no = String(r.document_no || '—');
  const dateStr = r.document_datetime ? new Date(r.document_datetime).toLocaleString() : '—';
  const status = String(r.status || '—');
  return `<!DOCTYPE html><html><head><title>Reprint ${no}</title>
    <style>
      body{font-family:'Consolas','Menlo',monospace;padding:20px;font-size:13px;color:#000;}
      h1{font-size:16px;text-align:center;margin:0 0 12px;}
      .label{font-size:10px;color:#666;text-transform:uppercase;letter-spacing:0.05em;margin-top:8px;}
      .value{font-size:14px;font-weight:700;}
      .divider{border-top:1px dashed #000;margin:12px 0;}
      .foot{text-align:center;font-size:10px;color:#888;margin-top:16px;line-height:1.4;}
    </style></head><body>
    <h1>Reprint — ${title}</h1>
    <div class="divider"></div>
    <div class="label">Document No</div>
    <div class="value">${no}</div>
    <div class="label">Type</div>
    <div class="value">${title}</div>
    <div class="label">Date</div>
    <div class="value">${dateStr}</div>
    <div class="label">Status</div>
    <div class="value">${status}</div>
    <div class="divider"></div>
    <div class="foot">This is a reprint record.<br/>For full document copy, please contact admin.</div>
    <script>window.onload = function(){ window.print(); };</script>
    </body></html>`;
}

function buildReceiptHTML(sale: any, shop: { getShopName: () => string; getLogoDataUrl: (forcedTheme?: 'light' | 'dark') => string | null }, fullShop?: any): string {
  const lines = Array.isArray(sale?.lines) ? sale.lines : [];
  const shopName = shop.getShopName();
  const logoUrl = shop.getLogoDataUrl('light');
  const address = fullShop?.address || '';
  const phone = fullShop?.phone || '';
  const email = fullShop?.email || '';
  const invoiceNo = sale?.invoice_no || '-';
  return `<!DOCTYPE html><html><head><title>Receipt ${invoiceNo}</title>
    <style>
      body{font-family:'Consolas','Menlo',monospace;padding:16px;font-size:13px;color:#000;}
      h1{font-size:16px;text-align:center;margin:0 0 4px;}
      .meta{text-align:center;font-size:11px;color:#333;margin-bottom:4px;}
      .contact{text-align:center;font-size:10px;color:#555;margin-bottom:8px;line-height:1.35;}
      .divider{border-top:1px dashed #000;margin:8px 0;}
      .row{display:flex;justify-content:space-between;gap:8px;}
      .line{padding:2px 0;}
      .total{font-size:15px;font-weight:700;}
      .foot{text-align:center;font-size:11px;margin-top:8px;}
      .vendor{text-align:center;font-size:9px;color:#888;margin-top:6px;letter-spacing:0.02em;}
      .logo{display:block;margin:0 auto 4px;max-width:80px;max-height:80px;object-fit:contain;}
    </style></head><body>
    ${logoUrl ? `<img src="${logoUrl}" class="logo" />` : ''}
    <h1>${shopName}</h1>
    ${(address || phone || email) ? `<div class="contact">${address ? address + '<br/>' : ''}${phone ? 'Tel: ' + phone : ''}${phone && email ? ' · ' : ''}${email || ''}</div>` : ''}
    <div class="meta">Invoice: ${invoiceNo}<br/>${new Date().toLocaleString()}</div>
    <div class="divider"></div>
    ${lines.map((l: any) => `
      <div class="line">
        <div>${l.description || l.item_code || ''}</div>
        <div class="row"><span>${l.quantity || '1'} × Rs. ${l.unit_price || '0'}</span><span>Rs. ${l.final_total || l.line_total || l.unit_price || '0'}</span></div>
      </div>
    `).join('')}
    <div class="divider"></div>
    <div class="row total"><span>TOTAL</span><span>Rs. ${sale?.grand_total || '0'}</span></div>
    <div class="divider"></div>
    <div class="foot">Thank you for shopping at ${shopName}!</div>
    <div class="vendor">Software by Lovely Tech</div>
    <script>window.onload = function(){ window.print(); };</script>
    </body></html>`;
}


export function POSHome({user,onLogout}:{user:User,onLogout:()=>void}) {
  const [tab,setTab]=useState('Dashboard'); const [error,setError]=useState('');
  const isAdmin=user.role.toUpperCase()==='ADMIN';
  return <DashboardLayout user={user} activeKey={tab} onNavigate={key=>{setTab(key);setError('')}} onLogout={()=>{serverLogout().finally(onLogout)}}>
    {error&&<div className="error-banner" role="alert"><span>{error}</span><button className="error-dismiss" aria-label="Dismiss error" onClick={()=>setError('')}>×</button></div>}
    {tab==='Dashboard'&&<HomeDashboard user={user} onNavigate={setTab}/>} {tab==='Customers'&&<CustomersTab onError={setError}/>} {tab==='Items'&&<ItemsTab onError={setError}/>} {tab==='Sales'&&<SalesTab isAdmin={isAdmin} onError={setError}/>} {tab==='SalesHistory'&&<SalesHistory isAdmin={isAdmin} onError={setError} onNavigate={setTab} user={user}/>} {tab==='Returns'&&<ReturnsWorkspace isAdmin={isAdmin} onError={setError}/>} {tab==='Repairs'&&<><RepairForm onError={setError} /><RepairWorkspace isAdmin={isAdmin} onError={setError}/></>} {tab==='Warranty'&&<WarrantyWorkspace isAdmin={isAdmin} onError={setError}/>} {tab==='Stock'&&<StockTab/>} {tab==='Purchases'&&<Purchases isAdmin={isAdmin} onError={setError}/>} {tab==='Expenses'&&<ExpensesTab onError={setError}/>} {tab==='Cash/Day'&&<DayEnd isAdmin={isAdmin} onError={setError}/>} {tab==='Reports'&&<ReportsTab isAdmin={isAdmin} onError={setError}/>} {tab==='Documents'&&<DocumentsTab onError={setError}/>} {tab==='Settings'&&<SettingsPanel isAdmin={isAdmin}/>} {tab==='Admin'&&isAdmin&&<AdminTab onError={setError}/>} {tab==='Users'&&isAdmin&&<UserManagement isAdmin={isAdmin} onError={setError}/>} {tab==='Backup'&&isAdmin&&<BackupTab onError={setError}/>}
  </DashboardLayout>;
}

function CustomersTab({onError}:{onError:(x:string)=>void}){
  const [q,setQ]=useState(''),[rows,setRows]=useState<any[]>([]),[selected,setSelected]=useState<any|null>(null),[history,setHistory]=useState<any|null>(null),[busy,setBusy]=useState(false);
  const [form,setForm]=useState({name:'',contact_no:'',notes:'',version:0});
  async function search(){try{setRows(await api<any[]>(`/customers?q=${encodeURIComponent(q.trim())}`))}catch(e){onError((e as Error).message)}}
  async function open(c:any){setSelected(c);setForm({name:c.name||'',contact_no:c.contact_no||'',notes:c.notes||'',version:Number(c.version||0)});setHistory(null)}
  async function save(){if(!selected)return;try{setBusy(true);const r=await api<any>(`/customers/${selected.customer_id}`,{method:'PUT',body:JSON.stringify(form)});setSelected(r);setRows(x=>x.map(c=>c.customer_id===r.customer_id?r:c));setForm({name:r.name||'',contact_no:r.contact_no||'',notes:r.notes||'',version:r.version});toast.success('Customer updated.')}catch(e){onError((e as Error).message)}finally{setBusy(false)}}
  async function create(){try{setBusy(true);const r=await api<any>('/customers',{method:'POST',body:JSON.stringify({name:form.name||null,contact_no:form.contact_no||null,notes:form.notes||null})});await search();open(r)}catch(e){onError((e as Error).message)}finally{setBusy(false)}}
  async function loadHistory(){if(!selected)return;try{setHistory(await api<any>(`/customers/${selected.customer_id}/history`))}catch(e){onError((e as Error).message)}}
  return <section className="split"><div className="glass panel"><div className="section-head"><div><span className="eyebrow">CUSTOMERS</span><h2>Customer directory</h2><p className="muted">Customer details are optional. History covers sales, repairs, warranty claims and settlements.</p></div><button onClick={search}>Search</button></div><div className="search-row"><input value={q} onChange={e=>setQ(e.target.value)} onKeyDown={e=>e.key==='Enter'&&search()} placeholder="Name or contact number"/><button onClick={search}>Find</button></div><div className="list-stack">{rows.map(c=><button className="list-row customer-row" key={c.customer_id} onClick={()=>open(c)}><span><b>{c.name||'Unnamed customer'}</b><small>{c.contact_no||'No contact'} · Version {c.version}</small></span><span>›</span></button>)}{rows.length===0&&<p className="muted">No customers loaded.</p>}</div></div><div className="glass panel"><div className="section-head"><div><span className="eyebrow">CUSTOMER PROFILE</span><h2>{selected?selected.name||selected.contact_no||'Customer':'Create customer'}</h2></div>{selected&&<button onClick={loadHistory}>History</button>}</div><div className="form-grid compact"><input placeholder="Name" value={form.name} onChange={e=>setForm({...form,name:e.target.value})}/><input placeholder="Contact no." value={form.contact_no} onChange={e=>setForm({...form,contact_no:e.target.value})}/><textarea className="wide-field" placeholder="Notes" value={form.notes} onChange={e=>setForm({...form,notes:e.target.value})}/></div>{selected?<button disabled={busy} onClick={save}>Save Customer</button>:<button disabled={busy||(!form.name.trim()&&!form.contact_no.trim())} onClick={create}>Create Customer</button>}{selected&&<p className="muted">Optimistic lock version: {form.version}. A stale save is rejected by the backend.</p>}{history&&<div className="history-card"><h3>History</h3><div className="status-strip"><div><span>Sales</span><b>{history.sales?.length||0}</b></div><div><span>Repairs</span><b>{history.repairs?.length||0}</b></div><div><span>Warranty</span><b>{history.warranty_claims?.length||0}</b></div></div><h4>Sales</h4>{(history.sales||[]).slice(0,20).map((x:any)=><div className="stock-row" key={x.sale_id}><span>{x.invoice_no} · {new Date(x.date).toLocaleString()}</span><b>Rs. {money(x.total)}</b></div>)}<h4>Settlements</h4>{(history.settlements||[]).slice(0,20).map((x:any)=><div className="stock-row" key={x.settlement_id}><span>{new Date(x.date).toLocaleString()} · {x.method}</span><b>Rs. {money(x.amount)}</b></div>)}<h4>Repairs</h4>{(history.repairs||[]).slice(0,20).map((x:any)=><div className="stock-row" key={x.repair_id}><span>{x.repair_no} · {x.status}</span><b>Rs. {money(x.total)}</b></div>)}</div>}</div></section>
}

function SalesTab({isAdmin,onError}:{isAdmin:boolean,onError:(x:string)=>void}){
  const [q,setQ]=useState(''),[items,setItems]=useState<Item[]>([]),[cart,setCart]=useState<CartLine[]>([]),[cash,setCash]=useState(''),[card,setCard]=useState(''),[online,setOnline]=useState(''),[credit,setCredit]=useState(false),[customer,setCustomer]=useState(''),[customerQuery,setCustomerQuery]=useState(''),[customers,setCustomers]=useState<any[]>([]),[settleAmount,setSettleAmount]=useState(''),[settleMethod,setSettleMethod]=useState('CASH'),[settlementKey,setSettlementKey]=useState(()=>crypto.randomUUID()),[saleKey,setSaleKey]=useState(()=>crypto.randomUUID()),[approvalId,setApprovalId]=useState(''),[pendingApproval,setPendingApproval]=useState<any|null>(null),[customerHistory,setCustomerHistory]=useState<any|null>(null),[doc,setDoc]=useState<DocType>(() => getDefaultDocType()),[manualRef,setManualRef]=useState(''),[saleDateTime,setSaleDateTime]=useState(''),[busy,setBusy]=useState(false),[last,setLast]=useState<any>();
  const [toast,setToast]=useState('');
  const [recentItems,setRecentItems]=useState<Item[]>(()=>loadRecent());
  const searchInputRef = useRef<HTMLInputElement>(null);
  const cashInputRef = useRef<HTMLInputElement>(null);
  const cartRef = useRef<CartLine[]>(cart);
  const itemsRef = useRef<Item[]>(items);
  const pendingFocusRef = useRef<string | null>(null);
  const checkoutGuardRef = useRef(false);
  const shop = useShopProfile();
const [fullShop, setFullShop] = useState<any>(null);
useEffect(() => {
  (async () => {
    try { setFullShop(await api('/branch/profile')); } catch { /* ignore */ }
  })();
}, []);
  useEffect(() => { cartRef.current = cart; }, [cart]);
  useEffect(() => { itemsRef.current = items; }, [items]);
  useEffect(() => {
    if (!toast) return;
    const t = window.setTimeout(() => setToast(''), 2500);
    return () => window.clearTimeout(t);
  }, [toast]);
  useEffect(() => {
    const id = pendingFocusRef.current;
    if (!id) return;
    const el = document.getElementById(`qty-${id}`) as HTMLInputElement | null;
    if (!el) return;
    el.focus();
    el.select();
    pendingFocusRef.current = null;
  }, [cart]);

  const total=useMemo(()=>cart.reduce((sum,x)=>moneyAdd(sum,moneySub(moneyTimesQty(x.price,x.quantity),x.discount)), '0.00'),[cart]);
  const totalDiscount=useMemo(()=>cart.reduce((sum,x)=>moneyAdd(sum, String(x.discount||'0')), '0.00'),[cart]);

  const cashPortion = Math.min(Number(cash || 0), Math.max(0, Number(total) - Number(card || 0) - Number(online || 0)));
  const totalPaid = cashPortion + Number(card || 0) + Number(online || 0);
  const changeDue = Math.max(0, Number(cash || 0) - cashPortion);
  const remaining = Math.max(0, Number(total) - totalPaid);
  const isFullyPaid = remaining < 0.01 || totalPaid >= Number(total);

  const moneyInputPattern = /^\d*\.?\d{0,2}$/;

  function recordRecent(item: Item) {
    const stored = loadRecent().filter(x => x.item_id !== item.item_id);
    const entry: Item = {
      item_id: item.item_id,
      item_code: item.item_code,
      description: item.description,
      is_serialized: item.is_serialized,
      sale_price: item.sale_price,
      stock: item.stock,
      warranty_default: item.warranty_default,
    };
    const next = [entry, ...stored].slice(0, 10);
    saveRecent(next);
    setRecentItems(next);
  }

  function addItemWithFocus(item: Item) {
    if (item.is_serialized) {
      const newId = `${item.item_id}:${crypto.randomUUID()}`;
      setCart(c => [...c, {
        ...item,
        line_id: newId,
        quantity: '1',
        price: item.sale_price == null ? '' : String(item.sale_price),
        discount: '0',
        warranty_override: null,
      }]);
      setToast(`Added phone model, scan IMEI`);
      recordRecent(item);
      return;
    }
    const existing = cartRef.current.find(x => x.line_id === item.item_id);
    if (existing) {
      const newQty = moneyAdd(existing.quantity, '1');
      setCart(c => c.map(x => x.line_id === item.item_id ? { ...x, quantity: newQty } : x));
      setToast(`Added: ${item.description} (qty: ${newQty})`);
      recordRecent(item);
      return;
    }
    setCart(c => [...c, {
      ...item,
      line_id: item.item_id,
      quantity: '1',
      price: item.sale_price == null ? '' : String(item.sale_price),
      discount: '0',
      warranty_override: null,
    }]);
    pendingFocusRef.current = item.item_id;
    setToast(`Added: ${item.description}`);
    recordRecent(item);
  }

  async function addFromImei(unit: any) {
    if (cartRef.current.some(x => x.serialized_unit_id === unit.serialized_unit_id)) {
      onError('That IMEI is already in the cart.');
      return;
    }
    const empty = cartRef.current.find(x => x.item_id === unit.item_id && x.is_serialized && !x.serialized_unit_id);
    if (empty) {
      setCart(c => c.map(x => x.line_id === empty.line_id ? {
        ...x,
        serialized_unit_id: unit.serialized_unit_id,
        serial_number: unit.serial_number,
        quantity: '1',
      } : x));
      setToast(`Added: ${empty.description} (IMEI: ${unit.serial_number})`);
      recordRecent({
        item_id: empty.item_id,
        item_code: empty.item_code,
        description: empty.description,
        is_serialized: empty.is_serialized,
        sale_price: empty.sale_price,
        stock: empty.stock,
        warranty_default: empty.warranty_default,
      });
      return;
    }
    try {
      let item = itemsRef.current.find(i => i.item_id === unit.item_id);
      if (!item) {
        const results = await api<Item[]>(`/inventory/items/search?q=${encodeURIComponent(unit.item_code || '')}`);
        item = results.find(i => i.item_id === unit.item_id);
      }
      if (!item) {
        onError(`Item not found for IMEI ${unit.serial_number}. Search by item code first.`);
        return;
      }
      const newLine: CartLine = {
        ...item,
        line_id: `${item.item_id}:${crypto.randomUUID()}`,
        quantity: '1',
        price: item.sale_price == null ? '' : String(item.sale_price),
        discount: '0',
        warranty_override: null,
        serialized_unit_id: unit.serialized_unit_id,
        serial_number: unit.serial_number,
      };
      setCart(c => [...c, newLine]);
      setToast(`Added: ${item.description} (IMEI: ${unit.serial_number})`);
      recordRecent(item);
    } catch (e) {
      onError((e as Error).message);
    }
  }

  async function smartSearch() {
    const query = q.trim();
    if (!query) return;

    // Step A — IMEI / serial exact match (single result)
    try {
      const units = await api<any[]>(`/inventory/serialized/search?q=${encodeURIComponent(query)}&status=IN_STOCK`);
      if (Array.isArray(units) && units.length === 1) {
        await addFromImei(units[0]);
        setQ('');
        searchInputRef.current?.focus();
        return;
      }
    } catch {
      // ignore IMEI search failure — fall through to item search
    }

    // Step B — item search
    try {
      const results = await api<Item[]>(`/inventory/items/search?q=${encodeURIComponent(query)}`);
      if (!Array.isArray(results)) return;
      if (results.length === 0) {
        setItems([]);
        setToast(`No results for "${query}". Try a different term.`);
        setQ('');
        return;
      }
      if (results.length === 1) {
        addItemWithFocus(results[0]);
        setQ('');
        searchInputRef.current?.focus();
        return;
      }
      // Step C — multiple results → grid
      setItems(results);
      setQ('');
    } catch (e) {
      onError((e as Error).message);
    }
  }

  async function searchCustomers(){try{setCustomers(await api<any[]>(`/customers?q=${encodeURIComponent(customerQuery)}`))}catch(e){onError((e as Error).message)}}
  async function loadCustomerHistory(){try{if(!customer){onError('Select a customer first.');return} setCustomerHistory(await api<any>(`/customers/${customer}/history`))}catch(e){onError((e as Error).message)}}
  function edit(id:string,k:'quantity'|'price'|'discount',v:string){setCart(c=>c.map(x=>x.line_id===id?{...x,[k]:v}:x))}
  function setWarrantyOverride(id:string, value:string){setCart(c=>c.map(x=>x.line_id===id?{...x,warranty_override:value==='DEFAULT'?null:{...(x.warranty_default||{warranty_type:'NONE'}),warranty_type:value,duration_value:value==='DAYS'||value==='MONTHS'?(x.warranty_override?.duration_value||x.warranty_default?.duration_value||null):null,custom_rule:value==='CUSTOM'?(x.warranty_override?.custom_rule||x.warranty_default?.custom_rule||''):null}}:x))}

  function writeReceipt(w: Window, sale: any, shop: { getShopName: () => string; getLogoDataUrl: (forcedTheme?: 'light' | 'dark') => string | null }, fullShop?: any) {
  try {
    if (!w || w.closed) return;
    w.document.open();
    w.document.write(buildReceiptHTML(sale, shop, fullShop));
    w.document.close();
  } catch {
    // ignore
  }
}

  function printReceipt(sale: any, shop: { getShopName: () => string; getLogoDataUrl: (forcedTheme?: 'light' | 'dark') => string | null }) {
  const w = window.open('', '_blank', 'width=420,height=640');
  if (!w) {
    onError('Print popup was blocked. Please allow popups for this site and try again.');
    return;
  }
  writeReceipt(w, sale, shop, fullShop);
}
  function openPrintWindow(): Window | null {
    try {
      const w = window.open('', '_blank', 'width=420,height=640');
      if (w) {
        w.document.write('<!DOCTYPE html><html><head><title>Preparing receipt…</title></head><body style="font-family:monospace;padding:20px;text-align:center;font-size:13px"><p>Preparing receipt…</p></body></html>');
        w.document.close();
      }
      return w;
    } catch {
      return null;
    }
  }

  async function checkout(preOpenedPrintWindow?: Window | null){
    if(busy || checkoutGuardRef.current) return;
    checkoutGuardRef.current = true;
    const saleDoc = doc;
    const saleCredit = credit;
    let printed = false;
    const closePre = () => {
      if (preOpenedPrintWindow && !preOpenedPrintWindow.closed) {
        try { preOpenedPrintWindow.close(); } catch { /* ignore */ }
      }
    };
    try{
      setBusy(true);
      if(!cart.length){onError('Add at least one item.');closePre();return}
      const noImei=cart.find(x=>x.is_serialized&&!x.serialized_unit_id);
      if(noImei){onError(`Select the IMEI / serial number for ${noImei.description} (scan the IMEI into the search box).`);closePre();return}
      if(cart.some(x=>!x.price||!moneyPositive(x.price))){onError('Enter a sale price for every item.');closePre();return}
      if(saleDoc==='MANUAL'&&!manualRef.trim()){onError('Manual invoice reference is required.');closePre();return}
      if(cart.some(x=>moneyPositive(moneySub(x.discount,moneyTimesQty(x.price,x.quantity))))){onError('Discount cannot exceed line total.');closePre();return}
      if(!saleCredit){
        const cardAndOnline = Number(card||0) + Number(online||0);
        if(cardAndOnline > Number(total) + 0.01){onError(`Card + Online exceeds total. Reduce the amounts.`);closePre();return}
        if(!isFullyPaid){onError(`Payment short. Remaining: Rs. ${remaining.toFixed(2)}`);closePre();return}
      }
      const cashPayStr = cashPortion > 0 ? cashPortion.toFixed(2) : '';
      const payments = saleCredit ? [] : [
        ['CASH', cashPayStr],
        ['CARD', card],
        ['ONLINE', online],
      ].filter(([,v]) => moneyPositive(String(v))).map(([method, amount]) => ({ method, amount: String(amount) }));
      const salePayload = {
        lines: cart.map(x => ({
          item_id: x.item_id,
          quantity: x.quantity,
          unit_price: String(x.price),
          discount: String(x.discount),
          serialized_unit_id: x.serialized_unit_id || null,
          warranty_type: x.warranty_override?.warranty_type || null,
          warranty_duration_value: x.warranty_override?.duration_value || null,
          warranty_custom_rule: x.warranty_override?.custom_rule || null,
        })),
        payments,
        credit_sale: saleCredit,
        customer_id: saleCredit ? customer || null : null,
        document_type: saleDoc,
        manual_invoice_ref: saleDoc === 'MANUAL' ? manualRef.trim() : null,
        sale_datetime: isAdmin && saleDateTime ? new Date(saleDateTime).toISOString() : null,
        cash_received: cash || null,
        idempotency_key: saleKey,
        admin_discount_approval_id: approvalId.trim() || null,
      };
      try {
        const result = await api<any>('/sales', { method: 'POST', body: JSON.stringify(salePayload) });
        setLast(result);
        setCart([]);
        setCash('');
        setCard('');
        setOnline('');
        setManualRef('');
        setSaleDateTime('');
        setCredit(false);
        setApprovalId('');
        setPendingApproval(null);
        setSaleKey(crypto.randomUUID());
        setDoc(getDefaultDocType());
        if (saleDoc === 'SYSTEM_PRINTED' && !saleCredit && preOpenedPrintWindow && !preOpenedPrintWindow.closed) {
          writeReceipt(preOpenedPrintWindow, result, shop, fullShop);
          printed = true;
        }
      } catch(e) {
        const msg = (e as Error).message;
        if (msg.includes('Admin approval required')) {
          const approval = await api<any>('/sales/discount-approval', { method: 'POST', body: JSON.stringify(salePayload) });
          setPendingApproval(approval);
          setApprovalId(approval.approval_id);
          onError(`Discount approval requested: ${approval.approval_action_id}. After Admin approves it, retry the sale using the approval ID below.`);
        } else throw e;
      }
    } catch(e) {
      onError((e as Error).message);
    } finally {
      if (!printed) closePre();
      checkoutGuardRef.current = false;
      setBusy(false);
    }
  }

  function handleCompleteSale() {
    if (busy || checkoutGuardRef.current) return;
    const wantsPrint = doc === 'SYSTEM_PRINTED' && !credit;
    const preOpened = wantsPrint ? openPrintWindow() : null;
    void checkout(preOpened);
  }

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement | null;
      const isInput = !!target && (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.tagName === 'SELECT');
      if (e.key === 'F2') {
        e.preventDefault();
        searchInputRef.current?.focus();
        searchInputRef.current?.select();
        return;
      }
      if (e.key === 'F4') {
        e.preventDefault();
        cashInputRef.current?.focus();
        cashInputRef.current?.select();
        return;
      }
      if (e.key === 'Escape') {
        if (searchInputRef.current && target === searchInputRef.current) {
          setQ('');
          searchInputRef.current.blur();
          return;
        }
        if (isInput && target) {
          (target as HTMLInputElement).blur();
          return;
        }
        if (cartRef.current.length > 0) {
          if (window.confirm('Clear cart?')) {
            setCart([]);
            setApprovalId('');
            setPendingApproval(null);
          }
        }
        return;
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, []);

  return (
    <section className="sales-layout">
      <div className="sales-left">
        {toast && <div className="sales-success">{toast}</div>}
        <div className="sales-search-box">
          <input
            ref={searchInputRef}
            autoFocus
            value={q}
            onChange={e => setQ(e.target.value)}
            onKeyDown={e => {
              if (e.key === 'Enter') {
                e.preventDefault();
                if (q.trim() === '') {
                  cashInputRef.current?.focus();
                  cashInputRef.current?.select();
                } else {
                  void smartSearch();
                }
              }
            }}
            placeholder="Scan barcode / IMEI or search items…"
          />
          <span className="kbd-hint">F2</span>
        </div>
        <div className="sales-kbd-bar">
          <span><kbd>F2</kbd> Search · <kbd>F4</kbd> Payment · <kbd>Esc</kbd> Clear · <kbd>Enter</kbd> Add/Scan · <kbd>Enter</kbd> (empty search) → Cash</span>
        </div>
        <div className="sales-recent">
          <span>Today's items:</span>
          {recentItems.length === 0
            ? <span style={{ fontStyle: 'italic' }}>No recent items yet — items you sell today appear here.</span>
            : <>
                {recentItems.map(r => (
                  <button
                    key={r.item_id}
                    type="button"
                    className="recent-item"
                    onClick={() => addItemWithFocus(r)}
                    title={r.description}
                  >
                    <b>{r.item_code}</b> · {r.description.slice(0, 20)}
                  </button>
                ))}
                <button
                  type="button"
                  onClick={() => { saveRecent([]); setRecentItems([]); }}
                  style={{ padding: '4px 10px', fontSize: '0.7rem', background: 'transparent', border: '1px solid var(--line)', borderRadius: 6, color: 'var(--muted)', cursor: 'pointer', minHeight: 28 }}
                >Clear</button>
              </>
          }
        </div>
        <div className="sales-product-grid">
          {items.map(i => (
            <button key={i.item_id} type="button" className="sales-product-card" onClick={() => addItemWithFocus(i)}>
              <span className="code">{i.item_code}</span>
              <span className="desc">{i.description}</span>
              <span className="meta">Stock {i.stock} · Rs. {i.sale_price ?? 'Type price'}</span>
            </button>
          ))}
        </div>
        {last && (
          <div className="sales-success" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 'var(--space-2)', flexWrap: 'wrap' }}>
            <span>Completed: {last.invoice_no} · Rs. {money(last.grand_total)}{last.negative_stock ? ' · Negative stock warning' : ''}</span>
            <button
              type="button"
              onClick={() => printReceipt(last, shop)}
              style={{ padding: 'var(--space-2) var(--space-3)', background: 'var(--color-success)', color: '#fff', border: 0, borderRadius: 'var(--radius-sm)', cursor: 'pointer', fontWeight: 600, whiteSpace: 'nowrap', minHeight: 36 }}
            >
              🖨 Print Receipt
            </button>
          </div>
        )}
      </div>

      <div className="sales-right">
        <div className="sales-panel">
          <div className="sales-panel-header">
            <h2>Cart <span style={{ fontSize: '0.75rem', fontWeight: 400, color: 'var(--muted)', marginLeft: 6 }}>({cart.length} items)</span></h2>
            <button
              type="button"
              disabled={!cart.length || busy}
              onClick={() => { setCart([]); setApprovalId(''); setPendingApproval(null); }}
              style={{ padding: '4px 10px', fontSize: '0.75rem', background: 'transparent', border: '1px solid var(--line)', borderRadius: 6, color: 'var(--muted)', cursor: cart.length ? 'pointer' : 'not-allowed', minHeight: 28 }}
            >Clear</button>
          </div>
          {cart.length === 0
            ? <div className="sales-cart-empty">No items yet. Scan or search to add.</div>
            : cart.map(x => (
                <div className="sales-cart-line" key={x.line_id}>
                  <div className="line-top">
                    <div>
                      <div className="line-name">{x.description}</div>
                      {x.is_serialized && (
                        <div className={`line-serial ${x.serialized_unit_id ? '' : 'missing'}`}>
                          {x.serialized_unit_id ? `IMEI: ${x.serial_number}` : '⚠ IMEI required — scan now'}
                        </div>
                      )}
                    </div>
                    <div className="line-total">Rs. {moneySub(moneyTimesQty(x.price, x.quantity), x.discount)}</div>
                    <button type="button" className="line-remove" aria-label={`Remove ${x.description}`} onClick={() => setCart(c => c.filter(y => y.line_id !== x.line_id))}>×</button>
                  </div>
                  <div className="line-controls">
                    <label>Qty <input
                      id={`qty-${x.line_id}`}
                      type="number"
                      min="1"
                      step="1"
                      value={x.quantity}
                      disabled={!!x.is_serialized}
                      onChange={e => {
                        const raw = e.target.value;
                        if (raw === '') { edit(x.line_id, 'quantity', '1'); return; }
                        const n = parseInt(raw, 10);
                        if (!Number.isFinite(n) || n < 1) { edit(x.line_id, 'quantity', '1'); return; }
                        edit(x.line_id, 'quantity', String(n));
                      }}
                      onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); searchInputRef.current?.focus(); } }}
                      onWheel={e => e.currentTarget.blur()}
                    /></label>
                    <label>Price <input type="number" min="0" step=".01" value={x.price} onChange={e => edit(x.line_id, 'price', e.target.value)} onWheel={(e) => e.currentTarget.blur()} /></label>
                    <label>Disc <input type="number" min="0" step=".01" value={x.discount} onChange={e => edit(x.line_id, 'discount', e.target.value)} onWheel={(e) => e.currentTarget.blur()} /></label>
                    <label>Warranty <select value={x.warranty_override?.warranty_type || 'DEFAULT'} onChange={e => setWarrantyOverride(x.line_id, e.target.value)}>
                      <option value="DEFAULT">Default</option>
                      <option value="NONE">None</option>
                      <option value="DAYS">Days</option>
                      <option value="MONTHS">Months</option>
                      <option value="CHECKING ONLY">Checking Only</option>
                      <option value="CUSTOM">Custom</option>
                    </select></label>
                    {(x.warranty_override?.warranty_type === 'DAYS' || x.warranty_override?.warranty_type === 'MONTHS') && (
                      <label>Duration <input type="number" min="1" step="1" value={x.warranty_override?.duration_value || ''} onChange={e => setCart(c => c.map(y => y.line_id === x.line_id ? { ...y, warranty_override: { ...y.warranty_override!, duration_value: Number(e.target.value) || null } } : y))} style={{ flexShrink: 0, width: 90 }} onWheel={(e) => e.currentTarget.blur()} /></label>
                    )}
                    {x.warranty_override?.warranty_type === 'CUSTOM' && (
                      <label>Rule <input type="text" placeholder="e.g. 45 DAYS" value={x.warranty_override?.custom_rule || ''} onChange={e => setCart(c => c.map(y => y.line_id === x.line_id ? { ...y, warranty_override: { ...y.warranty_override!, custom_rule: e.target.value } } : y))} style={{ flexShrink: 0, width: 200, minWidth: 200 }} /></label>
                    )}
                  </div>
                </div>
              ))
          }
          <div className="sales-totals">
            <div className="subtotal-row"><span>Subtotal</span><span>Rs. {money(moneyAdd(total, totalDiscount))}</span></div>
            <div className="subtotal-row"><span>Discount</span><span>Rs. {money(totalDiscount)}</span></div>
            <div className="total-row"><span>TOTAL</span><span className="amount">Rs. {money(total)}</span></div>
          </div>
        </div>

        <div className="sales-panel">
          <div className="sales-panel-header"><h3>Payment</h3></div>

          <div className={`payment-method ${Number(cash) > 0 ? 'active' : ''}`}>
            <label>💵 Cash (customer gives) <span>Rs.</span></label>
            <input
              ref={cashInputRef}
              type="text"
              inputMode="decimal"
              value={cash}
              onChange={e => { const v = e.target.value; if (v === '' || moneyInputPattern.test(v)) setCash(v); }}
              onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); handleCompleteSale(); } }}
              placeholder="0.00"
            />
          </div>
          <div className={`payment-method ${Number(card) > 0 ? 'active' : ''}`}>
            <label>💳 Card <span>Rs.</span></label>
            <input type="text" inputMode="decimal" value={card} onChange={e => { const v = e.target.value; if (v === '' || moneyInputPattern.test(v)) setCard(v); }} placeholder="0.00" />
          </div>
          <div className={`payment-method ${Number(online) > 0 ? 'active' : ''}`}>
            <label>🏦 Online <span>Rs.</span></label>
            <input type="text" inputMode="decimal" value={online} onChange={e => { const v = e.target.value; if (v === '' || moneyInputPattern.test(v)) setOnline(v); }} placeholder="0.00" />
          </div>

          {changeDue > 0 && (
            <div className="sales-change-due">
              <span>CHANGE TO GIVE</span>
              <span className="amount">Rs. {money(changeDue.toFixed(2))}</span>
            </div>
          )}

          {cart.length > 0 && (
            <div className={`sales-paid-status ${isFullyPaid ? 'complete' : ''}`}>
              <span>{isFullyPaid ? '✓ Paid in full' : 'Remaining'}</span>
              <span>Rs. {money((isFullyPaid ? totalPaid : remaining).toFixed(2))} / Rs. {money(total)}</span>
            </div>
          )}

          {isAdmin && (
            <div className="sales-admin-row">
              <label><input type="checkbox" checked={credit} onChange={e => setCredit(e.target.checked)} /> Credit Sale</label>
            </div>
          )}

          {isAdmin && (
            <div className="sales-admin-row">
              <label><input type="checkbox" checked={!!saleDateTime} onChange={e => {
                if (e.target.checked) {
                  const now = new Date();
                  const pad = (n:number) => String(n).padStart(2, '0');
                  const local = `${now.getFullYear()}-${pad(now.getMonth()+1)}-${pad(now.getDate())}T${pad(now.getHours())}:${pad(now.getMinutes())}`;
                  setSaleDateTime(local);
                } else {
                  setSaleDateTime('');
                }
              }} /> Backdate sale</label>
              {saleDateTime && <input type="datetime-local" value={saleDateTime} onChange={e => setSaleDateTime(e.target.value)} />}
            </div>
          )}

          {credit && (
            <div className="sales-panel" style={{ background: 'var(--surface-2)', marginTop: 'var(--space-2)' }}>
              <div style={{ display: 'flex', gap: 'var(--space-2)' }}>
                <input placeholder="Customer name / contact" value={customerQuery} onChange={e => setCustomerQuery(e.target.value)} onKeyDown={e => e.key === 'Enter' && searchCustomers()} style={{ flex: 1, padding: 'var(--space-2)', border: '1px solid var(--line)', borderRadius: 'var(--radius-sm)', background: 'var(--surface)', color: 'var(--text)' }} />
                <button type="button" onClick={searchCustomers} style={{ padding: 'var(--space-2) var(--space-3)', background: 'var(--accent)', color: '#fff', border: 0, borderRadius: 'var(--radius-sm)', cursor: 'pointer', fontWeight: 600 }}>Find</button>
              </div>
              <select value={customer} onChange={e => setCustomer(e.target.value)} style={{ width: '100%', marginTop: 'var(--space-2)', padding: 'var(--space-2)', border: '1px solid var(--line)', borderRadius: 'var(--radius-sm)', background: 'var(--surface)', color: 'var(--text)' }}>
                <option value="">Select customer</option>
                {customers.map(c => <option key={c.customer_id} value={c.customer_id}>{c.name || 'Unnamed'} · {c.contact_no || 'No contact'}</option>)}
              </select>
              <div style={{ display: 'flex', gap: 'var(--space-2)', marginTop: 'var(--space-2)' }}>
                <input id="newCustomerName" placeholder="New customer name" style={{ flex: 1, padding: 'var(--space-2)', border: '1px solid var(--line)', borderRadius: 'var(--radius-sm)', background: 'var(--surface)', color: 'var(--text)' }} />
                <input id="newCustomerContact" placeholder="Contact no." style={{ flex: 1, padding: 'var(--space-2)', border: '1px solid var(--line)', borderRadius: 'var(--radius-sm)', background: 'var(--surface)', color: 'var(--text)' }} />
                <button type="button" onClick={async () => {
                  try {
                    const n = (document.getElementById('newCustomerName') as HTMLInputElement)?.value.trim();
                    const c = (document.getElementById('newCustomerContact') as HTMLInputElement)?.value.trim();
                    if (!n && !c) { onError('Enter customer name or contact.'); return; }
                    const r = await api<any>('/customers', { method: 'POST', body: JSON.stringify({ name: n || null, contact_no: c || null, notes: null }) });
                    setCustomer(r.customer_id);
                    setCustomerQuery(r.name || r.contact_no || '');
                    searchCustomers();
                  } catch (e) { onError((e as Error).message); }
                }} style={{ padding: 'var(--space-2) var(--space-3)', background: 'var(--accent)', color: '#fff', border: 0, borderRadius: 'var(--radius-sm)', cursor: 'pointer', fontWeight: 600 }}>Create</button>
              </div>
              <button type="button" disabled={!customer} onClick={loadCustomerHistory} style={{ marginTop: 'var(--space-2)', padding: 'var(--space-2) var(--space-3)', background: 'var(--surface)', border: '1px solid var(--line)', borderRadius: 'var(--radius-sm)', color: 'var(--text)', cursor: customer ? 'pointer' : 'not-allowed' }}>History</button>
              {customerHistory && (
                <div style={{ marginTop: 'var(--space-2)', padding: 'var(--space-2)', background: 'var(--surface)', border: '1px solid var(--line)', borderRadius: 'var(--radius-sm)' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--space-1)' }}>
                    <b>{customerHistory.customer?.name || customerHistory.customer?.contact_no || 'Customer'}</b>
                    <button type="button" onClick={() => setCustomerHistory(null)}>Close</button>
                  </div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--muted)' }}>
                    Sales: {customerHistory.sales?.length || 0} · Repairs: {customerHistory.repairs?.length || 0} · Warranty: {customerHistory.warranty_claims?.length || 0}
                  </div>
                </div>
              )}
              {isAdmin && (
                <div style={{ marginTop: 'var(--space-2)', display: 'flex', gap: 'var(--space-2)' }}>
                  <input type="text" inputMode="decimal" placeholder="Settlement amount" value={settleAmount} onChange={e => { const v = e.target.value; if (v === '' || moneyInputPattern.test(v)) setSettleAmount(v); }} style={{ flex: 1, padding: 'var(--space-2)', border: '1px solid var(--line)', borderRadius: 'var(--radius-sm)', background: 'var(--surface)', color: 'var(--text)' }} />
                  <select value={settleMethod} onChange={e => setSettleMethod(e.target.value)} style={{ padding: 'var(--space-2)', border: '1px solid var(--line)', borderRadius: 'var(--radius-sm)', background: 'var(--surface)', color: 'var(--text)' }}>
                    <option>CASH</option>
                    <option>CARD</option>
                    <option>ONLINE</option>
                  </select>
                  <button type="button" disabled={!customer || !settleAmount} onClick={async () => {
                    try {
                      const r = await api<any>('/settlements', { method: 'POST', body: JSON.stringify({ idempotency_key: settlementKey, customer_id: customer, amount: settleAmount, payment_method: settleMethod }) });
                      setSettleAmount('');
                      setSettlementKey(crypto.randomUUID());
                      alert(`Settlement ${r.proof_no} recorded · Remaining Rs. ${money(r.remaining_outstanding)}`);
                      await api(`/documents/SETTLEMENT/${r.settlement_id}/reprint`, { method: 'POST' });
                    } catch (e) { onError((e as Error).message); }
                  }} style={{ padding: 'var(--space-2) var(--space-3)', background: 'var(--accent)', color: '#fff', border: 0, borderRadius: 'var(--radius-sm)', cursor: (customer && settleAmount) ? 'pointer' : 'not-allowed', fontWeight: 600 }}>Settle</button>
                </div>
              )}
            </div>
          )}

          <div className="sales-doc-row">
            <select value={doc} onChange={e => setDoc(e.target.value as DocType)}>
              <option value="SYSTEM_PRINTED">Thermal Receipt</option>
              <option value="MANUAL">Manual Invoice</option>
              <option value="NO_PRINT">No Print</option>
            </select>
            {doc === 'MANUAL' && <input placeholder="Handwritten invoice reference" value={manualRef} onChange={e => setManualRef(e.target.value)} style={{ flex: 1, padding: 'var(--space-2)', border: '1px solid var(--line)', borderRadius: 'var(--radius-sm)', background: 'var(--surface)', color: 'var(--text)' }} />}
          </div>

          {pendingApproval && (
            <div className="approval-box" style={{ marginTop: 'var(--space-2)' }}>
              <b>Discount approval</b>
              <span>Request: {pendingApproval.approval_action_id}</span>
              <label>Approved approval ID<input value={approvalId} onChange={e => setApprovalId(e.target.value)} placeholder="Paste approved approval_id" /></label>
              <small>Do not reuse an approval for a different sale. The backend validates the approved request.</small>
            </div>
          )}

          <button className="sales-complete-btn" disabled={!cart.length || busy || (!credit && !isFullyPaid)} onClick={handleCompleteSale}>
            {busy ? 'Processing…' : credit ? '✓ Complete Credit Sale' : '✓ Complete Sale'}
          </button>
        </div>
      </div>
    </section>
  );
}

function StockTab(){const [rows,setRows]=useState<any[]>([]),[age,setAge]=useState<any[]>([]),[serialRows,setSerialRows]=useState<any[]>([]),[q,setQ]=useState(''),[serial,setSerial]=useState('');async function load(){try{setRows(await api<any[]>('/inventory/summary'))}catch{}}async function loadAge(){try{setAge(await api<any[]>('/reports/stock-age',{method:'POST',body:JSON.stringify({start:today(),end:today()})}))}catch{}}async function findSerial(){try{setSerialRows(await api<any[]>(`/inventory/serialized/search?q=${encodeURIComponent(serial.trim())}`))}catch{setSerialRows([])}}useEffect(()=>{load()},[]);return <section className="glass panel"><div className="section-head"><h2>Stock Count / Serial & IMEI</h2><div><button onClick={load}>Refresh</button><button onClick={loadAge}>Stock Age by Batch</button></div></div><div className="search-row"><input placeholder="Search IMEI / Serial / barcode" value={serial} onChange={e=>setSerial(e.target.value)} onKeyDown={e=>e.key==='Enter'&&findSerial()}/><button onClick={findSerial}>Find Serial / IMEI</button></div>{serialRows.length>0&&<div className="glass panel"><h3>Serialized Units</h3>{serialRows.map(x=><div className="stock-row" key={x.serialized_unit_id}><span>{x.serial_number} · {x.item_code} · {x.description}</span><b>{x.status||'—'}</b></div>)}</div>}<input className="wide-input" placeholder="Filter stock" value={q} onChange={e=>setQ(e.target.value)}/>{rows.filter(x=>(x.item_code+' '+x.description).toLowerCase().includes(q.toLowerCase())).map(x=><div className="stock-row" key={x.item_id}><span>{x.item_code} · {x.description}</span><b>{money(x.stock)}{Number(x.stock)<0?' · NEGATIVE':''}</b></div>)}{age.length>0&&<><h3>Purchase Batch Age</h3>{age.map(x=><div className="stock-row" key={x.lot_id}><span>{x.item_code} · {x.description} · {x.lot_date}</span><b>{x.remaining_quantity} units · {x.age_days} days</b></div>)}</>}</section>}

function ExpensesTab({onError}:{onError:(x:string)=>void}){
  const [mode,setMode]=useState<'EXPENSE'|'INCOME'>('EXPENSE'),[cats,setCats]=useState<any[]>([]),[category,setCategory]=useState(''),[date,setDate]=useState(today()),[amount,setAmount]=useState(''),[method,setMethod]=useState('CASH'),[description,setDescription]=useState(''),[busy,setBusy]=useState(false),[last,setLast]=useState<any>();
  async function load(){try{const c=await api<any[]>('/admin/expense-categories');setCats(c);if(!category&&c[0])setCategory(c[0].id)}catch(e){onError((e as Error).message)}}
  useEffect(()=>{load()},[]);
  async function save(){if(!amount)return;setBusy(true);try{const path=mode==='EXPENSE'?'/admin/expenses':'/admin/other-income';const body=mode==='EXPENSE'?{category_id:category,expense_date:date,amount,payment_method:method,description:description||null}:{income_date:date,amount,payment_method:method,description:description||null};const r=await api(path,{method:'POST',body:JSON.stringify(body)});setLast({...r,mode});setAmount('');setDescription('')}catch(e){onError((e as Error).message)}finally{setBusy(false)}}
  return <section className="glass panel"><div className="section-head"><h2>Expenses / Other Income</h2><button onClick={load}>Refresh</button></div><div className="button-row"><button className={mode==='EXPENSE'?'':'ghost'} onClick={()=>setMode('EXPENSE')}>Expense</button><button className={mode==='INCOME'?'':'ghost'} onClick={()=>setMode('INCOME')}>Other Income</button></div><div className="form-grid compact">{mode==='EXPENSE'&&<select value={category} onChange={e=>setCategory(e.target.value)}><option value="">Category</option>{cats.map(c=><option key={c.id} value={c.id}>{c.name}</option>)}</select>}<input type="date" value={date} onChange={e=>setDate(e.target.value)}/><input {...moneyInputProps(amount, setAmount)} placeholder="Amount"/><select value={method} onChange={e=>setMethod(e.target.value)}><option>CASH</option><option>CARD</option><option>ONLINE</option></select><input placeholder="Description / note" value={description} onChange={e=>setDescription(e.target.value)}/><button disabled={busy||!amount||(mode==='EXPENSE'&&!category)} onClick={save}>{busy?'Saving…':mode==='EXPENSE'?'Add Expense':'Add Other Income'}</button></div>{last&&<div className="success-banner">{mode==='EXPENSE'?'Expense':'Other income'} saved · {last.status==='PENDING_APPROVAL'?'Pending Admin approval':'Approved'}</div>}<p className="muted">Cashier entries remain pending until Admin approval. Expenses are monthly outflows and do not automatically reduce the Day-End drawer.</p></section>}

function ReportsTab({isAdmin,onError}:{isAdmin:boolean,onError:(x:string)=>void}){
 const [d,setD]=useState<any>(),[comparison,setComparison]=useState<any>(),[cashHands,setCashHands]=useState<any>(),[cashiers,setCashiers]=useState<any[]>([]),[rows,setRows]=useState<any[]>([]),[start,setStart]=useState(today()),[end,setEnd]=useState(today()),[reportType,setReportType]=useState('sales'),[loading,setLoading]=useState(false);
 async function load(){try{setLoading(true);const range={start,end};setRows([]);setComparison(undefined);setCashHands(undefined);setCashiers([]);if(reportType==='sales'||reportType==='profit'){setD(await api('/reports/sales-summary',{method:'POST',body:JSON.stringify(range)}));setComparison(await api('/reports/comparison',{method:'POST',body:JSON.stringify(range)}));if(isAdmin)setCashiers(await api('/reports/cashiers',{method:'POST',body:JSON.stringify(range)}));}else if(reportType==='cash-in-hands'){if(isAdmin)setCashHands(await api('/reports/cash-in-hands',{method:'POST',body:JSON.stringify(range)}));}else if(reportType==='stock'){setRows(await api<any[]>('/inventory/summary'));}else{const path=reportType==='purchases'?'/reports/purchases':reportType==='repairs'?'/reports/repairs':reportType==='warranty'?'/reports/warranty':'/reports/cash-drawer';setRows(await api(path,{method:'POST',body:JSON.stringify(range)}));}}catch(e){onError((e as Error).message)}finally{setLoading(false)}}
 async function exportReport(fmt:'xlsx'|'pdf'){try{const token=localStorage.getItem('ltpos_token')||'';const apiBase=(import.meta.env.VITE_API_BASE??'/api/v1').replace(/\/$/,'');const r=await fetch(`${apiBase}/reports/export/${reportType}/${fmt}`,{method:'POST',headers:{'Content-Type':'application/json','Authorization':`Bearer ${token}`},body:JSON.stringify({start,end})});if(!r.ok)throw new Error(await r.text());const b=await r.blob();const u=URL.createObjectURL(b);const a=document.createElement('a');a.href=u;a.download=`lovely-tech-${reportType}-${start}-to-${end}.${fmt}`;a.click();URL.revokeObjectURL(u)}catch(e){onError((e as Error).message)}}
 function preset(kind:string){const now=new Date();if(kind==='today'){const x=today();setStart(x);setEnd(x)}else if(kind==='yesterday'){now.setDate(now.getDate()-1);const x=now.toISOString().slice(0,10);setStart(x);setEnd(x)}else if(kind==='month'){const x=today();setStart(x.slice(0,7)+'-01');setEnd(x)}else if(kind==='year'){const x=today();setStart(x.slice(0,4)+'-01-01');setEnd(x)}else{now.setMonth(now.getMonth()-1);const x=now.toISOString().slice(0,10);const e=new Date(now.getFullYear(),now.getMonth()+1,0).toISOString().slice(0,10);setStart(x.slice(0,7)+'-01');setEnd(e)}}
 return <section className="report-page"><div className="glass panel"><div className="section-head"><div><h2>Reports</h2><p className="muted">Daily, monthly, yearly/custom-range operational reports with PDF/Excel export.</p></div><div className="button-row"><button disabled={loading} onClick={load}>{loading?'Loading…':'Load'}</button><select value={reportType} onChange={e=>{setReportType(e.target.value);setRows([])}}><option value="sales">Sales</option><option value="profit" disabled={!isAdmin}>Profit (Admin)</option><option value="purchases" disabled={!isAdmin}>Purchases (Admin)</option><option value="repairs">Repairs</option><option value="warranty">Warranty</option><option value="cash-drawer" disabled={!isAdmin}>Cash Drawer (Admin)</option><option value="cash-in-hands" disabled={!isAdmin}>Cash In Hands (Admin)</option><option value="stock">Stock</option></select><button onClick={()=>exportReport('xlsx')}>Excel</button><button onClick={()=>exportReport('pdf')}>PDF</button></div></div><div className="button-row"><button onClick={()=>preset('today')}>Today</button><button onClick={()=>preset('yesterday')}>Yesterday</button><button onClick={()=>preset('month')}>This Month</button><button onClick={()=>preset('year')}>This Year</button><button onClick={()=>preset('previous')}>Previous Month</button></div><div className="date-row"><input type="date" value={start} onChange={e=>setStart(e.target.value)}/><input type="date" value={end} onChange={e=>setEnd(e.target.value)}/></div></div>
 {reportType==='sales'||reportType==='profit'?<><div className="glass panel"><div className="report-grid"><Metric t="Sales" v={`Rs. ${money(d?.sales_total)}`}/><Metric t="Bills" v={d?.sales_count??0}/><Metric t="Cash" v={`Rs. ${money(d?.cash_total)}`}/><Metric t="Card" v={`Rs. ${money(d?.card_total)}`}/><Metric t="Online" v={`Rs. ${money(d?.online_total)}`}/>{isAdmin&&<><Metric t="Cost" v={`Rs. ${money(d?.cost_total)}`}/><Metric t="Gross Profit" v={`Rs. ${money(d?.gross_profit)}`}/><Metric t="Refunds" v={`Rs. ${money(d?.refunds_total)}`}/><Metric t="Return Charges" v={`Rs. ${money(d?.return_charge_total)}`}/><Metric t="Expenses" v={`Rs. ${money(d?.expenses_total)}`}/><Metric t="Other Income" v={`Rs. ${money(d?.other_income_total)}`}/><Metric t="Repair Income" v={`Rs. ${money(d?.repair_income)}`}/><Metric t="Repair Profit" v={`Rs. ${money(d?.repair_profit)}`}/><Metric t="Damage/Loss" v={`Rs. ${money(d?.damage_loss_total)}`}/><Metric t="Net Profit" v={`Rs. ${money(d?.net_profit)}`}/></>}</div></div></>:null}
 {reportType==='cash-in-hands'&&isAdmin&&<div className="glass panel"><h3>Cash In Hands</h3><div className="cash-total-box"><span>Approved inflows − approved outflows</span><strong>Rs. {money(cashHands?.cash_in_hands)}</strong></div></div>}
 {reportType==='stock'&&<ReportRows title="Current Stock" rows={rows} fields={['item_code','description','stock']} />}
 {reportType==='purchases'&&isAdmin&&<ReportRows title="Purchases" rows={rows} fields={['purchase_date','reference_no','item_id','quantity','unit_cost']} />}
 {reportType==='repairs'&&<ReportRows title="Repairs" rows={rows} fields={['repair_no','date_in','status','total_amount','labour_amount','payments_total']} />}
 {reportType==='warranty'&&<ReportRows title="Warranty Claims" rows={rows} fields={['claim_no','created_at','item_id','quantity','decision','outcome']} />}
 {reportType==='cash-drawer'&&isAdmin&&<ReportRows title="Cash Drawer" rows={rows} fields={['business_date','opening_cash','expected_cash','actual_cash','difference','reload_total','reason']} />}
 {comparison&&<div className="glass panel"><h3>Previous-period comparison</h3><div className="comparison-row"><span>Sales</span><div className="compare-bar"><i style={{width:`${Math.min(100,Number(comparison.current.sales_total)/(Math.max(1,Number(comparison.previous.sales_total)))*100)}%`}}/></div><b>Rs. {money(comparison.current.sales_total)} vs Rs. {money(comparison.previous.sales_total)}</b></div><div className="comparison-row"><span>Bills</span><div className="compare-bar"><i style={{width:`${Math.min(100,Number(comparison.current.sales_count)/(Math.max(1,Number(comparison.previous.sales_count)))*100)}%`}}/></div><b>{comparison.current.sales_count} vs {comparison.previous.sales_count}</b></div></div>}{isAdmin&&cashiers.length>0&&<div className="glass panel"><h3>Cashier Summary</h3>{cashiers.map(c=><div className="stock-row" key={c.cashier_id}><span>{c.cashier_name} · {c.sales_count} bills</span><b>Rs. {money(c.gross_profit)} gross profit</b></div>)}</div>}</section>}
function ReportRows({title,rows,fields}:{title:string;rows:any[];fields:string[]}){return <div className="glass panel"><div className="section-head"><h3>{title}</h3><span className="muted">{rows.length} rows</span></div>{rows.length===0?<p className="muted">No records for this date range.</p>:rows.map((r,i)=><div className="stock-row" key={r.id||r.purchase_line_id||r.claim_id||r.repair_id||`${title}-${i}`}><span>{fields.slice(0,Math.ceil(fields.length/2)).map(f=><span key={f}>{f.replaceAll('_',' ')}: {String(r[f]??'—')} · </span>)}</span><b>{fields.slice(Math.ceil(fields.length/2)).map(f=>`${f.replaceAll('_',' ')}: ${r[f]??'—'}`).join(' · ')}</b></div>)}</div>}

function DocumentsTab({onError}:{onError:(x:string)=>void}){
  const shop = useShopProfile();
  const [fullShop, setFullShop] = useState<any>(null);
  const [dateFrom,setDateFrom]=useState(today());
  const [dateTo,setDateTo]=useState(today());
  const [docType,setDocType]=useState('');
  const [statusFilter,setStatusFilter]=useState('');
  const [q,setQ]=useState('');
  const [rows,setRows]=useState<any[]>([]);
  const [total,setTotal]=useState(0);
  const [hasMore,setHasMore]=useState(false);
  const [busy,setBusy]=useState(false);
  const [loadingMore,setLoadingMore]=useState(false);
  const [last,setLast]=useState('');
  const debounceRef = useRef<number | null>(null);

  useEffect(() => {
    (async () => {
      try { setFullShop(await api('/branch/profile')); } catch { /* ignore */ }
    })();
  }, []);

  async function load(append = false) {
    try {
      if (append) setLoadingMore(true); else setBusy(true);
      const params = new URLSearchParams();
      if (dateFrom) params.set('date_from', dateFrom);
      if (dateTo) params.set('date_to', dateTo);
      if (docType) params.set('document_type', docType);
      if (statusFilter) params.set('status', statusFilter);
      if (q.trim()) params.set('q', q.trim());
      params.set('limit', '50');
      params.set('offset', String(append ? rows.length : 0));
      const result = await api<{ items:any[]; total:number; has_more:boolean }>(`/documents?${params.toString()}`);
      if (append) setRows(prev => [...prev, ...result.items]);
      else setRows(result.items);
      setTotal(result.total);
      setHasMore(result.has_more);
      if (!append) setLast('');
    } catch (e) {
      onError((e as Error).message);
    } finally {
      setBusy(false);
      setLoadingMore(false);
    }
  }

  // Auto-load on mount + when filters change (debounced for q)
  useEffect(() => {
    if (debounceRef.current) window.clearTimeout(debounceRef.current);
    const delay = q !== '' ? 300 : 0;
    debounceRef.current = window.setTimeout(() => { void load(false); }, delay);
    return () => { if (debounceRef.current) window.clearTimeout(debounceRef.current); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dateFrom, dateTo, docType, statusFilter, q]);

  function quick(kind: 'today' | 'yesterday' | 'week' | 'month') {
    const now = new Date();
    if (kind === 'today') { setDateFrom(today()); setDateTo(today()); }
    else if (kind === 'yesterday') {
      const y = new Date(now); y.setDate(y.getDate()-1);
      const s = y.toISOString().slice(0,10); setDateFrom(s); setDateTo(s);
    } else if (kind === 'week') {
      const w = new Date(now); w.setDate(w.getDate()-6);
      setDateFrom(w.toISOString().slice(0,10)); setDateTo(today());
    } else {
      const m = new Date(now); m.setDate(m.getDate()-29);
      setDateFrom(m.toISOString().slice(0,10)); setDateTo(today());
    }
  }

  async function reprint(r:any) {
    // Pre-open print window synchronously to bypass popup blocker
    const w = window.open('', '_blank', 'width=420,height=640');
    if (!w) {
      onError('Print popup was blocked. Please allow popups for this site and try again.');
      return;
    }
    try {
      setBusy(true);

      // Record reprint event on backend
      await api<any>(`/documents/${r.document_type}/${r.document_id}/reprint`, { method:'POST' });

      // Build print HTML
      let html = '';
      if (r.document_type === 'SALE') {
        try {
          const saleDetail = await api<any>(`/sales/${encodeURIComponent(r.document_no)}`);
          html = buildReceiptHTML(saleDetail, shop, fullShop);
        } catch {
          html = buildGenericReprintHTML(r);
        }
      } else {
        html = buildGenericReprintHTML(r);
      }

      w.document.open();
      w.document.write(html);
      w.document.close();

      setLast(String(r.document_no || ''));
      toast.success(`Reprint opened: ${r.document_no}`);
    } catch (e) {
      try { w.close(); } catch { /* ignore */ }
      onError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return <section className="glass panel">
    <div className="section-head">
      <div>
        <h2>Documents / History</h2>
        <p className="muted">Browse all sale, repair, repair-payment and settlement documents. Filter by date/type or search, then reprint.</p>
      </div>
      <button onClick={() => void load(false)} disabled={busy}>{busy ? 'Refreshing…' : 'Refresh'}</button>
    </div>

    <div className="form-grid compact" style={{ marginBottom: '0.5rem' }}>
      <label>From<input type="date" value={dateFrom} onChange={e=>setDateFrom(e.target.value)} /></label>
      <label>To<input type="date" value={dateTo} onChange={e=>setDateTo(e.target.value)} /></label>
      <div className="button-row">
        <button type="button" onClick={()=>quick('today')}>Today</button>
        <button type="button" onClick={()=>quick('yesterday')}>Yest</button>
        <button type="button" onClick={()=>quick('week')}>Week</button>
        <button type="button" onClick={()=>quick('month')}>Month</button>
      </div>
    </div>

    <div className="form-grid compact" style={{ marginBottom: '0.5rem' }}>
      <label>Type
        <select value={docType} onChange={e=>setDocType(e.target.value)}>
          <option value="">All documents</option>
          <option value="SALE">Sales</option>
          <option value="REPAIR">Repairs</option>
          <option value="REPAIR_PAYMENT">Repair payments</option>
          <option value="SETTLEMENT">Settlements</option>
        </select>
      </label>
      <label>Status
        <select value={statusFilter} onChange={e=>setStatusFilter(e.target.value)}>
          <option value="">All statuses</option>
          <option value="COMPLETED">Completed</option>
          <option value="VOIDED">Voided</option>
          <option value="RECEIVED">Received</option>
          <option value="REPAIRING">Repairing</option>
          <option value="READY">Ready</option>
          <option value="DELIVERED">Delivered</option>
          <option value="CANCELLED">Cancelled</option>
        </select>
      </label>
    </div>

    <div className="search-row" style={{ marginBottom: '0.5rem' }}>
      <input value={q} onChange={e=>setQ(e.target.value)} placeholder="Search invoice / repair no / proof no / customer / item…" />
    </div>

    {last && (
      <div
        className="success-banner"
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          gap: '0.5rem',
          marginBottom: '0.5rem',
        }}
      >
        <span>✓ Reprint opened for <b>{last}</b></span>
        <button
          type="button"
          onClick={() => setLast('')}
          aria-label="Dismiss"
          style={{
            background: 'transparent',
            border: 0,
            cursor: 'pointer',
            color: 'inherit',
            fontSize: 18,
            lineHeight: 1,
            padding: '0 4px',
          }}
        >
          ×
        </button>
      </div>
    )}

    {busy && rows.length === 0 ? (
      <div style={{ padding: '2rem', textAlign: 'center' }}>
        <span className="spinner spinner-lg" />
        <p className="muted" style={{ marginTop: '0.5rem' }}>Loading documents…</p>
      </div>
    ) : rows.length === 0 ? (
      <div className="empty-state" style={{ padding: '2rem', textAlign: 'center' }}>
        <b>No documents found for these filters</b>
        <span className="muted">Try a wider date range or clear the search.</span>
      </div>
    ) : (
      <>
        <div style={{ overflowX: 'auto' }}>
          <table className="data-table" style={{ width: '100%' }}>
            <thead>
              <tr>
                <th>Type</th>
                <th>Document No</th>
                <th>Date</th>
                <th>Status</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {rows.map(r => {
                const st = String(r.status || '').toUpperCase();
                const isBad = st === 'VOIDED' || st === 'CANCELLED';
                return (
                  <tr key={`${r.document_type}-${r.document_id}`}>
                    <td>
                      <span className="sh-status" style={{ background: 'var(--surface-2)', color: 'var(--text)' }}>
                        {r.document_type}
                      </span>
                    </td>
                    <td><b>{r.document_no}</b></td>
                    <td>{r.document_datetime ? new Date(r.document_datetime).toLocaleString() : '—'}</td>
                    <td>
                      <span className={`sh-status ${isBad ? 'sh-status-void' : 'sh-status-ok'}`}>{r.status}</span>
                    </td>
                    <td style={{ textAlign: 'right' }}>
                      <button disabled={busy} onClick={()=>void reprint(r)}>Reprint</button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '0.5rem 0.75rem', borderTop: '1px solid var(--line)' }}>
          <span className="muted" style={{ fontSize: '0.75rem' }}>Showing {rows.length} of {total}</span>
          {hasMore && (
            <button className="ghost" onClick={()=>void load(true)} disabled={loadingMore}>
              {loadingMore ? 'Loading…' : 'Load more'}
            </button>
          )}
        </div>
      </>
    )}
  </section>;
}

const Metric=({t,v,icon}:{t:string,v:any,icon?:string})=><div className="metric metric-animated"><span><i>{icon||'•'}</i>{t}</span><b>{v}</b></div>;
function ItemsTab({onError}:{onError:(x:string)=>void}){
  return <section className="items-page"><div className="glass panel page-intro rise-in"><span className="eyebrow">INVENTORY MASTER</span><div className="section-head"><div><h2>Items & Item Master</h2><p className="muted">Create or edit items, barcodes, variants and compatibility. Buy cost is never entered here.</p></div><span className="feature-badge">FIFO • IMEI • BARCODE</span></div></div><ItemMasterPanel onError={onError}/></section>}

function ItemMasterPanel({onError}:{onError:(x:string)=>void}){
  const empty={description:'',category_id:'',item_type_id:'',brand:'',model:'',compatible_models:'',master_sale_price:'',barcode:''};
  const [q,setQ]=useState(''),[rows,setRows]=useState<any[]>([]),[masters,setMasters]=useState<any>({categories:[],item_types:[]}),[form,setForm]=useState<any>(empty),[editing,setEditing]=useState<any>(),[busy,setBusy]=useState(false),[variantName,setVariantName]=useState(''),[variantValue,setVariantValue]=useState(''),[variants,setVariants]=useState<any[]>([]),[warranty,setWarranty]=useState<any>({warranty_type:'NONE',duration_value:'',custom_rule:''});
  async function load(){try{setBusy(true);const [r,m]=await Promise.all([api<any[]>(`/items/admin-list?q=${encodeURIComponent(q)}`),api<any>('/items/masters')]);setRows(r);setMasters(m)}catch(e){onError((e as Error).message)}finally{setBusy(false)}}
  useEffect(()=>{load()},[]);
  function startNew(){setEditing(undefined);setForm(empty);setWarranty({warranty_type:'NONE',duration_value:'',custom_rule:''});setVariants([]);setVariantName('');setVariantValue('')}
  async function edit(x:any){setEditing(x);setForm({description:x.description,category_id:x.category_id,item_type_id:x.item_type_id,brand:x.brand||'',model:x.model||'',compatible_models:x.compatible_models||'',master_sale_price:x.master_sale_price==null?'':String(x.master_sale_price),barcode:''});setWarranty({warranty_type:x.warranty_default?.warranty_type||'NONE',duration_value:x.warranty_default?.duration_value==null?'':String(x.warranty_default.duration_value),custom_rule:x.warranty_default?.custom_rule||''});try{setVariants(await api<any[]>(`/items/${x.item_id}/variants`))}catch{setVariants([])}}
  async function save(){try{if(!form.description||!form.category_id||!form.item_type_id){onError('Description, category and item type are required.');return}const payload={description:form.description,category_id:form.category_id,item_type_id:form.item_type_id,brand:form.brand||null,model:form.model||null,compatible_models:form.compatible_models||null,master_sale_price:form.master_sale_price||null,version:editing?.version};const r:any=editing?await api(`/items/${editing.item_id}`,{method:'PUT',body:JSON.stringify(payload)}):await api('/items',{method:'POST',body:JSON.stringify({...payload,barcode:form.barcode||null})});const itemId=editing?.item_id||r.item_id;if(itemId){await api(`/items/${itemId}/warranty-default`,{method:'PUT',body:JSON.stringify({warranty_type:warranty.warranty_type,duration_value:warranty.duration_value?Number(warranty.duration_value):null,custom_rule:warranty.custom_rule||null})})}if(editing&&form.barcode.trim())await api(`/items/${editing.item_id}/barcodes`,{method:'POST',body:JSON.stringify({barcode:form.barcode.trim(),is_primary:false})});setForm(empty);setEditing(undefined);await load();toast.success(editing?'Item updated':'Item created')}catch(e){onError((e as Error).message)}}
  return <div className="glass panel"><div className="section-head"><h3>Item Master</h3><button disabled={busy} onClick={load}>Refresh</button></div><div className="search-row"><input placeholder="Item code / description / brand / model" value={q} onChange={e=>setQ(e.target.value)} onKeyDown={e=>e.key==='Enter'&&load()}/><button onClick={load}>Search</button><button onClick={startNew}>New Item</button></div><div className="form-grid compact"><input placeholder="Description" value={form.description} onChange={e=>setForm({...form,description:e.target.value})}/><select value={form.category_id} onChange={e=>setForm({...form,category_id:e.target.value})}><option value="">Category</option>{masters.categories?.map((c:any)=><option key={c.id} value={c.id}>{c.name}</option>)}</select><select value={form.item_type_id} onChange={e=>setForm({...form,item_type_id:e.target.value})}><option value="">Item Type</option>{masters.item_types?.map((t:any)=><option key={t.id} value={t.id}>{t.name}</option>)}</select><input placeholder="Brand" value={form.brand} onChange={e=>setForm({...form,brand:e.target.value})}/><input placeholder="Model" value={form.model} onChange={e=>setForm({...form,model:e.target.value})}/><input placeholder="Also compatible with models (comma separated)" value={form.compatible_models} onChange={e=>setForm({...form,compatible_models:e.target.value})}/><input type="number" min="0" step="0.01" placeholder="Master sale price" value={form.master_sale_price} onChange={e=>setForm({...form,master_sale_price:e.target.value})}/><input placeholder="Barcode" value={form.barcode} onChange={e=>setForm({...form,barcode:e.target.value})}/><select value={warranty.warranty_type} onChange={e=>setWarranty({...warranty,warranty_type:e.target.value})}><option>NONE</option><option>DAYS</option><option>MONTHS</option><option>CHECKING ONLY</option><option>CUSTOM</option></select>{warranty.warranty_type==="DAYS"||warranty.warranty_type==="MONTHS"?<input type="number" min="1" placeholder="Warranty duration" value={warranty.duration_value} onChange={e=>setWarranty({...warranty,duration_value:e.target.value})}/>:null}{warranty.warranty_type==="CUSTOM"?<input placeholder="Custom warranty rule" value={warranty.custom_rule} onChange={e=>setWarranty({...warranty,custom_rule:e.target.value})}/>:null}<button onClick={save}>{editing?'Save Item':'Create Item'}</button>{editing&&<><input placeholder="Variant / compatibility name" value={variantName} onChange={e=>setVariantName(e.target.value)}/><input placeholder="Variant value (e.g. Original / A12)" value={variantValue} onChange={e=>setVariantValue(e.target.value)}/><button disabled={!variantName.trim()||!variantValue.trim()} onClick={async()=>{try{const r=await api<any>(`/items/${editing.item_id}/variants`,{method:'POST',body:JSON.stringify({name:variantName,value:variantValue})});setVariants(v=>v.concat(r));setVariantName('');setVariantValue('')}catch(e){onError((e as Error).message)}}}>Add Variant</button></>}</div>{editing&&variants.length>0&&<div className="stock-row"><span>Variants / Compatibility</span><b>{variants.map(v=>`${v.name}: ${v.value}`).join(' · ')}</b></div>}<div className="stock-row"><span>Categories</span><b>{masters.categories?.length??0}</b><span>Item Types</span><b>{masters.item_types?.length??0}</b></div>{rows.map(x=><div className="claim-row" key={x.item_id}><span><b>{x.item_code}</b> · {x.description}{x.brand?` · ${x.brand}`:''}{x.model?` · ${x.model}`:''}<small> · {x.is_active?'ACTIVE':'INACTIVE'} · {x.barcodes?.join(', ')||'No barcode'}</small></span><span><b>{x.master_sale_price==null?'No master price':`Rs. ${money(x.master_sale_price)}`}</b><button onClick={()=>edit(x)}>Edit</button></span></div>)}</div>}

function AdminTab({onError}:{onError:(x:string)=>void}){
 const [roles,setRoles]=useState<any[]>([]),[perms,setPerms]=useState<any[]>([]),[users,setUsers]=useState<any[]>([]),[targets,setTargets]=useState<any[]>([]),[approvals,setApprovals]=useState<any[]>([]),[expenses,setExpenses]=useState<any[]>([]),[otherIncome,setOtherIncome]=useState<any[]>([]),[audit,setAudit]=useState<any[]>([]),[targetHistory,setTargetHistory]=useState<any[]>([]),[suppliers,setSuppliers]=useState<any[]>([]),[supplierName,setSupplierName]=useState(''),[supplierContact,setSupplierContact]=useState(''),[supplierAddress,setSupplierAddress]=useState(''),[expenseCats,setExpenseCats]=useState<any[]>([]),[expenseCatName,setExpenseCatName]=useState(''),[target,setTarget]=useState({target_type:'SALES_AMOUNT',target_value:'',period_type:'DAILY',period_start:today(),period_end:today()});
 const [adminLoading,setAdminLoading]=useState(false);
 const modal = useModal();
 async function load(){try{setAdminLoading(true);const [r,p,u,t,a,e,au,h,sp,ec,oi]=await Promise.all([api<any[]>('/admin/roles'),api<any[]>('/admin/permissions'),api<any[]>('/admin/users'),api<any[]>('/admin/targets'),api<any[]>('/admin/approvals'),api<any[]>('/admin/pending-expenses'),api<any[]>('/admin/audit'),api<any[]>('/reports/target-history',{method:'POST',body:JSON.stringify({start:'2000-01-01',end:'2100-12-31'})}),api<any[]>('/admin/suppliers'),api<any[]>('/admin/expense-categories'),api<any[]>('/admin/pending-other-income')]);setOtherIncome(oi);setRoles(r);setPerms(p);setUsers(u);setTargets(t);setApprovals(a);setExpenses(e);setAudit(au);setTargetHistory(h);setSuppliers(sp);setExpenseCats(ec)}catch(e){onError((e as Error).message)}finally{setAdminLoading(false)}}
 useEffect(()=>{load()},[]);
  async function saveRole(r:any){try{const admin_password=(await modal.prompt({title:'Admin re-authentication',message:'Enter admin password to save role permissions',placeholder:'Password',confirmText:'Save',type:'password'}))||'';if(!admin_password)return;await api(`/admin/roles/${r.role_id}/permissions?admin_password=${encodeURIComponent(admin_password)}`,{method:'PUT',body:JSON.stringify({permission_codes:r.permissions})});load()}catch(e){onError((e as Error).message)}}
 async function addTarget(){try{await api('/admin/targets',{method:'POST',body:JSON.stringify({...target,target_value:String(target.target_value)})});setTarget({...target,target_value:''});load()}catch(e){onError((e as Error).message)}}
 async function addExpenseCategory(){if(!expenseCatName.trim())return onError('Expense category name is required.');try{await api('/admin/expense-categories',{method:'POST',body:JSON.stringify({name:expenseCatName.trim()})});setExpenseCatName('');load()}catch(e){onError((e as Error).message)}}
 async function addSupplier(){if(!supplierName.trim())return onError('Supplier name is required.');try{await api('/admin/suppliers',{method:'POST',body:JSON.stringify({name:supplierName.trim(),contact_no:supplierContact.trim()||null,address:supplierAddress.trim()||null})});setSupplierName('');setSupplierContact('');setSupplierAddress('');load()}catch(e){onError((e as Error).message)}}
 async function reviewExpense(x:any,approve:boolean){try{await api(`/admin/expenses/${x.expense_id}/decision?approve=${approve}&version=${encodeURIComponent(String(x.version??''))}&reason=${encodeURIComponent(approve?'Approved by Admin':'Rejected by Admin')}`,{method:'POST'});load()}catch(e){onError((e as Error).message)}}
 async function reviewOtherIncome(x:any,approve:boolean){try{await api(`/admin/other-income/${x.other_income_id}/decision?approve=${approve}&version=${encodeURIComponent(String(x.version??''))}&reason=${encodeURIComponent(approve?'Approved by Admin':'Rejected by Admin')}`,{method:'POST'});load()}catch(e){onError((e as Error).message)}}
 async function reviewApproval(a:any,approve:boolean){try{await api(`/approvals/${a.approval_id}/review`,{method:'POST',body:JSON.stringify({approve,version:a.version??null,reject_reason:approve?null:'Rejected by Admin'})});load()}catch(e){onError((e as Error).message)}}
 return <section className="admin-page" style={{ position: 'relative' }}>
  {adminLoading && (
    <div className="loading-overlay" aria-live="polite">
      <div style={{ display: 'grid', placeItems: 'center', gap: 8 }}>
        <span className="spinner spinner-lg" />
        <span style={{ fontSize: '0.8rem', color: 'var(--muted)' }}>Loading admin data…</span>
      </div>
    </div>
  )}
  <div className="glass panel"><div className="section-head"><div><h2>Admin / Controls</h2><p className="muted">Security, users, permissions, suppliers, targets and approvals.</p></div><button onClick={load}>Refresh</button></div></div>
  <CategoryTypeManager onError={onError}/>
  <div className="glass panel"><h3>Expense Categories</h3><p className="muted">Admin can add categories beyond the locked defaults.</p><div className="form-grid compact"><input placeholder="New expense category" value={expenseCatName} onChange={e=>setExpenseCatName(e.target.value)}/><button disabled={!expenseCatName.trim()} onClick={addExpenseCategory}>Add Expense Category</button></div>{expenseCats.map(c=><span key={c.id} className="feature-badge" style={{display:'inline-block',margin:'4px'}}>{c.name}</span>)}</div>
  <div className="glass panel"><h3>Suppliers</h3><p className="muted">Admin-only supplier master. Supplier payment is not part of purchase entry.</p><div className="form-grid compact"><input placeholder="Supplier name" value={supplierName} onChange={e=>setSupplierName(e.target.value)}/><input placeholder="Contact no." value={supplierContact} onChange={e=>setSupplierContact(e.target.value)}/><input placeholder="Address (optional)" value={supplierAddress} onChange={e=>setSupplierAddress(e.target.value)}/><button disabled={!supplierName.trim()} onClick={addSupplier}>Add Supplier</button></div>{suppliers.map(s=><div className="stock-row" key={s.supplier_id}><span><b>{s.name}</b> · {s.contact_no||'No contact'} · {s.address||'No address'}</span></div>)}</div>
  <div className="glass panel"><h3>Users</h3>{users.map(u=><UserRow key={u.user_id} user={u} onError={onError} onSaved={load}/>)}</div>
  <div className="glass panel"><h3>Cashier Password Reset</h3><PasswordResetPanel users={users.filter((u:any)=>u.role!=='ADMIN')} onError={onError}/></div>
  <div className="glass panel"><h3>Pending Expense Approvals</h3>{expenses.length===0?<p className="muted">No pending expenses.</p>:expenses.map(x=><div className="claim-row" key={x.expense_id}><span>{x.expense_date} · Rs. {money(x.amount)} · {x.description||'Expense'}</span><button onClick={()=>reviewExpense(x,true)}>Approve</button><button className="danger-button" onClick={()=>reviewExpense(x,false)}>Reject</button></div>)}</div>
  <div className="glass panel"><h3>Pending Other Income Approvals</h3>{otherIncome.length===0?<p className="muted">No pending other income.</p>:otherIncome.map(x=><div className="claim-row" key={x.other_income_id}><span>{x.income_date} · Rs. {money(x.amount)} · {x.description||'Other income'}</span><button onClick={()=>reviewOtherIncome(x,true)}>Approve</button><button className="danger-button" onClick={()=>reviewOtherIncome(x,false)}>Reject</button></div>)}</div>
  <div className="glass panel"><h3>Approval Requests</h3>{approvals.filter(x=>x.status==='PENDING').length===0?<p className="muted">No pending approval requests.</p>:approvals.filter(x=>x.status==='PENDING').map(x=><div className="claim-row" key={x.approval_id}><span><b>{x.approval_action_id||x.action_type}</b> · {String(x.action_type).replaceAll('_',' ')}{x.payload?.discount_percent!=null&&<> · discount {money(x.payload.discount_percent)}%</>}{Array.isArray(x.payload?.sale?.lines)&&<> · {x.payload.sale.lines.length} line(s), Rs. {money(x.payload.sale.payments?.reduce((t:string,p:any)=>moneyAdd(t,p.amount),'0')||'0')} to pay</>}<small> requested {x.requested_at?new Date(x.requested_at).toLocaleString():''}</small></span><button onClick={()=>reviewApproval(x,true)}>Approve</button><button className="danger-button" onClick={()=>reviewApproval(x,false)}>Reject</button></div>)}</div>
  <div className="glass panel"><h3>Targets</h3><div className="form-grid compact"><select value={target.target_type} onChange={e=>setTarget({...target,target_type:e.target.value})}>{['SALES_AMOUNT','ITEM_SALES_PROFIT','REPAIR_INCOME','REPAIR_PROFIT','BILLS_COUNT','ITEMS_SOLD_COUNT'].map(x=><option key={x}>{x}</option>)}</select><input {...moneyInputProps(target.target_value, (v)=>setTarget({...target,target_value:v}))} placeholder="Target value"/><select value={target.period_type} onChange={e=>setTarget({...target,period_type:e.target.value})}><option>DAILY</option><option>MONTHLY</option></select><input type="date" value={target.period_start} onChange={e=>setTarget({...target,period_start:e.target.value})}/><input type="date" value={target.period_end} onChange={e=>setTarget({...target,period_end:e.target.value})}/><button onClick={addTarget}>Add Target</button></div>{targets.map(t=><div className="stock-row" key={t.target_id}><span>{t.target_type} · {t.period_start} → {t.period_end}</span><b>{t.target_value}</b></div>)}<h4>Target Progress History</h4>{targetHistory.length===0?<p className="muted">No target history.</p>:targetHistory.map(t=><div className="stock-row" key={`history-${t.target_id}`}><span>{t.target_type} · {t.period_start} → {t.period_end}</span><b>{t.progress==null?'Not calculated':`${money(t.progress)}%`}</b></div>)}</div>
  <div className="glass panel"><h3>Stock Adjustment</h3><StockAdjustPanel onError={onError}/></div>
  <div className="glass panel"><h3>Damage / Loss Records</h3><DamageRestockPanel onError={onError}/></div>
  <div className="glass panel"><h3>Void Sale</h3><VoidSalePanel onError={onError}/></div>
  <div className="glass panel"><h3>Role Permissions</h3>{roles.filter(r=>r.code!=='ADMIN').map(r=><RoleEditor key={r.role_id} role={r} perms={perms} onSave={saveRole}/>)}</div>
  <div className="glass panel"><h3>Recent Audit</h3>{audit.slice(0,20).map(x=><div className="audit-row" key={x.audit_id}><span>{new Date(x.timestamp).toLocaleString()} · {x.action_type} · {x.entity_type}</span><small>{x.reason||''}</small></div>)}</div>
 </section>}

function CategoryTypeManager({onError}:{onError:(x:string)=>void}){const [categoryName,setCategoryName]=useState(''),[typeName,setTypeName]=useState(''),[code,setCode]=useState(''),[serialized,setSerialized]=useState(false),[busy,setBusy]=useState(false);async function addCategory(){try{setBusy(true);await api('/items/categories',{method:'POST',body:JSON.stringify({name:categoryName})});setCategoryName('');toast.success('Category added')}catch(e){onError((e as Error).message)}finally{setBusy(false)}}async function addType(){try{setBusy(true);await api('/items/item-types',{method:'POST',body:JSON.stringify({code,name:typeName,is_serialized:serialized})});setCode('');setTypeName('');setSerialized(false);toast.success('Item type added')}catch(e){onError((e as Error).message)}finally{setBusy(false)}}return <div className="glass panel"><h3>Category / Item Type Management</h3><div className="form-grid compact"><input placeholder="New category name" value={categoryName} onChange={e=>setCategoryName(e.target.value)}/><button disabled={busy||!categoryName.trim()} onClick={addCategory}>Add Category</button><input placeholder="Item type code" value={code} onChange={e=>setCode(e.target.value)}/><input placeholder="Item type name" value={typeName} onChange={e=>setTypeName(e.target.value)}/><label className="check"><input type="checkbox" checked={serialized} onChange={e=>setSerialized(e.target.checked)}/> Serialized / IMEI</label><button disabled={busy||!code.trim()||!typeName.trim()} onClick={addType}>Add Item Type</button></div></div>}

function UserRow({user,onError,onSaved}:{user:any,onError:(x:string)=>void,onSaved:()=>void}){const [limit,setLimit]=useState(String(user.discount_limit_percent??0));const [busy,setBusy]=useState(false);async function save(){if(busy)return;const n=Number(limit);if(!Number.isFinite(n)||n<0||n>100)return onError('Discount limit must be between 0 and 100%.');if(user.version==null)return onError('User version is missing; refresh before editing.');try{setBusy(true);await api(`/admin/users/${user.user_id}/discount-limit`,{method:'PUT',body:JSON.stringify({discount_limit_percent:String(n),version:user.version})});onSaved()}catch(e){onError((e as Error).message)}finally{setBusy(false)}}return <div className="stock-row"><span>{user.username} · {user.display_name} · {user.role} · v{user.version ?? '—'}</span><span className="inline-control">Discount limit % <input {...moneyInputProps(limit, setLimit)}/><button disabled={busy} onClick={save}>{busy?'Saving…':'Save'}</button></span></div>}
function StockAdjustPanel({onError}:{onError:(x:string)=>void}){const [item,setItem]=useState(''),[search,setSearch]=useState(''),[items,setItems]=useState<any[]>([]),[qty,setQty]=useState(''),[reason,setReason]=useState(''),[units,setUnits]=useState<any[]>([]),[picked,setPicked]=useState<string[]>([]);const chosen=items.find((x:any)=>x.item_id===item);const serialized=!!chosen?.is_serialized;const modal = useModal();async function find(){try{setItems(await api<any[]>(`/inventory/items/search?q=${encodeURIComponent(search.trim())}`))}catch(e){onError((e as Error).message)}}async function pickItem(id:string){setItem(id);setPicked([]);setUnits([]);const it=items.find((x:any)=>x.item_id===id);if(it?.is_serialized){try{setUnits(await api<any[]>(`/inventory/serialized/search?q=&item_id=${id}&status=IN_STOCK`))}catch(e){onError((e as Error).message)}}}async function save(){try{const admin_password=(await modal.prompt({title:'Admin re-authentication',message:'Enter admin password to adjust stock',placeholder:'Password',confirmText:'Adjust',type:'password'}))||'';if(!admin_password)return; await api(`/stock-control/adjust?admin_password=${encodeURIComponent(admin_password)}`,{method:'POST',body:JSON.stringify(serialized?{item_id:item,quantity_delta:String(-picked.length),reason:reason.trim(),serialized_unit_ids:picked}:{item_id:item,quantity_delta:String(qty),reason:reason.trim()})});setQty('');setReason('');setPicked([]);if(serialized)pickItem(item);toast.success('Stock adjustment saved')}catch(e){onError((e as Error).message)}}return <div className="form-grid compact"><input placeholder="Search item / code" value={search} onChange={e=>setSearch(e.target.value)} onKeyDown={e=>e.key==='Enter'&&find()}/><button onClick={find}>Find Item</button><select value={item} onChange={e=>pickItem(e.target.value)}><option value="">Select item</option>{items.map((x:any)=><option key={x.item_id} value={x.item_id}>{x.item_code} · {x.description} · Stock {x.stock}</option>)}</select>{serialized?<div className="wide-field"><p className="muted">IMEI-tracked phone: tick the phones to WRITE OFF (stock goes down by the number ticked). To add phones use Purchases with their IMEI.</p>{units.length===0?<p className="muted">No in-stock units.</p>:units.map((u:any)=><label className="check" key={u.serialized_unit_id}><input type="checkbox" checked={picked.includes(u.serialized_unit_id)} onChange={e=>setPicked(p=>e.target.checked?[...p,u.serialized_unit_id]:p.filter(x=>x!==u.serialized_unit_id))}/> {u.serial_number}</label>)}</div>:<input {...signedIntInputProps(qty, setQty)} placeholder="+/- Quantity"/>}<input placeholder="Required reason" value={reason} onChange={e=>setReason(e.target.value)}/><button disabled={serialized&&picked.length===0} onClick={save}>Adjust Stock</button></div>}
function VoidSalePanel({onError}:{onError:(x:string)=>void}){const [inv,setInv]=useState(''),[sale,setSale]=useState<any>(null),[reason,setReason]=useState(''),[busy,setBusy]=useState(false),[done,setDone]=useState('');const modal=useModal();async function find(){try{setDone('');setSale(await api<any>(`/sales/${encodeURIComponent(inv.trim())}`))}catch(e){setSale(null);onError((e as Error).message)}}async function voidIt(){if(busy||!sale)return;if(!reason.trim())return onError('Void reason is required.');if(!window.confirm(`Void ${sale.invoice_no}? Stock, IMEI, warranty, drawer and reports are reversed. The invoice number is never reused.`))return;const admin_password=(await modal.prompt({title:'Admin re-authentication',message:'Enter admin password to void this sale',placeholder:'Password',confirmText:'Void Sale',type:'password'}))||'';if(!admin_password)return;try{setBusy(true);await api(`/sales/${sale.sale_id}/void?reason=${encodeURIComponent(reason.trim())}&version=${encodeURIComponent(String(sale.version??''))}&admin_password=${encodeURIComponent(admin_password)}`,{method:'POST'});setDone(`${sale.invoice_no} voided.`);setSale(null);setInv('');setReason('')}catch(e){onError((e as Error).message)}finally{setBusy(false)}}return <div><p className="muted">Admin only. Use for a wrong sale rung up today. After Day End, or once a return/settlement/warranty claim exists, use Returns instead.</p><div className="form-grid compact"><input placeholder="Invoice no. (e.g. INV-000123)" value={inv} onChange={e=>setInv(e.target.value)}/><button disabled={!inv.trim()} onClick={find}>Find Sale</button></div>{done&&<p className="success-banner">{done}</p>}{sale&&<div><p><b>{sale.invoice_no}</b> · Rs. {money(sale.grand_total)} · {new Date(sale.sale_datetime).toLocaleString()}</p>{sale.lines.map((l:any)=><div className="stock-row" key={l.sale_line_id}><span>{l.item_code} · {l.description} × {money(l.quantity)}</span><span>Rs. {money(l.final_total)}</span></div>)}<div className="form-grid compact"><input placeholder="Required void reason" value={reason} onChange={e=>setReason(e.target.value)}/><button className="danger-button" disabled={busy||!reason.trim()} onClick={voidIt}>{busy?'Voiding…':'Void This Sale'}</button></div></div>}</div>}

function RoleEditor({role,perms,onSave}:{role:any,perms:any[],onSave:(r:any)=>void}){const [selected,setSelected]=useState<string[]>(role.permissions);return <div className="role-editor"><b>{role.name}</b><div className="permission-grid">{perms.map(p=><label key={p.code}><input type="checkbox" checked={selected.includes(p.code)} onChange={e=>setSelected(e.target.checked?[...selected,p.code]:selected.filter(x=>x!==p.code))}/>{p.code}</label>)}</div><button onClick={()=>onSave({...role,permissions:selected})}>Save Permissions</button></div>}

function PasswordResetPanel({users,onError}:{users:any[],onError:(x:string)=>void}){const [uid,setUid]=useState(''),[adminPass,setAdminPass]=useState(''),[newPass,setNewPass]=useState('');async function reset(){try{await api('/admin/users/reset-password',{method:'POST',body:JSON.stringify({user_id:uid,admin_password:adminPass,new_password:newPass})});setAdminPass('');setNewPass('');toast.success('Password reset. Cashier must change password on next login.')}catch(e){onError((e as Error).message)}}return <div className="form-grid compact"><select value={uid} onChange={e=>setUid(e.target.value)}><option value="">Select cashier</option>{users.map(u=><option key={u.user_id} value={u.user_id}>{u.username} · {u.display_name}</option>)}</select><input type="password" placeholder="Admin password" value={adminPass} onChange={e=>setAdminPass(e.target.value)}/><input type="password" placeholder="Temporary new password" value={newPass} onChange={e=>setNewPass(e.target.value)}/><button disabled={!uid||!adminPass||!newPass} onClick={reset}>Reset Cashier Password</button></div>}

function BackupTab({onError}:{onError:(x:string)=>void}){const [rows,setRows]=useState<any[]>([]),[busy,setBusy]=useState(false);async function load(){try{setRows(await api<any[]>('/backup/points'))}catch(e){onError((e as Error).message)}}useEffect(()=>{load()},[]);async function create(){try{setBusy(true);await api('/backup/create',{method:'POST',body:JSON.stringify({filename:`lovely-tech-${Date.now()}.ltbak`})});await load();toast.success('Encrypted PostgreSQL backup created and verified.')}catch(e){onError((e as Error).message)}finally{setBusy(false)}}async function verify(id:string){try{await api(`/backup/verify/${id}`,{method:'POST'});await load()}catch(e){onError((e as Error).message)}}async function sync(id:string){try{await api(`/backup/sync/${id}`,{method:'POST'});await load()}catch(e){onError((e as Error).message)}}return <section className="glass panel"><h2>Backup / Restore</h2><p className="muted">Only VERIFIED backups are valid restore points. Google Drive sync is optional and shown separately.</p><div className="button-row"><button disabled={busy} onClick={create}>{busy?'Creating verified backup…':'Create Verified PostgreSQL Backup'}</button><button onClick={load}>Refresh</button></div>{rows.map(r=><div className="claim-row" key={r.backup_id}><span><b>{r.filename}</b> · {r.state} · {r.sync_state||'—'} · {r.sha256?.slice(0,12)||''}</span><span><button onClick={()=>verify(r.backup_id)}>Verify</button>{r.state==='VERIFIED'&&r.sync_state!=='SYNCED'&&<button onClick={()=>sync(r.backup_id)}>Sync Google Drive</button>}{r.state==='VERIFIED'&&<button onClick={async()=>{if(!window.confirm('Restore this verified backup? Current database will be replaced after a safety backup.'))return;const pw=window.prompt('Admin password')||'';try{await api(`/backup/restore/${r.backup_id}?confirm=true&admin_password=${encodeURIComponent(pw)}`,{method:'POST'});toast.success('Restore completed. Please log in again if the server session was reset.')}catch(e){onError((e as Error).message)}}}>Restore</button>}</span></div>)}</section>}

function DamageRestockPanel({onError}:{onError:(x:string)=>void}){
  const [rows,setRows]=useState<any[]>([]),[search,setSearch]=useState(''),[items,setItems]=useState<any[]>([]),[item,setItem]=useState(''),[qty,setQty]=useState('1'),[kind,setKind]=useState('DAMAGE'),[reason,setReason]=useState(''),[units,setUnits]=useState<any[]>([]),[picked,setPicked]=useState<string[]>([]),[busy,setBusy]=useState(false);
  const chosen=items.find((x:any)=>x.item_id===item); const serialized=!!chosen?.is_serialized;
  const modal = useModal();
  async function load(){try{setRows(await api<any[]>('/stock-control/damage-loss?limit=50'))}catch(e){onError((e as Error).message)}}
  useEffect(()=>{load()},[]);
  async function find(){try{setItems(await api<any[]>(`/inventory/items/search?q=${encodeURIComponent(search.trim())}`))}catch(e){onError((e as Error).message)}}
  async function pickItem(id:string){setItem(id);setPicked([]);setUnits([]);const it=items.find((x:any)=>x.item_id===id);if(it?.is_serialized){try{setUnits(await api<any[]>(`/inventory/serialized/search?q=&item_id=${id}&status=IN_STOCK`))}catch(e){onError((e as Error).message)}}}
  async function record(){
    if(busy) return; if(!item||!reason.trim()) return onError('Select an item and enter a reason.');
    const admin_password=(await modal.prompt({title:'Admin re-authentication',message:'Enter admin password to record damage/loss',placeholder:'Password',confirmText:'Record',type:'password'}))||'';if(!admin_password)return;
    try{setBusy(true);await api(`/stock-control/damage-loss?admin_password=${encodeURIComponent(admin_password)}`,{method:'POST',body:JSON.stringify({item_id:item,quantity:String(serialized?picked.length:qty),reason:reason.trim(),loss_type:kind,serialized_unit_ids:serialized?picked:undefined,idempotency_key:crypto.randomUUID()})});setReason('');setPicked([]);await load();if(serialized)pickItem(item);toast.success('Recorded')}catch(e){onError((e as Error).message)}finally{setBusy(false)}
  }
  async function restock(r:any){
    const reason=window.prompt('Reason: why is this item resellable? (required)')?.trim(); if(!reason) return;
    const admin_password=(await modal.prompt({title:'Admin re-authentication',message:'Enter admin password to restock this item',placeholder:'Password',confirmText:'Restock',type:'password'}))||'';if(!admin_password)return;
    try{await api(`/stock-control/damage-loss/${r.damage_loss_id}/restock?reason=${encodeURIComponent(reason)}&admin_password=${encodeURIComponent(admin_password)}`,{method:'POST'});await load();toast.success('Item restocked (audited)')}catch(e){onError((e as Error).message)}
  }
  async function finalize(r:any){
        const admin_password=(await modal.prompt({title:'Admin re-authentication',message:'Enter admin password to finalize this damage/loss record',placeholder:'Password',confirmText:'Finalize',type:'password'}))||'';
    if(!admin_password)return;
    try{await api(`/stock-control/damage-loss/${r.damage_loss_id}/finalize?admin_password=${encodeURIComponent(admin_password)}`,{method:'POST'});await load()}catch(e){onError((e as Error).message)}
  }
  return <div><p className="muted">Record damage, loss or internal use. Cashier-marked damage (returns/exchanges) waits here for Admin to finalize. Resellable items can be restocked: the damage stays in history and the loss is given back in profit.</p>
    <div className="form-grid compact"><input placeholder="Item code / description" value={search} onChange={e=>setSearch(e.target.value)}/><button onClick={find}>Find Item</button>
      <select value={item} onChange={e=>pickItem(e.target.value)}><option value="">Select item</option>{items.map((x:any)=><option key={x.item_id} value={x.item_id}>{x.item_code} · {x.description}</option>)}</select>
      <select value={kind} onChange={e=>setKind(e.target.value)}><option value="DAMAGE">Damage</option><option value="LOSS">Loss</option><option value="INTERNAL_USE">Internal use</option></select>
      {serialized?<div className="wide-field">{units.length===0?<p className="muted">No in-stock units.</p>:units.map((u:any)=><label className="check" key={u.serialized_unit_id}><input type="checkbox" checked={picked.includes(u.serialized_unit_id)} onChange={e=>setPicked(p=>e.target.checked?[...p,u.serialized_unit_id]:p.filter(x=>x!==u.serialized_unit_id))}/> {u.serial_number}</label>)}</div>:<input {...intInputProps(qty, setQty, 1)} placeholder="Quantity"/>}
      <input placeholder="Required reason" value={reason} onChange={e=>setReason(e.target.value)}/><button disabled={busy||!item||!reason.trim()||(serialized&&picked.length===0)} onClick={record}>Record</button></div>
    {rows.length===0?<p className="muted">No damage/loss records.</p>:rows.map(r=><div className="stock-row" key={r.damage_loss_id}><span><b>{r.item_code}</b> · {r.description} · qty {String(r.quantity)} · {String(r.loss_type||'DAMAGE').replace('_',' ')} · {r.reason} · <small>{r.source_type||'MANUAL'} · {r.review_status}</small></span>{r.review_status==='PENDING'&&<button onClick={()=>finalize(r)}>Finalize</button>}{(r.review_status==='APPROVED'||r.review_status==='PENDING')&&<button onClick={()=>restock(r)}>Restock</button>}</div>)}
  </div>}