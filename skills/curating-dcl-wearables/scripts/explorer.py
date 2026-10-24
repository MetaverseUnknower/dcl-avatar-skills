#!/usr/bin/env python3
"""Open an unpublished Builder collection in the Decentraland desktop explorer and drive it from the shell through the
explorer's built-in MCP server (screenshots, camera, walking, emotes, UI clicks). Works for any agent with a shell.

usage:
  python3 explorer.py launch <collection-uuid> [--position 150,-150] [--env org] [--backpack] [--app PATH] [--port 8123]
  python3 explorer.py wait                       # until the MCP server answers and the scene is ready
  python3 explorer.py tools                      # list the MCP tools and their arguments
  python3 explorer.py call <tool> ['{"json": "args"}']
  python3 explorer.py screenshot out.png [--world-only] [--max-width 1280]
  python3 explorer.py quit

`launch` quits a running explorer first: the self-preview flag is only read at a cold start. The wallet signed in to
the explorer must own (or be a collaborator on) the collection, and --env must match where it lives (org = the
production Builder, zone = the dev Builder). Preview items show in the Backpack beside your owned items, equipped for
you only. Port 8123 is full local control of the client while it's open: only use it on a machine you trust.
"""
import argparse, base64, json, os, platform, subprocess, sys, time, urllib.error, urllib.request

MAC_APP = os.path.expanduser('~/Library/Application Support/DecentralandLauncherLight/latest/Decentraland.app')
WIN_APP = os.path.join(os.environ.get('LOCALAPPDATA', ''), 'DecentralandLauncherLight', 'latest', 'Decentraland.exe')
STATE = os.path.join(os.path.expanduser('~'), '.cache', 'dcl-explorer-mcp.json')


def endpoint(port):
    return f'http://127.0.0.1:{port}/unity-explorer-mcp'


def rpc(port, method, params=None, session=None, notify=False, timeout=120):
    body = {'jsonrpc': '2.0', 'method': method}
    if params is not None:
        body['params'] = params
    if not notify:
        body['id'] = int(time.time() * 1000)
    headers = {'Content-Type': 'application/json', 'Accept': 'application/json, text/event-stream'}
    if session:
        headers['Mcp-Session-Id'] = session
    req = urllib.request.Request(endpoint(port), json.dumps(body).encode(), headers)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        sid = r.headers.get('Mcp-Session-Id') or session
        text = r.read().decode()
    if notify or not text.strip():
        return None, sid
    if text.lstrip().startswith('{'):
        msg = json.loads(text)
    else:   # server-sent events: take the last data line
        msg = json.loads([l[5:] for l in text.splitlines() if l.startswith('data:')][-1])
    if 'error' in msg:
        raise RuntimeError(msg['error'])
    return msg.get('result'), sid


def session(port):
    result, sid = rpc(port, 'initialize', {'protocolVersion': '2025-06-18', 'capabilities': {},
                                           'clientInfo': {'name': 'dcl-curator', 'version': '1'}}, timeout=10)
    try:
        rpc(port, 'notifications/initialized', session=sid, notify=True, timeout=10)
    except urllib.error.HTTPError:
        pass
    return sid


def call(port, tool, args=None):
    sid = session(port)
    result, _ = rpc(port, 'tools/call', {'name': tool, 'arguments': args or {}}, session=sid, timeout=300)
    return result


def show(result):
    for c in (result or {}).get('content', []):
        if c.get('type') == 'text':
            print(c['text'])
        else:
            print(f"[{c.get('type')} {c.get('mimeType', '')}]")
    if (result or {}).get('isError'):
        sys.exit(1)


def running():
    if platform.system() == 'Darwin':
        return subprocess.run(['pgrep', '-x', 'Explorer'], capture_output=True).returncode == 0
    if platform.system() == 'Windows':
        out = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq Decentraland.exe'], capture_output=True, text=True).stdout
        return 'Decentraland.exe' in out
    return False


def quit_explorer():
    if platform.system() == 'Darwin':
        subprocess.run(['osascript', '-e', 'tell application id "com.Decentraland.Explorer" to quit'], capture_output=True)
    elif platform.system() == 'Windows':
        subprocess.run(['taskkill', '/IM', 'Decentraland.exe'], capture_output=True)
    for _ in range(30):
        if not running():
            return
        time.sleep(1)
    sys.exit('the explorer is still running: quit it, then launch again')


def launch(a):
    flags = ['--self-preview-builder-collections', a.collection, '--dclenv', a.env, '--position', a.position,
             '--mcp-port', str(a.port), '--skip-minimum-specs-screen']
    if a.backpack:
        flags += ['--force-open-backpack', 'true']
    if running():
        print('quitting the running explorer (self-preview is read only at a cold start)')
        quit_explorer()
    if platform.system() == 'Darwin':
        app = a.app or MAC_APP
        if not os.path.exists(app):
            sys.exit(f'explorer not found at {app}: install Decentraland from decentraland.org/download or pass --app')
        subprocess.run(['open', '-n', app, '--args', *flags], check=True)
    elif platform.system() == 'Windows':
        app = a.app or WIN_APP
        subprocess.Popen([app, *flags])
    else:
        sys.exit('no desktop explorer for this OS; use the deep link: decentraland://?self-preview-builder-collections='
                 f'{a.collection}&dclenv={a.env}&position={a.position}')
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    json.dump({'port': a.port}, open(STATE, 'w'))
    print('launched; sign in if the explorer asks, then: python3 explorer.py wait')


def wait(port, timeout=600):
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            r = call(port, 'get_scene_state')
            text = ' '.join(c.get('text', '') for c in r.get('content', []))
            state = json.loads(text) if text.strip().startswith('{') else {}
            if state.get('loadingStage') == 'Completed' and not state.get('loadingScreenOn'):
                print(text)
                return
        except (urllib.error.URLError, ConnectionError, RuntimeError, TimeoutError):
            pass
        time.sleep(5)
    sys.exit('timed out: is the explorer signed in? (the MCP server starts once loading completes)')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--port', type=int, default=None)
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('launch')
    p.add_argument('collection')
    p.add_argument('--position', default='150,-150', help='an empty parcel by default (the Builder uses 150,-150)')
    p.add_argument('--env', default='org', choices=['org', 'zone'])
    p.add_argument('--backpack', action='store_true', help='open the Backpack on arrival')
    p.add_argument('--app')
    sub.add_parser('wait')
    sub.add_parser('tools')
    p = sub.add_parser('call')
    p.add_argument('tool')
    p.add_argument('args', nargs='?', default='{}')
    p = sub.add_parser('screenshot')
    p.add_argument('out')
    p.add_argument('--world-only', action='store_true')
    p.add_argument('--max-width', type=int, default=1280)
    sub.add_parser('quit')
    a = ap.parse_args()
    saved = json.load(open(STATE)) if os.path.exists(STATE) else {}
    port = a.port or saved.get('port', 8123)

    if a.cmd == 'launch':
        a.port = port
        launch(a)
    elif a.cmd == 'wait':
        wait(port)
    elif a.cmd == 'tools':
        sid = session(port)
        result, _ = rpc(port, 'tools/list', session=sid)
        for t in result['tools']:
            props = t.get('inputSchema', {}).get('properties', {})
            print(f"{t['name']}({', '.join(props)}): {t.get('description', '').splitlines()[0][:110]}")
    elif a.cmd == 'call':
        show(call(port, a.tool, json.loads(a.args)))
    elif a.cmd == 'screenshot':
        r = call(port, 'screenshot', {'maxWidth': a.max_width, 'worldOnly': a.world_only})
        imgs = [c for c in r.get('content', []) if c.get('type') == 'image']
        if not imgs:
            show(r)
            sys.exit('no image returned')
        open(a.out, 'wb').write(base64.b64decode(imgs[0]['data']))
        print(a.out)
    elif a.cmd == 'quit':
        quit_explorer()


if __name__ == '__main__':
    main()
