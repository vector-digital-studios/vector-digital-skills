# Radar IA · 2026-11-23

**Agentes que aprueban código; un escudo abierto para Linux sin reiniciar; Amazon compra eficiencia para competir con Nvidia**

El lunes giró alrededor de los agentes que ya no solo escriben código sino que deciden qué pasa a producción, y de la seguridad que acompaña a ese salto. En paralelo, la carrera del hardware sigue moviéndose por la vía del software que exprime cada chip.

## 1. Anthropic lanza Claude Ship: agentes que revisan, corrigen y aprueban cambios de código
*Agentes y herramientas · Empresa · relevancia 10/10*

Claude Ship suma a Code Review dos agentes en beta: PR Steward, que arregla CI fallida, conflictos y comentarios de revisión, y Claude Approvals, que aprueba cambios rutinarios según una política escrita en un archivo del repositorio. Se despliega para planes Team y Enterprise en GitHub.

**Por qué te importa:** Si tu equipo ya revisa PR generados por agentes, escribe hoy tu política de aprobación en lenguaje natural aunque no uses esta herramienta: es el insumo que cualquier aprobador automático va a pedir. Anthropic recomienda empezar en modo solo observación y con tope de gasto mensual.

Fuente: [TechCrunch — Anthropic launches Claude Ship, letting AI agents review, fix, and approve code changes](https://techcrunch.com/2026/11/23/anthropic-launches-claude-ship-letting-ai-agents-review-fix-and-approve-code-changes/) (2026-11-23)

## 2. OpenAI y Cisco presentan Shirudo, un runtime abierto que protege servidores Linux mientras llega el parche
*Seguridad · Agentes y herramientas · relevancia 9/10*

Shirudo usa eBPF para aplicar «escudos» temporales que bloquean el camino vulnerable sin reiniciar el servicio. En una prueba controlada, un escudo generado con Codex bloqueó un intento de explotación contra Elasticsearch en marcha. Los escudos van firmados y un operador los aprueba antes de cargarlos.

**Por qué te importa:** Si operas servicios Linux propios, vale la pena seguir el repositorio y probarlo en un entorno de pruebas: el modelo de «escudo aprobado por un humano» es el patrón sano para dejar que un agente toque producción.

Fuente: [OpenAI — OpenAI and Cisco introduce Shirudo](https://openai.com/index/introducing-shirudo) (2026-11-23)

## 3. Amazon compra la tecnología de optimización de Decart por 7.500 millones de dólares
*Infraestructura · Finanzas e inversión · relevancia 8/10*

Según Bloomberg, citado por TechCrunch, Amazon pagará 7.500 millones por el Decart Optimization Stack, el software que hace que los modelos corran eficientes en hardware de Nvidia, Amazon y Google, y se queda con el equipo fundador e investigadores. Amazon se prepara para vender sus chips Trainium a clientes.

**Por qué te importa:** Si tu costo principal es inferencia en la nube, agenda revisar precios de instancias con Trainium cuando salgan a la venta: la compra apunta justo a quitar la fricción de migrar desde Nvidia.

Fuente: [TechCrunch — Amazon snaps up Decart's AI optimization tech for $7.5B as it prepares to sell Trainium chips](https://techcrunch.com/2026/11/23/amazon-snaps-up-decarts-ai-optimization-tech-for-7-5b-as-it-prepares-to-sell-trainium-chips/) (2026-11-23)

## 4. Google DeepMind usa equipos de agentes y verificación formal para abaratar algoritmos cuánticos
*Modelos · Agentes y herramientas · relevancia 7/10*

Equipos independientes de agentes con Gemini 4 propusieron mejoras que se probaron matemáticamente con el demostrador Lean. En un caso de fusión por confinamiento inercial redujeron 11,8 veces el costo de cómputo y bajaron de 5.650 a 4.338 los qubits corregidos necesarios. Publicaron la biblioteca y las soluciones en GitHub.

**Por qué te importa:** La lección práctica es el diseño, no la física: si pones a varios agentes a competir en una tarea, dales un verificador automático (pruebas, tipos, un demostrador) como juez en lugar de otro modelo.

Fuente: [Google DeepMind — Finding faster quantum algorithms with agents and formal verification](https://deepmind.google/blog/finding-faster-quantum-algorithms-with-agents-and-formal-verification/) (2026-11-23)

## 5. Sierra duplica su valoración a 30.000 millones en seis meses con agentes de atención al cliente
*Finanzas e inversión · Empresa · relevancia 7/10*

Sierra levantó 1.750 millones en una Serie F liderada por Greenoaks y Lightspeed. La empresa dice que atiende a casi la mitad del Fortune 50 y que su cobro por resultados le ayudó a duplicar su facturación anualizada a 400 millones en cinco meses.

**Por qué te importa:** Si vendes un producto con agentes, el dato a mirar es el modelo de precio: cobrar por resultado y no por asiento es lo que la compañía señala como motor de su crecimiento.

Fuente: [TechCrunch — Sierra doubles valuation to $30B within six months as demand for AI in CX takes off](https://techcrunch.com/2026/11/23/sierra-doubles-valuation-to-30b-within-six-months-as-demand-for-ai-in-cx-takes-off/) (2026-11-23)

---
5 noticias · relevancia media 8.2 · tema del día: Agentes y herramientas
