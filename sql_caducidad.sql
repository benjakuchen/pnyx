-- ============================================================
--  Pnyx · Caducidad de proyectos viejos en la cola de curaduría
--  Un proyecto que lleva +60 días (por su 'fecha') en la cola,
--  sin media sanción, sin prensa y sin publicar, se ARCHIVA:
--  curaduria_estado = 'caducada'. No se borra: se puede rescatar.
--  Correr ENTERO en el SQL Editor de Supabase.
--
--  OJO: la columna 'fecha' es TEXT (formato 'aaaa-mm-dd'). Por eso
--  acá se castea a date, pero SOLO cuando el texto tiene formato de
--  fecha válido (regex), para que una fila con basura no rompa todo.
--
--  RESCATE: cuando un humano rescata una caducada, se marca
--  rescatada=true para que el caducado automático de las 4am NO la
--  vuelva a archivar (si no, rescatar no serviría de nada).
-- ============================================================

-- 0) Columna para marcar lo rescatado a mano (idempotente) ---
alter table leyes add column if not exists rescatada boolean default false;

-- 1) Marcar como caducadas las viejas de la cola -------------
--    Devuelve cuántas archivó. Se puede correr cuando quieras
--    (o sumarlo al maestro); solo toca las que cumplen TODO.
create or replace function public.archivar_caducadas(p_dias int default 60)
returns int
language plpgsql security definer
as $function$
declare v_n int;
begin
  update leyes
     set curaduria_estado = 'caducada'
   where curaduria_nivel = 'cola'
     and coalesce(curaduria_estado,'pendiente') = 'pendiente'
     and coalesce(publicada,false) = false
     and coalesce(media_sancion,false) = false
     and coalesce(importante_prensa,false) = false
     and coalesce(sugerida_prensa,false) = false
     and coalesce(rescatada,false) = false             -- no re-caducar lo rescatado a mano
     and fecha ~ '^\d{4}-\d{2}-\d{2}$'                 -- solo fechas válidas
     and fecha::date < (current_date - p_dias);
  get diagnostics v_n = row_count;
  return v_n;
end;
$function$;

-- 2) Listar las caducadas (para el botón del admin) ---------
create or replace function public.admin_caducadas(p_limit int default 200, p_offset int default 0)
returns table(bill_id text, titulo text, oracion_ia text, camara text, origen text, fecha text, dias int)
language plpgsql stable security definer
as $function$
begin
  if not es_admin() then raise exception 'No autorizado'; end if;
  return query
    select l.bill_id, l.titulo, l.oracion_ia, l.camara, l.origen, l.fecha,
           case when l.fecha ~ '^\d{4}-\d{2}-\d{2}$'
                then (current_date - l.fecha::date)::int
                else null end as dias
    from leyes l
    where l.curaduria_estado = 'caducada'
    order by l.fecha desc nulls last
    limit p_limit offset p_offset;
end;
$function$;

-- 3) Cuántas caducadas hay (para el contador del botón) -----
create or replace function public.admin_caducadas_total()
returns int
language plpgsql stable security definer
as $function$
declare v_n int;
begin
  if not es_admin() then raise exception 'No autorizado'; end if;
  select count(*)::int into v_n from leyes where curaduria_estado = 'caducada';
  return v_n;
end;
$function$;

-- 4) Rescatar una caducada: vuelve a la cola pendiente ------
create or replace function public.admin_rescatar_caducada(p_bill_id text)
returns void
language plpgsql security definer
as $function$
begin
  if not es_admin() then raise exception 'No autorizado'; end if;
  update leyes
     set curaduria_estado = 'pendiente',
         rescatada = true          -- marca: el caducado automático la deja en paz
   where bill_id = p_bill_id and curaduria_estado = 'caducada';
end;
$function$;

grant execute on function public.archivar_caducadas(int)        to anon, authenticated;
grant execute on function public.admin_caducadas(int,int)       to anon, authenticated;
grant execute on function public.admin_caducadas_total()        to anon, authenticated;
grant execute on function public.admin_rescatar_caducada(text)  to anon, authenticated;
