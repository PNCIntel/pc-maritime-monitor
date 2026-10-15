"""Embedded regional basemap for PDF briefs: location marker is contextual, not damage footprint."""
from __future__ import annotations
from io import BytesIO
from math import asinh, atan, cos, degrees, floor, pi, radians, sinh, tan
import base64
import requests
from PIL import Image, ImageDraw, ImageFont
import streamlit as st


@st.cache_data(ttl=604800, max_entries=256, show_spinner=False)
def regional_map_uri(latitude, longitude, zoom=8):
    """Return a PNG data URI and attribution; omit image cleanly if tile service is offline."""
    lat,lon=float(latitude),float(longitude)
    if not (-85<=lat<=85 and -180<=lon<=180): return None
    z=int(max(2,min(12,zoom))); n=2**z
    x=(lon+180)/360*n
    y=(1-asinh(tan(radians(lat)))/pi)/2*n
    left,top=floor(x)-1,floor(y)-1
    canvas=Image.new("RGB",(768,768),"#edf3f5")
    downloaded=0
    for dx in range(3):
        for dy in range(3):
            xx=(left+dx)%n; yy=top+dy
            if yy<0 or yy>=n:continue
            try:
                response=requests.get(f"https://tile.openstreetmap.org/{z}/{xx}/{yy}.png",
                  headers={"User-Agent":"PowerAndCorridors/1.0 (powerncorridors.com; intelligence brief renderer)"},
                  timeout=3)
                response.raise_for_status()
                with Image.open(BytesIO(response.content)) as tile:
                    canvas.paste(tile.convert("RGB"),(dx*256,dy*256))
                downloaded+=1
            except (requests.RequestException,OSError,ValueError): pass
    if downloaded<6:return None
    cx=(x-left)*256; cy=(y-top)*256
    d=ImageDraw.Draw(canvas)
    d.ellipse((cx-10,cy-10,cx+10,cy+10),fill="#0e617e",outline="white",width=3)
    d.ellipse((cx-3,cy-3,cx+3,cy+3),fill="white")
    d.rectangle((0,738,768,768),fill="#ffffff")
    d.text((10,745),"© OpenStreetMap contributors · openstreetmap.org/copyright",fill="#28495a")
    result=BytesIO();canvas.save(result,format="PNG",optimize=True)
    return "data:image/png;base64,"+base64.b64encode(result.getvalue()).decode("ascii")
