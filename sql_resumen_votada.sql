-- ============================================================
--  Pnyx · Resumen manual para VOTADAS sin ley linkeada
--  Cuando una votación del Congreso no está linkeada a ninguna ley
--  del feed, no hay dónde poner un resumen. Esta columna guarda un
--  resumen escrito a mano por el admin, propio de la votación.
--  El ciudadano lo ve en el detalle de esa votada.
--  Correr ENTERO en el SQL Editor de Supabase.
-- ============================================================

-- 1) Columna del resumen manual (idempotente) ----------------
alter table votaciones_congreso add column if not exists resumen_admin text;

-- 2) Guardar el resumen manual de una votada por su id -------
create or replace function admin_set_resumen_votada(p_id bigint, p_texto text)
returns void language plpgsql security definer as $function$
begin
  if not es_admin() then raise exception 'No autorizado'; end if;
  update votaciones_congreso set resumen_admin = p_texto where id = p_id;
end;
$function$;

-- 3) Que el ciudadano pueda LEER resumen_admin de una votada -
--    (lectura puntual por id al abrir el detalle). Como la tabla
--    tiene RLS, exponemos una función de solo-lectura, sin es_admin.
create or replace function votada_resumen(p_id bigint)
returns text language sql stable security definer as $function$
  select resumen_admin from votaciones_congreso where id = p_id;
$function$;

grant execute on function admin_set_resumen_votada(bigint, text) to authenticated;
grant execute on function votada_resumen(bigint)                 to anon, authenticated;
