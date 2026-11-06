"""Offline unit tests. Run `python -m unittest discover -s tests -v` after installing requirements.
No network is used; the Supabase client is replaced with a deterministic fake.
"""
import importlib
import os
import re
import unittest
from unittest.mock import patch
from types import SimpleNamespace

os.environ['SUPABASE_URL'] = 'https://example.supabase.co'
os.environ['SUPABASE_SECRET_KEY'] = 'sb_secret_test_only_not_a_real_key'
os.environ['SECRET_KEY'] = 'static-test-secret-string-32-characters!!'
os.environ['ADMIN_PASSWORD'] = 'test-password-not-for-production'
os.environ['PUBLIC_LAUNCH'] = '0'
os.environ['HTTPS_ONLY'] = '0'


class FakeTable:
    def __init__(self, state, name):
        self.state, self.name = state, name
        self.action = None
        self.filters = {}
        self.body = None
    def select(self, *args, **kwargs):
        self.action = 'select'
        return self
    def insert(self, body):
        self.action = 'insert'
        self.body = body
        return self
    def update(self, body):
        self.action = 'update'
        self.body = body
        return self
    def eq(self, key, value):
        self.filters[key] = value
        return self
    def gte(self, *_):
        return self
    def limit(self, *_):
        return self
    def order(self, *_args, **_kwargs):
        return self
    def range(self, *_):
        return self
    def execute(self):
        if self.action == 'insert':
            if self.name == 'orders':
                self.state['orders'].append(self.body)
            return SimpleNamespace(data=[self.body], count=None)
        if self.action == 'update':
            for row in self.state['orders']:
                if row['id'] == self.filters.get('id'):
                    row.update(self.body)
                    return SimpleNamespace(data=[row], count=None)
            return SimpleNamespace(data=[], count=None)
        if self.name == 'submission_limits':
            return SimpleNamespace(data=[], count=0)
        items = self.state['orders'][:]
        if 'id' in self.filters:
            items = [x for x in items if x['id'] == self.filters['id']]
        return SimpleNamespace(data=items, count=len(items))


class FakeBucket:
    def __init__(self, state):
        self.state = state
    def create_signed_upload_url(self, path):
        self.state['upload_path'] = path
        return {'signed_url': 'https://example.supabase.co/storage/v1/object/upload/sign/customers/' + path + '?token=dummy'}
    def info(self, path):
        if path != self.state.get('upload_path'):
            return None
        return {'metadata': {'size': self.state['file_size']}}
    def create_signed_url(self, path, seconds):
        return {'signed_url': 'https://example.supabase.co/storage/v1/object/sign/customers/' + path + '?token=dummy'}
    def upload(self, path, file, file_options):
        self.state['upload_path'] = path
        return {}
    def remove(self, paths):
        return []


class FakeSupabase:
    def __init__(self):
        self.state = {'orders': [], 'file_size': 3}
        self.bucket = FakeBucket(self.state)
    def table(self, name):
        return FakeTable(self.state, name)
    def from_(self, name):
        assert name == 'customers'
        return self.bucket
    @property
    def storage(self):
        return self


class TestPublicSite(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fake = FakeSupabase()
        with patch('supabase.create_client', return_value=cls.fake):
            cls.app_module = importlib.import_module('app')
        cls.app_module.app.config['TESTING'] = True
        cls.app_module.app.config['SECRET_KEY'] = 'test-test-test-test-test-test-test!!'
    def setUp(self):
        self.fake.state['orders'].clear()
        self.fake.state['file_size'] = 3
        self.client = self.app_module.app.test_client()
        page = self.client.get('/')
        self.assertEqual(page.status_code, 200)
        match = re.search(rb'name="csrf_token" value="([^"]+)"', page.data)
        self.assertIsNotNone(match)
        self.csrf = match.group(1).decode()
    def data(self):
        return {
            'csrf_token': self.csrf,
            'rights': 'on', 'privacy_agree': 'on',
            'name': 'Test Customer', 'email': 'test@example.com',
            'purpose': 'Test enclosure', 'material': 'PLA',
            'colour': 'Black', 'quantity': '1',
        }
    def test_public_pages_and_no_secret_leak(self):
        for page in ['/', '/privacy', '/terms', '/thank-you', '/healthz']:
            self.assertEqual(self.client.get(page).status_code, 200, page)
        self.assertNotIn(b'sb_secret_', self.client.get('/').data)
        self.assertIn(b'100 MB', self.client.get('/').data)
    def test_admin_is_not_public(self):
        response = self.client.get('/admin')
        self.assertEqual(response.status_code, 302)
        self.assertIn('/admin/login', response.headers['Location'])
    def test_requires_csrf(self):
        response = self.client.post('/api/quote/start', data={'upload_size': '123'})
        self.assertEqual(response.status_code, 400)
    def test_rejects_wrong_type(self):
        fields = self.data()
        fields.update(upload_name='virus.exe', upload_size='3')
        response = self.client.post('/api/quote/start', data=fields)
        self.assertEqual(response.status_code, 400)
        self.assertIn('STL', response.get_json()['error'])
    def test_rejects_oversized_file(self):
        fields = self.data()
        fields.update(upload_name='test.stl', upload_size=str(101*1024*1024))
        self.assertEqual(self.client.post('/api/quote/start', data=fields).status_code, 400)
    def test_full_signed_upload_flow(self):
        fields = self.data()
        begin = dict(fields, upload_name='test.stl', upload_size='3')
        response = self.client.post('/api/quote/start', data=begin)
        self.assertEqual(response.status_code, 200, response.data)
        link = response.get_json()['upload_url']
        self.assertIn('example.supabase.co', link)
        self.assertNotIn('sb_secret_', link)
        response = self.client.post('/api/quote/finish', data=fields)
        self.assertEqual(response.status_code, 200, response.data)
        ref = response.get_json()['reference']
        self.assertEqual(len(self.fake.state['orders']), 1)
        self.assertEqual(self.fake.state['orders'][0]['id'], ref)
        self.assertTrue(self.fake.state['orders'][0]['saved_filename'].startswith('orders/'))
        self.assertEqual(self.client.post('/api/quote/finish', data=fields).status_code, 409)
    def test_mismatching_metadata_fails_closed(self):
        fields = self.data()
        begin = dict(fields, upload_name='test.stl', upload_size='3')
        self.assertEqual(self.client.post('/api/quote/start', data=begin).status_code, 200)
        self.fake.state['file_size'] = 20
        response = self.client.post('/api/quote/finish', data=fields)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(len(self.fake.state['orders']), 0)


if __name__ == '__main__':
    unittest.main()
