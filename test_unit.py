"""Unit + integration test for Bug Bounty Finder."""
import sys, types, os, asyncio

apify_stub = types.ModuleType('apify')
class _ActorLog:
    def info(self, m): print(f'[INFO ] {m}')
    def warning(self, m): print(f'[WARN ] {m}')
    def error(self, m): print(f'[ERROR] {m}')
    def debug(self, m): pass
class _Actor:
    log = _ActorLog()
apify_stub.Actor = _Actor()
sys.modules['apify'] = apify_stub

sys.path.insert(0, os.path.dirname(__file__))
from src.main import fetch_hackerone, fetch_bugcrowd, fetch_security_txt, parse_security_txt, parse_money, looks_like_domain, normalize_domain

import httpx


print('=' * 60)
print('TEST 1: parse_money')
print('=' * 60)
assert parse_money('$500') == 500
assert parse_money('$4,500') == 4500
assert parse_money('200 USD') == 200
assert parse_money(None) is None
assert parse_money('') is None
print('  ✓ OK')

print()
print('=' * 60)
print('TEST 2: looks_like_domain / normalize_domain')
print('=' * 60)
assert looks_like_domain('shopify.com')
assert not looks_like_domain('shopify')
assert not looks_like_domain('http://shopify.com')
assert normalize_domain('https://shopify.com/path') == 'shopify.com'
assert normalize_domain('Shopify.COM') == 'shopify.com'
print('  ✓ OK')

print()
print('=' * 60)
print('TEST 3: parse_security_txt')
print('=' * 60)
sample = '''Contact: mailto:security@shopify.com
Contact: https://www.shopify.com/security-response
Policy: https://hackerone.com/shopify
Encryption: https://www.shopify.com/shopify-security.pub
Hiring: https://www.shopify.com/careers
# this is a comment
'''
p = parse_security_txt(sample)
assert p['contact'] == ['mailto:security@shopify.com', 'https://www.shopify.com/security-response']
assert p['policy'] == ['https://hackerone.com/shopify']
assert p['encryption'] == ['https://www.shopify.com/shopify-security.pub']
print(f'  parsed: {p}')
print('  ✓ OK')

print()
print('=' * 60)
print('TEST 4: REAL fetch_hackerone for "shopify"')
print('=' * 60)
async def t4():
    async with httpx.AsyncClient(timeout=30) as c:
        return await fetch_hackerone(c, 'shopify', 10)
results = asyncio.run(t4())
print(f'  HackerOne returned {len(results)} programs')
assert len(results) >= 1, 'expected at least Shopify itself'
for r in results[:3]:
    print(f'    - {r["programName"]:30s} min=${r["minBounty"] or 0:>5}  reports={r["resolvedReports"]}  url={r["url"]}')
print('  ✓ HackerOne live fetch works')

print()
print('=' * 60)
print('TEST 5: REAL fetch_bugcrowd for "tesla"')
print('=' * 60)
async def t5():
    async with httpx.AsyncClient(timeout=30) as c:
        return await fetch_bugcrowd(c, 'tesla', 10)
results = asyncio.run(t5())
print(f'  Bugcrowd returned {len(results)} matched programs')
for r in results[:3]:
    print(f'    - {r["programName"]:30s} reward={r.get("rewardSummary")} access={r.get("accessStatus")}')
print('  ✓ Bugcrowd live fetch works (search-filtered)')

print()
print('=' * 60)
print('TEST 6: REAL fetch_security_txt for shopify.com')
print('=' * 60)
async def t6():
    async with httpx.AsyncClient(timeout=30) as c:
        return await fetch_security_txt(c, 'shopify.com')
res = asyncio.run(t6())
print(f'  shopify.com: {res is not None}')
if res:
    print(f'    contact: {res["contact"]}')
    print(f'    policy: {res["policy"]}')
    print(f'    encryption: {res["encryption"]}')
assert res is not None, 'expected security.txt on shopify.com'
assert 'security@shopify.com' in (res.get('contact') or '')
print('  ✓ security.txt live fetch works')

print()
print('=' * 60)
print('TEST 7: REAL fetch_security_txt for nonexistent domain')
print('=' * 60)
async def t7():
    async with httpx.AsyncClient(timeout=15) as c:
        return await fetch_security_txt(c, 'this-domain-truly-does-not-exist-12345.com')
res = asyncio.run(t7())
print(f'  result: {res}')
assert res is None, 'expected None for nonexistent domain'
print('  ✓ Gracefully returns None on miss')

print()
print('ALL TESTS PASS ✓')
