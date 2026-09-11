"""Supabase authentication and P&C product/organization context for Streamlit."""
from __future__ import annotations
import os
from typing import Optional

try:
    import streamlit as st
except Exception:
    st = None

try:
    from supabase import create_client
except Exception:
    create_client = None


def _secret(name, default=""):
    v = os.getenv(name, default)
    if v:
        return v
    if st is not None:
        try:
            if name in st.secrets:
                return str(st.secrets[name])
            if "supabase" in st.secrets:
                mp={"SUPABASE_URL":"url","SUPABASE_ANON_KEY":"anon_key","SUPABASE_SERVICE_ROLE_KEY":"service_role_key"}
                k=mp.get(name)
                if k and k in st.secrets["supabase"]:
                    return str(st.secrets["supabase"][k])
        except Exception:
            pass
    return default


def configured():
    return bool(create_client and _secret("SUPABASE_URL") and _secret("SUPABASE_ANON_KEY"))


def anon_client():
    if not configured():
        return None
    return create_client(_secret("SUPABASE_URL"), _secret("SUPABASE_ANON_KEY"))


def service_client():
    if not create_client or not _secret("SUPABASE_URL") or not _secret("SUPABASE_SERVICE_ROLE_KEY"):
        return None
    return create_client(_secret("SUPABASE_URL"), _secret("SUPABASE_SERVICE_ROLE_KEY"))


def _set_session(auth_response):
    sess = getattr(auth_response, "session", None)
    user = getattr(auth_response, "user", None)
    if st is not None:
        st.session_state["pc_auth_session"] = sess
        st.session_state["pc_auth_user"] = user
    return user


def sign_in(email: str, password: str):
    c = anon_client()
    if c is None:
        raise RuntimeError("Supabase auth is not configured")
    resp = c.auth.sign_in_with_password({"email": email, "password": password})
    return _set_session(resp)


def sign_out():
    if st is not None:
        for k in ["pc_auth_session","pc_auth_user","pc_user_context"]:
            st.session_state.pop(k, None)


def current_user():
    if st is None:
        return None
    return st.session_state.get("pc_auth_user")


def _uid(user):
    return str(getattr(user, "id", "") or "")


def user_context(user=None):
    if st is not None and st.session_state.get("pc_user_context"):
        return st.session_state["pc_user_context"]
    user = user or current_user()
    uid = _uid(user)
    if not uid:
        return None
    svc = service_client()
    if svc is None:
        return {"user_id":uid,"email":getattr(user,"email",None),"global_role":"user","memberships":[],"products":[]}
    profile = (svc.table("pc_profiles").select("*").eq("user_id",uid).limit(1).execute().data or [{}])[0]
    memberships = svc.table("pc_organization_members").select("organization_id,role,active,pc_organizations(name,slug,status,seat_limit)").eq("user_id",uid).eq("active",True).execute().data or []
    org_ids=[m.get("organization_id") for m in memberships if m.get("organization_id")]
    products=[]
    if org_ids:
        products = svc.table("pc_organization_entitlements").select("organization_id,product_code,tier,active,start_date,end_date,feature_overrides").in_("organization_id",org_ids).eq("active",True).execute().data or []
    ctx={
        "user_id":uid,
        "email":profile.get("email") or getattr(user,"email",None),
        "display_name":profile.get("display_name"),
        "global_role":profile.get("global_role","user"),
        "memberships":memberships,
        "products":products,
    }
    if st is not None:
        st.session_state["pc_user_context"]=ctx
    return ctx


def has_product(ctx, product_code: str) -> bool:
    if not ctx:
        return False
    if ctx.get("global_role") in {"super_admin","staff"}:
        return True
    code=product_code.upper()
    return any(str(p.get("product_code","")).upper()==code and p.get("active",True) for p in ctx.get("products",[]))


def require_login(product_code: Optional[str]=None, title="P&C Client Login"):
    """Render a login gate. In local development, PC_ALLOW_LOCAL_DEV=true bypasses auth."""
    if _secret("PC_ALLOW_LOCAL_DEV","false").lower()=="true" and not configured():
        return {"user_id":"local","email":"local@pc","global_role":"super_admin","memberships":[],"products":[{"product_code":product_code or "TRADE","active":True}]}
    if not configured():
        if st is not None:
            st.error("Supabase authentication is not configured. Add SUPABASE_URL and SUPABASE_ANON_KEY to Streamlit secrets.")
            st.stop()
        return None
    user=current_user()
    if not user:
        if st is None:
            return None
        st.subheader(title)
        with st.form(f"pc_login_{product_code or 'generic'}"):
            email=st.text_input("Email")
            password=st.text_input("Password",type="password")
            submitted=st.form_submit_button("Sign in")
        if submitted:
            try:
                sign_in(email,password)
                st.rerun()
            except Exception as exc:
                st.error(f"Sign-in failed: {exc}")
        st.stop()
    ctx=user_context(user)
    if product_code and not has_product(ctx, product_code):
        if st is not None:
            st.error(f"Your organization does not currently have access to {product_code}.")
            if st.button("Sign out"):
                sign_out(); st.rerun()
            st.stop()
        return None
    return ctx


def require_super_admin():
    ctx=require_login(None,"P&C Power Admin")
    if ctx.get("global_role") not in {"super_admin","staff"}:
        st.error("P&C staff access required.")
        st.stop()
    return ctx


def organization_for_context(ctx):
    ms=ctx.get("memberships",[]) if ctx else []
    return ms[0] if ms else None
