"""Native streaming reader for OFAC ENHANCED_XML. No AI or lossy row caps."""
from __future__ import annotations
import hashlib
import io
import json
import re
import uuid
from collections import Counter
from datetime import datetime
from xml.etree.ElementTree import iterparse
import xml.etree.ElementTree as ET

NS = 'https://sanctionslistservice.ofac.treas.gov/api/PublicationPreview/exports/ENHANCED_XML'
SOURCE_URL = 'https://sanctionslist.ofac.treas.gov/Home/SdnList'
PARSER_VERSION = 'ofac_enhanced_v1'

def stable_id(kind, *parts):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, 'https://ofac.treasury.gov/sdn/' + kind + '/' + '/'.join(map(str, parts))))

def norm(value):
    return ' '.join(str(value or '').casefold().split())

def text(el, path):
    found = el.find('/'.join('{'+NS+'}'+p for p in path.split('/')))
    return (found.text or '').strip() if found is not None else None

def children(el, path):
    return el.findall('/'.join('{'+NS+'}'+p for p in path.split('/')))

def raw_tree(el):
    """Lossless element data, including all attributes, children and reference IDs."""
    return {'tag': el.tag.rsplit('}', 1)[-1], 'attributes': dict(el.attrib),
            'text': (el.text or '').strip(), 'children': [raw_tree(c) for c in el]}

def feature_value(el, references):
    value = text(el, 'value')
    if value:
        return value
    ref = text(el, 'valueRefId')
    return references.get(ref, {}).get('value') if ref else None

def parse_entity(el, references):
    external_id = el.get('id')
    if not external_id:
        raise ValueError('OFAC entity missing its source ID')
    names = []
    for name in children(el, 'names/name'):
        for translation in children(name, 'translations/translation'):
            full = text(translation, 'formattedFullName')
            if not full:
                full = ' '.join(text(p, 'value') or '' for p in children(translation, 'nameParts/namePart')).strip()
            if full:
                names.append({'name_id': name.get('id'), 'translation_id': translation.get('id'),
                    'name': full, 'is_primary_name': text(name, 'isPrimary') == 'true',
                    'is_primary_translation': text(translation, 'isPrimary') == 'true',
                    'is_low_quality': text(name, 'isLowQuality') == 'true',
                    'alias_type': text(name, 'aliasType'), 'script': text(translation, 'script'),
                    'raw': raw_tree(name)})
    primary = [n for n in names if n['is_primary_name']]
    if not primary:
        raise ValueError(f'OFAC {external_id} missing primary name')
    primary.sort(key=lambda n: (n['script'] != 'Latin', not n['is_primary_translation']))
    features = [{'feature_id': f.get('id'), 'type': text(f, 'type'),
                 'value': feature_value(f, references), 'raw': raw_tree(f)}
                for f in children(el, 'features/feature')]
    identifiers = []
    for d in children(el, 'identityDocuments/identityDocument'):
        typ = text(d, 'type'); val = text(d, 'documentNumber')
        if val:
            identifiers.append({'document_id': d.get('id'), 'type': typ, 'value': val,
                'country': text(d, 'issuingCountry'), 'issuing_authority': text(d, 'issuingAuthority'),
                'is_valid': text(d, 'isValid') == 'true', 'raw': raw_tree(d)})
    imos = set()
    for ident in identifiers:
        if ident['type'] == 'Vessel Registration Identification' and ident['is_valid']:
            match = re.fullmatch(r'(?:IMO\s*)?(\d{7})', ident['value'], re.I)
            if match:
                from pc_document_vessels import valid_imo
                if valid_imo(match.group(1)):
                    imos.add(match.group(1))
    addresses = []
    for a in children(el, 'addresses/address'):
        for tr in children(a, 'translations/translation') or [None]:
            parts = [{'type': text(p, 'type'), 'value': text(p, 'value')} for p in (children(tr, 'addressParts/addressPart') if tr is not None else [])]
            addresses.append({'address_id': a.get('id'), 'translation_id': tr.get('id') if tr is not None else None,
                'country': text(a, 'country'), 'script': text(tr, 'script') if tr is not None else None, 'parts': parts, 'raw': raw_tree(a)})
    relationships = []
    for rel in children(el, 'relationships/relationship'):
        target = rel.find('{'+NS+'}relatedEntity')
        if target is None or not target.get('entityId'):
            raise ValueError(f'OFAC {external_id} has a relationship without a source endpoint')
        relationships.append({'relationship_id': rel.get('id'), 'type': text(rel, 'type'),
            'related_entity_id': target.get('entityId'), 'related_entity_name': (target.text or '').strip(),
            'raw': raw_tree(rel)})
    lists = [{'name': (x.text or '').strip(), 'source_list_id': x.get('refId'),
              'record_id': x.get('id'), 'date_published': x.get('datePublished')} for x in children(el, 'sanctionsLists/sanctionsList')]
    dates = [x['date_published'] for x in lists if x['name'] == 'SDN List' and x['date_published']]
    return {'external_id': external_id, 'identity_id': text(el, 'generalInfo/identityId'),
        'entity_type': text(el, 'generalInfo/entityType'), 'primary_name': primary[0]['name'],
        'names': names, 'features': features, 'identifiers': identifiers, 'addresses': addresses,
        'relationships': relationships, 'sanctions_lists': lists,
        'programmes': [{'code': (p.text or '').strip(), 'ref_id': p.get('refId')} for p in children(el, 'sanctionsPrograms/sanctionsProgram')],
        'sanctions_types': [(p.text or '').strip() for p in children(el, 'sanctionsTypes/sanctionsType')],
        'legal_authorities': [(p.text or '').strip() for p in children(el, 'legalAuthorities/legalAuthority')],
        'designation_date': min(dates) if dates else None,
        'imo': next(iter(imos)) if len(imos) == 1 else None,
        'imo_resolution': 'unique_valid_imo' if len(imos)==1 else 'multiple_imos' if imos else 'no_valid_imo',
        'raw_record': raw_tree(el)}


def records(stream, metadata=None):
    """Stream without retaining the 105 MB source tree. Metadata receives its dictionaries."""
    metadata = metadata if metadata is not None else {}
    refs = {}; feature_types = []; container = None; first = True
    class NoDTD:
        def __init__(self, source): self.source = source; self.tail = b''
        def read(self, size=-1):
            data = self.source.read(size)
            probe = self.tail + data
            if b'<!DOCTYPE' in probe.upper() or b'<!ENTITY' in probe.upper() or b'\x00' in probe:
                raise ValueError('DTD/entity declarations and non-UTF-8 XML are not supported')
            self.tail = probe[-32:]
            return data
    for event, el in iterparse(NoDTD(stream), events=('start', 'end')):
        tag = el.tag.rsplit('}', 1)[-1]
        if first:
            first = False
            if el.tag != '{'+NS+'}sanctionsData':
                raise ValueError('Expected the OFAC ENHANCED_XML sanctionsData namespace')
        if event == 'start' and tag == 'entities':
            container = el
        if event != 'end':
            continue
        if tag == 'publicationInfo':
            metadata['data_as_of'] = text(el, 'dataAsOf')
            if not metadata['data_as_of']:
                raise ValueError('Missing OFAC dataAsOf')
            datetime.fromisoformat(metadata['data_as_of'])
            metadata['publication_info'] = raw_tree(el)
            source_lists = [x.text for x in el.iter('{'+NS+'}sanctionsList')]
            if source_lists != ['SDN List']:
                raise ValueError('Only a full SDN List export is supported by this importer')
        elif tag == 'referenceValue':
            refs[el.get('refId')] = {'type': text(el, 'type'), 'value': text(el, 'value'), 'raw': raw_tree(el)}
            el.clear()
        elif tag == 'featureType':
            feature_types.append(raw_tree(el)); el.clear()
        elif tag == 'entity':
            record = parse_entity(el, refs)
            yield record
            el.clear()
            if container is not None:
                container.clear()
    metadata['references'] = refs
    metadata['feature_types'] = feature_types
    metadata['parser_version'] = PARSER_VERSION


def inspect_xml(stream):
    metadata = {}; counts = Counter(); ids = set(); targets = set()
    for record in records(stream, metadata):
        if record['external_id'] in ids:
            raise ValueError('Duplicate OFAC entity ID: ' + record['external_id'])
        ids.add(record['external_id']); counts['records'] += 1; counts[record['entity_type']] += 1
        for key in ('names', 'identifiers', 'addresses', 'features', 'relationships', 'programmes', 'sanctions_types', 'legal_authorities'):
            counts[key] += len(record[key])
        if record['entity_type'] == 'Vessel':
            counts[record['imo_resolution']] += 1
        targets.update(r['related_entity_id'] for r in record['relationships'])
    if not ids:
        raise ValueError('Empty OFAC export')
    missing = targets - ids
    metadata['external_relationship_targets'] = sorted(missing)
    counts['external_relationship_targets'] = len(missing)
    metadata['counts'] = dict(counts)
    return metadata
