"""ProtoVex V2: Flask quote-request site backed by Supabase.

Server-side only. Needs public.orders, public.submission_limits, and a PRIVATE
Supabase Storage bucket named 'customers'. Never expose the secret key in HTML.
Do not publish until the privacy notice, terms, and operational checks are ready.
"""

import csv
import hmac
import io
import logging
import math
import os
import secrets
import uuid
import time
from urllib.parse import urlparse, urljoin
from datetime import datetime, timedelta, timezone
from functools import wraps
from pathlib import Path

from dotenv import load_dotenv
from flask import (Flask, abort, flash, make_response, redirect,
                   render_template, request, send_file, session, url_for, jsonify)
from supabase import Client, create_client
from werkzeug.utils import secure_filename

BASE = Path(__file__).resolve().parent
load_dotenv(BASE / '.env')

SUPABASE_URL = os.getenv('SUPABASE_URL', '').strip().rstrip('/')
SUPABASE_SECRET_KEY = os.getenv('SUPABASE_SECRET_KEY', '').strip()
BUCKET = 'customers'  # The private bucket already created in the Supabase dashboard.
MAX_FILE_MB = 20  # Only for basic non-JavaScript fallback uploads.
MAX_FILE_BYTES = MAX_FILE_MB * 1024 * 1024
MAX_DIRECT_FILE_MB = min(max(int(os.getenv('MAX_DIRECT_FILE_MB', '100')), 1), 200)
MAX_DIRECT_FILE_BYTES = MAX_DIRECT_FILE_MB * 1024 * 1024
ALLOWED = {'stl', '3mf', 'obj'}
STATES = ('New', 'Quoted', 'Paid', 'Printing', 'Ready', 'Dispatched', 'Completed', 'Declined')

if not SUPABASE_URL.startswith('https://') or not SUPABASE_SECRET_KEY:
    raise RuntimeError('Set SUPABASE_URL and SUPABASE_SECRET_KEY in .env (do not share them).')

# Supabase client exists only on the Flask backend. No browser gets the secret key.
sb: Client = create_client(SUPABASE_URL, SUPABASE_SECRET_KEY)

app = Flask(__name__)
app.config.update(
    SECRET_KEY=os.getenv('SECRET_KEY') or secrets.token_hex(32),
    MAX_CONTENT_LENGTH=MAX_FILE_BYTES + 1024 * 1024,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    SESSION_COOKIE_SECURE=os.getenv('HTTPS_ONLY', '0') == '1',
    PERMANENT_SESSION_LIFETIME=3600,
)
app.jinja_env.globals['business_name'] = os.getenv('BUSINESS_NAME', 'ProtoVex')
app.jinja_env.globals['business_email'] = os.getenv('BUSINESS_EMAIL', 'contact@example.com')
app.jinja_env.globals['launch_ready'] = os.getenv('PUBLIC_LAUNCH', '0') == '1'
app.jinja_env.globals['max_direct_file_mb'] = MAX_DIRECT_FILE_MB
app.jinja_env.globals['legal_name'] = os.getenv('LEGAL_NAME', '[LEGAL BUSINESS NAME]')
app.jinja_env.globals['business_address'] = os.getenv('BUSINESS_ADDRESS', '[BUSINESS CONTACT ADDRESS]')
app.jinja_env.globals['privacy_retention'] = os.getenv('PRIVACY_RETENTION', '[SET RETENTION POLICY]')
app.jinja_env.globals['policy_reviewed'] = os.getenv('LEGAL_REVIEWED', '0') == '1'

if os.getenv('PUBLIC_LAUNCH') == '1':
    for required in ('SECRET_KEY', 'ADMIN_PASSWORD', 'BUSINESS_EMAIL', 'LEGAL_NAME', 'BUSINESS_ADDRESS', 'PRIVACY_RETENTION'):
        if not os.getenv(required, '').strip():
            raise RuntimeError(f'Cannot enable PUBLIC_LAUNCH until {required} is configured')
    for sensitive in ('SECRET_KEY', 'ADMIN_PASSWORD', 'SUPABASE_SECRET_KEY'):
        v = os.getenv(sensitive, '')
        if len(v) < 24 or 'REPLACE' in v.upper() or 'YOUR-' in v.upper():
            raise RuntimeError(f'{sensitive} needs a non-placeholder value for launch')
    if os.getenv('BUSINESS_EMAIL', '').endswith('@example.com'):
        raise RuntimeError('Configure a real business email for launch')
    if os.getenv('LEGAL_REVIEWED', '0') != '1':
        raise RuntimeError('Review all public policies, then set LEGAL_REVIEWED=1 for launch')


def time_now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def time_ago(minutes):
    return (datetime.now(timezone.utc) - timedelta(minutes=minutes)).isoformat(timespec='seconds')


def csrf_token():
    if 'csrf' not in session:
        session['csrf'] = secrets.token_urlsafe(32)
    return session['csrf']


app.jinja_env.globals['csrf_token'] = csrf_token


def csrf_check():
    received = request.form.get('csrf_token', '')
    if not received or not hmac.compare_digest(received, session.get('csrf', '')):
        abort(400, 'Form validation expired. Refresh the page and try again.')


@app.after_request
def response_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['Cache-Control'] = 'no-store' if request.path.startswith('/admin') else 'private, max-age=0'
    return response


def admin_required(view):
    @wraps(view)
    def inner(*args, **kwargs):
        if not session.get('admin'):
            return redirect(url_for('login', next=request.path))
        return view(*args, **kwargs)
    return inner


def cleaned(value, max_len=250):
    return (value or '').strip()[:max_len]


def visitor_identifier(prefix):
    # Matches the existing MVP's Render proxy handling. Only use X-Real-IP when
    # a trusted reverse proxy sets/overwrites it (as Render normally does).
    ip = request.headers.get('X-Real-IP', request.remote_addr or 'unknown')[:64]
    return prefix + ip


def recent_attempts(identifier, minutes):
    result = (sb.table('submission_limits')
              .select('identifier', count='exact')
              .eq('identifier', identifier)
              .gte('created_at', time_ago(minutes))
              .limit(1).execute())
    return result.count if result.count is not None else len(result.data or [])


def record_attempt(identifier):
    sb.table('submission_limits').insert({
        'identifier': identifier,
        'created_at': time_now(),
    }).execute()


def order_by_id(order_id):
    result = (sb.table('orders').select('*').eq('id', order_id)
              .limit(1).execute())
    return (result.data or [None])[0]


def all_orders(batch=500):
    # Supabase's REST API has a default max rows per query; paginate CSV export.
    rows = []
    while True:
        chunk = (sb.table('orders').select('*').order('created_at', desc=True)
                 .range(len(rows), len(rows) + batch - 1).execute().data or [])
        rows.extend(chunk)
        if len(chunk) < batch:
            return rows


@app.route('/')
def home():
    return render_template('home.html')


@app.route('/privacy')
def privacy():
    return render_template('privacy.html')


@app.route('/terms')
def terms():
    return render_template('terms.html')


@app.route('/quote', methods=['POST'])
def submit_quote():
    csrf_check()
    if request.form.get('trap'):
        return redirect(url_for('thank_you'))
    if not request.form.get('rights') or not request.form.get('privacy_agree'):
        flash('Please confirm design rights and read the privacy notice.', 'error')
        return redirect(url_for('home') + '#quote')

    name = cleaned(request.form.get('name'), 100)
    email = cleaned(request.form.get('email'), 254)
    purpose = cleaned(request.form.get('purpose'), 1000)
    material = cleaned(request.form.get('material'), 10).upper()
    colour = cleaned(request.form.get('colour'), 40)
    try:
        quantity = int(request.form.get('quantity', '0'))
    except (ValueError, TypeError):
        quantity = 0
    model = request.files.get('file')
    filename = secure_filename(model.filename or '') if model else ''
    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
    if (not name or '@' not in email or len(email) < 5 or not purpose
            or material not in ('PLA', 'PETG') or not colour
            or not 1 <= quantity <= 50 or not filename or ext not in ALLOWED):
        flash('Check the fields and upload an STL, 3MF or OBJ model.', 'error')
        return redirect(url_for('home') + '#quote')
    if not model or not model.stream:
        flash('Please attach your model.', 'error')
        return redirect(url_for('home') + '#quote')

    contents = model.stream.read(MAX_FILE_BYTES + 1)
    if not contents or len(contents) > MAX_FILE_BYTES:
        flash('Your file must be between 1 byte and 20 MB.', 'error')
        return redirect(url_for('home') + '#quote')

    identifier = visitor_identifier('quote:')
    if recent_attempts(identifier, 60) >= 3:
        abort(429, 'Too many enquiries. Please contact us by email.')
    record_attempt(identifier)

    order_id = 'QP-' + uuid.uuid4().hex[:9].upper()
    # Randomized object name prevents user filenames from becoming public paths.
    storage_path = 'orders/' + uuid.uuid4().hex + '.' + ext
    created = time_now()
    # Upload first. If order insertion fails, delete the uploaded object.
    sb.storage.from_(BUCKET).upload(
        path=storage_path,
        file=contents,
        file_options={'content-type': 'application/octet-stream', 'upsert': 'false'},
    )
    try:
        sb.table('orders').insert({
            'id': order_id,
            'created_at': created,
            'customer_name': name,
            'email': email,
            'company': cleaned(request.form.get('company'), 120),
            'material': material,
            'colour': colour,
            'quantity': quantity,
            'purpose': purpose,
            'due': cleaned(request.form.get('due'), 80),
            'original_filename': filename,
            'saved_filename': storage_path,
            'state': 'New',
            'updated_at': created,
        }).execute()
    except Exception:
        try:
            sb.storage.from_(BUCKET).remove([storage_path])
        except Exception:
            logging.exception('Could not clean up uploaded model after failed order insert')
        raise
    return redirect(url_for('thank_you', ref=order_id))


@app.route('/thank-you')
def thank_you():
    return render_template('thanks.html', ref=cleaned(request.args.get('ref'), 20))


@app.route('/admin/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        csrf_check()
        identifier = visitor_identifier('login:')
        if recent_attempts(identifier, 15) >= 8:
            abort(429, 'Too many login attempts')
        expected = os.getenv('ADMIN_PASSWORD', '')
        supplied = request.form.get('password', '')
        if expected and hmac.compare_digest(supplied, expected):
            session.clear()
            session['admin'] = True
            session.permanent = True
            csrf_token()
            return redirect(url_for('admin'))
        record_attempt(identifier)
        flash('Invalid password, or ADMIN_PASSWORD has not been configured.', 'error')
    return render_template('login.html')


@app.route('/admin/logout', methods=['POST'])
@admin_required
def logout():
    csrf_check()
    session.clear()
    return redirect(url_for('home'))


@app.route('/admin')
@admin_required
def admin():
    orders = (sb.table('orders').select('*')
              .order('created_at', desc=True).limit(300).execute().data or [])
    counts = {state: sum(o['state'] == state for o in orders) for state in STATES}
    return render_template('admin.html', orders=orders, counts=counts)


@app.route('/admin/order/<order_id>', methods=['GET', 'POST'])
@admin_required
def order(order_id):
    if request.method == 'POST':
        csrf_check()
        state = request.form.get('state', '')
        if state not in STATES:
            abort(400)

        def optional_money(field):
            value = cleaned(request.form.get(field), 30)
            if not value:
                return None
            try:
                amount = float(value)
            except (TypeError, ValueError):
                abort(400, 'Invalid amount')
            if not math.isfinite(amount) or not 0 <= amount <= 100000:
                abort(400, 'Invalid amount')
            return round(amount, 2)

        updated = (sb.table('orders').update({
            'state': state,
            'price_gbp': optional_money('price_gbp'),
            'costs_gbp': optional_money('costs_gbp'),
            'payment_url': cleaned(request.form.get('payment_url'), 600),
            'tracking': cleaned(request.form.get('tracking'), 300),
            'notes': cleaned(request.form.get('notes'), 3000),
            'updated_at': time_now(),
        }).eq('id', order_id).select('id').execute().data or [])
        if not updated:
            abort(404)
        flash('Order saved. Tell the customer manually about status changes.', 'ok')
        return redirect(url_for('order', order_id=order_id))
    entry = order_by_id(order_id)
    if not entry:
        abort(404)
    return render_template('order.html', order=entry, states=STATES)


@app.route('/admin/order/<order_id>/download')
@admin_required
def download(order_id):
    entry = order_by_id(order_id)
    if not entry:
        abort(404)
    # A 60-second download URL avoids buffering a 100MB file on Render.
    # Only an authenticated administrator can request it. The bucket stays private.
    signed = sb.storage.from_(BUCKET).create_signed_url(entry['saved_filename'], 60)
    url = _signed_url(signed)
    return redirect(url, code=303)


@app.route('/admin/export.csv')
@admin_required
def export_csv():
    fields = ('id', 'created_at', 'customer_name', 'email', 'company',
              'material', 'colour', 'quantity', 'purpose', 'due', 'state',
              'price_gbp', 'costs_gbp', 'tracking', 'notes')
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(fields)
    for row in all_orders():
        # Stop values like '=HYPERLINK(...)' becoming executable formulas in Excel.
        writer.writerow([
            "'" + str(row.get(field))
            if isinstance(row.get(field), str) and row[field].lstrip(' \t\r\n')[:1] in ('=', '+', '-', '@')
            else row.get(field)
            for field in fields
        ])
    response = make_response(buf.getvalue())
    response.headers['Content-Type'] = 'text/csv; charset=utf-8'
    response.headers['Content-Disposition'] = 'attachment; filename="orders.csv"'
    return response


@app.errorhandler(413)
def too_large(_):
    return render_template('error.html', message='File too large. Maximum file size is 20 MB.'), 413


@app.errorhandler(429)
def rate_limited(_):
    return render_template('error.html', message='Too many submissions. Please contact us by email.'), 429


@app.errorhandler(400)
def invalid(_):
    return render_template('error.html', message='Please refresh and try again.'), 400




# PUBLIC RELEASE CANDIDATE: signed uploads avoid passing large files through Render.
# The customer never receives our Supabase secret key; the URL can upload only
# to one random object name and has a short lifetime set by Supabase.

def _validate_quote_fields(form):
    if form.get('trap'):
        return None, 'Please try again.'
    if not form.get('rights') or not form.get('privacy_agree'):
        return None, 'Please accept the rights declaration and privacy notice.'
    name = cleaned(form.get('name'), 100)
    email = cleaned(form.get('email'), 254)
    purpose = cleaned(form.get('purpose'), 1000)
    material = cleaned(form.get('material'), 10).upper()
    colour = cleaned(form.get('colour'), 40)
    try:
        quantity = int(form.get('quantity', '0'))
    except (ValueError, TypeError):
        quantity = 0
    if (not name or '@' not in email or len(email) < 5 or not purpose or
        material not in ('PLA', 'PETG') or not colour or not 1 <= quantity <= 50):
        return None, 'Please check the required fields.'
    return {
        'customer_name': name,
        'email': email,
        'company': cleaned(form.get('company'), 120),
        'material': material,
        'colour': colour,
        'quantity': quantity,
        'purpose': purpose,
        'due': cleaned(form.get('due'), 80),
    }, None


def _signed_url(response):
    if isinstance(response, dict):
        raw = response.get('signed_url') or response.get('signedUrl')
    else:
        raw = getattr(response, 'signed_url', None) or getattr(response, 'signedUrl', None)
    if not isinstance(raw, str) or not raw:
        raise RuntimeError('Supabase did not return a signed upload URL')
    if raw.startswith('/object/'):
        raw = '/storage/v1' + raw
    if raw.startswith('/'):
        raw = urljoin(SUPABASE_URL, raw)
    parsed, trusted = urlparse(raw), urlparse(SUPABASE_URL)
    if parsed.scheme != 'https' or parsed.hostname != trusted.hostname:
        raise RuntimeError('Supabase returned an unexpected upload endpoint')
    return raw


@app.post('/api/quote/start')
def quote_upload_start():
    csrf_check()
    fields, error = _validate_quote_fields(request.form)
    if error:
        return jsonify(error=error), 400
    filename = secure_filename(cleaned(request.form.get('upload_name'), 160))
    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
    try:
        size = int(request.form.get('upload_size', '0'))
    except ValueError:
        size = 0
    if not filename or ext not in ALLOWED:
        return jsonify(error='Please upload an STL, 3MF or OBJ file.'), 400
    if not 0 < size <= MAX_DIRECT_FILE_BYTES:
        return jsonify(error=f'File must be between 1 byte and {MAX_DIRECT_FILE_MB} MB.'), 400
    identifier = visitor_identifier('quote:')
    if recent_attempts(identifier, 60) >= 3:
        return jsonify(error='Too many requests. Please contact us by email.'), 429
    record_attempt(identifier)
    # No personal data is placed in the signed browser session cookie.
    order_id = 'QP-' + uuid.uuid4().hex[:9].upper()
    path = 'orders/' + uuid.uuid4().hex + '.' + ext
    signed = sb.storage.from_(BUCKET).create_signed_upload_url(path)
    upload_url = _signed_url(signed)
    session['pending_upload'] = {
        'order_id': order_id, 'path': path, 'filename': filename,
        'bytes': size, 'started': int(time.time()),
    }
    return jsonify(upload_url=upload_url, max_mb=MAX_DIRECT_FILE_MB)


@app.post('/api/quote/finish')
def quote_upload_finish():
    csrf_check()
    fields, error = _validate_quote_fields(request.form)
    if error:
        return jsonify(error=error), 400
    pending = session.get('pending_upload')
    if not pending or int(time.time()) - pending.get('started', 0) > 7200:
        return jsonify(error='Upload session expired. Please reload and try again.'), 409

    # Confirm the object actually exists in PRIVATE Storage. Customer-supplied
    # filenames, sizes and paths are never trusted as evidence of an upload.
    try:
        info = sb.storage.from_(BUCKET).info(pending['path'])
    except Exception:
        logging.exception('Could not verify uploaded file')
        return jsonify(error='Your upload could not be verified. Please try again.'), 409
    if not info:
        return jsonify(error='Your file has not finished uploading.'), 409
    metadata = info.get('metadata', {}) if isinstance(info, dict) else getattr(info, 'metadata', {})
    if not isinstance(metadata, dict):
        metadata = {}
    size = metadata.get('size') or (info.get('size') if isinstance(info, dict) else getattr(info, 'size', None))
    if size is not None:
        try:
            size_int = int(size)
        except (TypeError, ValueError):
            size_int = 0
        if size_int != pending['bytes'] or not 0 < size_int <= MAX_DIRECT_FILE_BYTES:
            return jsonify(error='Uploaded size did not match the selected file.'), 409

    created = time_now()
    row = {
        'id': pending['order_id'], 'created_at': created, **fields,
        'original_filename': pending['filename'],
        'saved_filename': pending['path'], 'state': 'New', 'updated_at': created,
    }
    try:
        sb.table('orders').insert(row).execute()
    except Exception:
        # A browser may retry after a connection drops despite a successful
        # insert. Do not delete the file belonging to an already saved order.
        try:
            if order_by_id(row['id']):
                session.pop('pending_upload', None)
                return jsonify(reference=row['id'], redirect=url_for('thank_you', ref=row['id']))
        except Exception:
            logging.exception('Could not verify a retry of the order submission')
        logging.exception('Could not save the uploaded order')
        return jsonify(error='Your file uploaded, but your order could not be saved. Please retry.'), 503
    session.pop('pending_upload', None)
    return jsonify(reference=row['id'], redirect=url_for('thank_you', ref=row['id']))


@app.get('/healthz')
def healthz():
    return jsonify(status='ok')


@app.errorhandler(500)
def error_500(_):
    return render_template('error.html', message='An unexpected error occurred. Please try again or email us.'), 500


if __name__ == '__main__':
    app.run(debug=False, host='127.0.0.1', port=5000)
