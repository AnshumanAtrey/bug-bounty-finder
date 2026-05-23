"""
Bug Bounty Finder — finds public bug bounty / VDP programs for a given company or domain.

Sources:
- HackerOne directory:   https://hackerone.com/programs/search.json?query=X
- Bugcrowd engagements:  https://bugcrowd.com/engagements.json?search=X
- target/.well-known/security.txt
"""
import asyncio
import re
from datetime import datetime, timezone
from urllib.parse import urlparse

import httpx
from apify import Actor


UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36'
H1_URL = 'https://hackerone.com/programs/search.json'
BC_URL = 'https://bugcrowd.com/engagements.json'


def looks_like_domain(s: str) -> bool:
    return '.' in s and ' ' not in s and not s.startswith('http')


def normalize_domain(s: str) -> str:
    s = s.strip().lower()
    if s.startswith(('http://', 'https://')):
        s = urlparse(s).netloc
    return s.split('/')[0]


def parse_money(s: str) -> int | None:
    """Extract a number from strings like '$200', '$4,500', '500 USD'."""
    if not s:
        return None
    m = re.search(r'([\d,]+)', s.replace(' ', ''))
    if not m:
        return None
    try:
        return int(m.group(1).replace(',', ''))
    except ValueError:
        return None


async def fetch_hackerone(client: httpx.AsyncClient, query: str, limit: int) -> list:
    """Returns list of normalized program records."""
    try:
        r = await client.get(H1_URL, params={'query': query}, headers={'User-Agent': UA})
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        Actor.log.warning(f'HackerOne fetch failed: {e}')
        return []

    out = []
    for p in (data.get('results') or [])[:limit]:
        meta = p.get('meta') or {}
        out.append({
            'platform': 'HackerOne',
            'programName': p.get('name'),
            'url': f'https://hackerone.com{p.get("url","")}',
            'handle': p.get('handle'),
            'minBounty': meta.get('minimum_bounty'),
            'maxBounty': None,  # HackerOne JSON doesn't include max here
            'currency': (meta.get('default_currency') or '').upper() or None,
            'offersBounties': meta.get('offers_bounties'),
            'resolvedReports': meta.get('resolved_report_count'),
            'submissionState': meta.get('submission_state'),
            'about': (p.get('about') or '')[:500],
            'policySnippet': (p.get('stripped_policy') or '')[:500],
            'internetBugBounty': p.get('internet_bug_bounty'),
            'teamType': p.get('team_type'),
        })
    return out


async def fetch_bugcrowd(client: httpx.AsyncClient, query: str, limit: int) -> list:
    """Returns list of normalized program records."""
    try:
        r = await client.get(BC_URL, params={'search': query}, headers={'User-Agent': UA})
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        Actor.log.warning(f'Bugcrowd fetch failed: {e}')
        return []

    out = []
    q_lower = query.lower()
    for e in (data.get('engagements') or [])[:limit]:
        name = e.get('name') or ''
        # Bugcrowd search returns featured programs even with no match — filter client-side
        if q_lower and q_lower not in name.lower() and q_lower not in (e.get('tagline') or '').lower():
            continue
        rw = e.get('rewardSummary') or {}
        et = e.get('productEngagementType') or {}
        out.append({
            'platform': 'Bugcrowd',
            'programName': name,
            'url': f'https://bugcrowd.com{e.get("briefUrl","")}',
            'handle': (e.get('briefUrl') or '').strip('/').split('/')[-1] or None,
            'minBounty': parse_money(rw.get('minReward')),
            'maxBounty': parse_money(rw.get('maxReward')),
            'currency': 'USD' if (rw.get('minReward') or '').startswith('$') else None,
            'offersBounties': bool(rw.get('minReward')),
            'rewardSummary': rw.get('summary'),
            'engagementType': et.get('label'),
            'industry': e.get('industryName'),
            'accessStatus': e.get('accessStatus'),
            'serviceLevel': e.get('serviceLevel'),
            'tagline': (e.get('tagline') or '')[:500],
        })
    return out


def parse_security_txt(raw: str) -> dict:
    """Parse RFC 9116 security.txt into structured fields."""
    out = {'contact': [], 'policy': [], 'encryption': [], 'hiring': [], 'acknowledgments': [], 'preferred_languages': None, 'canonical': [], 'expires': None}
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        if ':' not in line:
            continue
        k, v = line.split(':', 1)
        key = k.strip().lower().replace('-', '_')
        val = v.strip()
        if key in out and isinstance(out[key], list):
            out[key].append(val)
        elif key in out:
            out[key] = val
    return out


async def fetch_security_txt(client: httpx.AsyncClient, domain: str) -> dict | None:
    """Try www.domain and domain, at /.well-known/security.txt then /security.txt.
    Some apex domains (Shopify, Tesla) return 403 via Cloudflare; www subdomain often works."""
    # Build host candidates — try www first if domain doesn't already have it
    hosts = []
    if not domain.startswith('www.'):
        hosts.append(f'www.{domain}')
    hosts.append(domain)

    for host in hosts:
        for path in ['/.well-known/security.txt', '/security.txt']:
            url = f'https://{host}{path}'
            try:
                r = await client.get(url, headers={'User-Agent': UA}, follow_redirects=True)
                if r.status_code == 200 and r.text.strip() and 'Contact:' in r.text:
                    parsed = parse_security_txt(r.text)
                    return {
                        'domain': domain,
                        'sourceUrl': str(r.url),
                        'raw': r.text[:2000],
                        'contact': '; '.join(parsed['contact']) or None,
                        'policy': '; '.join(parsed['policy']) or None,
                        'encryption': '; '.join(parsed['encryption']) or None,
                        'hiring': '; '.join(parsed['hiring']) or None,
                        'acknowledgments': '; '.join(parsed['acknowledgments']) or None,
                        'canonical': '; '.join(parsed['canonical']) or None,
                        'expires': parsed.get('expires'),
                        'preferredLanguages': parsed.get('preferred_languages'),
                    }
            except Exception as e:
                Actor.log.debug(f'security.txt for {host}{path} failed: {e}')
                continue
    return None


async def main() -> None:
    async with Actor:
        Actor.log.info('Bug Bounty Finder starting')

        input_data = await Actor.get_input() or {}
        query = (input_data.get('query') or '').strip()
        if not query:
            await Actor.fail(status_message='query (company name or domain) is required')
            return

        sources = input_data.get('sources') or ['hackerone', 'bugcrowd', 'security_txt']
        limit = int(input_data.get('limit', 25))
        timeout = int(input_data.get('timeout', 30))
        additional_domains = input_data.get('additionalDomains') or []
        timestamp = datetime.now(timezone.utc).isoformat()
        start_wall = datetime.now(timezone.utc)

        Actor.log.info(f'Query: {query}')
        Actor.log.info(f'Sources: {sources}')

        # Build the set of domains to fetch security.txt from
        sec_txt_domains = set()
        if 'security_txt' in sources:
            if looks_like_domain(query):
                sec_txt_domains.add(normalize_domain(query))
            for d in additional_domains:
                sec_txt_domains.add(normalize_domain(d))

        # Search queries: include both the raw query AND the brand root if the query is a domain
        # (e.g., "shopify.com" -> also search "shopify" since HackerOne program is named "Shopify")
        search_terms = [query]
        if looks_like_domain(query):
            brand = normalize_domain(query).split('.')[0]
            if brand and brand != query.lower():
                search_terms.append(brand)
                Actor.log.info(f'Domain query — also searching brand root: "{brand}"')

        async with httpx.AsyncClient(timeout=timeout) as client:
            tasks = []
            for term in search_terms:
                if 'hackerone' in sources:
                    tasks.append(('hackerone', fetch_hackerone(client, term, limit)))
                if 'bugcrowd' in sources:
                    tasks.append(('bugcrowd', fetch_bugcrowd(client, term, limit)))
            for d in sec_txt_domains:
                tasks.append(('security_txt', fetch_security_txt(client, d)))

            results = await asyncio.gather(*[t[1] for t in tasks], return_exceptions=True)

        programs = []
        sec_txt_records = []
        seen_program_urls = set()
        for (name, _), res in zip(tasks, results):
            if isinstance(res, Exception):
                Actor.log.warning(f'{name} task failed: {res}')
                continue
            if name in ('hackerone', 'bugcrowd'):
                if isinstance(res, list):
                    for p in res:
                        if p['url'] not in seen_program_urls:
                            seen_program_urls.add(p['url'])
                            programs.append(p)
            elif name == 'security_txt' and res:
                sec_txt_records.append(res)

        # Push program records
        for p in programs:
            await Actor.push_data({
                'recordType': 'program',
                'query': query,
                'timestamp': timestamp,
                **p,
            })

        # Push security.txt records
        for s in sec_txt_records:
            await Actor.push_data({
                'recordType': 'securityTxt',
                'query': query,
                'timestamp': timestamp,
                **s,
            })

        wall_duration = (datetime.now(timezone.utc) - start_wall).total_seconds()

        await Actor.push_data({
            'recordType': 'summary',
            'query': query,
            'sources': sources,
            'programsFound': len(programs),
            'securityTxtFound': len(sec_txt_records),
            'programsByPlatform': {
                'HackerOne':  sum(1 for p in programs if p['platform'] == 'HackerOne'),
                'Bugcrowd':   sum(1 for p in programs if p['platform'] == 'Bugcrowd'),
            },
            'duration': round(wall_duration, 2),
            'success': True,
            'timestamp': timestamp,
        })

        Actor.log.info(f'Done: {len(programs)} programs + {len(sec_txt_records)} security.txt records in {wall_duration:.1f}s')


if __name__ == '__main__':
    asyncio.run(main())
