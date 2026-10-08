-- ============================================================
--  Pnyx · Linkeo v2 — manual, seguro y hacia DESTACADAS
--  - Solo se linkean votaciones del Congreso con leyes que ESTUVIERON
--    sometidas a plebiscito (publicadas ahora, o ya votadas/despublicadas
--    por un linkeo previo).
--  - El linkeo es 100% MANUAL desde el admin. El obrero 16 solo SUGIERE.
--  - Al linkear, la votada pasa a DESTACADAS con su resumen.
--  Correr ENTERO en el SQL Editor de Supabase.
-- ============================================================

-- 0) Extensión para medir similitud de texto (idempotente)
create extension if not exists pg_trgm;

-- 1) Candidatas para linkear: buscador que SOLO trae leyes que
--    estuvieron en plebiscito, ordenadas por parecido de título.
--    "estuvo en plebiscito" = publicada=true  O  curaduria_estado='votada'
--    (esta última es una ley que ya se despublicó al ser votada).
create or replace function buscar_leyes_linkeo(p_camara text, p_q text)
returns table(bill_id text, titulo text, oracion_ia text, expediente text, publicada boolean, sim real)
language sql stable security definer
as $function$
  select l.bill_id, l.titulo, l.oracion_ia, l.expediente, coalesce(l.publicada,false),
         greatest(
           similarity(lower(coalesce(l.oracion_ia,'')), lower(p_q)),
           similarity(lower(coalesce(l.titulo,'')),     lower(p_q)),
           similarity(lower(coalesce(l.expediente,'')), lower(p_q))
         ) as sim
  from leyes l
  where l.camara = p_camara
    and ( coalesce(l.publicada,false) = true
          or coalesce(l.curaduria_estado,'') = 'votada' )
    and (
      p_q is null or p_q = '' or
      l.titulo ilike '%'||p_q||'%' or
      l.oracion_ia ilike '%'||p_q||'%' or
      l.expediente ilike '%'||p_q||'%'
    )
  order by sim desc nulls last
  limit 12;
$function$;

-- 2) Sugerencia automática de la MEJOR candidata para una votación
--    (la usa el panel para mostrar "sugerida con X% de confianza").
--    No linkea: solo devuelve la mejor coincidencia publicada/votada.
create or replace function sugerencia_linkeo(p_acta text, p_camara text)
returns table(bill_id text, titulo text, oracion_ia text, expediente text, sim real)
language plpgsql stable security definer
as $function$
declare v_titulo text;
begin
  if not es_admin() then raise exception 'No autorizado'; end if;
  select titulo into v_titulo from votaciones_congreso where acta_id = p_acta and camara = p_camara;
  if v_titulo is null then return; end if;
  return query
    select l.bill_id, l.titulo, l.oracion_ia, l.expediente,
           similarity(lower(coalesce(l.oracion_ia, l.titulo,'')), lower(v_titulo)) as sim
    from leyes l
    where l.camara = p_camara
      and ( coalesce(l.publicada,false) = true or coalesce(l.curaduria_estado,'') = 'votada' )
    order by sim desc nulls last
    limit 1;
end;
$function$;

-- 3) Linkear MANUAL: empareja, y manda la votada a DESTACADAS.
--    (porque esa ley pasó por el plebiscito de Pnyx y ahora tiene veredicto)
create or replace function linkear_manual(p_acta text, p_camara text, p_bill_id text)
returns void language plpgsql security definer as $function$
begin
  if not es_admin() then raise exception 'No autorizado'; end if;
  update votaciones_congreso
     set ley_bill_id = p_bill_id,
         link_descartado = false,
         match_metodo = 'manual',
         destacada = true,
         destacada_desde = coalesce(destacada_desde, now())
   where acta_id = p_acta and camara = p_camara;
  -- la ley del feed: ya fue votada por el Congreso -> sale de "votar"
  update leyes
     set publicada = false, estado_tramite = 'votada', curaduria_estado = 'votada'
   where bill_id = p_bill_id;
end;
$function$;

-- 4) Descartar link (la votación no corresponde a ninguna ley del feed)
create or replace function descartar_link(p_acta text, p_camara text)
returns void language plpgsql security definer as $function$
begin
  if not es_admin() then raise exception 'No autorizado'; end if;
  update votaciones_congreso set link_descartado = true, ley_bill_id = null
   where acta_id = p_acta and camara = p_camara;
end;
$function$;

grant execute on function buscar_leyes_linkeo(text, text)   to authenticated;
grant execute on function sugerencia_linkeo(text, text)     to authenticated;
grant execute on function linkear_manual(text, text, text)  to authenticated;
grant execute on function descartar_link(text, text)        to authenticated;
