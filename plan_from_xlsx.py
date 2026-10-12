# -*- coding: utf-8 -*-
"""План ОПУ из выгрузки численности операторов по партнёрам → plan_opu.json.

Выгрузка: лист с колонками ФИО_П | org_name | Месяц | Кол-во людей | ФИО людей.
План ОПУ партнёра = сумма «Кол-во людей» по всем его ИП/ТОО за последний месяц в файле.
Берутся только партнёры из отчёта (plan_daily.json); остальные из выгрузки игнорируются.

    pip install openpyxl
    python plan_from_xlsx.py "март сентябрь.xlsx"
"""
import io, json, os, sys, collections
import openpyxl

# имя в отчёте -> ФИО_П в выгрузке
MATCH = {
    u'Айткулова А.': u'Айткулова Айжан',
    u'Оспанова Г': u'Оспанова Гульмира',
    u'Роза Ерасылова': u'Ерасылова Роза',
    u'Жапабаева Б.': u'Жапабаева Бахытгуль Бейбитовна',
    u'Токенова С.': u'Токенова Сара',
    u'Болатбек А.': u'Болатбек Абдуахмат',
    u'Илиясов Р.': u'Илиясов Рашид',
    u'Нысанбеков Е.': u'Нысанбеков Ербол',
    u'Мусаева Р.': u'Мусаева Рабинур',
    u'Назарова М.': u'Назарова Мукарям',
    u'Айтуганова Ю.': u'Айтуганова Юлия Константиновна',
    u'Полоз О.': u'Полоз Ольга',
    u'Кан Т.': u'Кан Татьяна',
    u'Куатова М.': u'Куатов Акжигит',          # ИП Куатов; Куатова М. в его списке операторов
    u'Черней Т.': u'Черней Татьяна',
    u'Кабиева А.': u'Кабиева Айгерим',
    u'Ли А.': u'Ли Александр',
    u'Калиаскар Б.': u'Калиаскар Бакытгул',
    u'Бут Р.': u'Бут Римма',
    u'Жандос Альсейтов': u'Жандос Альсейтов',
    u'Рузиева Зоя': u'Рузиева Зоя',
    u'Аубакирова А.': u'Аубакирова Ания',
    u'Рсалдин Е.': u'Рсалдин Ермухаммет',
    u'Омельченко С.': u'Омельченко Сергей',
    # Исмагамбетов М — в выгрузке нет, план не задан
}

src = sys.argv[1]
ws = openpyxl.load_workbook(src, read_only=True, data_only=True).worksheets[0]
rows = [r for r in list(ws.iter_rows(values_only=True))[1:] if r[0] and r[2]]
month = max(r[2] for r in rows)
people = collections.Counter()
for p, org, m, n, names in rows:
    if m == month:
        people[' '.join(p.split())] += n or 0

report = [r['name'] for r in json.load(io.open('plan_daily.json', encoding='utf-8'))['rows']]
plan = {}
for name in report:
    src_name = MATCH.get(' '.join(name.split()))       # в отчёте бывают неразрывные пробелы
    plan[name] = people.get(src_name) if src_name else None
    if plan[name] is None:
        print(u'нет плана: %s' % name)

io.open('plan_opu.json', 'w', encoding='utf-8').write(json.dumps(
    {'source': os.path.basename(src), 'month': month.strftime('%Y-%m'), 'plan': plan},
    ensure_ascii=False, indent=1))
print(u'plan_opu.json: месяц %s, партнёров %d, людей %d'
      % (month.strftime('%m.%Y'), len(plan), sum(v or 0 for v in plan.values())))
