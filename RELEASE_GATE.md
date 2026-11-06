# What must be verified before public release

This package preserves the tested V2 workflow, but **is not yet a certified production release**. Testing must be done against *your actual accounts*, not assumed from static inspection.

1. **Supabase Storage:** private bucket `customers`; max object >= 100MB; signed upload from browser; correct file metadata, names, and private admin download. Account/project quota and additional charges still apply. Audit bucket policies and periodically remove abandoned upload objects.
2. **Database:** `public.orders`, `public.submission_limits` schema as in existing V2; `service_role` required SQL privileges. Test insert/read/update/export; ensure no public read/write access to personal data.
3. **Runtime:** `PUBLIC_LAUNCH=0`, `HTTPS_ONLY=0` for local; never use `SECRET_KEY` default in production; confirm paid Render, HTTPS, domain, response times and safe request errors.
4. **Legal:** actual legal/trading name, service address, UK GDPR retention and notice, commercial and consumer rights, model ownership, risk, product safety and insurance. Privacy/terms are structured drafts and must be reviewed; `LEGAL_REVIEWED=1` is an operator assertion, not a legal audit.
5. **Payments and notifications:** quote approval, manual secure payment link and human verification of payment, manual customer messages; this version does **not** automatically collect payments or send emails.
6. **Ops:** backups including private files, restore test, retention/deletion job, 3D printing capacity, packaging and support workflow, quality records.
7. **Security tests:** rate limit, CSRF, invalid extension, empty file, oversized file, spam, admin session, vulnerable dependencies, mobile UX. Obtain independent review before processing untrusted customer files at scale.

**Release decision:** only switch DNS from V1 once you have a tested production deployment with all appropriate checks passed. No outcome here guarantees zero future changes: bug fixes, dependencies and security patches remain normal operational requirements.
