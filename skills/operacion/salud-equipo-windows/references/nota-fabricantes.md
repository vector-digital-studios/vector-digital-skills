# Nota opcional: utilidades y WMI del fabricante

Muchos portátiles traen una utilidad oficial del fabricante con ajustes que Windows no expone:

- límite de carga de la batería (60 % / 80 % / 100 %);
- modo de GPU (solo integrada o híbrida);
- perfiles de ventilador y de potencia.

A menudo esa utilidad habla con el firmware mediante clases WMI propias en `root\wmi`. Para ver
cuáles existen en tu equipo (consulta de solo lectura):

```powershell
Get-CimClass -Namespace root/wmi | Where-Object CimClassName -notmatch '^(MS|Win32|__|CIM|Battery|Wmi|Kernel|Ms)' |
  Select-Object -ExpandProperty CimClassName
```

**Esta skill no usa esas clases ni cambia ninguno de esos ajustes**, por tres motivos:

1. Son específicas de cada marca y modelo; un identificador de método que funciona en un modelo
   puede hacer otra cosa en otro.
2. Casi siempre requieren administrador, y desde una sesión sin elevar suelen fallar **en
   silencio**: la llamada «funciona» pero el valor no se aplica.
3. La utilidad oficial puede sobrescribir el valor al tocar su interfaz.

Si quieres un límite de carga, usa la utilidad oficial del fabricante. Para verificarlo sin
administrador: con el equipo enchufado, la batería se queda en el límite (p. ej. 80 %) y no sube al
100 %. El informe muestra la carga actual y si está en CA.
