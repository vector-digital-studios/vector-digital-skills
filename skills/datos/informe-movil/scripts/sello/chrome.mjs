// chrome.mjs · imprime la ruta del Chrome que usará el sello, o «ERROR …» si no hay ninguno.
import { buscarChrome } from './comun.mjs';
try { console.log(buscarChrome()); } catch (e) { console.log('ERROR ' + e.message); }
