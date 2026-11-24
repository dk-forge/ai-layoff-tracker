"""Measure the new CTA inside the publisher's actual generated iframe."""
import json
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from cdp import Browser
from tests.test_widget_match_cta import PLUGIN, widget_document


class EmbeddedWidget(unittest.TestCase):
    def test_builder_iframe_does_not_clip_the_match_cta(self):
        widget = widget_document().replace('https://example.org/plugin/', '/')
        css = (PLUGIN / 'assets/widget.css').read_bytes()
        source = (PLUGIN / 'assets/health.js').read_text()
        builder = source[source.index('  function initWidgetBuilder()'):source.index('\n  initWidgetBuilder();')]
        parent = '''<!doctype html><html><body style="margin:0">
<select id="alt-widget-year" hidden></select><select id="alt-widget-state" hidden></select>
<textarea id="alt-widget-code" hidden></textarea><button id="alt-widget-copy" hidden>Copy</button>
<a id="alt-widget-tracker-link" hidden>Tracker</a><span id="alt-widget-copy-status" hidden></span>
<div id="preview"></div></body></html>'''

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path.startswith('/assets/widget.css'):
                    time.sleep(0.25)  # Exercise the iframe before its stylesheet arrives.
                content = widget.encode() if self.path.startswith('/widget?') else (
                    css if self.path.startswith('/assets/widget.css') else (
                        b'' if self.path.startswith('/assets/') else parent.encode()))
                self.send_response(200)
                self.send_header('Content-Type', 'text/css' if self.path.startswith('/assets/widget.css') else 'text/html')
                self.end_headers()
                self.wfile.write(content)

            def log_message(self, *args):
                pass

        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        origin = f'http://127.0.0.1:{server.server_port}'
        with Browser() as browser:
            for width in (320, 390, 1280):
                browser.resize(width, 900)
                browser.navigate(origin)
                browser.eval_js('window.altHealthData=' + json.dumps({
                    'widgetUrl': origin + '/widget', 'trackerUrl': origin + '/tracker'})
                    + ';function $(id){return document.getElementById(id)};'
                    + 'function get(){return Promise.resolve({states:[]})};'
                    + builder + ';initWidgetBuilder();'
                    + 'document.getElementById("preview").innerHTML=$("alt-widget-code").value;')
                deadline = time.monotonic() + 5
                bounds = None
                while time.monotonic() < deadline:
                    bounds = browser.eval_js('''(() => {
const frame=document.querySelector('iframe'), doc=frame?.contentDocument;
if(!doc || doc.readyState!=='complete')return null;
const link=doc.querySelector('.alt-widget-cta');
if(!link)return null;
const box=link.getBoundingClientRect();
return {bottom:box.bottom, height:box.height, frameHeight:frame.clientHeight};
})()''')
                    if bounds:
                        break
                    time.sleep(.02)
                self.assertIsNotNone(bounds, f'widget did not load at {width}px')
                self.assertGreaterEqual(bounds['height'], 44)
                self.assertLessEqual(bounds['bottom'], bounds['frameHeight'], f'CTA clipped at {width}px: {bounds}')
