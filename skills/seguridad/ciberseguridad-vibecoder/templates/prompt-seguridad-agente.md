# Bloque de seguridad para CLAUDE.md / AGENTS.md de un proyecto

Pegar en el archivo de instrucciones del proyecto (Claude Code, Codex). Versión mejorada del
prompt viral de Revolutia.ai: mismas 27 peticiones, pero como reglas permanentes, con prioridad,
prueba y límites de alcance.

```markdown
## Seguridad (Escudo VD-44 · perfil: <P0|P1|P2|P3> <+IA>)
Reglas permanentes mientras programas:
1. Nunca confíes en el cliente: precio, rol, usuario, puntuación o permiso se deciden en servidor.
2. Ninguna clave secreta en el código del navegador ni con prefijo VITE_/NEXT_PUBLIC_; variables de entorno de servidor.
3. Todo endpoint privado verifica sesión y que el recurso es del usuario antes de cualquier lógica.
4. Base de datos: reglas por fila (RLS) en cada tabla expuesta; consultas parametrizadas siempre.
5. Valida en servidor con esquema; pinta datos con textContent (no innerHTML) salvo HTML sanitizado.
6. Cookies de sesión HttpOnly + Secure + SameSite; POST/PUT/DELETE comprueban Origin.
7. Límite de peticiones en login, registro, recuperación, IA y endpoints caros; topes de gasto en APIs pagadas.
8. Archivos subidos: tipo real, tamaño máximo, nombre aleatorio, fuera de la web pública.
9. Pagos: precio buscado en servidor; webhooks con firma verificada.
10. Producción: sin debug, sin source maps públicos, cabeceras de seguridad, .vercelignore al día.
11. Antes de instalar un paquete, verifica que existe y es legítimo; no añadas dependencias sin necesidad.
12. Si encuentras un secreto en el código o la historia: detente y avisa (hay que rotarlo), no lo copies.
Al terminar una funcionalidad que toque login, datos, pagos, IA, archivos o despliegue:
corre `python <ruta-skill>/scripts/vd_sec_scan.py repo . --history` y reporta en tabla
"control · encontrado · arreglado · cómo lo probaste · pendiente". No declares "seguro" sin re-test.
No hagas pruebas contra producción ni contra sitios ajenos; usa local/preview con datos ficticios.
```
