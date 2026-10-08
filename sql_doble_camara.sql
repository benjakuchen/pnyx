-- ============================================================
--  Pnyx · Doble cámara (base) — vincular las dos versiones de una
--  misma ley entre Diputados y Senado.
--
--  Una ley pasa por las dos cámaras: son DOS filas con bill_id
--  distinto (HCDN... y SENADO...). Esta columna las enlaza: cada
--  una guarda el bill_id de su par en la otra cámara.
--  NINGÚN obrero toca ley_par (es 100% manual, como orden_manual).
--
--  Esto deja la base lista. La pantalla de vinculación en el admin y
--  la comparación de textos se suman cuando haya pares y textos reales.
--  Correr ENTERO en el SQL Editor de Supabase.
-- ============================================================

-- 1) Columna del par en la otra cámara (idempotente) ---------
alter table leyes add column if not exists ley_par text;

-- 2) Vincular dos versiones (enlaza los dos lados a la vez) ---
create or replace function admin_vincular_camaras(p_bill_a text, p_bill_b text)
returns void language plpgsql security definer as $function$
begin
  if not es_admin() then raise exception 'No autorizado'; end if;
  update leyes set ley_par = p_bill_b where bill_id = p_bill_a;
  update leyes set ley_par = p_bill_a where bill_id = p_bill_b;
end;
$function$;

-- 3) Desvincular (limpia los dos lados) ----------------------
create or replace function admin_desvincular_camaras(p_bill_id text)
returns void language plpgsql security definer as $function$
declare v_par text;
begin
  if not es_admin() then raise exception 'No autorizado'; end if;
  select ley_par into v_par from leyes where bill_id = p_bill_id;
  update leyes set ley_par = null where bill_id = p_bill_id;
  if v_par is not null then
    update leyes set ley_par = null where bill_id = v_par;
  end if;
end;
$function$;

-- 4) Datos del par para el aviso al votar (lectura pública) ---
--    Devuelve la cámara y el título del par, para el cartel
--    "ya votaste esta ley en la otra cámara".
create or replace function ley_par_info(p_bill_id text)
returns table(par_bill_id text, par_camara text, par_titulo text)
language sql stable security definer as $function$
  select p.bill_id, p.camara, coalesce(p.oracion_ia, p.titulo)
  from leyes l
  join leyes p on p.bill_id = l.ley_par
  where l.bill_id = p_bill_id;
$function$;

grant execute on function admin_vincular_camaras(text, text)   to authenticated;
grant execute on function admin_desvincular_camaras(text)      to authenticated;
grant execute on function ley_par_info(text)                   to anon, authenticated;
