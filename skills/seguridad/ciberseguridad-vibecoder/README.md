# Ciberseguridad vibecoder · Escudo VD-44

Una skill para que tu agente de IA construya y audite webs, apps, juegos y funciones de IA **sin
dejar las puertas abiertas** que dejan casi todas las apps hechas con IA.

## Qué trae

- **44 controles en 11 familias** (secretos, acceso, entradas, web, abuso, configuración, cadena de
  suministro, monitoreo, IA, juegos y privacidad), cada uno con *qué es, por qué importa, cómo se
  comprueba y cómo se arregla*, mapeado a OWASP Top 10:2025 y ASVS 5.0.
- **Perfiles de riesgo**: una landing no necesita lo mismo que una app con pagos.
- **Escáner pasivo** (`scripts/vd_sec_scan.py`, solo Python estándar): claves en el código y en el
  historial de Git, archivos publicados por error, cabeceras de seguridad, CORS, CSP y `npm audit`.
- **Autoprueba**: siembra 15 fallos en un proyecto trampa y exige encontrar los 15.
- **Regla de evidencia** y verificación independiente: menos falsas alarmas, ningún «es seguro» sin pruebas.
- **Puerta antes de publicar**: 0 críticos, 0 altos y re-test de cada arreglo.

## Uso rápido

```bash
python scripts/vd_sec_scan.py all ./mi-proyecto https://mi-dominio.com --perfil P1
python scripts/autoprueba.py   # 15/15
```
Pide a tu agente: *«carga ciberseguridad-vibecoder y audita este proyecto en modo AUDITAR»*.

## Probada en

Un panel personal con login en Vercel: aparecieron 11 archivos internos publicados por falta de
`.vercelignore`, login sin límite de intentos y librerías de CDN sin control. Se cerró todo el mismo
día: CSP estricta sin romper ninguna vista, límite de 5 intentos y librerías servidas desde el propio dominio.

## Créditos

- Checklist viral de 27 pedidos de seguridad para agentes de código (@revolutia.ai, TikTok).
- [cloudflare/security-audit-skill](https://github.com/cloudflare/security-audit-skill): libro de
  cobertura, re-test, verificación independiente y antipatrones (ideas, no código).
- OWASP Top 10:2025, ASVS 5.0, Top 10 for LLM Applications 2025 y Game Security Framework.
- Veracode GenAI Code Security Report 2025; CVE-2025-48757.

## Aviso

Solo sobre activos propios o con autorización escrita. Sin garantía: reduce riesgo, no lo elimina.
