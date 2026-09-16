-- Power & Corridors
-- Transaction metadata seed for canonical loader
-- Purpose: ensure FK-controlled transaction vocabulary exists BEFORE loading
-- packages containing pc_transactions / pc_transaction_participants.
--
-- Safe to run repeatedly: all statements are idempotent UPSERTs.

begin;

-- ---------------------------------------------------------------------------
-- 1. Transaction participant roles
-- pc_transaction_participants.role -> pc_meta_transaction_participant_roles.role
-- ---------------------------------------------------------------------------

insert into pc_meta_transaction_participant_roles
    (role, display_name, role_group, description, active, metadata)
values
    ('buyer',       'Buyer / Acquirer',          'acquirer',    'Purchasing or acquiring party.', true, '{"system_baseline":true}'::jsonb),
    ('seller',      'Seller / Disposing Party',  'seller',      'Selling or disposing party.', true, '{"system_baseline":true}'::jsonb),
    ('target',      'Target',                     'target',      'Company, asset or business that is the subject of the transaction.', true, '{"system_baseline":true}'::jsonb),
    ('offeror',     'Offeror',                    'acquirer',    'Party making a tender, takeover or other formal offer.', true, '{"system_baseline":true}'::jsonb),
    ('shareholder', 'Shareholder',                'shareholder', 'Shareholder participating in or affected by the transaction.', true, '{"system_baseline":true}'::jsonb),
    ('sponsor',     'Sponsor / Parent',           'sponsor',     'Parent, sponsor or controlling party backing the transaction.', true, '{"system_baseline":true}'::jsonb),
    ('advisor',     'Advisor',                    'advisor',     'Financial, legal or other transaction adviser.', true, '{"system_baseline":true}'::jsonb),
    ('financier',   'Financier',                  'financier',   'Debt or equity financing provider.', true, '{"system_baseline":true}'::jsonb)
on conflict (role) do update set
    display_name = excluded.display_name,
    role_group   = excluded.role_group,
    description  = excluded.description,
    active       = true,
    metadata     = coalesce(pc_meta_transaction_participant_roles.metadata, '{}'::jsonb)
                   || excluded.metadata,
    updated_at   = now();

-- ---------------------------------------------------------------------------
-- 2. Transaction category needed by the ADQ / AD Ports tender example
-- ---------------------------------------------------------------------------

insert into pc_meta_transaction_categories
    (transaction_category, display_name, category_group, description, active, metadata)
values
    ('m_and_a_ownership', 'M&A / Ownership', 'corporate_control',
     'Mergers, acquisitions, tender offers, equity purchases and changes in corporate ownership/control.',
     true, '{"system_baseline":true}'::jsonb)
on conflict (transaction_category) do update set
    display_name = excluded.display_name,
    category_group = excluded.category_group,
    description = excluded.description,
    active = true,
    metadata = coalesce(pc_meta_transaction_categories.metadata, '{}'::jsonb)
               || excluded.metadata;

-- ---------------------------------------------------------------------------
-- 3. Transaction type
-- pc_transactions.transaction_type is FK-controlled by pc_meta_transaction_types.
-- ---------------------------------------------------------------------------

insert into pc_meta_transaction_types
    (transaction_type, transaction_category, display_name, description, active, metadata)
values
    ('voluntary_cash_tender_offer', 'm_and_a_ownership',
     'Voluntary Cash Tender Offer',
     'Voluntary cash offer to acquire shares from existing shareholders.',
     true, '{"system_baseline":true}'::jsonb)
on conflict (transaction_type) do update set
    transaction_category = excluded.transaction_category,
    display_name = excluded.display_name,
    description = excluded.description,
    active = true,
    metadata = coalesce(pc_meta_transaction_types.metadata, '{}'::jsonb)
               || excluded.metadata,
    updated_at = now();

-- ---------------------------------------------------------------------------
-- 4. Transaction stage
-- ---------------------------------------------------------------------------

insert into pc_meta_transaction_stages
    (transaction_stage, display_name, stage_order, description, active, metadata)
values
    ('accepted_pending_settlement', 'Accepted — Pending Settlement', 60,
     'Offer acceptance threshold reached or acceptances received; settlement has not yet completed.',
     true, '{"system_baseline":true}'::jsonb)
on conflict (transaction_stage) do update set
    display_name = excluded.display_name,
    stage_order = excluded.stage_order,
    description = excluded.description,
    active = true,
    metadata = coalesce(pc_meta_transaction_stages.metadata, '{}'::jsonb)
               || excluded.metadata,
    updated_at = now();

commit;

-- Verification
select role, display_name, role_group, active
from pc_meta_transaction_participant_roles
where role in ('buyer','seller','target','offeror','shareholder','sponsor','advisor','financier')
order by role;

select transaction_category, display_name, active
from pc_meta_transaction_categories
where transaction_category = 'm_and_a_ownership';

select transaction_type, transaction_category, display_name, active
from pc_meta_transaction_types
where transaction_type = 'voluntary_cash_tender_offer';

select transaction_stage, display_name, stage_order, active
from pc_meta_transaction_stages
where transaction_stage = 'accepted_pending_settlement';
