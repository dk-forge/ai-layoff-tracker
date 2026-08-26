"""Minimal Chrome DevTools Protocol client — stdlib only, no pip install.

Why hand-rolled: every workflow in this repo installs from a hash-pinned lock
(see CLAUDE.md). Adding playwright/websocket-client to that lock to render one
page would drag a browser download and a transitive tree into runners that hold
WP_API_KEY and OPENROUTER_API_KEY. Chrome is already present on GitHub-hosted
ubuntu runners and on the owner's Mac, and the slice of CDP we need is
"navigate, then evaluate one expression". That is ~150 lines of RFC 6455
client framing, so we own it rather than importing it.

Not a general-purpose client. It speaks exactly enough to:
  launch headless Chrome -> open a target -> Page.navigate -> Runtime.evaluate.
"""

import base64
import json
import os
import shutil
import socket
import struct
import subprocess
import tempfile
import time
import urllib.request

# Where Chrome actually lives, most-likely-first. GitHub's ubuntu-latest image
# ships google-chrome-stable on PATH; macOS keeps it inside the .app bundle.
CHROME_CANDIDATES = (
    os.environ.get('CHROME_BIN') or '',
    'google-chrome-stable',
    'google-chrome',
    'chromium-browser',
    'chromium',
    '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    '/Applications/Chromium.app/Contents/MacOS/Chromium',
)

BROWSER_UA = ('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 '
              '(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36')


class CDPError(RuntimeError):
    pass


class CDPUnavailable(CDPError):
    """No usable Chrome. Distinct from 'Chrome ran and the check failed' —
    callers must resolve this to UNKNOWN, never to a pass (CLAUDE.md)."""


def find_chrome():
    for cand in CHROME_CANDIDATES:
        if not cand:
            continue
        if os.path.sep in cand:
            if os.path.exists(cand) and os.access(cand, os.X_OK):
                return cand
        else:
            found = shutil.which(cand)
            if found:
                return found
    return None


class _WS:
    """RFC 6455 client. Text frames only, which is all CDP sends."""

    def __init__(self, url, timeout=30):
        assert url.startswith('ws://'), url
        rest = url[len('ws://'):]
        hostport, _, path = rest.partition('/')
        host, _, port = hostport.partition(':')
        self.sock = socket.create_connection((host, int(port or 80)), timeout=timeout)
        self.sock.settimeout(timeout)
        key = base64.b64encode(os.urandom(16)).decode()
        req = (
            'GET /%s HTTP/1.1\r\n'
            'Host: %s\r\n'
            'Upgrade: websocket\r\n'
            'Connection: Upgrade\r\n'
            'Sec-WebSocket-Key: %s\r\n'
            'Sec-WebSocket-Version: 13\r\n\r\n'
        ) % (path, hostport, key)
        self.sock.sendall(req.encode())
        self._buf = b''
        while b'\r\n\r\n' not in self._buf:
            chunk = self.sock.recv(4096)
            if not chunk:
                raise CDPError('websocket handshake closed early')
            self._buf += chunk
        head, _, self._buf = self._buf.partition(b'\r\n\r\n')
        if b'101' not in head.split(b'\r\n')[0]:
            raise CDPError('websocket handshake refused: %r' % head[:200])

    def _recv_exact(self, n):
        while len(self._buf) < n:
            chunk = self.sock.recv(65536)
            if not chunk:
                raise CDPError('websocket closed')
            self._buf += chunk
        out, self._buf = self._buf[:n], self._buf[n:]
        return out

    def send(self, text):
        payload = text.encode()
        n = len(payload)
        header = bytearray([0x81])  # FIN + text
        if n < 126:
            header.append(0x80 | n)
        elif n < (1 << 16):
            header.append(0x80 | 126)
            header += struct.pack('>H', n)
        else:
            header.append(0x80 | 127)
            header += struct.pack('>Q', n)
        mask = os.urandom(4)
        header += mask
        masked = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
        self.sock.sendall(bytes(header) + masked)

    def recv(self):
        """Return one complete text message, reassembling continuation frames."""
        chunks = []
        while True:
            b0, b1 = self._recv_exact(2)
            fin = b0 & 0x80
            opcode = b0 & 0x0F
            length = b1 & 0x7F
            if length == 126:
                length = struct.unpack('>H', self._recv_exact(2))[0]
            elif length == 127:
                length = struct.unpack('>Q', self._recv_exact(8))[0]
            data = self._recv_exact(length) if length else b''
            if opcode == 0x8:
                raise CDPError('websocket close frame')
            if opcode == 0x9:  # ping -> pong, keep the connection alive
                self.sock.sendall(b'\x8a\x80' + os.urandom(4))
                continue
            if opcode == 0xA:
                continue
            chunks.append(data)
            if fin:
                return b''.join(chunks).decode('utf-8', 'replace')

    def close(self):
        try:
            self.sock.close()
        except Exception:
            pass


# How many times to RELAUNCH Chrome when it comes up but never hands us a debug
# target. Measured on the deploy contrast step, which reddened main twice on
# 2026-08-26 (runs 32946362017 and the retry) with "Chrome never exposed a debug
# target: timed out" at ONE viewport width while every other width passed
# cleanly, producing exit 3 UNKNOWN -> red main + an alert. A fresh headless
# Chrome occasionally wedges on launch in CI and comes straight up on a clean
# relaunch, so the fix is to retry the LAUNCH, with a fresh process and profile.
#
# THIS IS NOT A LONGER TIMEOUT, and must never become one. `_wait_for_target`
# keeps its own 30s deadline: a launch that is genuinely dead still resolves to
# CDPUnavailable -> UNKNOWN after every attempt, never to a pass. Only a
# transient launch/connection flake is retried, and a retry that keeps failing
# is still exactly the UNKNOWN it was before.
LAUNCH_ATTEMPTS = 3
LAUNCH_BACKOFF = (1.0, 3.0)  # seconds before the 2nd and 3rd attempt


class Browser:
    """Headless Chrome, one tab, context-managed."""

    def __init__(self, width=1280, height=900, timeout=60):
        self.timeout = timeout
        self.width, self.height = width, height
        self._proc = None
        self._ws = None
        self._id = 0
        self._profile = None

    def __enter__(self):
        chrome = find_chrome()
        if not chrome:
            # A MISSING browser is not a transient launch flake — retrying it
            # only stalls. It is UNKNOWN immediately, exactly as before.
            raise CDPUnavailable(
                'no Chrome/Chromium found. Set CHROME_BIN, or install Chrome. '
                'This is UNKNOWN, not a pass.')
        last = None
        for attempt in range(1, LAUNCH_ATTEMPTS + 1):
            try:
                self._launch(chrome)
                return self
            except CDPUnavailable as exc:
                # Chrome came up (or tried to) and never exposed a usable debug
                # target within the deadline. Tear this attempt's process and
                # profile down and try a CLEAN relaunch — the wall does not move.
                last = exc
                self._teardown()
                if attempt < LAUNCH_ATTEMPTS:
                    delay = LAUNCH_BACKOFF[min(attempt - 1, len(LAUNCH_BACKOFF) - 1)]
                    print('    Chrome did not expose a debug target (attempt %d/%d): '
                          'relaunching in %.0fs' % (attempt, LAUNCH_ATTEMPTS, delay))
                    time.sleep(delay)
        # Every launch attempt failed to connect. This stays UNKNOWN, never a
        # pass: a transient flake is healed, a Chrome that will not come up is
        # still reported as unmeasured.
        raise CDPUnavailable(
            'Chrome never exposed a debug target after %d launch attempts: %s. '
            'This is UNKNOWN, not a pass.' % (LAUNCH_ATTEMPTS, last))

    def _launch(self, chrome):
        """One launch: start Chrome, connect to its debug target, enable the
        domains. Raises CDPUnavailable on a launch/connection flake so
        __enter__ can retry it with a fresh process."""
        port = _free_port()
        self._profile = tempfile.mkdtemp(prefix='alt-cdp-')
        args = [
            chrome,
            '--headless=new',
            '--disable-gpu',
            '--no-sandbox',
            '--disable-dev-shm-usage',
            '--hide-scrollbars',
            '--no-first-run',
            '--no-default-browser-check',
            '--disable-extensions',
            '--disable-background-networking',
            '--remote-debugging-port=%d' % port,
            '--user-data-dir=%s' % self._profile,
            '--window-size=%d,%d' % (self.width, self.height),
            '--user-agent=%s' % BROWSER_UA,
            'about:blank',
        ]
        self._proc = subprocess.Popen(
            args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            ws_url = self._wait_for_target(port)
            self._ws = _WS(ws_url, timeout=self.timeout)
            self.call('Page.enable')
            self.call('Runtime.enable')
            self.call('Emulation.setDeviceMetricsOverride', {
                'width': self.width, 'height': self.height,
                'deviceScaleFactor': 1, 'mobile': self.width < 768})
        except (CDPError, OSError) as exc:
            # A wedged launch: the target never appeared, the websocket
            # handshake failed, or the first command timed out on a Chrome that
            # is not really up. All are the same transient class — surface them
            # as CDPUnavailable so __enter__ relaunches rather than resolving to
            # a FAIL/PASS on a browser that never rendered anything.
            raise CDPUnavailable('launch did not connect: %s' % exc)

    def _wait_for_target(self, port, deadline=30):
        end = time.time() + deadline
        last = None
        while time.time() < end:
            try:
                raw = urllib.request.urlopen(
                    'http://127.0.0.1:%d/json/list' % port, timeout=2).read()
                for t in json.loads(raw):
                    if t.get('type') == 'page' and t.get('webSocketDebuggerUrl'):
                        return t['webSocketDebuggerUrl']
            except Exception as exc:  # chrome is still booting
                last = exc
            time.sleep(0.25)
        raise CDPUnavailable('Chrome never exposed a debug target: %s' % last)

    def call(self, method, params=None, timeout=None):
        self._id += 1
        mid = self._id
        self._ws.send(json.dumps({'id': mid, 'method': method,
                                  'params': params or {}}))
        end = time.time() + (timeout or self.timeout)
        while time.time() < end:
            msg = json.loads(self._ws.recv())
            if msg.get('id') != mid:
                continue  # an event, or a reply we already gave up on
            if 'error' in msg:
                raise CDPError('%s: %s' % (method, msg['error']))
            return msg.get('result', {})
        raise CDPError('%s timed out' % method)

    def resize(self, width, height):
        self.width, self.height = width, height
        self.call('Emulation.setDeviceMetricsOverride', {
            'width': width, 'height': height,
            'deviceScaleFactor': 1, 'mobile': width < 768})

    def navigate(self, url, settle=2.5):
        self.call('Page.navigate', {'url': url}, timeout=self.timeout)
        # Poll readyState rather than trusting one load event: the dashboard
        # paints its charts from /aggregate after DOMContentLoaded.
        end = time.time() + self.timeout
        while time.time() < end:
            try:
                if self.eval_js('document.readyState') == 'complete':
                    break
            except CDPError:
                pass
            time.sleep(0.25)
        time.sleep(settle)

    def eval_js(self, expression, await_promise=False):
        res = self.call('Runtime.evaluate', {
            'expression': expression,
            'returnByValue': True,
            'awaitPromise': await_promise,
        })
        if res.get('exceptionDetails'):
            desc = res['exceptionDetails'].get('exception', {}).get(
                'description') or json.dumps(res['exceptionDetails'])[:400]
            raise CDPError('page threw: %s' % desc)
        return res.get('result', {}).get('value')

    def _teardown(self):
        """Close the websocket, stop Chrome, and remove the profile — best
        effort, never raises. Used both to clean up a failed launch before a
        retry and to exit the context. Resets the handles so a retry starts from
        a known-empty state."""
        if self._ws:
            try:
                self._ws.close()
            except Exception:
                pass
            self._ws = None
        if self._proc:
            try:
                self._proc.terminate()
                try:
                    self._proc.wait(timeout=10)
                except Exception:
                    self._proc.kill()
            except Exception:
                pass
            self._proc = None
        if self._profile:
            shutil.rmtree(self._profile, ignore_errors=True)
            self._profile = None

    def __exit__(self, *exc):
        self._teardown()
        return False


def _free_port():
    s = socket.socket()
    s.bind(('127.0.0.1', 0))
    port = s.getsockname()[1]
    s.close()
    return port
