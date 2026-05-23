# Bug Bounty Finder

📦 **Open source · MIT:** [github.com/AnshumanAtrey/bug-bounty-finder](https://github.com/AnshumanAtrey/bug-bounty-finder)


Find every public bug bounty / responsible disclosure program for a company or domain. Pulls in real time from:

- **HackerOne** — public directory of 1000+ programs
- **Bugcrowd** — public engagements API
- **security.txt** — RFC 9116 standard at `/.well-known/security.txt`

Built for bug bounty hunters, pen testers, and security researchers who need to know "does this target have a program I can report to?" — fast.

## Quick start

```json
{
  "query": "shopify"
}
```

Returns 5+ records: matching HackerOne program (with min bounty + resolved-report count), Bugcrowd match if any, and the parsed `security.txt` from `shopify.com`.

## Output structure

Each record has a `recordType` discriminator:

| recordType | Fields | When |
|---|---|---|
| `program` | `platform`, `programName`, `url`, `minBounty`, `maxBounty`, `currency`, `offersBounties`, `resolvedReports`, `policySnippet`, `engagementType`, `industry` | One per matched program (HackerOne or Bugcrowd) |
| `securityTxt` | `domain`, `contact`, `policy`, `encryption`, `hiring`, `acknowledgments`, `canonical`, `expires`, `raw` (first 2KB) | Per domain where security.txt was found |
| `summary` | `programsFound`, `securityTxtFound`, `programsByPlatform`, `duration` | Always last record |

Filter by `recordType=program` in the Apify Console table view to see only paid bounty programs.

## Example with extras

```json
{
  "query": "github",
  "sources": ["hackerone", "bugcrowd", "security_txt"],
  "additionalDomains": ["github.com", "github.io", "githubusercontent.com"],
  "limit": 50
}
```

This searches HackerOne + Bugcrowd for "github" AND fetches security.txt from all three github-owned domains.

## Pricing

$0.005 per record. A typical scan returns 3-10 records = $0.015-$0.050 per query. Cheaper than the gas it took to drive to HackerOne in your head.

## Use cases

- **Bug bounty hunters** — quickly check if a new target has a program before spending hours hunting
- **Pen testers** — find responsible disclosure contacts when finding accidental vulns during engagements
- **Security teams** — audit your own brand's program presence across platforms
- **Researchers** — investigate disclosure norms across industries

## Notes

- HackerOne returns up to 6 results per query (their pagination limit)
- Bugcrowd search is fuzzy — we filter client-side to only return matches containing the query
- security.txt is tried at both `/.well-known/security.txt` and `/security.txt` per RFC 9116
- No API keys required for any source

## FAQ

### Why does HackerOne return at most 6 results per query?
That's HackerOne's own search pagination limit on the public directory — not a limitation we add. To get more, refine your query (e.g., `shopify` vs `shop`), or split the query into multiple searches with different keywords.

### Is the `security.txt` data trustworthy?
Yes — it's served by the target organization itself per RFC 9116. The actor parses but does not validate the contents (e.g., we don't verify the `Contact:` email is monitored). Treat security.txt as the company's official position.

### Can I monitor a brand for new programs over time?
Yes — schedule this actor to run weekly via Apify Schedules, send the dataset to a webhook, and diff the records. New programs appearing means new disclosure surface.

### What about private / invite-only programs?
This actor only queries public directories. Private programs (Synack, invite-only HackerOne, internal disclosure) are by definition not discoverable from outside — those require an existing invitation.

### Can I filter results by bounty range?
Yes — once data lands in the dataset, filter by `minBounty` / `maxBounty` in the Apify Console table view, or query the dataset via the API with a filter expression.

## Pairs nicely with

Bundle for full bounty-hunting recon:

- **[theHarvester](https://apify.com/anshumanatrey/theharvester-osint)** — Discover subdomains, then check each for bounty program coverage
- **[nmap](https://apify.com/anshumanatrey/nmap-scanner)** — Find open services on in-scope targets
- **[NetIntel](https://apify.com/anshumanatrey/netintel)** — Enrich each program's domain with WHOIS, DNS, SSL, GeoIP intel
- **[Holehe Email OSINT](https://apify.com/anshumanatrey/holehe-email-osint)** — Confirm the security contact email is real and check what platforms it's registered on
- **[Social Analyzer](https://apify.com/anshumanatrey/social-analyzer)** — Find a target company's security-team usernames across platforms
- **[Zomato Restaurant Scraper](https://apify.com/anshumanatrey/zomato-restaurant-scraper)** — Restaurant lead lists (separate B2B use case)

## Credits

Public data from [HackerOne](https://hackerone.com), [Bugcrowd](https://bugcrowd.com), and target operators' own [security.txt](https://securitytxt.org) files.
