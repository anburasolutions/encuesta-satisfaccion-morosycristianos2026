-- =============================================================
-- ENCUESTA MOROS Y CRISTIANOS DE ASPE 2026
-- Esquema mínimo para Supabase
-- =============================================================

create extension if not exists pgcrypto;

-- 1) Respuestas anónimas. Los campos de segmentación se duplican fuera
-- del JSON para facilitar filtros; no se guarda nombre, DNI, email ni teléfono.
create table if not exists public.responses (
    id uuid primary key default gen_random_uuid(),
    created_at timestamptz not null default now(),
    comparsa text not null,
    edad text not null,
    antiguedad text not null,
    cargo text not null,
    answers jsonb not null
);

create index if not exists responses_created_at_idx on public.responses (created_at desc);
create index if not exists responses_comparsa_idx on public.responses (comparsa);
create index if not exists responses_edad_idx on public.responses (edad);
create index if not exists responses_antiguedad_idx on public.responses (antiguedad);
create index if not exists responses_cargo_idx on public.responses (cargo);

-- 2) Invitaciones únicas. Solo se almacena el hash del token y la comparsa.
-- No se almacena nombre, DNI, email ni teléfono.
create table if not exists public.invitations (
    id uuid primary key default gen_random_uuid(),
    created_at timestamptz not null default now(),
    token_hash text not null unique,
    comparsa text,
    used_at timestamptz
);

create index if not exists invitations_token_hash_idx on public.invitations (token_hash);
create index if not exists invitations_used_at_idx on public.invitations (used_at);

-- 3) Número de festeros invitados para calcular participación.
create table if not exists public.comparsa_config (
    comparsa text primary key,
    invited_count integer not null default 0 check (invited_count >= 0),
    updated_at timestamptz not null default now()
);

insert into public.comparsa_config (comparsa, invited_count)
values
('Moros Alcaná', 0),
('Moros Aljau', 0),
('Moros Fauquíes', 0),
('Moros Sulaymán', 0),
('Cristianos Contrabandistas de la Sierra Negra', 0),
('Cristianos Duque de Maqueda', 0),
('Cristianos Estudiantes', 0),
('Cristianos Lanceros de Uchel', 0)
on conflict (comparsa) do nothing;

-- 4) RLS: no damos acceso directo a anon/authenticated.
alter table public.responses enable row level security;
alter table public.invitations enable row level security;
alter table public.comparsa_config enable row level security;

-- El backend Streamlit usa la service key, que debe mantenerse SOLO en Secrets.
-- No se crean políticas públicas de SELECT/INSERT para estas tablas.

-- 5) Función atómica para guardar respuesta y consumir una invitación.
-- Si p_token_hash es NULL, permite una respuesta pública normal.
-- Si lleva token, lo bloquea con FOR UPDATE para impedir uso simultáneo.
create or replace function public.submit_survey(
    p_answers jsonb,
    p_token_hash text default null
)
returns uuid
language plpgsql
security definer
set search_path = public
as $$
declare
    v_response_id uuid;
    v_invitation_id uuid;
begin
    if p_answers is null then
        raise exception 'INVALID_ANSWERS';
    end if;

    if coalesce(p_answers->>'comparsa', '') = ''
       or coalesce(p_answers->>'edad', '') = ''
       or coalesce(p_answers->>'antiguedad', '') = ''
       or coalesce(p_answers->>'cargo', '') = '' then
        raise exception 'MISSING_REQUIRED_SEGMENTATION';
    end if;

    if p_token_hash is not null then
        select id
          into v_invitation_id
          from public.invitations
         where token_hash = p_token_hash
           and used_at is null
         for update;

        if v_invitation_id is null then
            raise exception 'INVALID_OR_USED_TOKEN';
        end if;
    end if;

    insert into public.responses (comparsa, edad, antiguedad, cargo, answers)
    values (
        p_answers->>'comparsa',
        p_answers->>'edad',
        p_answers->>'antiguedad',
        p_answers->>'cargo',
        p_answers
    )
    returning id into v_response_id;

    if v_invitation_id is not null then
        update public.invitations
           set used_at = now()
         where id = v_invitation_id;
    end if;

    return v_response_id;
end;
$$;

revoke all on function public.submit_survey(jsonb, text) from public;
revoke all on function public.submit_survey(jsonb, text) from anon;
revoke all on function public.submit_survey(jsonb, text) from authenticated;
grant execute on function public.submit_survey(jsonb, text) to service_role;
