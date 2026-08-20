# Security analysis

Assessment date: 21 August 2026

## Scope and method

This review covered the Node.js server, browser client, SQLite persistence,
Terraform configuration, deployment and benchmark scripts, dependencies,
tracked/untracked publish candidates, and repository ignore rules. Checks
included manual trust-boundary review, credential-pattern scanning, inspection
of dynamic HTML and filesystem access, `npm audit`, syntax validation, and the
local regression suite.

## Executive summary

No credentials were found in the proposed repository content. Provider keys
remain server-side, local secret files and generated state are ignored, npm
reports no known vulnerabilities, and all tests pass. The application is
appropriate for its documented single-user, localhost-only mode.

It must not be exposed directly to an untrusted network. There is currently no
application authentication or authorization layer, and saved conversations and
attachments are plaintext in the local SQLite database. Those are acceptable
constraints for localhost development, but deployment blockers for shared or
internet-facing operation.

## Findings

### Medium: no application authentication outside localhost

The default `HOST=127.0.0.1` prevents remote access, which is the primary
control. If an operator changes `HOST` to `0.0.0.0` or places the service behind
a public proxy without authentication, any reachable client could invoke the
paid inference API and read, modify, or delete saved chats.

Recommended action before shared deployment:

- put the service behind TLS and an identity-aware proxy;
- require an authenticated session on every `/api/*` route;
- add per-user authorization for chat IDs;
- enforce request and concurrency rate limits; and
- reject untrusted forwarding headers unless they come from a known proxy.

### Medium: chat and attachment data is plaintext at rest

SQLite stores prompts, responses, metrics, image data URLs, and uploaded
documents. Any process or user able to read the database file can recover that
content. Ignoring the database in Git prevents accidental publication but does
not provide encryption.

Recommended action for sensitive use:

- place the database on an encrypted volume with restrictive filesystem
  permissions;
- add retention and deletion controls;
- avoid storing raw attachments when history is unnecessary; and
- use per-user encrypted storage if the application becomes multi-user.

### Low: document parsing consumes the main Node.js process

PDF processing is bounded to two files, 8 MB per PDF, 100 pages, and 50,000
extracted characters. A deliberately complex compressed PDF could still consume
significant CPU and delay other requests because parsing occurs in-process.

Recommended action for a hosted service: move document extraction to a worker
with CPU, memory, and wall-clock limits; reject encrypted or malformed files;
and consider malware scanning before persistence.

### Low: upstream error details are returned to the browser

The server truncates upstream errors to 1,000 characters and does not include
authorization headers, but provider diagnostics may expose implementation
details. Return stable public error codes in production and keep detailed
provider errors only in access-controlled logs.

## Controls verified

- Verda and Tavily credentials are read only by the server and are not returned
  from `/api/config` or embedded in static assets.
- `.env`, `scripts/env.sh`, Terraform state/plans, SQLite files, caches, and
  crash artifacts are excluded from Git.
- The secret scan found no API keys, access tokens, or private-key blocks in the
  proposed publish set.
- SQLite operations use parameterized statements.
- Chat identifiers, titles, generation settings, history size, request bodies,
  images, and documents have explicit validation or bounds.
- PDF.js `6.2.108` is installed; `npm audit --omit=dev` reports zero known
  vulnerabilities.
- PDF JavaScript evaluation and workers are disabled during extraction.
- Attached documents and Tavily excerpts are labelled untrusted and cannot
  override the server-controlled system instruction.
- Model Markdown is sanitized with DOMPurify before insertion. User-controlled
  filenames, titles, URLs, and error text are HTML-escaped.
- Static-file access is rooted under `public/` and traversal attempts are
  rejected.
- The service binds to `127.0.0.1` by default and sends CSP, anti-framing,
  MIME-sniffing, referrer, opener, and browser permissions headers.
- Streaming requests are cancelled when the browser disconnects.

## Pre-publication result

No high or critical code vulnerability was identified in the documented local
deployment model. Publication is safe provided ignored secrets and generated
local data remain excluded. Internet or multi-user deployment requires the
authentication, authorization, rate-limiting, TLS, and encrypted-storage work
described above.
