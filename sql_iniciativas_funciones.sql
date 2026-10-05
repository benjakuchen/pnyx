-- ============================================================
--  Pnyx · Iniciativas — funciones (RPC) que usa la app
--  Correr DESPUÉS de sql_iniciativas.sql, ENTERO, en Supabase.
-- ============================================================

-- 0) Nick cívico: elegir/guardar y leer -----------------------------
--    acepto_aviso marca que la persona leyó el cartel de anonimato/acoso.
create or replace function guardar_nick(p_user_id uuid, p_nick text, p_acepto boolean default true)
returns text
language plpgsql security definer
as $function$
begin
  insert into perfil_civico (user_id, nick, acepto_aviso)
  values (p_user_id, p_nick, p_acepto)
  on conflict (user_id) do update set nick = excluded.nick, acepto_aviso = true;
  return 'OK';
end;
$function$;

create or replace function mi_nick(p_user_id uuid)
returns table(nick text, acepto_aviso boolean)
language sql stable security definer
as $function$
  select nick, acepto_aviso from perfil_civico where user_id = p_user_id;
$function$;

-- helper interno: nick de un user (o 'Anónimo' si no eligió)
create or replace function _nick_de(p_user_id uuid)
returns text
language sql stable security definer
as $function$
  select coalesce((select nick from perfil_civico where user_id = p_user_id), 'Vecino/a');
$function$;

-- ¿soy curador de esta iniciativa? (para mostrar el editor) --------
create or replace function soy_curador(p_user_id uuid, p_iniciativa_id bigint)
returns boolean
language sql stable security definer
as $function$
  select exists(select 1 from iniciativa_curadores where iniciativa_id = p_iniciativa_id and user_id = p_user_id);
$function$;

-- A) Crear una iniciativa. El autor queda como primer curador. -----
create or replace function crear_iniciativa(
  p_user_id uuid, p_titulo text, p_problema text, p_propuesta text, p_tema text)
returns bigint
language plpgsql security definer
as $function$
declare v_id bigint; v_nick text;
begin
  v_nick := _nick_de(p_user_id);
  insert into iniciativas (titulo, problema, propuesta, tema, autor_user_id, autor_seudo)
  values (p_titulo, p_problema, p_propuesta, p_tema, p_user_id, v_nick)
  returning id into v_id;
  insert into iniciativa_curadores (iniciativa_id, user_id, seudonimo, es_autor)
  values (v_id, p_user_id, v_nick, true);
  return v_id;
end;
$function$;

-- B) Buscar iniciativas parecidas (anti-duplicados) ----------------
--    Compara por similitud de título usando pg_trgm si está, o ILIKE.
create or replace function iniciativas_parecidas(p_titulo text)
returns table(id bigint, titulo text, estado text, apoyos bigint)
language sql stable security definer
as $function$
  select i.id, i.titulo, i.estado,
         (select count(*) from iniciativa_apoyos a where a.iniciativa_id = i.id)::bigint
  from iniciativas i
  where i.titulo ilike '%' || p_titulo || '%'
     or p_titulo ilike '%' || i.titulo || '%'
  limit 5;
$function$;

-- C) Listar iniciativas por estado (para "La plaza") ---------------
drop function if exists iniciativas_listar(text);
create or replace function iniciativas_listar(p_estado text default null)
returns table(id bigint, titulo text, problema text, propuesta text, tema text, estado text, version int,
              texto_cerrado boolean, presentada_por text,
              curadores int, cupo int, apoyos bigint, provincias bigint, created_at timestamptz)
language sql stable security definer
as $function$
  select i.id, i.titulo, i.problema, i.propuesta, i.tema, i.estado, i.version,
         coalesce(i.texto_cerrado,false), i.presentada_por,
         (select count(*) from iniciativa_curadores c where c.iniciativa_id = i.id)::int,
         i.cupo_curadores,
         (select count(*) from iniciativa_apoyos a where a.iniciativa_id = i.id)::bigint,
         (select count(distinct a.zona) from iniciativa_apoyos a where a.iniciativa_id = i.id)::bigint,
         i.created_at
  from iniciativas i
  where (p_estado is null or i.estado = p_estado)
  order by i.created_at desc;
$function$;

-- D) Sumarse al equipo curador (respeta el cupo) -------------------
create or replace function sumarse_curador(p_user_id uuid, p_iniciativa_id bigint)
returns text
language plpgsql security definer
as $function$
declare v_cupo int; v_actual int;
begin
  select cupo_curadores into v_cupo from iniciativas where id = p_iniciativa_id;
  if v_cupo is null then return 'NO_EXISTE'; end if;
  select count(*) into v_actual from iniciativa_curadores where iniciativa_id = p_iniciativa_id;
  if exists(select 1 from iniciativa_curadores where iniciativa_id = p_iniciativa_id and user_id = p_user_id)
    then return 'YA_SOS_CURADOR'; end if;
  if v_actual >= v_cupo then return 'CUPO_LLENO'; end if;
  insert into iniciativa_curadores (iniciativa_id, user_id, seudonimo) values (p_iniciativa_id, p_user_id, _nick_de(p_user_id));
  return 'OK';
end;
$function$;

-- E) Guardar/editar un artículo (solo curadores) ------------------
create or replace function guardar_articulo(
  p_user_id uuid, p_iniciativa_id bigint, p_numero int, p_contenido text)
returns text
language plpgsql security definer
as $function$
begin
  if not exists(select 1 from iniciativa_curadores where iniciativa_id = p_iniciativa_id and user_id = p_user_id)
    then return 'NO_SOS_CURADOR'; end if;
  if exists(select 1 from iniciativas where id = p_iniciativa_id and texto_cerrado = true)
    then return 'TEXTO_CERRADO'; end if;
  -- upsert por (iniciativa, numero)
  if exists(select 1 from iniciativa_articulos where iniciativa_id = p_iniciativa_id and numero = p_numero) then
    update iniciativa_articulos set contenido = p_contenido
      where iniciativa_id = p_iniciativa_id and numero = p_numero;
  else
    insert into iniciativa_articulos (iniciativa_id, numero, contenido)
      values (p_iniciativa_id, p_numero, p_contenido);
  end if;
  return 'OK';
end;
$function$;

-- F) Leer los artículos de una iniciativa --------------------------
create or replace function iniciativa_texto(p_iniciativa_id bigint)
returns table(numero int, contenido text)
language sql stable security definer
as $function$
  select numero, contenido from iniciativa_articulos
  where iniciativa_id = p_iniciativa_id order by numero;
$function$;

-- G) Proponer una enmienda / objeción (cualquier verificado) -------
create or replace function proponer_enmienda(
  p_user_id uuid, p_iniciativa_id bigint, p_tipo text, p_texto text)
returns bigint
language plpgsql security definer
as $function$
declare v_id bigint;
begin
  insert into iniciativa_enmiendas (iniciativa_id, tipo, seudonimo, texto)
  values (p_iniciativa_id, coalesce(p_tipo,'enmienda'), _nick_de(p_user_id), p_texto)
  returning id into v_id;
  return v_id;
end;
$function$;

create or replace function enmiendas_listar(p_iniciativa_id bigint)
returns table(id bigint, tipo text, seudonimo text, texto text, estado text, apoyos int, created_at timestamptz)
language sql stable security definer
as $function$
  select id, tipo, seudonimo, texto, estado, apoyos, created_at
  from iniciativa_enmiendas where iniciativa_id = p_iniciativa_id
  order by apoyos desc, created_at desc;
$function$;

-- H) APOYAR una iniciativa — ANÓNIMO (igual que emitir_voto) -------
--    Sello HMAC con la clave secreta; no se guarda user_id en apoyos.
create or replace function apoyar_iniciativa(
  p_usuario text, p_iniciativa_id bigint, p_zona text default null)
returns text
language plpgsql security definer
set search_path to 'public', 'extensions'
as $function$
declare v_clave text; v_sello text; v_existe int; v_ver int;
begin
  select valor into v_clave from config_secreta where clave = 'sello_secreto';
  if v_clave is null then return 'ERROR: falta la clave'; end if;

  v_sello := encode(extensions.hmac(p_usuario || '|ini|' || p_iniciativa_id::text, v_clave, 'sha256'), 'hex');

  insert into ya_apoyo (user_id, iniciativa_id) values (p_usuario::uuid, p_iniciativa_id)
    on conflict (user_id, iniciativa_id) do nothing;

  select count(*) into v_existe from iniciativa_apoyos where sello = v_sello and iniciativa_id = p_iniciativa_id;
  if v_existe > 0 then return 'YA_APOYASTE'; end if;

  select version into v_ver from iniciativas where id = p_iniciativa_id;
  insert into iniciativa_apoyos (iniciativa_id, sello, zona, version_apoyada)
    values (p_iniciativa_id, v_sello, p_zona, v_ver);
  return 'OK';
end;
$function$;

-- ¿ya apoyé esta? (para pintar el botón) ---------------------------
create or replace function ya_apoye(p_usuario text, p_iniciativa_id bigint)
returns boolean
language sql stable security definer
as $function$
  select exists(select 1 from ya_apoyo where user_id = p_usuario::uuid and iniciativa_id = p_iniciativa_id);
$function$;

-- I) Cerrar el texto (punto de no retorno, solo curador) ----------
create or replace function cerrar_texto(p_user_id uuid, p_iniciativa_id bigint)
returns text
language plpgsql security definer
as $function$
begin
  if not exists(select 1 from iniciativa_curadores where iniciativa_id = p_iniciativa_id and user_id = p_user_id)
    then return 'NO_SOS_CURADOR'; end if;
  update iniciativas set texto_cerrado = true, estado = 'apoyo' where id = p_iniciativa_id;
  return 'OK';
end;
$function$;

-- permisos
grant execute on function soy_curador(uuid,bigint)                         to authenticated;
grant execute on function guardar_nick(uuid,text,boolean)                  to authenticated;
grant execute on function mi_nick(uuid)                                     to authenticated;
grant execute on function crear_iniciativa(uuid,text,text,text,text)       to authenticated;
grant execute on function iniciativas_parecidas(text)                      to anon, authenticated;
grant execute on function iniciativas_listar(text)                         to anon, authenticated;
grant execute on function sumarse_curador(uuid,bigint)                     to authenticated;
grant execute on function guardar_articulo(uuid,bigint,int,text)           to authenticated;
grant execute on function iniciativa_texto(bigint)                         to anon, authenticated;
grant execute on function proponer_enmienda(uuid,bigint,text,text)         to authenticated;
grant execute on function enmiendas_listar(bigint)                         to anon, authenticated;
grant execute on function apoyar_iniciativa(text,bigint,text)              to authenticated;
grant execute on function ya_apoye(text,bigint)                            to authenticated;
grant execute on function cerrar_texto(uuid,bigint)                        to authenticated;
