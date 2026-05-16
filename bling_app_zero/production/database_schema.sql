-- MapeiaAI production schema draft
-- Target: PostgreSQL / Supabase

create table if not exists app_users (
    id uuid primary key,
    email text unique not null,
    name text,
    status text not null default 'active',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists credit_wallets (
    user_id uuid primary key references app_users(id) on delete cascade,
    balance integer not null default 0 check (balance >= 0),
    updated_at timestamptz not null default now()
);

create table if not exists credit_transactions (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references app_users(id) on delete cascade,
    type text not null,
    amount integer not null,
    balance_after integer not null,
    reference_type text,
    reference_id text,
    metadata jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now()
);

create table if not exists mapping_jobs (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references app_users(id) on delete cascade,
    operation text not null,
    source_hash text not null,
    mapping_signature text not null,
    status text not null default 'created',
    credit_cost integer not null default 1,
    credit_transaction_id uuid references credit_transactions(id),
    metadata jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique (user_id, mapping_signature)
);

create table if not exists payments (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references app_users(id) on delete cascade,
    provider text not null,
    provider_payment_id text unique,
    status text not null default 'pending',
    package_label text,
    credits integer not null default 0,
    amount_brl numeric(10,2) not null default 0,
    raw_payload jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists uploaded_files (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references app_users(id) on delete cascade,
    mapping_job_id uuid references mapping_jobs(id) on delete set null,
    file_name text not null,
    file_hash text not null,
    storage_path text,
    mime_type text,
    size_bytes bigint not null default 0,
    created_at timestamptz not null default now()
);

create table if not exists audit_logs (
    id uuid primary key default gen_random_uuid(),
    user_id uuid references app_users(id) on delete set null,
    area text not null,
    event text not null,
    status text,
    metadata jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now()
);

create index if not exists idx_credit_transactions_user_created on credit_transactions(user_id, created_at desc);
create index if not exists idx_mapping_jobs_user_created on mapping_jobs(user_id, created_at desc);
create index if not exists idx_payments_user_created on payments(user_id, created_at desc);
create index if not exists idx_audit_logs_user_created on audit_logs(user_id, created_at desc);
