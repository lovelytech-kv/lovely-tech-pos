import { api } from '../../api/client';
import { escapeHtml } from '../../utils/escapeHtml';

export type PaperSize = '80mm' | 'A4';

export type ReceiptTemplate = {
  id?: string;
  name: string;
  paper_size: PaperSize;
  is_default?: boolean;
  is_active?: boolean;
  show_logo: boolean;
  header_text: string | null;
  show_address: boolean;
  show_phone: boolean;
  show_email: boolean;
  show_customer_name: boolean;
  show_customer_phone: boolean;
  show_item_description: boolean;
  show_item_code: boolean;
  show_unit_price: boolean;
  show_warranty_info: boolean;
  show_repair_details: boolean;
  show_payment_method: boolean;
  show_cashier: boolean;
  show_customer_notes: boolean;
  logo_monochrome: boolean;
  footer_text: string | null;
  warranty_terms: string | null;
  show_footer_note: boolean;
};

export type ShopContextLike = {
  getShopName: () => string;
  getLogoDataUrl: (forcedTheme?: 'light' | 'dark') => string | null;
  getDeveloperPhone?: () => string;
};

export type FullShopLike = {
  address?: string | null;
  phone?: string | null;
  email?: string | null;
} | null;

export const LOCKED_FOOTER_PREFIX = 'Software by Lovely Tech';

export const DEFAULT_TEMPLATES: Record<PaperSize, ReceiptTemplate> = {
  '80mm': {
    name: 'Default 80mm',
    paper_size: '80mm',
    is_default: true,
    is_active: true,
    show_logo: true,
    header_text: null,
    show_address: true,
    show_phone: true,
    show_email: false,
    show_customer_name: true,
    show_customer_phone: true,
    show_item_description: true,
    show_item_code: true,
    show_unit_price: true,
    show_warranty_info: true,
    show_repair_details: true,
    show_payment_method: false,
    show_cashier: false,
    show_customer_notes: false,
    logo_monochrome: false,
    footer_text: 'Thank you for shopping at {shop_name}!',
    warranty_terms: null,
    show_footer_note: true,
  },
  A4: {
    name: 'Default A4',
    paper_size: 'A4',
    is_default: true,
    is_active: true,
    show_logo: true,
    header_text: null,
    show_address: true,
    show_phone: true,
    show_email: true,
    show_customer_name: true,
    show_customer_phone: true,
    show_item_description: true,
    show_item_code: true,
    show_unit_price: true,
    show_warranty_info: true,
    show_repair_details: true,
    show_payment_method: false,
    show_cashier: false,
    show_customer_notes: false,
    logo_monochrome: false,
    footer_text: 'Thank you for shopping at {shop_name}!',
    warranty_terms: null,
    show_footer_note: true,
  },
};

const CACHE_PREFIX = 'ltpos_invoice_template_';

export function readCachedTemplate(paperSize: PaperSize): ReceiptTemplate | null {
  try {
    const raw = localStorage.getItem(CACHE_PREFIX + paperSize);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Partial<ReceiptTemplate> | null;
    if (!parsed || typeof parsed !== 'object') return null;
    return { ...DEFAULT_TEMPLATES[paperSize], ...parsed, paper_size: paperSize };
  } catch {
    return null;
  }
}

export function cacheTemplate(template: ReceiptTemplate): void {
  try {
    localStorage.setItem(CACHE_PREFIX + template.paper_size, JSON.stringify(template));
  } catch {
    // Cache is best-effort; printing still works with in-memory/default values.
  }
}

/**
 * Loads the active default template for printing. Network/API failures fall
 * back to the last cached template, then to the built-in defaults.
 */
export async function loadDefaultTemplate(paperSize: PaperSize): Promise<ReceiptTemplate> {
  try {
    const result = await api<ReceiptTemplate>(`/invoice-templates/default?paper_size=${paperSize}`);
    const merged = { ...DEFAULT_TEMPLATES[paperSize], ...result, paper_size: paperSize };
    cacheTemplate(merged);
    return merged;
  } catch {
    return readCachedTemplate(paperSize) ?? DEFAULT_TEMPLATES[paperSize];
  }
}

const LOGO_BW_PREFIX = 'ltpos_logo_bw_';
const LOGO_BW_MAX_DIMENSION = 480;
// 0-255 luminance split; mid-grey keeps anti-aliased edges readable in 1-bit.
const LOGO_BW_THRESHOLD = 160;

function hashLogoUrl(value: string): string {
  let hash = 5381;
  for (let index = 0; index < value.length; index += 1) {
    hash = ((hash << 5) + hash) ^ value.charCodeAt(index);
  }
  return (hash >>> 0).toString(36);
}

/**
 * Converts a data-URL logo to a 1-bit black/white PNG for thermal printing.
 * Converts in the browser with Canvas (no packages) and caches by source hash.
 * Any failure returns the original logo so receipts still print (G9).
 */
export async function toMonochromeDataUrl(dataUrl: string | null): Promise<string | null> {
  if (!dataUrl) return null;

  const cacheKey = LOGO_BW_PREFIX + hashLogoUrl(dataUrl);
  try {
    const cached = localStorage.getItem(cacheKey);
    if (cached) return cached;
  } catch {
    // Storage is optional; conversion still works without the cache.
  }

  const converted = await new Promise<string | null>((resolve) => {
    const image = new Image();
    image.onload = () => {
      try {
        const naturalWidth = image.naturalWidth || image.width;
        const naturalHeight = image.naturalHeight || image.height;
        if (!naturalWidth || !naturalHeight) {
          resolve(null);
          return;
        }
        const scale = Math.min(1, LOGO_BW_MAX_DIMENSION / Math.max(naturalWidth, naturalHeight));
        const canvas = document.createElement('canvas');
        canvas.width = Math.max(1, Math.round(naturalWidth * scale));
        canvas.height = Math.max(1, Math.round(naturalHeight * scale));
        const context = canvas.getContext('2d');
        if (!context) {
          resolve(null);
          return;
        }
        context.drawImage(image, 0, 0, canvas.width, canvas.height);
        const pixels = context.getImageData(0, 0, canvas.width, canvas.height);
        const data = pixels.data;
        for (let index = 0; index < data.length; index += 4) {
          if (data[index + 3] === 0) continue;
          const luminance = 0.299 * data[index] + 0.587 * data[index + 1] + 0.114 * data[index + 2];
          const value = luminance < LOGO_BW_THRESHOLD ? 0 : 255;
          data[index] = value;
          data[index + 1] = value;
          data[index + 2] = value;
        }
        context.putImageData(pixels, 0, 0);
        resolve(canvas.toDataURL('image/png'));
      } catch {
        resolve(null);
      }
    };
    image.onerror = () => resolve(null);
    image.src = dataUrl;
  });

  if (!converted) return dataUrl;
  try {
    localStorage.setItem(cacheKey, converted);
  } catch {
    // Quota/private-mode failures must not break printing.
  }
  return converted;
}

function fillTokens(text: string, shopName: string, phone: string): string {
  return text
    .replace(/\{shop_name\}/g, shopName)
    .replace(/\{phone\}/g, phone);
}

function escapeMultiline(text: string): string {
  return escapeHtml(text).replace(/\r?\n/g, '<br/>');
}

function toAmount(value: unknown): number | null {
  if (typeof value === 'number') return Number.isFinite(value) ? value : null;
  if (typeof value === 'string' && value.trim()) {
    const parsed = Number(value.replace(/,/g, ''));
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}

function formatAmount(value: number): string {
  return value.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function lineSubtotal(line: any): number | null {
  const unitPrice = toAmount(line?.unit_price);
  const quantity = toAmount(line?.quantity) ?? 1;
  if (unitPrice !== null) return unitPrice * quantity;
  const lineTotal = toAmount(line?.final_total ?? line?.line_total);
  if (lineTotal === null) return null;
  return lineTotal + (toAmount(line?.discount) ?? 0);
}

function paperCss(paperSize: PaperSize): string {
  if (paperSize === 'A4') {
    return `
      @page{size:A4;margin:14mm;}
      body{width:auto;max-width:182mm;padding:0;font-size:12px;}
      h1{font-size:22px;}
      .logo{max-width:120px;max-height:120px;}
      .meta{font-size:12px;}
      .contact{font-size:11px;}
      .line{padding:5px 0;}
      .total{font-size:17px;}
    `;
  }
  return `
    @page{size:80mm auto;margin:0;}
    body{width:80mm;padding:4mm;font-size:11px;}
  `;
}

type BuildOptions = {
  autoPrint?: boolean;
  printedAt?: Date;
};

export async function buildReceiptHTML(
  sale: any,
  shop: ShopContextLike,
  fullShop: FullShopLike,
  template: ReceiptTemplate,
  options: BuildOptions = {},
): Promise<string> {
  const paperSize: PaperSize = template?.paper_size === 'A4' ? 'A4' : '80mm';
  const t: ReceiptTemplate = { ...DEFAULT_TEMPLATES[paperSize], ...template };
  const lines = Array.isArray(sale?.lines) ? sale.lines : [];

  const shopName = shop.getShopName();
  const phone = fullShop?.phone || '';
  const address = fullShop?.address || '';
  const email = fullShop?.email || '';
  const rawLogoUrl = t.show_logo ? shop.getLogoDataUrl('light') : null;
  const logoUrl = rawLogoUrl && t.logo_monochrome && paperSize === '80mm'
    ? await toMonochromeDataUrl(rawLogoUrl)
    : rawLogoUrl;

  const invoiceNo = sale?.invoice_no || '-';
  const when = sale?.sale_datetime ? new Date(sale.sale_datetime) : (options.printedAt ?? new Date());

  const headerRaw = (t.header_text || '').trim();
  const headerText = headerRaw ? fillTokens(headerRaw, shopName, phone) : shopName;

  const contactBits: string[] = [];
  if (t.show_address && address) contactBits.push(escapeHtml(address));
  const phoneBit = t.show_phone && phone ? `Tel: ${escapeHtml(phone)}` : '';
  const emailBit = t.show_email && email ? escapeHtml(email) : '';
  const lineTwo = [phoneBit, emailBit].filter(Boolean).join(' · ');
  const contactHtml = (contactBits.length > 0 || lineTwo)
    ? `<div class="contact">${contactBits.length ? contactBits.join('<br/>') + '<br/>' : ''}${lineTwo}</div>`
    : '';

  const custName = t.show_customer_name ? (sale?.customer_name || '') : '';
  const custPhone = t.show_customer_phone ? (sale?.customer_contact || '') : '';
  const customerLine = (custName || custPhone)
    ? `<div class="meta">Customer: ${custName ? escapeHtml(custName) : ''}${custName && custPhone ? ' · ' : ''}${custPhone ? escapeHtml(custPhone) : ''}</div>`
    : '';

  const cashierName = t.show_cashier ? (sale?.cashier_name || '') : '';
  const cashierLine = cashierName
    ? `<div class="meta">Cashier: ${escapeHtml(cashierName)}</div>`
    : '';

  const customerNotes = t.show_customer_notes ? (sale?.customer_notes || '') : '';
  const customerNotesHtml = customerNotes
    ? `<div class="notes"><b>Notes:</b> ${escapeMultiline(customerNotes)}</div>`
    : '';

  const paymentSummary = t.show_payment_method ? (sale?.payment_method_summary || '') : '';

  const linesHtml = lines.map((l: any) => {
    const description = t.show_item_description ? (l?.description || '') : '';
    const itemCode = t.show_item_code ? (l?.item_code || '') : '';
    const quantity = l?.quantity ?? '1';
    const unitPrice = l?.unit_price ?? '0';
    const lineTotal = l?.final_total ?? l?.line_total ?? l?.unit_price ?? '0';
    const headline = description
      ? `<div class="ln-desc">${escapeHtml(description)}</div>`
      : '';
    const codeLine = itemCode
      ? `<div class="ln-code">SKU: ${escapeHtml(itemCode)}</div>`
      : '';
    const calc = t.show_unit_price
      ? `${escapeHtml(quantity)} × Rs. ${escapeHtml(unitPrice)}`
      : `Qty ${escapeHtml(quantity)}`;
    return `
      <div class="line">
        ${headline}${codeLine}
        <div class="row"><span class="calc">${calc}</span><span>Rs. ${escapeHtml(lineTotal)}</span></div>
      </div>
    `;
  }).join('');

  const repairValue = [sale?.repair_no, sale?.repair_details].filter(Boolean).join(' · ');
  const repairHtml = (t.show_repair_details && repairValue)
    ? `<div class="repair"><b>Repair:</b> ${escapeMultiline(repairValue)}</div>`
    : '';

  // Labeled totals. Paid/Balance are omitted when the payload has no payment
  // fields (sale detail currently exposes neither); Change comes from SaleOut.
  const subtotalValues = lines.map((l: any) => lineSubtotal(l)).filter((value: number | null): value is number => value !== null);
  const computedSubtotal = subtotalValues.length === lines.length && lines.length > 0
    ? subtotalValues.reduce((sum: number, value: number) => sum + value, 0)
    : null;
  const discountTotal = lines.reduce((sum: number, l: any) => sum + (toAmount(l?.discount) ?? 0), 0);
  const declaredTotal = toAmount(sale?.grand_total);
  const subtotal = computedSubtotal ?? (declaredTotal !== null ? declaredTotal + discountTotal : null);
  const totalAmount = declaredTotal ?? subtotal;
  const changeAmount = toAmount(sale?.change_amount);

  const summaryRows: string[] = [];
  if (subtotal !== null) {
    summaryRows.push(`<div class="row sum-line"><span>Subtotal</span><span>Rs. ${escapeHtml(formatAmount(subtotal))}</span></div>`);
  }
  if (discountTotal > 0.005) {
    summaryRows.push(`<div class="row sum-line"><span>Discount</span><span>-Rs. ${escapeHtml(formatAmount(discountTotal))}</span></div>`);
  }
  if (paymentSummary) {
    summaryRows.push(`<div class="row sum-line"><span>Payment</span><span>${escapeHtml(paymentSummary)}</span></div>`);
  }
  const totalDisplay = totalAmount !== null
    ? `Rs. ${escapeHtml(formatAmount(totalAmount))}`
    : `Rs. ${escapeHtml(sale?.grand_total ?? '0')}`;
  const changeRow = (changeAmount !== null && changeAmount > 0.005)
    ? `<div class="row sum-line"><span>Change</span><span>Rs. ${escapeHtml(formatAmount(changeAmount))}</span></div>`
    : '';

  const warrantyRaw = t.show_warranty_info && t.warranty_terms ? fillTokens(t.warranty_terms, shopName, phone) : '';
  const warrantyHtml = warrantyRaw
    ? `<div class="warranty"><div class="warranty-title">Warranty</div>${escapeMultiline(warrantyRaw)}</div>`
    : '';

  const footerRaw = t.show_footer_note && t.footer_text ? fillTokens(t.footer_text, shopName, phone) : '';
  const footerHtml = footerRaw ? `<div class="foot">${escapeMultiline(footerRaw)}</div>` : '';

  // LOCKED branding — always last, never configurable by template/user.
  // The phone is the independent developer number, NOT the shop's phone.
  const developerPhone = (
    (shop.getDeveloperPhone ? shop.getDeveloperPhone() : '')
    || import.meta.env.VITE_DEVELOPER_PHONE
    || '0770290008'
  ).trim();
  const lockedFooter = developerPhone
    ? `${LOCKED_FOOTER_PREFIX} · ${escapeHtml(developerPhone)}`
    : LOCKED_FOOTER_PREFIX;

  const autoPrintScript = options.autoPrint === false
    ? ''
    : '<script>window.onload = function(){ window.print(); };</script>';

  return `<!DOCTYPE html><html><head><title>Receipt ${escapeHtml(invoiceNo)}</title>
    <link rel="icon" href="data:," />
    <style>
      body{font-family:'Consolas','Menlo',monospace;margin:0 auto;color:#000;background:#fff;box-sizing:border-box;}
      h1{font-size:16px;text-align:center;margin:0 0 4px;word-break:break-word;}
      .meta{text-align:center;font-size:10px;color:#333;margin-bottom:4px;}
      .contact{text-align:center;font-size:10px;color:#555;margin-bottom:8px;line-height:1.35;}
      .notes{margin-top:4px;font-size:9px;color:#333;line-height:1.35;word-break:break-word;}
      .divider{border-top:1px dashed #000;margin:8px 0;}
      .row{display:flex;justify-content:space-between;gap:8px;}
      .line{padding:2px 0;}
      .ln-desc{word-break:break-word;}
      .ln-code{font-size:9px;color:#666;}
      .calc{color:#333;}
      .sum-line{font-size:11px;color:#333;padding:1px 0;}
      .total{font-size:15px;font-weight:700;}
      .foot{text-align:center;font-size:10px;margin-top:8px;line-height:1.35;}
      .warranty{margin-top:8px;font-size:9px;color:#444;line-height:1.35;}
      .warranty-title{font-weight:700;text-transform:uppercase;letter-spacing:0.04em;margin-bottom:2px;}
      .repair{margin-top:6px;font-size:10px;color:#333;line-height:1.35;}
      .receipt-locked-footer{font-family:inherit;font-style:normal;font-weight:400;font-size:10px;text-align:center;margin-top:8px;padding-top:6px;border-top:1px dashed #ccc;color:#888;}
      .logo{display:block;margin:0 auto 4px;max-width:80px;max-height:80px;object-fit:contain;}
      ${paperCss(paperSize)}
    </style></head><body>
    ${logoUrl ? `<img src="${escapeHtml(logoUrl)}" class="logo" />` : ''}
    <h1>${escapeHtml(headerText)}</h1>
    ${contactHtml}
    <div class="meta">Invoice: ${escapeHtml(invoiceNo)}<br/>${escapeHtml(when.toLocaleString())}</div>
    ${customerLine}
    ${cashierLine}
    ${customerNotesHtml}
    <div class="divider"></div>
    ${linesHtml}
    <div class="divider"></div>
    ${summaryRows.join('')}
    <div class="row total"><span>TOTAL</span><span>${totalDisplay}</span></div>
    ${changeRow}
    ${repairHtml}
    ${warrantyHtml}
    ${footerHtml}
    <div class="divider"></div>
    <div class="receipt-locked-footer">${lockedFooter}</div>
    ${autoPrintScript}
    </body></html>`;
}

/** Deterministic sample used by the Settings live preview. */
export const PREVIEW_SALE = {
  invoice_no: 'INV-000123',
  customer_name: 'Nimal Perera',
  customer_contact: '077 123 4567',
  customer_notes: 'Screen replaced under warranty. Handle with care.',
  cashier_name: 'Kasun Silva',
  payment_method_summary: 'Cash',
  grand_total: '4,250.00',
  lines: [
    { description: 'iPhone 13 Screen Replacement', item_code: 'SCR-013', quantity: '1', unit_price: '3,500.00', final_total: '3,500.00' },
    { description: 'Tempered Glass Protector', item_code: 'ACC-002', quantity: '2', unit_price: '375.00', final_total: '750.00' },
  ],
};

export async function renderReceiptPreview(
  template: ReceiptTemplate,
  shop: ShopContextLike,
  fullShop: FullShopLike,
): Promise<string> {
  return buildReceiptHTML(PREVIEW_SALE, shop, fullShop, template, { autoPrint: false });
}
