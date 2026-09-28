#!/usr/bin/env python3
"""
Descarga los horarios públicos de la EINA (centro 110) desde la Consulta pública
de horarios de la Universidad de Zaragoza y los guarda en data/ en un formato
compacto para Eina 3D.

Solo usa la biblioteca estándar de Python. Hace las consultas despacio (una cada
pocos segundos) para no cargar el servidor de la Universidad.

Uso:  python scripts/scrape_sia.py [--out data] [--plan 716] [--delay 1.5]
"""
import argparse, datetime as dt, html, http.cookiejar, json, os, re, sys, time, urllib.parse, urllib.request
from html.parser import HTMLParser

try:  # en Windows, usa los certificados del sistema (si está instalado: pip install truststore)
    import truststore; truststore.inject_into_ssl()
except ImportError:
    pass

BASE = 'https://sia.unizar.es/pds/consultaPublica/'
CENTRO = '110'
UA = 'Eina3D-horarios/1.0 (+https://0xeriic.github.io/eina-3d/)'


class Selects(HTMLParser):
    """Recoge las opciones de cada <select name=...> de la página."""
    def __init__(self):
        super().__init__(); self.sel = {}; self.cur = None; self.opt = None
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == 'select':
            self.cur = a.get('name'); self.sel.setdefault(self.cur, [])
        elif tag == 'option' and self.cur:
            self.opt = {'v': a.get('value', ''), 't': '', 's': 'selected' in a}
            self.sel[self.cur].append(self.opt)
    def handle_endtag(self, tag):
        if tag == 'select': self.cur = None
        if tag == 'option': self.opt = None
    def handle_data(self, data):
        if self.opt is not None: self.opt['t'] += data


class Client:
    def __init__(self, delay):
        self.delay = delay
        self.op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        self.op.addheaders = [('User-Agent', UA), ('Accept-Language', 'es-ES,es;q=0.9')]
        self.n = 0

    def _open(self, url, data=None, tries=4):
        for i in range(tries):
            try:
                time.sleep(self.delay if self.n else 0); self.n += 1
                with self.op.open(url, data=data, timeout=60) as r:
                    raw = r.read(); ct = r.headers.get('Content-Type', '')
                m = re.search(r'charset=([\w-]+)', ct, re.I)
                return raw.decode(m.group(1) if m else 'iso-8859-1', errors='replace')
            except Exception as e:
                if i == tries - 1: raise
                print(f'  reintento {i+1} tras error: {e}', file=sys.stderr); time.sleep(5 * (i + 1))

    def get(self, path):
        return self._open(BASE + path)

    def post(self, path, fields):
        return self._open(BASE + path, urllib.parse.urlencode(fields, encoding='iso-8859-1').encode('ascii'))


def selects(page):
    p = Selects(); p.feed(page); return p.sel


def clean(t):
    return re.sub(r'\s+', ' ', html.unescape(t or '')).strip()


def academic_year(opts):
    today = dt.date.today()
    want = today.year if today.month >= 8 else today.year - 1
    years = sorted(int(o['v']) for o in opts if o['v'].isdigit())
    return want if want in years else max(y for y in years if y <= want) if any(y <= want for y in years) else years[-1]


def base_fields(year, plan=None, curso=None):
    f = [('planDocente', str(year)), ('centro', CENTRO)]
    if plan: f.append(('planEstudio', str(plan)))
    if curso: f.append(('curso', str(curso)))
    f += [('trimestre', '-2/-2'), ('idPestana', '1'), ('ultimoPlanDocente', str(year)), ('accesoSecretaria', 'null')]
    return f


ROOM_RE = re.compile(r'CRE\.?\s*(\d{4})\.([0-9A-Z]{2})\.([0-9A-Z]{3})', re.I)


def compact_plan(plan, name, year, cursos_data):
    """cursos_data: {curso: {'subjects': {code: name}, 'groups': [...], 'events': [...]}}"""
    d0 = dt.date(year, 8, 1)
    subjects, types, blocks, rooms = {}, [], [], []
    idx = lambda lst, v: lst.index(v) if v in lst else (lst.append(v) or len(lst) - 1)
    rows, seen = {}, set()
    cursos_out = {}
    for curso, cd in sorted(cursos_data.items()):
        cursos_out[str(curso)] = {'subjects': sorted(cd['subjects']), 'groups': cd['groups']}
        for code, nm in cd['subjects'].items():
            s = subjects.setdefault(code, {'n': nm, 'c': []})
            if curso not in s['c']: s['c'].append(curso)
        for e in cd['events']:
            if not isinstance(e, dict) or not e.get('start') or not e.get('codAsignatura'): continue
            if e.get('festivoNoLectivo'): continue
            code = str(e['codAsignatura'])
            if code not in subjects:
                subjects[code] = {'n': clean(e.get('title') or e.get('descAsignatura', '')).split(' - ', 1)[-1], 'c': [curso]}
            st = dt.datetime.strptime(e['start'][:16], '%Y-%m-%d %H:%M')
            en = dt.datetime.strptime((e.get('end') or e['start'])[:16], '%Y-%m-%d %H:%M')
            grp = str(e.get('grup') or e.get('codGrupo') or '')
            blk = clean(str(e.get('codigoBloque') or ''))
            typ = clean(e.get('tipologia') or '')
            aula = clean(e.get('aula') or '')
            key = (code, grp, blk, typ, aula, st, en)
            if key in seen: continue
            seen.add(key)
            rk = (code, grp, idx(blocks, blk), idx(types, typ), idx(rooms, aula), st.strftime('%H%M'), en.strftime('%H%M'))
            rows.setdefault(rk, []).append((st.date() - d0).days)
    sess = [[*k, sorted(v)] for k, v in sorted(rows.items(), key=lambda kv: (kv[0][0], kv[0][1], min(kv[1])))]
    return {
        'v': 1, 'plan': plan, 'name': name, 'year': year, 'd0': d0.isoformat(),
        'updated': dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'cursos': cursos_out, 'subjects': subjects, 'blocks': blocks, 'types': types, 'rooms': rooms,
        # cada sesión: [asignatura, grupo, bloque, tipología, aula, inicio HHMM, fin HHMM, [días desde d0]]
        's': sess,
    }


def load(path):
    try:
        with open(path, encoding='utf-8') as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=os.path.join(os.path.dirname(__file__), '..', 'data'))
    ap.add_argument('--plan', action='append', help='solo estos planes (se puede repetir)')
    ap.add_argument('--delay', type=float, default=1.5)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    c = Client(a.delay)
    first = selects(c.get('look[conpub]InicioPubHora?entradaPublica=true'))
    year = academic_year(first.get('planDocente', []))
    s0 = selects(c.post('look[conpub]ActualizarCombosPubHora?rnd=2', base_fields(year)))
    plans = [(o['v'], clean(o['t']).split(' - ', 1)[-1]) for o in s0.get('planEstudio', []) if o['v'].isdigit()]
    if a.plan: plans = [p for p in plans if p[0] in a.plan]
    print(f'Curso académico {year}/{year+1}: {len(plans)} planes')
    start = int(dt.datetime(year, 8, 1, tzinfo=dt.timezone.utc).timestamp())
    end = int(dt.datetime(year + 1, 8, 31, tzinfo=dt.timezone.utc).timestamp())
    index = []
    for plan, pname in plans:
        sp = selects(c.post('look[conpub]ActualizarCombosPubHora?rnd=3', base_fields(year, plan)))
        cursos = [o['v'] for o in sp.get('curso', []) if o['v'].lstrip('-').isdigit() and int(o['v']) > 0]
        cdata = {}
        for curso in cursos:
            sc = selects(c.post('look[conpub]ActualizarCombosPubHora?rnd=4', base_fields(year, plan, curso)))
            asig = [(o['v'], clean(o['t']).split(' - ', 1)[-1]) for o in sc.get('asignaturas', []) if o['v']]
            grps = [o['v'] for o in sc.get('grupos', []) if o['v']]
            if not asig:
                continue
            f = base_fields(year, plan, curso)
            for g in grps: f += [('grupos', g), ('grupo' + g, g)]
            for s, _ in asig: f += [('asignaturas', s), ('asignatura' + s, s)]
            c.post('look[conpub]MostrarPubHora?rnd=5', f)
            txt = c.get(f'[Ajax]selecionarRangoHorarios?rnd=6&start={start}&end={end}')
            try:
                ev = json.loads(txt)
            except json.JSONDecodeError:
                print(f'  {plan} curso {curso}: respuesta no válida', file=sys.stderr); ev = []
            ev = [e for e in ev if isinstance(e, dict) and 'start' in e]
            cdata[int(curso)] = {'subjects': dict(asig), 'groups': grps, 'events': ev}
            print(f'  {plan} {pname[:40]} · curso {curso}: {len(asig)} asignaturas, {len(ev)} sesiones', flush=True)
        if not cdata:
            continue
        out = compact_plan(int(plan), pname, year, cdata)
        path = os.path.join(a.out, f'p{plan}.json')
        prev = load(path)
        if prev and {k: v for k, v in prev.items() if k != 'updated'} == {k: v for k, v in out.items() if k != 'updated'}:
            out['updated'] = prev['updated']          # sin cambios: no se reescribe el archivo
        else:
            with open(path, 'w', encoding='utf-8') as fh:
                json.dump(out, fh, ensure_ascii=False, separators=(',', ':'))
            print(f'  -> {path} actualizado')
        index.append({'plan': int(plan), 'name': pname, 'cursos': sorted(int(k) for k in out['cursos']),
                      'sessions': sum(len(r[7]) for r in out['s']), 'updated': out['updated']})
    if a.plan and load(os.path.join(a.out, 'plans.json')):
        old = load(os.path.join(a.out, 'plans.json'))
        keep = {p['plan']: p for p in old.get('plans', [])}
        for p in index: keep[p['plan']] = p
        index = sorted(keep.values(), key=lambda p: p['plan'])
    idx = {'centro': int(CENTRO), 'year': year, 'updated': max((p['updated'] for p in index), default=''), 'plans': index}
    ipath = os.path.join(a.out, 'plans.json')
    if load(ipath) != idx:
        with open(ipath, 'w', encoding='utf-8') as fh:
            json.dump(idx, fh, ensure_ascii=False, separators=(',', ':'))
    print(f'Listo: {len(index)} planes guardados en {os.path.abspath(a.out)}')


if __name__ == '__main__':
    main()
