# Cadena de suministro y secretos

## Secretos: ciclo completo
1. **Dónde viven**: variables de entorno del proveedor (Vercel) y, en local, una bóveda cifrada o un
   gestor de secretos. Nunca en el repo, informes, chats ni capturas.
2. **Detección**: `vd_sec_scan.py repo <ruta> --history` (bundle, código e historia).
   Opcional más profundo, si se aprueba instalarlo en venv aislado: gitleaks o trufflehog.
3. **Si aparece uno real (orden fijo)**: revocar/rotar en el panel del proveedor → actualizar la
   variable de entorno → redesplegar → revisar facturación/uso por abuso → recién entonces limpiar
   historia (`git filter-repo`) si el repo se comparte. Borrar el commit sin rotar no sirve.
4. **Informe**: el valor jamás aparece; solo proveedor, primeros 4 caracteres, longitud y archivo.

## Dependencias npm
- Lockfile commiteado; `npm ci` en CI (instala exactamente el lockfile).
- `npm audit --omit=dev` mensual o antes de publicar; altas/críticas bloquean la puerta.
- Quitar sobrantes: `npx depcheck` (revisar falsos positivos de plugins de build).
- **Paquetes alucinados (slopsquatting)**: la IA a veces sugiere paquetes que no existen; un
  atacante registra ese nombre con malware. Antes de `npm install <x>` sugerido por un agente:
  existe en npmjs.com, dueño reconocible, descargas semanales razonables, repo enlazado y antigüedad.
- Versiones fijas para SDKs críticos; leer el changelog antes de saltar versiones mayores.
- Python: un entorno virtual por herramienta (`uv venv`), nunca instalar en el entorno del agente.

## Publicar artefactos propios (skill, repo, informe) en GitHub u otro sitio público
Un artefacto interno suele llevar el mapa de tu infraestructura. Antes de publicarlo:
1. **Contar lo que se filtraría** y reportarlo en cifras:
   `grep -rEc "Users/<tu-usuario>|<tu-unidad>:/|<dominio privado>|<tu nombre>|<proyectos internos>" <carpeta>`.
2. **Versión saneada en una copia** (nunca editar la skill en uso): rutas como variables (`$SKILL_DIR`,
   `<ruta-proyecto>`), dominios y casos reales anonimizados («un panel personal con login»), sin
   referencias a skills privadas, backlog ni almacén de llaves.
3. **Créditos**: citar las fuentes de ideas (otras skills, normas, el vídeo) aunque no se haya copiado
   código; si se copió código, conservar su LICENSE/NOTICE.
4. **Aviso de uso**: herramientas de escaneo «solo sobre sitios propios» y «sin garantía» (MIT ya lo cubre).
5. **Identidad del commit**: correo noreply de GitHub, nunca el personal.
6. Escanear la copia saneada con `vd_sec_scan.py repo <copia> --history` y repetir el grep del paso 1
   (debe dar 0) antes de publicar.

## Scripts de CDN
SRI (`integrity` + `crossorigin="anonymous"`) o descargar el archivo y servirlo desde el propio
dominio. Generar hash: `curl -s URL | openssl dgst -sha384 -binary | openssl base64 -A`.

## Skills, MCP y plugins (cadena de suministro del agente)
Una skill es texto que el agente obedece y scripts que puede ejecutar: tratarla como código ajeno.
Antes de instalar: leer SKILL.md y scripts completos, revisar licencia, buscar descargas remotas en
tiempo de ejecución, ofuscación o exfiltración. Nunca `curl | bash` ni instaladores que escriban fuera
de las rutas del agente.
