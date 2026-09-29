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

## 7. OCR de los PDF NO legibles (escaneados)
Al subir (paso 5), los PDF que eran imagen quedan marcados como "escaneados".
Este obrero los lee con IA y les saca texto + resumen de una sola pasada.
```powershell
python 15_ocr.py --incluir-no-publicadas 20
```
(El número es el máximo a procesar. Gasta crédito de API: subilo si hay muchos.)

## 8. Resumir los que tienen texto legible pero sin resumen
Para los PDF que SÍ eran legibles (texto directo), este obrero les hace el
resumen con IA.
```powershell
python 7_resumir_senado.py --incluir-no-publicadas 50
```

## Notas
- El flag `--incluir-no-publicadas` es la clave: sin él, los obreros 7 y 15
  solo tocan leyes YA publicadas (así corren a las 4 AM). Con él, resumís
  también las que acabás de subir y todavía no pasaron por curaduría.
- Diferencia 7 vs 15:
  - 15_ocr.py  → PDF ESCANEADOS (imagen). Lee con IA y deja texto + resumen.
  - 7_resumir_senado.py → PDF con TEXTO legible pero sin resumen.
  - Conviene correr el 15 PRIMERO y el 7 DESPUÉS.
- Esto es ADEMÁS del automático de las 4 AM (que hace lo mismo, pero solo
  sobre las publicadas). Correrlo a mano te adelanta el resumen apenas subís.
- Chequeos útiles:
  - python senado_ultimos.py        (últimas cargadas)
  - python senado_ver_textos.py 641 642   (si una tiene texto/resumen)
- Dónde va cada cosa:
  - senado.xls  → carpeta PNYX (raíz)
  - PDFs        → PNYX\senado_pdfs\  (los procesados van a senado_pdfs\subidos\)
  - los python  → siempre parado en la carpeta PNYX

## Resumen del ciclo completo
```
1) bajar senado.xls (web)     5) python senado_subir.py
2) python senado_desde_excel.py   6) python 9_mezclar_ordenar.py
3) python senado_prioridad.py     7) python 15_ocr.py --incluir-no-publicadas 20
4) bajar PDFs a senado_pdfs\      8) python 7_resumir_senado.py --incluir-no-publicadas 50
```
