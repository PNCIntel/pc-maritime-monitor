-- Global, mode-agnostic P&C publication feed. Independent of Saudi/legacy regional view.
-- These are authored qualitative judgments, NOT event-severity-derived scores.
BEGIN;
CREATE TABLE IF NOT EXISTS public.pc_global_risk_briefings (
 assessment_id text PRIMARY KEY,
 region_code text NOT NULL,
 geography text NOT NULL,
 headline text NOT NULL,
 risk_level text NOT NULL DEFAULT 'NOT RATED',
 trend text NOT NULL DEFAULT 'UNDETERMINED',
 confidence text NOT NULL DEFAULT 'Unassigned',
 executive_summary text NOT NULL,
 explanation text NOT NULL,
 risk_outlook text NOT NULL,
 monitoring_priorities jsonb NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(monitoring_priorities)='array'),
 review_triggers jsonb NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(review_triggers)='array'),
 threat_drivers jsonb NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(threat_drivers)='array'),
 company_exposure jsonb NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(company_exposure)='array'),
 evidence jsonb NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(evidence)='array'),
 assessment_date date NOT NULL,
 as_known_at timestamptz NOT NULL,
 valid_until timestamptz NOT NULL,
 coverage_status text NOT NULL DEFAULT 'Source-qualified',
 scope_note text,
 methodology_notice text NOT NULL DEFAULT 'P&C qualitative assessment; scenario outlook is not a prediction. Reported incidents and effects remain separately qualified.',
 publication_status text NOT NULL DEFAULT 'draft' CHECK (publication_status IN ('draft','published','withdrawn'))
);
-- The following published entries contain authored assessment and evidence; no fabricated event IDs,
-- corporate damage, vessel positions or probabilities. Update with local canonical event links after review.
INSERT INTO public.pc_global_risk_briefings
 (assessment_id,region_code,geography,headline,risk_level,trend,confidence,executive_summary,explanation,risk_outlook,monitoring_priorities,review_triggers,threat_drivers,evidence,assessment_date,as_known_at,valid_until,coverage_status,scope_note,publication_status)
VALUES
 ('PC_GLOBAL_BLACK_SEA_TURKIYE_20261015','BLACK_SEA','Türkiye / Black Sea','Attack-damaged merchant shipping: cross-border consequences',
 'ELEVATED','UNDETERMINED','Moderate',
 'Merchant-vessel attacks in the Black Sea can create a second, geographically displaced hazard after crew evacuation: unmanned drift, grounding, pollution and salvage exposure along neighbouring coasts.',
 'The reported Golden Sapling and Omskiy-107 groundings on Türkiye’s coast demonstrate that the effect of an attack is not confined to the location of the strike. This matters to coastal authorities, emergency towing, coastal navigation, marine insurers and port approaches. Incident attribution and current vessel conditions require separate confirmation. Affected shipping, grain and energy corridors can experience secondary costs even without a new strike at the destination.',
 'Further secondary maritime disruption remains possible where damaged or abandoned vessels drift toward the Turkish coast. This is a conditional outlook, not a forecast of a specific new grounding or closure.',
 '["Fresh attacks on commercial hulls and crew abandonment","Turkish coastguard warnings, salvage and pollution reports","Drift tracks and weather affecting damaged vessels","Bosphorus and port approach advisories","Grain, energy cargo routing and war-risk insurance terms"]'::jsonb,
 '["New unmanned drift toward traffic lanes or shore","Pollution, casualty or navigation restriction confirmed","Further strikes involving Turkish-operated ships"]'::jsonb,
 '["Commercial hull attacks","Residual vessel mobility after crew evacuation","Weather, towage and salvage capacity"]'::jsonb,
 '[{"title":"P&C Black Sea Maritime Alert, 03 September 2026","source_url":"https://www.powerncorridors.com/maritime-alert-03-sept-2026-black-sea/"},{"title":"Splash247, attack-damaged ships grounding on Turkish coast, 31 August 2026","source_url":"https://splash247.com/two-attack-damaged-ships-wash-up-on-turkish-black-sea-coast/"},{"title":"Reuters, ships adopt makeshift anti-drone defences, 02 September 2026","source_url":"https://www.reuters.com/world/ships-adopt-makeshift-anti-drone-defences-black-sea-attacks-intensify-2026-09-02/"}]'::jsonb,
 '2026-10-15','2026-10-15 10:00+00','2026-10-22 10:00+00','Historical incidents; current status requires confirmation',
 'Black Sea merchant shipping and Turkish coastal exposure; not a general rating for all of Türkiye.','published'),
 ('PC_GLOBAL_KOREAN_PENINSULA_20261015','KOREAN_PENINSULA','Korean Peninsula / Northeast Asia','DPRK military signalling and cross-border connectivity',
 'ELEVATED','INCREASING','Moderate',
 'Repeated DPRK missile launches and reported submarine-launched cruise missile tests increase regional military signalling. The opening of the China–DPRK New Yalu River Bridge is a separate transport-connectivity development requiring sanctions-aware trade monitoring.',
 'South Korean and Japanese reporting on 12 October launches and DPRK state reporting of 14 October naval tests establish continuing weapons activity, but do not establish a direct threat to any named merchant ship, airport or port. The new bridge changes potential road-trade capacity; physical opening does not establish unrestricted trade or sanction relief. These strands are monitored together for corridor relevance, not conflated into a single incident.',
 'Continued military signalling is plausible, with heightened attention to subsequent naval tests and allied responses. Cross-border road traffic may develop gradually after the bridge opening, subject to operational controls and existing sanctions. No immediate corridor closure is established by these reports.',
 '["DPRK launch notices and South Korean/Japanese military responses","Maritime and aviation navigational warnings","Further submarine or ballistic-missile tests","Observed operating rules and traffic on the New Yalu River Bridge","Official sanctions, customs and border-control changes"]'::jsonb,
 '["Missile activity affecting a declared navigational or aviation area","New official border restrictions or throughput changes","Verified disruption to a named transport or infrastructure asset"]'::jsonb,
 '["Weapons testing and military signalling","Regional force posture and notices","Dandong–Sinuiju road connectivity under sanctions"]'::jsonb,
 '[{"title":"Reuters, North Korea missile launches, 12 October 2026","source_url":"https://www.reuters.com/world/asia-pacific/north-korea-fires-unidentified-projectile-toward-sea-off-its-east-coast-seoul-2026-10-12/"},{"title":"Reuters, DPRK submarine-launched cruise missile tests, 14 October 2026","source_url":"https://www.reuters.com/world/asia-pacific/north-korea-says-it-tested-submarine-launched-cruise-missiles-kcna-says-2026-10-14/"},{"title":"Reuters, New Yalu River Bridge opening, 15 October 2026","source_url":"https://www.reuters.com/world/asia-pacific/trucks-line-up-long-delayed-china-north-korea-bridge-officially-opens-2026-10-15/"}]'::jsonb,
 '2026-10-15','2026-10-15 10:00+00','2026-10-22 10:00+00','Source-qualified; facility impacts not established',
 'Northeast Asia military developments and cross-border transport connectivity; not an assertion of direct asset damage.','published')
ON CONFLICT (assessment_id) DO NOTHING;
COMMIT;
SELECT assessment_id,geography,headline,risk_level,risk_outlook,publication_status FROM public.pc_global_risk_briefings ORDER BY as_known_at DESC;
