"""Explicit, bounded Cloudflare DoH for public-image hosts only.

The fixed numeric HTTPS endpoint avoids the system resolver's FakeIP answers.
Its certificate is verified normally. This never falls back from unsafe system
DNS and never accepts a caller-supplied resolver endpoint or account hostname.
"""
import ipaddress
import json
import re
import socket

import httpx


_ENDPOINT = 'https://1.1.1.1/dns-query'
_MAX_RESPONSE_BYTES = 16384
_MAX_RECORDS = 32


def _name(value):
    if not isinstance(value, str) or not 1 <= len(value) <= 254 or not value.isascii():
        raise ValueError('qq_asset_dns_invalid')
    normalized = value[:-1] if value.endswith('.') else value
    if not normalized or any(not re.fullmatch(r'[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?',
                                             label) for label in normalized.split('.')):
        raise ValueError('qq_asset_dns_invalid')
    return normalized.lower()


def _addresses(raw, hostname):
    try:
        data = json.loads(raw)
    except (ValueError, RecursionError) as error:
        raise ValueError('qq_asset_dns_invalid') from error
    if (not isinstance(data, dict) or type(data.get('Status')) is not int or data['Status'] != 0
            or data.get('TC') is not False or data.get('CD') is not False):
        raise ValueError('qq_asset_dns_invalid')
    questions, answers = data.get('Question'), data.get('Answer')
    if (not isinstance(questions, list) or len(questions) != 1 or not isinstance(questions[0], dict)
            or type(questions[0].get('type')) is not int or questions[0]['type'] != 1
            or _name(questions[0].get('name')) != hostname or not isinstance(answers, list)
            or not 1 <= len(answers) <= _MAX_RECORDS):
        raise ValueError('qq_asset_dns_invalid')
    aliases, records = {}, []
    for row in answers:
        if (not isinstance(row, dict) or type(row.get('type')) is not int or row['type'] not in (1, 5)
                or type(row.get('TTL')) is not int or not 0 <= row['TTL'] <= 4294967295):
            raise ValueError('qq_asset_dns_invalid')
        owner = _name(row.get('name'))
        if row['type'] == 5:
            target = _name(row.get('data'))
            if owner in aliases and aliases[owner] != target:
                raise ValueError('qq_asset_dns_invalid')
            aliases[owner] = target
            continue
        address = row.get('data')
        if not isinstance(address, str):
            raise ValueError('qq_asset_dns_invalid')
        try:
            ip = ipaddress.IPv4Address(address)
        except ipaddress.AddressValueError as error:
            raise ValueError('qq_asset_dns_invalid') from error
        if not ip.is_global or ip.is_multicast or ip.is_reserved:
            raise ValueError('qq_asset_dns_private')
        records.append((owner, str(ip)))
    final, visited = hostname, set()
    while final in aliases:
        if final in visited:
            raise ValueError('qq_asset_dns_invalid')
        visited.add(final)
        final = aliases[final]
    if (not records or any(owner != final for owner, _ in records)
            or any(owner not in visited for owner in aliases)):
        raise ValueError('qq_asset_dns_invalid')
    return [(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, '', (address, 443))
            for address in dict.fromkeys(address for _, address in records)]


async def cloudflare_addresses(hostname, *, allowed_hosts):
    if hostname not in allowed_hosts:
        raise ValueError('qq_asset_dns_invalid')
    # The caller's single deadline includes this request, CDN TLS and image body.
    # Numeric bootstrap has a normally verified IP certificate; proxies, cookies,
    # redirects, caller headers and compressed responses are never used.
    try:
        async with httpx.AsyncClient(trust_env=False, follow_redirects=False, timeout=5) as client:
            async with client.stream('GET', _ENDPOINT, params={'name': hostname, 'type': 'A'},
                    headers={'Accept': 'application/dns-json', 'Accept-Encoding': 'identity'}) as response:
                if (response.status_code != 200
                        or response.headers.get('content-type', '').split(';')[0].strip().lower() != 'application/dns-json'
                        or response.headers.get('content-encoding', 'identity').lower() not in ('', 'identity')):
                    raise ValueError('qq_asset_dns_invalid')
                length = response.headers.get('content-length')
                if length is not None and (not re.fullmatch(r'[0-9]{1,5}', length)
                                           or not 0 < int(length) <= _MAX_RESPONSE_BYTES):
                    raise ValueError('qq_asset_dns_invalid')
                body = bytearray()
                async for chunk in response.aiter_raw():
                    if len(body) + len(chunk) > _MAX_RESPONSE_BYTES:
                        raise ValueError('qq_asset_dns_invalid')
                    body.extend(chunk)
    except httpx.HTTPError as error:
        raise ValueError('qq_asset_dns_unavailable') from error
    return _addresses(body, hostname)
