# ProtoVex V2 — first design milestone

This is a separate development copy of the uploaded Flask project, with a Three.js interactive **stylised planetary gearbox** replacing the homepage CSS cubes. The model is procedural and illustrative, not a validated printable CAD assembly.

## Run locally
1. Extract this ZIP into a NEW folder; do not overwrite your live project.
2. Create a virtual environment and install your existing Flask, python-dotenv and gunicorn requirements.
3. Set `SECRET_KEY`, `ADMIN_PASSWORD`, `BUSINESS_NAME=ProtoVex`, `BUSINESS_EMAIL=contact@protovex.co.uk` locally in `.env` (do not commit it).
4. Run `python app.py`, then open `http://127.0.0.1:5000`.
5. The 3D model loads Three.js from a CDN, so an internet connection is needed.

## Scope and cautions
- First milestone only: homepage visual upgrade, not production-ready.
- Existing quotation form and owner dashboard are preserved.
- Uploaded model preview, persistent database/uploads, payment integration, automated emails, security review and legal pages are NOT implemented.
- Test on desktop/mobile before deployment. Keep the current Render service unchanged.
