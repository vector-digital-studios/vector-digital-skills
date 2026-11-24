# Memoria: RAM, VRAM y el proceso culpable

## Orden de trabajo

1. **Verifica la premisa midiendo antes de opinar.** Las cifras de memoria se confunden: los «6 GB»
   que alguien recuerda pueden ser la VRAM de la GPU y no la RAM. Mide RAM física, VRAM y el
   proceso concreto. Si la premisa era errónea, corrígela en una línea.
2. **RAM y módulos**: `Win32_OperatingSystem` (total, libre, virtual), `Win32_PhysicalMemory` (un solo
   módulo = canal simple) y `Win32_PageFileUsage`.
3. **Agrupa los procesos por nombre** (`WorkingSet64` y `PrivateMemorySize64`): diez procesos
   `python` o cuarenta de un navegador suman más que cualquier aplicación sola. Para saber QUÉ
   script es cada uno, usa `Win32_Process` y su `CommandLine`.
4. **VRAM**: los contadores de Windows `GPUAdapterMemory` y `GPUProcessMemory` funcionan con
   cualquier fabricante y sin herramientas extra (el LUID se traduce al nombre del adaptador con
   `HKLM:\SOFTWARE\Microsoft\DirectX`). Con NVIDIA:
   `nvidia-smi --query-gpu=memory.used,memory.total --format=csv,noheader` y
   `--query-compute-apps=pid,process_name,used_memory`. En portátiles con controlador WDDM, la
   memoria por proceso sale como `[N/A]`: usa los contadores de Windows (`GPUProcessMemory`), que es lo
   que hace el informe.
5. **Historial**: los eventos 2004 de `Microsoft-Windows-Resource-Exhaustion-Detector` (registro
   System) nombran a los mayores consumidores de memoria virtual de los últimos días.
6. **Compara siempre con el mismo medidor.** Una foto en reposo no refuta un pico que alguien
   reporta: deja el muestreador 24 h antes de recomendar comprar RAM.

## Cifras que importan

| Métrica | Qué dice | Umbral del informe |
|---|---|---|
| RAM disponible | lo que Windows puede dar sin paginar (libre + caché reutilizable) | ≥ 25 % bien · 10-25 % revisar · < 10 % atención |
| Memoria comprometida / límite | lo prometido a los procesos frente a RAM + archivo de paginación | < 80 % bien · 80-90 % revisar · ≥ 90 % atención (al 100 % fallan las aplicaciones) |
| VRAM usada | si se llena, el exceso cae a memoria compartida (mucho más lenta) | ≥ 90 % revisar |

## Trampas

- La RAM libre justo después de reiniciar es engañosa. Reporta el tiempo encendido junto a la cifra
  (el informe avisa si lleva menos de 30 min).
- «Libre» no es «disponible»: la caché en espera cuenta como disponible.
- Las líneas de comando (`CommandLine`) pueden contener rutas y argumentos privados. El muestreador
  las trunca a 160 caracteres y `-SinLineaDeComando` las omite. Revisa los CSV antes de compartirlos.

## Muestreador continuo

`scripts/muestreo_memoria.ps1` se lanza cada minuto y decide si toma una muestra:

- **reposo**: una muestra cada 10 min.
- **intenso**: una muestra por minuto si corre un proceso vigilado (`-Vigilar`, por ejemplo
  render o grabación) o si la RAM disponible baja de `-UmbralIntensoMB`.

Escribe CSV mensuales (`sistema_`, `procesos_`, `grandes_`, `gpu_`) y `ultimo_latido.txt`, la prueba
de que la tarea sigue viva. Para analizarlos:

```bash
python scripts/analizar_muestras.py memoria CARPETA [AAAA-MM]
python scripts/informe_salud.py --memoria CARPETA        # gráfico y «peores momentos» en el HTML
```
