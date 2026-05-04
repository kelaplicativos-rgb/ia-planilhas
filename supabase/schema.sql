-- BLING PRODUCTION MODE
-- Rode este SQL no Supabase SQL Editor antes de ativar enterprise.enabled=true.

create table if not exists public.workspaces (
  id text primary key,
  name text,
  plan text default 'free',
  status text default 'active',
  created_at timestamptz default now()
);

create table if not exists public.usage_logs (
  id bigserial primary key,
  workspace text not null,
  event text not null,
  payload jsonb default '{}'::jsonb,
  created_at timestamptz default now()
);

create table if not exists public.mapping_memory (
  id bigserial primary key,
  workspace text not null,
  signature text not null,
  fornecedor_nome text default '',
  mapping jsonb not null default '{}'::jsonb,
  created_at timestamptz default now(),
  updated_at timestamptz default now(),
  unique(workspace, signature)
);

create index if not exists usage_logs_workspace_created_idx
  on public.usage_logs(workspace, created_at desc);

create index if not exists mapping_memory_workspace_signature_idx
  on public.mapping_memory(workspace, signature);

alter table public.workspaces enable row level security;
alter table public.usage_logs enable row level security;
alter table public.mapping_memory enable row level security;

-- Fase inicial: policies abertas para anon key enquanto o app usa workspace manual.
-- Em produção com Supabase Auth, troque por policies baseadas em auth.uid().
create policy if not exists "workspaces anon read" on public.workspaces for select using (true);
create policy if not exists "workspaces anon insert" on public.workspaces for insert with check (true);
create policy if not exists "usage anon insert" on public.usage_logs for insert with check (true);
create policy if not exists "usage anon read" on public.usage_logs for select using (true);
create policy if not exists "mapping anon read" on public.mapping_memory for select using (true);
create policy if not exists "mapping anon insert" on public.mapping_memory for insert with check (true);
create policy if not exists "mapping anon update" on public.mapping_memory for update using (true) with check (true);
