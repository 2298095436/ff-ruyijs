"""Read-only live flight-query probe for an explicitly selected itinerary.

Uses a fresh native Context, the repository's complete environment profile,
and real page scripts. Never imports cookies, uses a browser, adds a flight
to a basket, logs in, or submits payment. Output excludes request bodies,
cookie values and query strings. Run manually, outside the offline CI suite.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
from pathlib import Path
import time
from urllib.parse import urlencode, urlsplit

from ruyijs import Context


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--origin', required=True)
    parser.add_argument('--destination', required=True)
    parser.add_argument('--date', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    datetime.strptime(args.date, '%Y-%m-%d')
    if not all(len(code) == 3 and code.isascii() and code.isalpha()
               for code in [args.origin, args.destination]):
        parser.error('origin and destination must be three-letter airport codes')
    profile = json.loads((Path(__file__).resolve().parents[1] / 'profiles/firefox-environment.json').read_text())
    profile.pop('location', None)
    url = 'https://www.easyjet.com/deeplink?' + urlencode({
        'dep': args.origin.upper(), 'dest': args.destination.upper(), 'dd': args.date,
        'isOneWay': 'on', 'apax': 1, 'cpax': 0, 'ipax': 0, 'fare': 'Y', 'lang': 'EN'})
    result = {'startedAtUTC': datetime.now(timezone.utc).isoformat(),
        'package': importlib.metadata.version('ruyijs'), 'pureNative': True,
        'browserAssist': False, 'importedSession': False, 'requestBodiesIncluded': False,
        'basketMutations': False, 'status': 'starting', 'responses': []}
    try:
        with Context(timeout=45, tls=160, http_timeout=25, http_read_timeout=15) as ctx:
            ctx.configure_environment(profile)
            ctx.configure_clock('system')
            shell = Path(ctx.shell)
            result['shellSHA256'] = hashlib.sha256(shell.read_bytes()).hexdigest()
            ctx.navigate(url)
            deadline = time.monotonic() + 90
            blocked = None
            while time.monotonic() < deadline:
                state = ctx.eval("""({title:document.title,path:location.pathname,ready:document.readyState,
                    welcome:!!document.querySelector('#welcomeModal[open]'),
                    flightButtons:document.querySelectorAll('button[aria-labelledby^="standard-"]').length})""")
                rows = ctx.net_log()
                queries = [r for r in rows if r['method'] == 'POST'
                           and urlsplit(r['url']).path == '/funnel/api/query']
                statuses = [r.get('status', 0) for r in queries]
                result.update(state=state, queryStatuses=statuses)
                if state['title'] == 'Access Denied':
                    result['status'] = 'security-blocked'
                    break
                if 200 in statuses and state['flightButtons']:
                    result['status'] = 'query-passed'
                    break
                if any(status >= 400 for status in statuses):
                    blocked = blocked or time.monotonic()
                    if time.monotonic() - blocked > 8:
                        result['status'] = 'security-blocked'
                        break
                if state['welcome'] and blocked is None:
                    if ctx.eval('!!document.querySelector("#ensRejectAll")'):
                        ctx.click('document.querySelector("#ensRejectAll")', hold_ms=0)
                    ctx.click('document.querySelector("button[data-cy=welcome-modal__button--confirm]")', hold_ms=0)
                try:
                    ctx.advance(100, max_tasks=16, max_wall_ms=200)
                except Exception as error:
                    if 'Awaiting human js challenge' not in str(error):
                        raise
                    result.setdefault('pageErrors', []).append(str(error))
                    blocked = blocked or time.monotonic()
            else:
                result['status'] = 'timed-out'
            for row in ctx.net_log():
                parsed = urlsplit(row.get('url', ''))
                if parsed.hostname == 'www.easyjet.com' and '/api/' in parsed.path:
                    result['responses'].append({'method': row['method'], 'path': parsed.path,
                        'status': row.get('status'), 'error': row.get('error')})
            result['consoleErrors'] = [row['text'][:500] for row in ctx.console_log()
                                       if row.get('level') == 'error'][:15]
    except Exception as error:
        result.update(status='runtime-error', error=str(error))
    result['completedAtUTC'] = datetime.now(timezone.utc).isoformat()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)
    return 0 if result['status'] == 'query-passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
