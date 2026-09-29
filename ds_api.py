# -*- coding: utf-8 -*-
"""Клиент API Dream Square. Ключи берутся из окружения — в репозиторий они не попадают.

Локально:  DS_CLIENT_ID=... DS_CLIENT_SECRET=... python build_data.py
В Actions: те же значения лежат в Secrets репозитория.
"""
import json, os, urllib.request, urllib.parse

BASE = os.environ.get('DS_BASE', 'https://icg.lendo.kz')
CLIENT_ID = os.environ.get('DS_CLIENT_ID', '')
CLIENT_SECRET = os.environ.get('DS_CLIENT_SECRET', '')
_tok = [None]


def token():
    if not CLIENT_ID or not CLIENT_SECRET:
        raise RuntimeError('нет DS_CLIENT_ID / DS_CLIENT_SECRET в окружении')
    if _tok[0] is None:
        r = urllib.request.Request(
            BASE + '/api/dream-square/v1/auth/token',
            data=json.dumps({'clientId': CLIENT_ID, 'clientSecret': CLIENT_SECRET}).encode(),
            headers={'Content-Type': 'application/json'})
        _tok[0] = json.loads(urllib.request.urlopen(r, timeout=30).read().decode())['accessToken']
    return _tok[0]


def attendance(frm, to, **extra):
    q = dict(extra)
    q['from'] = frm
    q['to'] = to
    r = urllib.request.Request(
        BASE + '/api/dream-square/v1/reports/attendance?' + urllib.parse.urlencode(q),
        headers={'Authorization': 'Bearer ' + token()})
    return json.loads(urllib.request.urlopen(r, timeout=90).read().decode())
