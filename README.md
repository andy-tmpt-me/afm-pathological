# afm-pathological

Web servers are unpredictable assholes, so I finally decided to build one that is predictably an asshole all the
time.

You already know that web servers are assholes if you've ever done any web crawling or scraping: they lie about
timestamps, have missing or outdated sitemaps, return empty responses, and so much more.

So over the holiday weekend I built a misbehaving web server that predictably exhibits all of the pathologies I've
seen over the years. Honestly I should have done this decades ago. It's live at https://pathological.answersfrom.me,
or you can build and host it yourself.

If you do anything with web crawling or scraping, feel free to give it a try. I hope it fails miserably for you!

## What it is

A web server with predictable bad behavior, for tests of crawlers, scrapers and HTTP clients. Each host of the
server behaves like one kind of difficult website, and each path of a page family is one case: redirect loops,
wrong content types, pages that change each day, sitemaps that lie, feeds with odd dates, slow and torn responses,
and more. The server keeps no state: each answer depends only on the request and its time. It uses only the Python
standard library.

## Quick start with Docker

```bash
make image
make run
curl -H 'Host: breadcrumbs.localhost' http://localhost:8080/
```

`http://localhost:8080/` is the landing page: it lists every host with a link. A browser resolves
`http://breadcrumbs.localhost:8080/` by itself, so you can open that URL with no DNS setup.
`make serve` runs the same server with no container.

## How a host is selected

The host is the first label of the `Host` header, after an optional `www.`: `breadcrumbs.localhost`,
`breadcrumbs.example.com` and `www.breadcrumbs.example.com` all select `breadcrumbs`. The request header
`X-Pathological-Host: breadcrumbs` replaces the `Host` header:

```bash
curl -H 'X-Pathological-Host: breadcrumbs' http://localhost:8080/
```

An `X-Pathological-Host` value that is not a host name answers 404 with the list of host names on every path.
With no such header, a `Host` that names no host (such as `localhost:8080` or the bare domain of the server) is the
site domain: `/` answers the landing page, `/README.md` the same as Markdown, `/clock` and `/robots.txt` answer, and
every other path answers 404 with the list of host names.

## The root page of each host

The root page `/` of each host is the README of that host. It lists every URL of the host with its behavior, and
`/README.md` gives the same text as Markdown. Start there when you look at a case.

Some cases in the URL table have tags. `own source`: the section page of the family does not link to the case, so
point a crawler at the URL itself. `local only`: the result depends on the second of the request or the case is slow,
so assert on it only with a fixed clock. `production only`: the result depends on the real network path, such as a
proxy or a rendering service between the client and the server, so a test in the same process cannot show it.

## How time works

Content that changes each day uses the day number: the number of days from 2026-01-01 to the UTC date of the
request. The request header `X-Pathological-Date: YYYY-MM-DD` replaces the date for one request. `/clock` returns
the UTC time, the date and the day number that the server uses, as JSON.

Behavior that needs state on a real website uses two 30-second slots: a request in seconds 0 to 29 of the minute is
in the error slot, and a request in seconds 30 to 59 is in the ok slot. A case that fails, then succeeds, answers
with an error in the first slot and with 200 in the second.

```bash
curl -H 'Host: breadcrumbs.localhost' http://localhost:8080/clock
curl -H 'Host: breadcrumbs.localhost' -H 'X-Pathological-Date: 2026-03-01' http://localhost:8080/daily/
```

## Hosts

| Host | Character | What the host root says |
| --- | --- | --- |
| `breadcrumbs` | You find its pages only by following links | `robots.txt` with no `Sitemap:` line. No feed, no `/sitemap.xml`, no `/wp-json` |
| `librarian` | Keeps an accurate catalog | `robots.txt` lists `/sitemap.xml`. Each `lastmod` is the true date of the last change. ETag and Last-Modified are true; a conditional GET answers 304 |
| `town-crier` | Announces everything in a feed | An RSS feed at `/feed`. `robots.txt` with no `Sitemap:` line |
| `mirage` | Promises a map that is not there | `robots.txt` lists `/sitemap.xml`, which answers 404 |
| `chicken-little` | Says that everything changed, each time | As `librarian`, but each `lastmod`, and the ETag and Last-Modified of each response, are the time of the request. The text of the 18 pages of its sitemap never changes |
| `rip-van-winkle` | Says that nothing changes | As `librarian`, but each `lastmod` is `2026-01-01`, also for new pages. The ETag and Last-Modified of each response never change and each conditional GET answers 304. Its sitemap lists 20 URLs: the 18, and `/chameleons/honest-edit` and `/chameleons/silent-edit`, whose text changes each day |
| `hoarder` | Has more pages than a crawler probably wants | `robots.txt` lists `/sitemap_index.xml`: five nested sitemaps of 100 constant articles each (`/hoard/1` to `/hoard/500`). The fifth also lists the seven daily pages, at its end: 507 URLs. The index has no dates |
| `squirrel` | Has a map and tells no one | `/sitemap.xml` exists with no `lastmod`. `/robots.txt` answers 404 |
| `headless-horseman` | Cannot answer a HEAD request | Each HEAD answers 405. GET is normal. An RSS feed at `/feed`. `robots.txt` with no `Sitemap:` line |
| `tipsy-cartographer` | Draws maps that are wrong | `robots.txt` lists five sitemaps: `/maps/good.xml` (the 18 URLs, with a PHP warning before `<?xml`), `/maps/missing.xml` (404), `/maps/feed.xml` (an RSS feed), `/maps/elsewhere.xml` (only URLs of `librarian` and `example.com`) and `/maps/malformed.xml` (XML that does not parse) |
| `gutenberg` | Is a WordPress site | `/wp-json/wp/v2/posts` answers with JSON. The root page has `<meta name="generator" content="WordPress 6.6">`. An RSS feed at `/feed` |
| `yes-man` | Answers 200 to everything | Each path returns the README as `text/html`, also `/robots.txt`, `/feed`, `/index.xml`, `/sitemap.xml` and `/wp-json/wp/v2/posts`, for GET and HEAD |
| `sloth` | Takes its time | `robots.txt`, with no `Sitemap:` line, answers after 15 s. Each HEAD answers after 12 s. Each other response answers after 2 s. A longer delay of a case stays: `/potholes/slow-get` answers a GET after 35 s |
| `whisperer` | Names its feed only in the head of its root page | No feed at the six root paths, no sitemap, `robots.txt` with no `Sitemap:` line. The README has `<link rel="alternate" type="application/rss+xml" href="/dispatches">`. `/dispatches` is an RSS feed |
| `masquerade` | Serves its root page as XML | `/index.xml` returns the README HTML as `application/xml`. `/feed` returns it as `text/html` |
| `janus` | One site with two names | Two hostnames, same content. `robots.txt` lists `/sitemap.xml`. Each of its 18 URLs has the apex name. After the apex entry of `/articles/starter` it lists that page two more times: with the `www.` name, and with the host in upper case |
| `forwarding-address` | Moved away | Each path except `/README.md` and `/clock`, also `/robots.txt`, answers 301 to the same path on `librarian` |
| `doorman` | Lets in only guests that it does not know | Each request with a Chrome 120 User-Agent (`Chrome/120.0.0.0`) answers 403, also `/robots.txt` and each HEAD. Each other request is normal. `robots.txt` has no `Sitemap:` line |

## Page families

Each host serves the same page families at the same paths, unless the table of hosts says otherwise.

| Family | Cases | Section page or first URL |
| --- | --- | --- |
| regulars | 7 | `/articles/` |
| chameleons | 16 | `/chameleons/` |
| tangle | 17 | `/tangle/` |
| doppelgangers | 7 | `/doppelgangers/` |
| detours | 5 | `/detours/` |
| speakeasy | 5 | `/speakeasy/` |
| potholes | 13 | `/potholes/` |
| bouncer | 4 | `/bouncer/` |
| holograms | 4 | `/holograms/` |
| labyrinth | 3 | `/labyrinth/calendar/` |
| attic | 9 | `/attic/` |
| feeds | 8 | `/feeds/atom.xml` |

## Demo site

A public instance runs at `https://pathological.answersfrom.me/`, a landing page that links to every host, and at
`https://<host>.pathological.answersfrom.me/`, for example `https://breadcrumbs.pathological.answersfrom.me/`.
It is best effort: it can be rate-limited or capped at any time. Every response has
`X-Robots-Tag: noindex, nofollow`.

## Configuration

| Variable | Meaning | Default |
| --- | --- | --- |
| `PORT` | The port that the server listens on | `8080` |
| `PATHOLOGICAL_OPERATOR` | Who runs the site, named in each host README | `Answers From Me` |

An operator sets `PATHOLOGICAL_OPERATOR` to their own name; an empty value shows no name.

`make run` passes `PATHOLOGICAL_OPERATOR` from your shell to the container:

```bash
PATHOLOGICAL_OPERATOR='Example Corp' make run
```

## Run it on your own infrastructure

The container listens on `$PORT`, 8080 by default. It keeps no state, so you can run any number of copies. Point one
wildcard DNS name (for example `*.pathological.example.com`) or several names at it. Some cases answer 5xx on
purpose and some wait up to 35 seconds before they answer, so set your monitoring, alerts and timeouts with that in
mind.

## Development

The server and its tests need Python 3.12 or later.

```bash
make install
make test
make lint
```

## Licence

MIT. See [LICENSE](LICENSE).
