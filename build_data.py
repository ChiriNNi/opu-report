# -*- coding: utf-8 -*-
"""Собирает data.json для отчёта: план на день из разбивки, факт отметок из API Dream Square.

Факт по каждому дню запрашивается заново, поэтому прошлые дни тоже пересчитываются.
build() вызывает и этот скрипт (пишет data.json), и функция Vercel api/data.py (живая кнопка).
"""
import json, io, difflib, datetime, os
from concurrent.futures import ThreadPoolExecutor
import ds_api

HERE = os.path.dirname(os.path.abspath(__file__))
PLAN = os.path.join(HERE, 'plan_daily.json')
OUT = os.environ.get('OUT', 'data.json')
TZ_OFFSET = datetime.timedelta(hours=5)              # Asia/Almaty
WD = [u'ПН', u'ВТ', u'СР', u'ЧТ', u'ПТ', u'СБ', u'ВС']


def key(n):
    """Имя -> 'фамилия|инициал': 'Роза Ерасылова' и 'Ерасылова Р.' дают один ключ."""
    t = [w.strip(u'.,«»"') for w in n.replace(u'\xa0', ' ').split() if w.strip(u'.,«»"')]
    if not t:
        return ''
    t.sort(key=len, reverse=True)
    return t[0].lower() + u'|' + (t[1][0].lower() if len(t) > 1 else '')


def build():
    """План + факт на текущий момент; возвращает то, что лежит в data.json."""
    NOW = datetime.datetime.now(datetime.timezone.utc) + TZ_OFFSET
    TODAY = NOW.date()
    P = json.load(io.open(PLAN, encoding='utf-8'))
    days, rows = P['days'], P['rows']

    # разбивка кончается раньше сегодняшнего дня — дотягиваем календарь,
    # на новых днях держим план последнего дня разбивки
    _last = datetime.date(*map(int, days[-1].split('-')))
    _hold = {id(r): r['daily'][-1] for r in rows}
    while _last < TODAY:
        _last += datetime.timedelta(1)
        days.append(_last.isoformat())
        for _r in rows:
            _r['daily'].append(_hold[id(_r)])

    plan_keys = {key(r['name']): i for i, r in enumerate(rows)}

    def resolve(name):
        """Ключ партнёра из плана; опечатки в фамилии (Ильясов / Илиясов) сводятся к одному."""
        k = key(name)
        if k in plan_keys:
            return k
        sur, _, ini = k.partition(u'|')
        best = difflib.get_close_matches(sur, [p.split(u'|')[0] for p in plan_keys
                                               if p.split(u'|')[1] == ini], 1, 0.85)
        return best[0] + u'|' + ini if best else k

    have = [d for d in days if datetime.date(*map(int, d.split('-'))) <= TODAY]
    # дни запрашиваем параллельно: в функции Vercel важна скорость ответа
    ds_api.reset_token()
    ds_api.token()
    with ThreadPoolExecutor(8) as ex:
        resp = dict(zip(have, ex.map(lambda d: ds_api.attendance(d, d), have)))
    fact, ops = {}, {}
    for i, d in enumerate(days):
        if d not in have:
            continue
        for p in resp[d]['partners']:
            k = resolve(p['partnerName'])
            fact.setdefault(k, [None] * len(days))
            ops.setdefault(k, [None] * len(days))
            fact[k][i] = (fact[k][i] or 0) + p['shiftsCount']
            ops[k][i] = (ops[k][i] or 0) + p['operatorsCheckedIn']
    for k in fact:
        for i, d in enumerate(days):
            if d in have and fact[k][i] is None:
                fact[k][i] = 0
                ops[k][i] = 0

    out = []
    for r in rows:
        k = key(r['name'])
        f = fact.get(k) or [0 if d in have else None for d in days]
        o = ops.get(k) or [0 if d in have else None for d in days]
        out.append({'name': r['name'], 'obj': r['obj'], 'plan': r['plan'], 'plan80': r['plan80'],
                    'p': r['daily'], 'f': f, 'o': o,
                    'zero': sum(v or 0 for v in f) == 0})
    # партнёров, которых нет в плане (TazaLike, Айсултан, ИП Оспанова, «Блеск»), в отчёт не выводим

    tot = {'obj': sum(r['obj'] for r in out), 'plan': sum(r['plan'] for r in out),
           'plan80': sum(r['plan80'] for r in out),
           'p': [sum(r['p'][i] for r in out) for i in range(len(days))],
           'f': [(sum(r['f'][i] or 0 for r in out) if days[i] in have else None) for i in range(len(days))]}

    data = {'days': days,
            'wd': [WD[datetime.date(*map(int, d.split('-'))).weekday()] for d in days],
            'have': have, 'rows': out, 'tot': tot,
            'gen': NOW.strftime('%d.%m.%Y %H:%M')}
    return data


if __name__ == '__main__':
    data = build()
    io.open(OUT, 'w', encoding='utf-8').write(json.dumps(data, ensure_ascii=False))
    have, f = data['have'], data['tot']['f']
    print('saved %s: дней %d, с фактом %d, факт за последний день %s'
          % (OUT, len(data['days']), len(have), f[len(have) - 1]))
