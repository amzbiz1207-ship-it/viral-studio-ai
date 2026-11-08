"""Persistence for a single-owner prototype.

Supabase REST provides durability on Streamlit Community Cloud when configured.
SQLite is a local-only fallback: ephemeral on Streamlit Community Cloud.
No API keys, passwords or credentials are written to project state.
"""
from __future__ import annotations
import json
import os
import sqlite3
from pathlib import Path
import requests

class StorageError(RuntimeError):
    pass

class StateStore:
    def __init__(self, supabase_url='', supabase_key='', path=None):
        self.url = supabase_url.rstrip('/')
        self.key = supabase_key
        if bool(self.url) != bool(self.key):
            raise StorageError('Configure both SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY, or neither.')
        self.remote = bool(self.url)
        self.path = Path(path or os.getenv('VIRAL_DB_PATH', str(Path.home() / '.viral_studio_ai' / 'state.sqlite3')))
        if not self.remote:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            try:
                os.chmod(self.path.parent, 0o700)
            except OSError:
                pass
            with sqlite3.connect(self.path) as db:
                db.execute('CREATE TABLE IF NOT EXISTS app_state (owner TEXT PRIMARY KEY, payload TEXT NOT NULL)')

    def _headers(self):
        return {'apikey': self.key, 'Authorization': f'Bearer {self.key}',
                'Content-Type': 'application/json', 'Prefer': 'resolution=merge-duplicates,return=minimal'}

    def load(self, owner='personal'):
        try:
            if self.remote:
                r = requests.get(f'{self.url}/rest/v1/viral_studio_state',
                                 params={'owner': f'eq.{owner}', 'select': 'payload'},
                                 headers=self._headers(), timeout=12)
                r.raise_for_status()
                items = r.json()
                return items[0]['payload'] if items else None
            with sqlite3.connect(self.path) as db:
                row = db.execute('SELECT payload FROM app_state WHERE owner=?', (owner,)).fetchone()
            return json.loads(row[0]) if row else None
        except (requests.RequestException, ValueError, OSError, sqlite3.Error, KeyError) as e:
            raise StorageError(f'Could not load saved data: {e}') from e

    def save(self, state, owner='personal'):
        if not isinstance(state, dict) or not isinstance(state.get('projects'), dict):
            raise StorageError('Invalid project state.')
        # Serialization also guards against accidentally writing Streamlit internals.
        payload = json.loads(json.dumps(state, ensure_ascii=False))
        try:
            if self.remote:
                r = requests.post(f'{self.url}/rest/v1/viral_studio_state',
                                  json={'owner':owner, 'payload':payload}, headers=self._headers(), timeout=12)
                r.raise_for_status()
            else:
                with sqlite3.connect(self.path) as db:
                    db.execute('INSERT INTO app_state (owner,payload) VALUES (?,?) '
                               'ON CONFLICT(owner) DO UPDATE SET payload=excluded.payload',
                               (owner,json.dumps(payload,ensure_ascii=False)))
                    db.commit()
                try: os.chmod(self.path, 0o600)
                except OSError: pass
        except (requests.RequestException, OSError, sqlite3.Error, ValueError) as e:
            raise StorageError(f'Could not save data: {e}') from e


def validate_restore(content):
    if not isinstance(content,dict) or content.get('schema') not in (1,2):
        raise ValueError('Unsupported backup format')
    if not isinstance(content.get('projects'),dict) or not content['projects']:
        raise ValueError('Missing projects')
    if not isinstance(content.get('library',[]),list) or not isinstance(content.get('videos',[]),list):
        raise ValueError('Invalid collections')
    return {k:content.get(k,default) for k,default in {
        'projects': {}, 'current': 'My channel', 'library': [], 'videos': [],
        'saved_outputs': [], 'language_output': 'EN', 'prompt_language': 'EN',
    }.items()}
