# -*- coding: utf-8 -*-
"""Функция Vercel: GET /api/operators[?date=YYYY-MM-DD] — операторы партнёров отчёта за день.

Вкладка «Операторы» на странице: кто из операторов уже отметился, а кто ещё нет.
"""
import json, os, re, sys, traceback
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import build_data


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        date = (parse_qs(urlparse(self.path).query).get('date') or [''])[0]
        try:
            if date and not re.fullmatch(r'\d{4}-\d{2}-\d{2}', date):
                code, body = 400, {'error': 'дата должна быть в формате YYYY-MM-DD'}
            else:
                code, body = 200, build_data.build_operators(date or None)
        except Exception as e:
            traceback.print_exc()                    # видно в Vercel → Logs
            code, body = 502, {'error': str(e) or e.__class__.__name__}
        raw = json.dumps(body, ensure_ascii=False).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(raw)
