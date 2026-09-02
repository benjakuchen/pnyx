-- ============================================================
--  PNYX — VOTADAS: recientes + historicas con buscador
--  Correr en Supabase -> SQL Editor.
-- ============================================================

-- ------------------------------------------------------------
-- 1) RECIENTES: las N mas recientes (por defecto 15).
--    Reemplaza a votadas_lista(): ahora acepta un limite.
-- ------------------------------------------------------------
create or replace function votadas_lista(p_limite int default 15)
returns table (
    id            bigint,
    camara        text,
    titulo        text,
    resultado     text,
    afirmativos   int,
    negativos     int,
    abstenciones  int,
    ausentes      int,
    votada_en     timestamptz,
    ley_bill_id   text
)
language sql stable security definer
as $$
    select v.id, v.camara, v.titulo, v.resultado,
           v.afirmativos, v.negativos, v.abstenciones, v.ausentes,
           v.votada_en, v.ley_bill_id
    from votaciones_congreso v
    order by v.votada_en desc nulls last
    limit p_limite;
$$;

-- ------------------------------------------------------------
-- 2) HISTORICAS: busqueda por titulo + filtro por año.
--    p_texto: busca en el titulo (case-insensitive, sin tildes).
--    p_anio:  null = todos los años.
-- ------------------------------------------------------------
create or replace function votadas_buscar(
    p_texto text default '',
    p_anio  int  default null,
    p_limite int default 50
)
returns table (
    id            bigint,
    camara        text,
    titulo        text,
    resultado     text,
    afirmativos   int,
    negativos     int,
    abstenciones  int,
    ausentes      int,
    votada_en     timestamptz,
    ley_bill_id   text
)
language sql stable security definer
as $$
    select v.id, v.camara, v.titulo, v.resultado,
           v.afirmativos, v.negativos, v.abstenciones, v.ausentes,
           v.votada_en, v.ley_bill_id
    from votaciones_congreso v
    where (
            coalesce(p_texto,'') = ''
            or translate(lower(v.titulo),'áéíóúüñ','aeiouun')
               like '%' || translate(lower(p_texto),'áéíóúüñ','aeiouun') || '%'
          )
      and (p_anio is null or extract(year from v.votada_en) = p_anio)
    order by v.votada_en desc nulls last
    limit p_limite;
$$;

-- ------------------------------------------------------------
-- 3) AÑOS disponibles (para armar el filtro del buscador)
-- ------------------------------------------------------------
create or replace function votadas_anios()
returns table (anio int, cantidad bigint)
language sql stable security definer
as $$
    select extract(year from votada_en)::int as anio, count(*) as cantidad
    from votaciones_congreso
    where votada_en is not null
    group by 1
    order by 1 desc;
$$;

grant execute on function votadas_lista(int)                 to anon;
grant execute on function votadas_buscar(text, int, int)     to anon;
grant execute on function votadas_anios()                    to anon;
