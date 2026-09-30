"""Consented reader for bounded public company sources; OpenAI API wrapper."""
import urllib.request
import urllib.parse
import socket
import ipaddress
import json


def public_company_reader(url):
    p=urllib.parse.urlsplit(url)
    if p.scheme!='https' or not p.hostname or p.username or p.password:
        raise ValueError('Only HTTPS public company pages without credentials are allowed')
    if len(url)>2000:raise ValueError('URL is too long')
    try:
        ipaddress.ip_address(p.hostname)
        raise ValueError('IP-literal addresses are not allowed')
    except ValueError as exc:
        if str(exc)=='IP-literal addresses are not allowed':raise
    addresses=socket.getaddrinfo(p.hostname,None)
    if not addresses or any(not ipaddress.ip_address(item[4][0]).is_global for item in addresses):
        raise ValueError('Company domain is not publicly resolvable')
    # Jina receives only deliberately entered official public URLs and bounded
    # same-host child pages; not private documents or internal endpoints.
    req=urllib.request.Request('https://r.jina.ai/'+url,headers={'User-Agent':'PC-Company-Research/2.0'})
    with urllib.request.urlopen(req,timeout=35) as res:
        return res.read(160_000).decode('utf-8',errors='replace')


def company_api_call(endpoint,key,payload,timeout=140):
    if endpoint!='https://api.openai.com/v1/chat/completions':
        raise ValueError('Unsupported API endpoint')
    req=urllib.request.Request(endpoint,data=json.dumps(payload).encode('utf-8'),
        headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=timeout) as res:
        return json.loads(res.read().decode('utf-8'))
