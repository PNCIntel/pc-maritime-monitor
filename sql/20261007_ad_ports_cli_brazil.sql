-- Power & Corridors
-- AD Ports Group / CLI Brazil corporate graph load
-- 2026-10-07
-- Idempotent and source-backed.
--
-- Official sources:
-- 2026-06-02 announcement:
-- https://www.adportsgroup.com/en/news-and-media/2026/06/02/ad-ports-group-acquires-cli
-- 2026-10-02 completion:
-- https://www.adportsgroup.com/en/news-and-media/2026/10/02/ad-ports-group-successfully-completes-acquisition-of-brazils-cli

begin;

-- ---------------------------------------------------------------------------
-- 1. Create CLI / CLI Norte / CLI Sul / Noatum Ports if not already canonical.
--    Reuse existing name matches rather than creating duplicates.
-- ---------------------------------------------------------------------------

with seed(entity_id,name,subtype,hq_city,hq_country,source_url) as (
    values
      (
        'COMP_CLI',
        'Corredor Logistica e Infraestrutura',
        'port_terminal_operator',
        'Sao Paulo',
        'Brazil',
        'https://www.adportsgroup.com/en/news-and-media/2026/10/02/ad-ports-group-successfully-completes-acquisition-of-brazils-cli'
      ),
      (
        'COMP_CLI_NORTE',
        'CLI Norte',
        'terminal_operating_company',
        'Sao Luis',
        'Brazil',
        'https://www.adportsgroup.com/en/news-and-media/2026/06/02/ad-ports-group-acquires-cli'
      ),
      (
        'COMP_CLI_SUL',
        'CLI Sul',
        'terminal_operating_company',
        'Santos',
        'Brazil',
        'https://www.adportsgroup.com/en/news-and-media/2026/06/02/ad-ports-group-acquires-cli'
      ),
      (
        'COMP_NOATUM_PORTS',
        'Noatum Ports',
        'ports_operating_company',
        null,
        null,
        'https://www.adportsgroup.com/en/news-and-media/2026/10/02/ad-ports-group-successfully-completes-acquisition-of-brazils-cli'
      )
)
insert into public.pc_entities(
    entity_id,
    name,
    entity_type,
    subtype,
    hq_city,
    hq_country,
    status,
    record_status,
    data_quality,
    as_of,
    metadata
)
select
    s.entity_id,
    s.name,
    'company',
    s.subtype,
    s.hq_city,
    s.hq_country,
    'active',
    'provisional',
    'high',
    date '2026-10-07',
    jsonb_build_object(
        'research_program','AD_PORTS_GROUP_CORPORATE_TREE_2026',
        'research_sources',jsonb_build_array(s.source_url),
        'source_quality','official'
    )
from seed s
where not exists (
    select 1
    from public.pc_entities e
    where e.entity_id=s.entity_id
       or lower(trim(e.name))=lower(trim(s.name))
);

-- ---------------------------------------------------------------------------
-- 2. Aliases.
-- ---------------------------------------------------------------------------

insert into public.pc_entity_aliases(entity_id,alias)
select x.entity_id,x.alias
from (
    values
      ('COMP_CLI','CLI'),
      ('COMP_CLI','Corredor Logística e Infraestrutura'),
      ('COMP_CLI_NORTE','CLI Norte Terminal'),
      ('COMP_CLI_SUL','CLI Sul Terminal')
) as x(entity_id,alias)
where exists (
    select 1 from public.pc_entities e where e.entity_id=x.entity_id
)
and not exists (
    select 1
    from public.pc_entity_aliases a
    where a.entity_id=x.entity_id
      and lower(trim(a.alias))=lower(trim(x.alias))
);

-- ---------------------------------------------------------------------------
-- 3. AD Ports Group -> CLI.
--    Completion occurred 2026-10-02.
--    The official release confirms operational membership of AD Ports Group
--    after regulatory / antitrust approvals. No percentage is asserted here
--    because the release does not explicitly state a numeric stake.
-- ---------------------------------------------------------------------------

insert into public.pc_company_relationships(
    parent_company_key,
    child_company_key,
    relationship,
    value,
    unit,
    effective_from,
    effective_to,
    confidence,
    source_url,
    notes,
    metadata
)
select
    'COMP_ADPORTS',
    'COMP_CLI',
    'controlled_interest',
    null,
    null,
    date '2026-10-02',
    null,
    'high',
    'https://www.adportsgroup.com/en/news-and-media/2026/10/02/ad-ports-group-successfully-completes-acquisition-of-brazils-cli',
    'AD Ports Group completed the acquisition of CLI after regulatory and antitrust approvals. Announcement was 2 June 2026; completion was 2 October 2026.',
    jsonb_build_object(
        'transaction_type','acquisition',
        'announcement_date','2026-06-02',
        'completion_date','2026-10-02',
        'enterprise_value_aed',3100000000,
        'enterprise_value_usd',835000000,
        'operational_control_via','COMP_NOATUM_PORTS',
        'sellers',jsonb_build_array('Macquarie Asset Management','IG4 Capital'),
        'first_entry_region','South America',
        'business_vertical','agrifood / ports'
    )
where exists (select 1 from public.pc_entities where entity_id='COMP_ADPORTS')
  and exists (select 1 from public.pc_entities where entity_id='COMP_CLI')
  and not exists (
      select 1
      from public.pc_company_relationships r
      where r.parent_company_key='COMP_ADPORTS'
        and r.child_company_key='COMP_CLI'
        and lower(r.relationship)=lower('controlled_interest')
        and coalesce(r.effective_from,date '1900-01-01')=date '2026-10-02'
  );

-- ---------------------------------------------------------------------------
-- 4. Noatum -> Noatum Ports.
--    Official completion release calls Noatum Ports the international ports
--    operating arm of AD Ports Group. We retain this as a business-unit edge.
-- ---------------------------------------------------------------------------

insert into public.pc_company_relationships(
    parent_company_key,
    child_company_key,
    relationship,
    effective_from,
    confidence,
    source_url,
    notes,
    metadata
)
select
    'COMP_NOATUM',
    'COMP_NOATUM_PORTS',
    'business_unit_parent',
    null,
    'high',
    'https://www.adportsgroup.com/en/news-and-media/2026/10/02/ad-ports-group-successfully-completes-acquisition-of-brazils-cli',
    'Noatum Ports is identified by AD Ports Group as its international ports operating arm.',
    jsonb_build_object(
        'as_of_date','2026-10-02',
        'relationship_basis','official group description'
    )
where exists (select 1 from public.pc_entities where entity_id='COMP_NOATUM')
  and exists (select 1 from public.pc_entities where entity_id='COMP_NOATUM_PORTS')
  and not exists (
      select 1 from public.pc_company_relationships r
      where r.parent_company_key='COMP_NOATUM'
        and r.child_company_key='COMP_NOATUM_PORTS'
        and lower(r.relationship)=lower('business_unit_parent')
        and r.effective_to is null
  );

-- ---------------------------------------------------------------------------
-- 5. Noatum Ports -> CLI operational control from financial close.
-- ---------------------------------------------------------------------------

insert into public.pc_company_relationships(
    parent_company_key,
    child_company_key,
    relationship,
    effective_from,
    confidence,
    source_url,
    notes,
    metadata
)
select
    'COMP_NOATUM_PORTS',
    'COMP_CLI',
    'operator',
    date '2026-10-02',
    'high',
    'https://www.adportsgroup.com/en/news-and-media/2026/10/02/ad-ports-group-successfully-completes-acquisition-of-brazils-cli',
    'Noatum Ports assumed operational control of CLI following financial close and regulatory approvals.',
    jsonb_build_object(
        'role_detail','operational_control',
        'completion_date','2026-10-02'
    )
where exists (select 1 from public.pc_entities where entity_id='COMP_NOATUM_PORTS')
  and exists (select 1 from public.pc_entities where entity_id='COMP_CLI')
  and not exists (
      select 1 from public.pc_company_relationships r
      where r.parent_company_key='COMP_NOATUM_PORTS'
        and r.child_company_key='COMP_CLI'
        and lower(r.relationship)=lower('operator')
        and r.effective_to is null
  );

-- ---------------------------------------------------------------------------
-- 6. CLI -> CLI Norte / CLI Sul.
--    Official 2 June announcement gives 100% and 80% respectively.
-- ---------------------------------------------------------------------------

insert into public.pc_company_relationships(
    parent_company_key,
    child_company_key,
    relationship,
    value,
    unit,
    effective_from,
    effective_to,
    confidence,
    source_url,
    notes,
    metadata
)
select *
from (
    values
      (
        'COMP_CLI',
        'COMP_CLI_NORTE',
        'equity_owner',
        100::numeric,
        'percent',
        null::date,
        null::date,
        'high',
        'https://www.adportsgroup.com/en/news-and-media/2026/06/02/ad-ports-group-acquires-cli',
        'CLI owns 100% of CLI Norte, operator of the agri-bulk terminal at the Port of Itaqui.',
        jsonb_build_object(
            'as_of_date','2026-06-02',
            'location','Port of Itaqui',
            'cargo_focus','grain / agri-bulk',
            'corridor','Arc of the North'
        )
      ),
      (
        'COMP_CLI',
        'COMP_CLI_SUL',
        'equity_owner',
        80::numeric,
        'percent',
        null::date,
        null::date,
        'high',
        'https://www.adportsgroup.com/en/news-and-media/2026/06/02/ad-ports-group-acquires-cli',
        'CLI owns 80% of CLI Sul, operator of the agri-bulk terminal at the Port of Santos.',
        jsonb_build_object(
            'as_of_date','2026-06-02',
            'location','Port of Santos',
            'cargo_focus','sugar / corn / soybeans'
        )
      )
) as s(
    parent_company_key,
    child_company_key,
    relationship,
    value,
    unit,
    effective_from,
    effective_to,
    confidence,
    source_url,
    notes,
    metadata
)
where exists (
    select 1 from public.pc_entities e where e.entity_id=s.parent_company_key
)
and exists (
    select 1 from public.pc_entities e where e.entity_id=s.child_company_key
)
and not exists (
    select 1
    from public.pc_company_relationships r
    where r.parent_company_key=s.parent_company_key
      and r.child_company_key=s.child_company_key
      and lower(r.relationship)=lower(s.relationship)
      and coalesce(r.value,-1)=coalesce(s.value,-1)
      and r.effective_to is null
);

commit;

-- ---------------------------------------------------------------------------
-- Verification
-- ---------------------------------------------------------------------------

select
    r.parent_company_key,
    p.name as parent_name,
    r.child_company_key,
    c.name as child_name,
    r.relationship,
    r.value,
    r.unit,
    r.effective_from,
    r.effective_to,
    r.source_url
from public.pc_company_relationships r
left join public.pc_entities p on p.entity_id=r.parent_company_key
left join public.pc_entities c on c.entity_id=r.child_company_key
where r.parent_company_key in (
    'COMP_ADPORTS','COMP_NOATUM','COMP_NOATUM_PORTS','COMP_CLI'
)
  and r.child_company_key in (
    'COMP_NOATUM_PORTS','COMP_CLI','COMP_CLI_NORTE','COMP_CLI_SUL'
)
order by coalesce(r.effective_from,date '1900-01-01'), r.parent_company_key, r.child_company_key;
