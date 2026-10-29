# -*- coding: utf-8 -*-
"""Собирает data.json для отчёта: план ОПУ (численность операторов), факт отметок из API Dream Square.

Факт по каждому дню запрашивается заново, поэтому прошлые дни тоже пересчитываются.
build() вызывает и этот скрипт (пишет data.json), и функция Vercel api/data.py (живая кнопка).
"""
import json, io, difflib, datetime, os
from concurrent.futures import ThreadPoolExecutor
import ds_api

HERE = os.path.dirname(os.path.abspath(__file__))
PLAN = os.path.join(HERE, 'plan_daily.json')           # партнёры, объекты, календарь
PLAN_OPU = os.path.join(HERE, 'plan_opu.json')         # план ОПУ, собирается plan_from_xlsx.py
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


def make_resolver(rows):
    """Имя партнёра из API -> ключ партнёра отчёта; опечатки в фамилии (Ильясов / Илиясов) сводятся к одному."""
    plan_keys = {key(r['name']) for r in rows}

    def resolve(name):
        k = key(name)
        if k in plan_keys:
            return k
        sur, _, ini = k.partition(u'|')
        best = difflib.get_close_matches(sur, [p.split(u'|')[0] for p in plan_keys
                                               if p.split(u'|')[1] == ini], 1, 0.85)
        return best[0] + u'|' + ini if best else k
    return resolve


def city_rows(by_city, days, have):
    """Города партнёра: факт по дням (0 там, где день прошёл, а отметок не было), сначала крупные."""
    rows = []
    for name, c in by_city.items():
        fill = lambda a: [(v or 0) if d in have else None for v, d in zip(a, days)]
        rows.append({'name': name, 'f': fill(c['f']), 'o': fill(c['o'])})
    return sorted(rows, key=lambda r: (-sum(v or 0 for v in r['f']), r['name']))


def build():
    """План + факт на текущий момент; возвращает то, что лежит в data.json."""
    NOW = datetime.datetime.now(datetime.timezone.utc) + TZ_OFFSET
    TODAY = NOW.date()
    P = json.load(io.open(PLAN, encoding='utf-8'))
    days, rows = P['days'], P['rows']
    opu = json.load(io.open(PLAN_OPU, encoding='utf-8'))

    # календарь из разбивки кончается раньше сегодняшнего дня — дотягиваем его
    _last = datetime.date(*map(int, days[-1].split('-')))
    while _last < TODAY:
        _last += datetime.timedelta(1)
        days.append(_last.isoformat())

    resolve = make_resolver(rows)

    have = [d for d in days if datetime.date(*map(int, d.split('-'))) <= TODAY]
    # дни запрашиваем параллельно: в функции Vercel важна скорость ответа
    ds_api.reset_token()
    ds_api.token()
    with ThreadPoolExecutor(8) as ex:
        resp = dict(zip(have, ex.map(lambda d: ds_api.attendance(d, d, groupBy='city'), have)))
    fact, ops = {}, {}
    cur, curp = {}, {}                  # админы компании (кураторы): отметки и люди по дням
    cities = {}                         # ключ партнёра -> город -> {'f': [...], 'o': [...]} по дням
    for i, d in enumerate(days):
        if d not in have:
            continue
        for p in resp[d]['partners']:
            k = resolve(p['partnerName'])
            fact.setdefault(k, [None] * len(days))
            ops.setdefault(k, [None] * len(days))
            fact[k][i] = (fact[k][i] or 0) + p['shiftsCount']
            ops[k][i] = (ops[k][i] or 0) + p['operatorsCheckedIn']
            cur.setdefault(k, [None] * len(days))
            curp.setdefault(k, [None] * len(days))
            cur[k][i] = (cur[k][i] or 0) + (p.get('curatorsShiftsCount') or 0)
            curp[k][i] = (curp[k][i] or 0) + (p.get('curatorsCheckedIn') or 0)
            for c in p.get('cities') or []:
                cc = cities.setdefault(k, {}).setdefault(c['city'] or u'город не указан',
                                                         {'f': [None] * len(days), 'o': [None] * len(days)})
                cc['f'][i] = (cc['f'][i] or 0) + c['shiftsCount']
                cc['o'][i] = (cc['o'][i] or 0) + c['operatorsCheckedIn']
    for k in fact:
        for i, d in enumerate(days):
            if d in have and fact[k][i] is None:
                fact[k][i] = 0
                ops[k][i] = 0
                cur[k][i] = 0
                curp[k][i] = 0

    out = []
    for r in rows:
        k = key(r['name'])
        f = fact.get(k) or [0 if d in have else None for d in days]
        o = ops.get(k) or [0 if d in have else None for d in days]
        plan = opu['plan'].get(r['name'])                 # None — партнёра нет в выгрузке
        out.append({'name': r['name'], 'obj': r['obj'], 'plan_old': r['plan'], 'plan': plan,
                    'plan80': round(plan * 0.8) if plan is not None else None,
                    'f': f, 'o': o,
                    'cur': cur.get(k) or [0 if d in have else None for d in days],
                    'curp': curp.get(k) or [0 if d in have else None for d in days],
                    'cities': city_rows(cities.get(k, {}), days, have),
                    'zero': sum(v or 0 for v in f) == 0})
    # партнёров, которых нет в плане (TazaLike, Айсултан, ИП Оспанова, «Блеск»), в отчёт не выводим

    tot = {'obj': sum(r['obj'] for r in out), 'plan_old': sum(r['plan_old'] for r in out),
           'plan': sum(r['plan'] or 0 for r in out),
           'plan80': sum(r['plan80'] or 0 for r in out),
           'f': [(sum(r['f'][i] or 0 for r in out) if days[i] in have else None) for i in range(len(days))]}

    data = {'days': days,
            'wd': [WD[datetime.date(*map(int, d.split('-'))).weekday()] for d in days],
            'have': have, 'rows': out, 'tot': tot, 'plan_month': opu['month'],
            'gen': NOW.strftime('%d.%m.%Y %H:%M')}
    return data


SHOW_PHONES = True      # телефоны операторов на вкладке «Операторы» (страница без пароля)


def build_operators(date=None):
    """Операторы партнёров отчёта за день: кто отметился, кто ещё нет (вкладка «Операторы»)."""
    now = datetime.datetime.now(datetime.timezone.utc) + TZ_OFFSET
    date = date or now.date().isoformat()
    rows = json.load(io.open(PLAN, encoding='utf-8'))['rows']
    names = {key(r['name']): r['name'] for r in rows}
    resolve = make_resolver(rows)

    ds_api.reset_token()
    out = {}
    for p in ds_api.operators(date)['partners']:
        k = resolve(p['partnerName'])
        if k not in names:              # партнёров вне отчёта не показываем
            continue
        part = out.setdefault(k, {'name': names[k], 'total': 0, 'checked': 0, 'ops': []})
        part['total'] += p['operatorsTotal']
        part['checked'] += p['operatorsCheckedIn']
        for o in p['operators']:
            op = {'n': ' '.join(o['fullName'].split()), 'c': o['checkedIn']}
            if o['checkedIn']:
                op['t'] = o['firstCheckInAt'][11:16]
                op['m'] = o['method']
                op['obj'] = [c['objectName'] for c in o['checkIns']]
            if SHOW_PHONES:
                op['ph'] = o.get('phone')
            part['ops'].append(op)
    for part in out.values():
        part['ops'].sort(key=lambda o: (o['c'], o.get('t', ''), o['n']))
    return {'date': date, 'gen': now.strftime('%d.%m.%Y %H:%M'),
            'partners': sorted(out.values(), key=lambda p: p['name'])}


if __name__ == '__main__':
    data = build()
    io.open(OUT, 'w', encoding='utf-8').write(json.dumps(data, ensure_ascii=False))
    have, f = data['have'], data['tot']['f']
    print('saved %s: дней %d, с фактом %d, факт за последний день %s'
          % (OUT, len(data['days']), len(have), f[len(have) - 1]))
