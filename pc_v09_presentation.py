"""Safe, source-preserving Trade narrative presentation and editorial QA.
No automatic facts or inferred commercial effects are generated here.
"""
import json
import re
from urllib.parse import urlparse

MISSING={'','none','null','not assessed','not supplied','n/a','na','unknown'}
FIELD_NAMES={'description':'What happened / description', 'what_it_means':'Why it matters',
 'operational_impact':'Operational implications','commercial_implications':'Commercial implications',
 'pc_assessment':'P&C assessment','monitoring_indicators':'Monitoring indicators',
 'research_gaps':'Research gaps'}


def as_object(value):
 if isinstance(value,str):
  try:return json.loads(value)
  except (ValueError,TypeError):return value
 return value


def readable(value):
 """Correct presentation artifacts only; keep original source text unchanged in DB."""
 value=as_object(value)
 if value is None:return ''
 if isinstance(value,dict):return json.dumps(value,ensure_ascii=False)
 if isinstance(value,list):return '; '.join(filter(None,(readable(x) for x in value)))
 s=str(value).strip()
 # Common corrupted inline dollar/LaTeX formatting from rich spreadsheet->markdown displays.
 s=s.replace('\\$','$').replace('\\mathrm{TEU}','TEU').replace('\\text{TEU}','TEU')
 s=re.sub(r'\$\{([^{}]+)\}',lambda m:'$'+m[1],s)
 # Preserve numeric content, but avoid inventing missing spaces in a concatenated passage.
 s=re.sub(r'(?i)(USD?|US\$)\s*([0-9][0-9,.]*)\s*/\s*TEU',lambda m:'US$'+m[2]+'/TEU',s)
 return s


def missing(value):
 if value is None:return True
 v=as_object(value)
 if isinstance(v,(dict,list)):return not v
 return readable(v).strip().casefold() in MISSING


def entries(value):
 v=as_object(value)
 if v is None:return []
 if isinstance(v,list):
  result=[]
  for x in v:
   if isinstance(x,dict):
    text=x.get('indicator') or x.get('description') or x.get('text') or x.get('value')
    if text:result.append(readable(text))
   elif not missing(x):result.append(readable(x))
  return result
 if isinstance(v,dict):
  return [readable(x) for x in v.values() if not missing(x)]
 if missing(v):return []
 s=str(v)
 # Split genuine line-separated or semicolon-delimited indicators, not full prose at commas.
 return [re.sub(r'^\s*(?:[-•*]|\d+[.)])\s*','',x).strip() for x in re.split(r'\n|\s*;\s*',s) if x.strip()]


def sources(value):
 v=as_object(value)
 if isinstance(v,dict):v=[v]
 if isinstance(v,str):v=[{'url':v}]
 if not isinstance(v,list):return []
 result=[];seen=set()
 for item in v:
  if isinstance(item,str):
   item=as_object(item)
   if isinstance(item,str):item={'url':item}
  if not isinstance(item,dict):continue
  url=item.get('url') or item.get('source_url')
  if not isinstance(url,str):continue
  p=urlparse(url.strip())
  if p.scheme not in ('https','http') or not p.hostname:continue
  norm=url.strip()
  if norm in seen:continue
  seen.add(norm)
  result.append({'url':norm,'publisher':readable(item.get('publisher')) or p.hostname,
   'headline':readable(item.get('headline') or item.get('title')),
   'published_at':readable(item.get('published_at')),'role':readable(item.get('role'))})
 return result


def quality_flags(record):
 flags=[]
 for field in ('description','what_it_means','operational_impact','commercial_implications','pc_assessment'):
  if missing(record.get(field)):flags.append(f'Missing {FIELD_NAMES[field].lower()}')
 if not entries(record.get('monitoring_indicators')):flags.append('Missing monitoring indicators')
 if not sources(record.get('source_evidence') or record.get('research_sources')):flags.append('Missing source URLs')
 if not missing(record.get('commercial_implications')) and missing(record.get('operational_impact')):
  flags.append('Commercial text present, operational implications still unassessed')
 text=readable(record.get('description'))
 if re.search(r'\$\{[^{}]+\}|\\mathrm\{|\\text\{|\$\s*\\',text):
  flags.append('Possible broken currency or mathematical formatting in source')
 return list(dict.fromkeys(flags))


def render_sections(st,record,heading=True):
 """Streamlit rendering without unsafe HTML or JSON dumps to screen."""
 if heading:st.subheader(readable(record.get('title')) or 'Untitled development')
 for field in ('description','what_it_means','operational_impact','commercial_implications','pc_assessment'):
  st.markdown('**'+FIELD_NAMES[field]+'**')
  if missing(record.get(field)):
   st.caption('Analysis pending — not established by supplied sources.')
  else:st.write(readable(record[field]))
 st.markdown('**Monitoring indicators**')
 indicators=entries(record.get('monitoring_indicators'))
 if indicators:
  for indicator in indicators:st.markdown('- '+indicator)
 else:st.caption('Monitoring indicators not yet supplied.')
 gaps=entries(record.get('research_gaps'))
 if gaps:
  with st.expander('Research gaps',expanded=False):
   for gap in gaps:st.markdown('- '+gap)
 src=sources(record.get('source_evidence') or record.get('research_sources'))
 if src:
  st.markdown('**Sources**')
  for index,source in enumerate(src,1):
   label=source['headline'] or source['publisher'] or 'Source '+str(index)
   st.markdown(f"{index}. [{label}]({source['url']})")
 else:st.caption('Source references pending.')
 flags=quality_flags(record)
 if flags:
  with st.expander(f'Editorial checks ({len(flags)})',expanded=False):
   for flag in flags:st.markdown('- '+flag)
 return flags
