// primera.mjs <html> [hash] : palabras de la primera pantalla (390x844) por bloque
import { puppeteer, exe, espera, urlDe, movil } from './comun.mjs';
const [file, hash = ''] = process.argv.slice(2);
const b = await puppeteer.launch({ executablePath: exe }); const p = await movil(b, urlDe(file, hash), { dpr: 1 });
const r = await p.evaluate(() => {
  const H = innerHeight, por = {}; let tot = 0;
  const w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT); let n;
  while ((n = w.nextNode())) {
    const el = n.parentElement; if (!el || /^(SCRIPT|STYLE|NOSCRIPT)$/.test(el.tagName) || !el.getClientRects().length || el.closest('svg')) continue;
    const r = el.getBoundingClientRect(); if (!(r.top < H && r.bottom > 0)) continue;
    const k = n.textContent.trim().split(/\s+/).filter(Boolean).length; if (!k) continue; tot += k;
    const blq = el.closest('.top,.hd,.ver,.rib,.att,.tile,.rk,.card,.k,.nt,.bn,.dc,.ask,.cph,.lsc,.cap,.hoja,.sheet') || el;
    const key = blq.tagName.toLowerCase() + (typeof blq.className === 'string' && blq.className ? '.' + blq.className.split(' ')[0] : '');
    por[key] = (por[key] || 0) + k;
  }
  return { total: tot, por: Object.entries(por).sort((a, b) => b[1] - a[1]).slice(0, 10) };
});
console.log(JSON.stringify(r)); await b.close();
