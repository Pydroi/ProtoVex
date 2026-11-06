# ProtoVex – Public release candidate (local test package)

**Built from your actual V2 interactive-gearbox design and the Supabase-backed app you uploaded.** This is a self-contained website folder for local testing. It is **not verified as safe to publish** until the outstanding launch gates below are completed and an end-to-end test has passed against your own accounts.

## 1) Local test on Windows

1. Extract `ProtoVex_Public_Release_Candidate.zip` into a **new folder** (keep your live V1 and working V2 copies unchanged).
2. Copy your **existing, private** `.env` file from `ProtoVex_V2_milestone1` into the *new* folder. Do not upload it here, to GitHub, or put secrets in chat.
3. Open the new folder in File Explorer, click its address bar, type `cmd`, press Enter.
4. Copy and paste these **one at a time**:
   ```cmd
   py -m venv .venv
   .venv\Scripts\activate.bat
   python -m pip install -r requirements.txt
   python app.py
   ```
5. Open **http://127.0.0.1:5000**. For admin, go to **http://127.0.0.1:5000/admin/login** and sign in using your existing `ADMIN_PASSWORD`.

If your `.env` is missing values, copy `.env.example` to `.env` and fill in your existing private credentials. **Never use the example Supabase URL or secret key.** For local HTTP testing, keep `HTTPS_ONLY=0` and `PUBLIC_LAUNCH=0`.

## 2) What to test locally

- Homepage, mobile layout, interactive 3D gearbox, links and policies.
- Submit a **small non-sensitive** STL, and confirm receipt, order record and private Storage object.
- Submit files larger than 20 MB, then try a file up to 100 MB using the **JavaScript direct upload**, confirm the progress bar and stored metadata. Use dummy data; tests create real rows in your Supabase project.
- Sign into `/admin`, check the order, download the STL, update a quote/status and export CSV. Admin downloads use a 60-second signed URL.
- Test wrong file extensions, an oversized upload, empty required fields, rate limits and admin access without logging in.
- Do not send real customer data or real payment links during testing.

**Important:** You must configure your private Supabase `customers` bucket to accept at least **100 MB** individual files and allow supported content types. Raising the plan does not by itself change the bucket size limit. Signed uploads are sent directly from the browser to Supabase. The non-JavaScript fallback remains limited to 20 MB.

## 3) What this package includes

- `app.py` – Flask and Supabase (orders, admin, direct signed uploads).
- `templates/` and `static/` – full V2 frontend, including original Three.js interactive gearbox.
- `render.yaml` – Starter service blueprint. Only apply after tests and checks.
- `.env.example`, `.gitignore`, `requirements.txt` – configuration without live credentials.
- `tests/` – automated test script, mocking the Supabase API for basic route checks.
- `docs/` – previous customer email templates, operating process, launch checklist.

## 4) Public launch gates – still mandatory

**You cannot establish a reliable public release by modifying the code alone.** Before redirecting `protovex.co.uk` or setting `PUBLIC_LAUNCH=1`:

- Confirm a real UK business identity, contact/address, privacy notice, cancellation/returns rules, risk and insurance requirements; obtain appropriate review. Set `LEGAL_NAME`, `BUSINESS_ADDRESS`, `PRIVACY_RETENTION`, `LEGAL_REVIEWED=1` only once the wording is accurate and checked.
- Check Supabase private bucket visibility, storage size/allowed MIME types, service-role permissions, storage/database backups and retention, and remove test data.
- Set long persistent `SECRET_KEY`, strong `ADMIN_PASSWORD`, private `SUPABASE_SECRET_KEY` in Render environment settings. Never commit `.env` or credentials.
- Get a **paid always-on Render service**; use HTTPS (`HTTPS_ONLY=1`), `PUBLIC_LAUNCH=1` after review, health check, custom domain and DNS configuration. Audit logs, error monitoring and rate limiting need review under real traffic.
- Payments remain **manual Stripe payment links**, with verification in your Stripe account. **There is no automatic checkout or webhook** and no automatic email system in this package. These workflows can operate manually, but do not claim automated customer updates.
- Test the full payment/order/fulfilment journey in sandbox or with a controlled transaction, and set up a process for abandoned uploads and file deletion.

For large files, direct PUT uploads are a good first step and keep Render responsive; **for unreliable connections, resumable TUS uploads are recommended by Supabase for files over 6 MB**. Test with real-world 3D model sizes and mobile connections before launch.

## 5) GitHub safety

This release candidate includes `.gitignore` to exclude `.env`, `.venv`, `storage/`, caches and databases. **Before uploading to GitHub, run `git status` and check for secrets.** Existing committed secrets are not removed simply by adding `.gitignore`.

Official references: https://supabase.com/docs/guides/storage/uploads/standard-uploads ; https://supabase.com/docs/reference/python/storage-from-createsigneduploadurl ; https://render.com/docs/deploy-flask
