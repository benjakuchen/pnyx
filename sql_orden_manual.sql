-- ============================================================
--  Pnyx · Orden manual del feed (sin que los obreros lo pisen)
--  Principio: lo MANUAL y lo AUTOMÁTICO viven en columnas distintas.
--   - puntaje_pnyx  -> lo escribe el obrero 9 (automático).
--   - orden_manual  -> lo escribe SOLO el admin a mano. Ningún obrero
--                      la toca, así que nunca se pisan.
--  El feed muestra PRIMERO lo que tiene orden_manual (arriba, en ese
--  orden), y DESPUÉS el resto por puntaje_pnyx como siempre.
--  Correr ENTERO en el SQL Editor de Supabase.
-- ============================================================

-- 1) Columna del orden manual (idempotente) ------------------
--    NULL = sin tocar (va por puntaje). Número = posición fija arriba
--    (más chico = más arriba).
alter table leyes add column if not exists orden_manual int;

-- 2) Guardar el orden manual de una ley ----------------------
--    p_orden = número de posición (o null para soltarla y que vuelva
--    al orden automático).
create or replace function admin_set_orden_manual(p_bill_id text, p_orden int)
returns void language plpgsql security definer as $function$
begin
  if not es_admin() then raise exception 'No autorizado'; end if;
  update leyes set orden_manual = p_orden where bill_id = p_bill_id;
end;
$function$;

-- 3) Intercambiar el orden de dos leyes (para las flechas ↑↓) -
--    Sube una y baja la otra en un solo paso, atómico.
create or replace function admin_swap_orden(p_bill_a text, p_bill_b text)
returns void language plpgsql security definer as $function$
declare oa int; ob int;
begin
  if not es_admin() then raise exception 'No autorizado'; end if;
  select orden_manual into oa from leyes where bill_id = p_bill_a;
  select orden_manual into ob from leyes where bill_id = p_bill_b;
  update leyes set orden_manual = ob where bill_id = p_bill_a;
  update leyes set orden_manual = oa where bill_id = p_bill_b;
end;
$function$;

-- 4) El feed del admin ahora trae también orden_manual -------
--    y ordena: primero lo manual (nulls al final), después puntaje.
drop function if exists admin_feed_leyes(boolean);
create or replace function admin_feed_leyes(p_solo_pub boolean default null)
returns table(bill_id text, camara text, expediente text, titulo text, oracion_ia text, resumen_ia text, fecha text, puntaje_pnyx bigint, orden_manual int, media_sancion boolean, publicada boolean)
language plpgsql security definer as $function$
begin
  if not es_admin() then raise exception 'No autorizado'; end if;
  return query
    select l.bill_id, l.camara, l.expediente, l.titulo, l.oracion_ia, l.resumen_ia,
           l.fecha::text, l.puntaje_pnyx, l.orden_manual, l.media_sancion, coalesce(l.publicada,true)
    from leyes l
    where (p_solo_pub is null or coalesce(l.publicada,true) = p_solo_pub)
    order by l.orden_manual asc nulls last,
             coalesce(l.puntaje_pnyx,0) desc, l.fecha desc;
end;
$function$;

grant execute on function admin_set_orden_manual(text, int) to authenticated;
grant execute on function admin_swap_orden(text, text)      to authenticated;
grant execute on function admin_feed_leyes(boolean)         to authenticated;
