# Rutina diaria del Senado (manual)

El Senado NO se puede automatizar (el sitio tiene anti-bot). Estos pasos se
hacen a mano, por ejemplo a la tarde. Diputados sí es automático (4 AM), no
hay que tocarlo.

## 0. Preparar la terminal (una vez por sesión de PowerShell)
```powershell
cd C:\Users\bekuc\Downloads\PNYX
$env:SUPABASE_SERVICE_KEY="tu-service-role-key"
$env:ANTHROPIC_API_KEY="tu-anthropic-key"
```

## 1. Bajar el Excel del Senado (navegador, a mano)
- Entrar a: https://www.senado.gob.ar/parlamentario/parlamentaria/
- "INGRESADOS POR MESA DE ENTRADAS", fechas 01/01/2026 → hoy, Buscar.
- Descargar el Excel y guardarlo en la carpeta PNYX como  senado.xls
  (reemplazando el anterior). Debe pesar cientos de KB (si pesa poquito,
  la descarga falló, volver a intentar).

## 2. Meter las leyes nuevas en la base
```powershell
python senado_desde_excel.py
```

## 3. Ver cuáles bajar primero (ordenadas por prensa)
```powershell
python senado_prioridad.py
notepad senado_prioridad.txt
```
Las de arriba (con ⭐) son las que están sonando en los medios: bajá esas primero.

## 4. Bajar los PDF de las prioritarias (navegador, a mano)
- Carpeta destino:  C:\Users\bekuc\Downloads\PNYX\senado_pdfs\
- Abrir la ficha de cada una (link en el .txt), descargar el PDF.
- Guardar cada PDF en senado_pdfs\ (el nombre se normaliza solo, pero lo
  ideal es como dice el .txt, ej: SENADO641-26.pdf).

## 5. Subir los textos
```powershell
python senado_subir.py
```

## 6. Reflejar en el feed
```powershell
python 9_mezclar_ordenar.py
```

## Notas
- El RESUMEN (obrero 7) NO se corre a mano: sale solo a las 4 AM cuando la
  curaduría publica la ley. Vos solo dejás el texto cargado.
- Chequeos útiles:
  - python senado_ultimos.py        (últimas cargadas)
  - python senado_ver_textos.py 641 642   (si una tiene texto)
- Dónde va cada cosa:
  - senado.xls  → carpeta PNYX (raíz)
  - PDFs        → PNYX\senado_pdfs\
  - los python  → siempre parado en la carpeta PNYX
