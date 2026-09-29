# -*- coding: utf-8 -*-
"""Функция Vercel: GET /api/data — собирает план/факт прямо сейчас из API Dream Square.

Кнопка «Обновить» на странице вызывает её. Ключи — в Environment Variables проекта Vercel
(DS_CLIENT_ID, DS_CLIENT_SECRET), в браузер они не попадают.
"""
import json, os, sys, traceback
from http.server import BaseHTTPRequestHandler

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import build_data


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            code, body = 200, build_data.build()
        except Exception as e:
            traceback.print_exc()                    # видно в Vercel → Logs
            code, body = 502, {'error': str(e) or e.__class__.__name__}
        raw = json.dumps(body, ensure_ascii=False).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(raw)
