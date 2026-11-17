# Changelog

## 1.1.0 · 2026-11-17
- Libro de cobertura por perfil (`--perfil`) y re-test contra la corrida previa (`--previo`).
- Respeta `.vercelignore` y sondea carpetas ocultas publicadas por Vercel.
- CSP evaluada por directiva (`unsafe-inline` solo cuenta en `script-src`).
- Verificación independiente para críticos y altos; antipatrones; ejecución aislada de código ajeno.
- `scripts/banco_csp_local.cjs`: prueba de CSP en local con las cabeceras reales.

## 1.0.0 · 2026-11-17
- 44 controles en 11 familias; escáner pasivo `vd_sec_scan.py`; autoprueba 15/15; guías Vercel, juegos e IA.
