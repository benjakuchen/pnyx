# -*- coding: utf-8 -*-
"""
clasificar_tipo.py — MODULO COMPARTIDO de clasificacion de proyectos del Congreso.
Lo usan TANTO el obrero de Votadas (10_votadas.py) COMO los obreros del Feed.
Una sola fuente de verdad para los 6 tipos, asi las dos partes de la app coinciden.

TIPOS:
  LEY         - proyecto de ley (se convierte en ley). Tratados y codigos incluidos.
  ACUERDO     - designaciones (jueces, embajadores), pliegos, ascensos. Propio del Senado.
  DECLARACION - "declarase de interes", adhesiones, repudios, beneplacitos.
  RESOLUCION  - resoluciones internas, pedidos de informes.
  HOMENAJE    - "instituyese el dia de", homenajes, reconocimientos, aniversarios.
  INTERNO     - mociones, apartamientos, ratificaciones, cuartos intermedios (tramite).

Estrategia hibrida: primero el TITULO (senal mas fuerte de la INTENCION),
                    despues el SUFIJO del expediente como respaldo.
"""

import re
import unicodedata

def _n(t):
    """normaliza: sin tildes, minusculas."""
    t = unicodedata.normalize("NFKD", t or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"\s+", " ", t)

def clasificar_tipo(titulo, expediente=None):
    """Devuelve uno de: LEY, ACUERDO, DECLARACION, RESOLUCION, HOMENAJE, INTERNO.

    Prioridad: el SUFIJO del expediente manda cuando existe (es el dato oficial).
    Solo si no hay sufijo claro se decide por el titulo. Esto evita que un
    'Acuerdo con Austria' (tratado, -PL, es LEY) caiga en ACUERDO por la palabra."""
    t = _n(titulo)
    exp = (expediente or "").upper()
    suf = ""
    m = re.search(r"-([A-Z]{2,3})$", exp)
    if m:
        suf = m.group(1)

    # --- INTERNO siempre primero: es tramite, no es proyecto ---
    if re.search(r"\b(mocion|apartamiento|cuarto intermedio|sobre tablas|"
                 r"habilitacion de tratamiento|ratificacion|"
                 r"designacion de (la senadora|el senador|auditores|secretari)|"
                 r"vicepresidencia|preferencia para el tratamiento)\b", t):
        return "INTERNO"

    # --- SUFIJO OFICIAL: manda si existe ---
    #   PL = proyecto de ley (incluye tratados/convenios que se llaman "Acuerdo con...")
    #   AC = acuerdo (designaciones, pliegos)
    #   PD = declaracion   PR = resolucion
    if suf == "PL":
        return "LEY"
    if suf == "AC":
        return "ACUERDO"
    if suf == "PD":
        # puede ser declaracion o homenaje: refinar por titulo
        if re.search(r"\b(instituyese el dia|dia nacional|dia mundial|homenaje|"
                     r"reconocimiento a|aniversario|conmemoracion)\b", t):
            return "HOMENAJE"
        return "DECLARACION"
    if suf == "PR":
        return "RESOLUCION"

    # --- SIN sufijo claro: decidir por TITULO ---
    if re.search(r"\b(instituyese el dia|declarase el dia|dia nacional|dia mundial|"
                 r"homenaje|reconocimiento a|aniversario|conmemoracion|"
                 r"beneplacito por|adhesion a la conmemoracion)\b", t):
        return "HOMENAJE"

    if re.search(r"\b(declaracion de|declarase de interes|declaracion con motivo|"
                 r"declarase|adhesion|repudio|solidaridad con|preocupacion por)\b", t):
        return "DECLARACION"

    if re.search(r"\b(pedido de informes|solicita informes|resolucion)\b", t):
        return "RESOLUCION"

    # designaciones/pliegos/ascensos SIN sufijo -> ACUERDO (pero no si dice "ley" o es tratado)
    if re.search(r"\b(designar|designacion|designaciones|pliego|promover a grado|"
                 r"ascenso|embajador|vocal|magistrad)\b", t):
        if not re.search(r"\b(ley|tratado|convenio|protocolo|codigo)\b", t):
            return "ACUERDO"

    # por defecto: LEY (tratados, convenios, codigos, regimenes, creaciones)
    return "LEY"


# --- autotest rapido ---
if __name__ == "__main__":
    casos = [
        ("Modernización Laboral", "PE-159/25-PL", "LEY"),
        ("Acuerdo para designar embajadora extraordinaria", "PE-9/26-AC", "ACUERDO"),
        ("Acuerdo de Libre Comercio entre el Mercosur y la Unión Europea", None, "LEY"),
        ("Designación de auditores para la Auditoría General", "", "INTERNO"),
        ("Ratificación de secretarios y prosecretarios", "", "INTERNO"),
        ("Declaración con motivo del 50º aniversario del golpe", None, "HOMENAJE"),
        ("Moción de orden del senador Recalde", "", "INTERNO"),
        ("INSTITUYASE EL 17 DE MAYO COMO DIA NACIONAL DE LUCHA", "1234-D-2026", "HOMENAJE"),
        ("REGIMEN LEGAL DE LA ELECTROMOVILIDAD", "2392-D-2026", "LEY"),
        ("DECLARASE DE INTERES LA FIESTA NACIONAL DEL FOLCLORE", "1040/26", "DECLARACION"),
        ("Pliego de Fernando Iglesias como embajador", "PE-175/25-AC", "ACUERDO"),
        ("Tratado de extradición entre Argentina y Chile", None, "LEY"),
        ("Reconocimiento a la labor del Equipo Argentino de Antropología", "", "HOMENAJE"),
        ("Acuerdo con la República de Austria para eliminar doble imposición", "CD-21/24-PL", "LEY"),
        ("Protocolo de enmienda al convenio con Francia", "PE-46/24-PL", "LEY"),
        ("Declaración de la ciudad de San Miguel de Tucumán capital", None, "DECLARACION"),
        ("Modificación de los artículos 22 bis y 123 bis del reglamento", "S-112/26-PR", "RESOLUCION"),
    ]
    ok = 0
    for tit, exp, esperado in casos:
        got = clasificar_tipo(tit, exp)
        marca = "OK " if got == esperado else "XX "
        if got == esperado: ok += 1
        print(f"  {marca} [{got:11s}] esperaba {esperado:11s} | {tit[:50]}")
    print(f"\n  {ok}/{len(casos)} correctos")
