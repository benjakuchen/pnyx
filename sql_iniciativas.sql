-- ============================================================
--  Pnyx · Iniciativas ciudadanas ("La plaza") — base de datos
--  La gente propone, un equipo curador redacta, y los ciudadanos
--  apoyan. El apoyo es ANÓNIMO igual que el voto (sello HMAC, sin
--  user_id en la tabla de apoyos). Los curadores sí se identifican
--  entre ellos por SEUDÓNIMO (eligieron exponerse como equipo).
--  Correr ENTERO en el SQL Editor de Supabase.
-- ============================================================

-- 0) Perfil cívico: el NICK único de cada persona ------------
--    La persona elige cuánto se identifica (su nombre real, un alias,
--    lo que quiera). Vale para TODA la comunidad. El apoyo a una
--    iniciativa NO usa esto: sigue siendo anónimo como el voto.
create table if not exists perfil_civico (
  user_id      uuid primary key,
  nick         text not null,
  acepto_aviso boolean default false,   -- leyó el cartel de anonimato/acoso
  creado_en    timestamptz default now()
);

-- 1) La iniciativa -------------------------------------------
create table if not exists iniciativas (
  id            bigint generated always as identity primary key,
  titulo        text not null,
  problema      text,
  propuesta     text,
  tema          text,
  estado        text not null default 'construccion',  -- construccion | aporte | apoyo | presentada
  version       int  not null default 1,
  cupo_curadores int not null default 9,
  autor_user_id uuid not null,
  autor_seudo   text,
  presentada_por text,                 -- legislador que la presentó (cuando aplique)
  texto_cerrado boolean default false, -- punto de no retorno: congela para juntar apoyo
  created_at    timestamptz default now()
);

-- 2) Artículos del texto (versionados) ----------------------
create table if not exists iniciativa_articulos (
  id            bigint generated always as identity primary key,
  iniciativa_id bigint not null references iniciativas(id) on delete cascade,
  numero        int not null,
  contenido     text not null,
  version       int not null default 1,
  created_at    timestamptz default now()
);

-- 3) Equipo curador (con seudónimo, hasta el cupo) ----------
create table if not exists iniciativa_curadores (
  iniciativa_id bigint not null references iniciativas(id) on delete cascade,
  user_id       uuid not null,
  seudonimo     text not null,
  es_autor      boolean default false,
  mail_compartido text,               -- NULL salvo que lo comparta, y solo tras presentar
  sumado_en     timestamptz default now(),
  primary key (iniciativa_id, user_id)
);

-- 4) Enmiendas / objeciones de la comunidad -----------------
create table if not exists iniciativa_enmiendas (
  id            bigint generated always as identity primary key,
  iniciativa_id bigint not null references iniciativas(id) on delete cascade,
  tipo          text not null default 'enmienda',   -- enmienda | objecion
  seudonimo     text,
  texto         text not null,
  estado        text not null default 'pendiente',  -- pendiente | incorporada | respondida
  apoyos        int default 0,
  created_at    timestamptz default now()
);

-- 5) Apoyos a la iniciativa — ANÓNIMO (igual que los votos) --
--    Sin user_id: solo el sello HMAC + zona (provincia).
create table if not exists iniciativa_apoyos (
  id            bigint generated always as identity primary key,
  iniciativa_id bigint not null references iniciativas(id) on delete cascade,
  sello         text not null,
  zona          text,
  version_apoyada int,                 -- a qué versión del texto se apoyó
  created_at    timestamptz default now()
);

-- 6) Quién ya apoyó (para no re-contar) — sin el sentido ----
create table if not exists ya_apoyo (
  user_id       uuid not null,
  iniciativa_id bigint not null,
  apoyado_en    timestamptz default now(),
  primary key (user_id, iniciativa_id)
);

-- índices útiles
create index if not exists ix_art_ini  on iniciativa_articulos(iniciativa_id);
create index if not exists ix_enm_ini  on iniciativa_enmiendas(iniciativa_id);
create index if not exists ix_apo_ini  on iniciativa_apoyos(iniciativa_id);
create index if not exists ix_cur_ini  on iniciativa_curadores(iniciativa_id);

-- RLS: se opera por funciones SECURITY DEFINER (abajo). Igual activamos
-- RLS en las tablas sensibles para que nadie lea directo por PostgREST.
alter table iniciativas          enable row level security;
alter table iniciativa_articulos enable row level security;
alter table iniciativa_curadores enable row level security;
alter table iniciativa_enmiendas enable row level security;
alter table iniciativa_apoyos    enable row level security;
alter table ya_apoyo             enable row level security;

-- lectura pública de lo que el ciudadano necesita ver (sin apoyos crudos)
drop policy if exists p_ini_read on iniciativas;
create policy p_ini_read on iniciativas for select using (true);
drop policy if exists p_art_read on iniciativa_articulos;
create policy p_art_read on iniciativa_articulos for select using (true);
drop policy if exists p_enm_read on iniciativa_enmiendas;
create policy p_enm_read on iniciativa_enmiendas for select using (true);
drop policy if exists p_cur_read on iniciativa_curadores;
create policy p_cur_read on iniciativa_curadores for select using (true);
-- apoyos y ya_apoyo: NO lectura directa (solo por funciones)

alter table perfil_civico enable row level security;
-- perfil_civico: NO lectura directa (el nick se usa vía funciones)
