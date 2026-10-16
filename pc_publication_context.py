"""Build bounded, provenance-aware publication context from already resolved canonical records.

Do not turn association into causation or research queues into legal designations.
This module contains no database writes and works across transport modes.
"""
from __future__ import annotations


def _text(v):
    return str(v or "").strip()


def _meta(v):
    m=(v or {}).get("metadata") or {}
    return m if isinstance(m,dict) else {}


def _public_record(v, fields):
    return {k:v.get(k) for k in fields if v.get(k) not in (None,"",[],{})}


def build_context(record, vessel=None, company_roles=None, designations=None,
                  pgsa_queue=None, related=None, assets=None, updates=None,
                  corporate_edges=None, identity_history=None, historical_roles=None):
    """Return structured context and coverage gaps; no speculative link generation."""
    vessel=vessel or {}
    result={"subject":_public_record(record,("title","start_date","verification_status","description","country")),
            "vessel_profile":_public_record(vessel,("name","imo","flag","asset_type","vessel_type",
                        "built_year","year_built","owner_entity_id","operator_entity_id")),
            "vessel_record_metadata":_meta(vessel),
            "company_history":[],"published_sanctions":[],"non_designation_research":[],
            "related_developments":[],"infrastructure":[],"updates":[],"corporate_context":[],
            "coverage_gaps":[],"identity_history":[],"dated_company_roles":[]}
    for item in identity_history or []:
        result["identity_history"].append({
          "identity":_public_record(item,("identity_type","identity_value","observed_on","date_basis","valid_from","valid_to","source_url")),
          "qualification":"Source observation is not proof of the exact rename or flag-change date"})
    for item in historical_roles or []:
        role=item.get("role") or {}; company=item.get("company") or {}
        result["dated_company_roles"].append({
          "company":_public_record(company,("entity_id","name","country")),
          "role":_public_record(role,("asset_role","role_status","valid_from","valid_to","as_of","source_id")),
          "metadata":_public_record(_meta(role),("role_detail","source_url","source_urls","date_qualification")),
          "qualification":"An as-of date documents an observation, not necessarily the start of the role; dated former roles are not current roles"})
    for edge,company in company_roles or []:
        result["company_history"].append({
          "company":_public_record(company,("entity_id","name","country")),
          "relationship":_public_record(edge,("relationship_type","relationship","valid_from","valid_to",
                                            "source_url","confidence","review_status","record_status")),
          "metadata":_public_record(_meta(edge),("source_urls","observed_on","observation_date","date_qualification","editorial_status")),
          "qualification":"Registry-reported role; observation date is not role inception and registered ownership is not beneficial ownership"})
    for link,designation in designations or []:
        result["published_sanctions"].append({
          "designation":_public_record(designation,("primary_name","source_list","designation_date",
                                   "status","source_url","sanctions_designation_id")),
          "link":_public_record(link,("review_status","is_direct_designation","linked_type")),
          "qualification":"The designation and vessel link must be checked against their authority and dates"})
    for item in pgsa_queue or []:
        result["non_designation_research"].append({
          "record":_public_record(item,("authority_code","subject_identifier","reported_name",
                                       "research_status","source_url")),
          "qualification":"Research roster only; not a legal sanctions designation"})
    for edge,event in related or []:
        result["related_developments"].append({
          "event":_public_record(event,("title","start_date","verification_status","description")),
          "relationship":_public_record(edge,("relationship_type","relationship","claim_status","rationale")),
          "qualification":"Contextual link alone does not prove shared cause, actor or impact"})
    for item in assets or []:
        result["infrastructure"].append(_public_record(item,("name","mode","relationship","impact_status")))
    for item in updates or []:
        result["updates"].append(_public_record(item,("summary","occurred_at","reported_at","published_at","source_url")))
    for edge,parent,child in corporate_edges or []:
        result["corporate_context"].append({
          "parent":_text(parent.get("name")),"child":_text(child.get("name")),
          "relationship":_public_record(edge,("relationship_type","relationship","valid_from","valid_to","source_url")),
          "qualification":"Network context, not proof of direct event involvement"})
    if not result["vessel_profile"] and not result["infrastructure"]:
        result["coverage_gaps"].append("No resolved mobile or fixed asset profile attached")
    if result["vessel_profile"] and not result["company_history"]:
        result["coverage_gaps"].append("Vessel corporate role history not resolved in this dossier")
    if not result["related_developments"]:
        result["coverage_gaps"].append("No expressly linked prior developments returned")
    if not result["published_sanctions"]:
        result["coverage_gaps"].append("No linked published designation returned; this is not a clearance finding")
    return result
