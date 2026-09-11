#!/usr/bin/env python3
"""Promote an existing Supabase Auth user to P&C super_admin by email."""
import argparse, os
from supabase import create_client
ap=argparse.ArgumentParser(); ap.add_argument('email'); args=ap.parse_args()
url=os.getenv('SUPABASE_URL'); key=os.getenv('SUPABASE_SERVICE_ROLE_KEY')
if not url or not key: raise SystemExit('Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY')
sb=create_client(url,key)
# Supabase admin list_users can be paginated; try first 1000 for bootstrap.
resp=sb.auth.admin.list_users(page=1,per_page=1000)
users=getattr(resp,'users',None) or resp
match=next((u for u in users if str(getattr(u,'email','')).lower()==args.email.lower()),None)
if not match: raise SystemExit('Auth user not found. Create the user in Supabase Authentication first.')
uid=str(getattr(match,'id'))
sb.table('pc_profiles').upsert({'user_id':uid,'email':args.email,'global_role':'super_admin','active':True},on_conflict='user_id').execute()
print(f'P&C super_admin: {args.email} ({uid})')
