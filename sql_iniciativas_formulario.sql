-- ============================================================
--  Pnyx · Iniciativas — formulario metodológico (estructura de ley)
--  Agrega: secciones tipadas a los artículos + fundamentos + rol autor.
--  Incremental: no rompe lo ya creado. Correr ENTERO en Supabase.
-- ============================================================

-- 1) Fundamentos (exposición de motivos) de la iniciativa ----
alter table iniciativas add column if not exists fundamentos text;
-- documento que presentó el legislador (transparencia)
alter table iniciativas add column if not exists doc_presentado text;
alter table iniciativas add column if not exists autor_ultimo_activo timestamptz default now();

-- 2) Tipo de sección en cada artículo ------------------------
--    objeto | definiciones | cuerpo | autoridad | vigencia  (editable).
alter table iniciativa_articulos add column if not exists seccion text default 'cuerpo';

-- 3) Guardar artículo CON sección (el autor edita directo) ---
create or replace function guardar_articulo2(
  p_user_id uuid, p_iniciativa_id bigint, p_numero int, p_seccion text, p_contenido text)
returns text
language plpgsql security definer
as $function$
begin
  if not exists(select 1 from iniciativa_curadores where iniciativa_id = p_iniciativa_id and user_id = p_user_id)
    then return 'NO_SOS_CURADOR'; end if;
  if exists(select 1 from iniciativas where id = p_iniciativa_id and texto_cerrado = true)
    then return 'TEXTO_CERRADO'; end if;
  if exists(select 1 from iniciativa_articulos where iniciativa_id = p_iniciativa_id and numero = p_numero) then
    update iniciativa_articulos set contenido = p_contenido, seccion = coalesce(p_seccion,'cuerpo')
      where iniciativa_id = p_iniciativa_id and numero = p_numero;
  else
    insert into iniciativa_articulos (iniciativa_id, numero, seccion, contenido)
      values (p_iniciativa_id, p_numero, coalesce(p_seccion,'cuerpo'), p_contenido);
  end if;
  return 'OK';
end;
$function$;

-- 4) Borrar un artículo (solo curador, texto no cerrado) -----
create or replace function borrar_articulo(p_user_id uuid, p_iniciativa_id bigint, p_numero int)
returns text
language plpgsql security definer
as $function$
begin
  if not exists(select 1 from iniciativa_curadores where iniciativa_id = p_iniciativa_id and user_id = p_user_id)
    then return 'NO_SOS_CURADOR'; end if;
  if exists(select 1 from iniciativas where id = p_iniciativa_id and texto_cerrado = true)
    then return 'TEXTO_CERRADO'; end if;
  delete from iniciativa_articulos where iniciativa_id = p_iniciativa_id and numero = p_numero;
  return 'OK';
end;
$function$;

-- 5) Guardar fundamentos (solo curador) ---------------------
create or replace function guardar_fundamentos(p_user_id uuid, p_iniciativa_id bigint, p_texto text)
returns text
language plpgsql security definer
as $function$
begin
  if not exists(select 1 from iniciativa_curadores where iniciativa_id = p_iniciativa_id and user_id = p_user_id)
    then return 'NO_SOS_CURADOR'; end if;
  update iniciativas set fundamentos = p_texto where id = p_iniciativa_id;
  return 'OK';
end;
$function$;

-- 6) Leer texto con sección + fundamentos -------------------
drop function if exists iniciativa_texto(bigint);
create or replace function iniciativa_texto(p_iniciativa_id bigint)
returns table(numero int, seccion text, contenido text)
language sql stable security definer
as $function$
  select numero, coalesce(seccion,'cuerpo'), contenido from iniciativa_articulos
  where iniciativa_id = p_iniciativa_id order by numero;
$function$;

create or replace function iniciativa_fundamentos(p_iniciativa_id bigint)
returns text language sql stable security definer
as $function$ select fundamentos from iniciativas where id = p_iniciativa_id; $function$;

grant execute on function guardar_articulo2(uuid,bigint,int,text,text) to authenticated;
grant execute on function borrar_articulo(uuid,bigint,int)             to authenticated;
grant execute on function guardar_fundamentos(uuid,bigint,text)        to authenticated;
grant execute on function iniciativa_texto(bigint)                     to anon, authenticated;
grant execute on function iniciativa_fundamentos(bigint)               to anon, authenticated;
