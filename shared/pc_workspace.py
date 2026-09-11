"""Client workspace persistence helpers."""
from __future__ import annotations
from pc_auth import service_client


def primary_org_id(ctx):
    ms=(ctx or {}).get('memberships',[])
    return ms[0].get('organization_id') if ms else None


def save_query(ctx,product_code,title,query_text,query_type='search',parameters=None,last_result=None):
    sb=service_client(); oid=primary_org_id(ctx); uid=(ctx or {}).get('user_id')
    if not sb or not oid or not uid: return False,"Client workspace is not configured for this login."
    row={
        'organization_id':oid,'user_id':uid,'product_code':product_code,
        'title':title or query_text[:100],'query_text':query_text,'query_type':query_type,
        'parameters':parameters or {},'last_result':last_result,
    }
    sb.table('pc_saved_queries').insert(row).execute()
    return True,'Saved to your organization workspace.'


def create_watchlist(ctx,product_code,name,description=''):
    sb=service_client(); oid=primary_org_id(ctx); uid=(ctx or {}).get('user_id')
    if not sb or not oid or not uid: return None
    data=sb.table('pc_saved_watchlists').insert({'organization_id':oid,'created_by':uid,'product_code':product_code,'name':name,'description':description,'shared_with_org':True}).execute().data or []
    return data[0] if data else None
