import sys
import os
import urllib.parse

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from flask_app import app

class VercelPathMiddleware:
    def __init__(self, wsgi_app):
        self.wsgi_app = wsgi_app

    def __call__(self, environ, start_response):
        # 1. Check query string for __path passed by vercel.json rewrite
        qs = environ.get('QUERY_STRING', '')
        params = urllib.parse.parse_qs(qs)
        if '__path' in params and params['__path']:
            path = params['__path'][0]
            if not path.startswith('/'):
                path = '/' + path
            environ['PATH_INFO'] = path
        # 2. Check HTTP_X_NOW_ROUTE_MATCHES if provided by Vercel
        elif environ.get('HTTP_X_NOW_ROUTE_MATCHES'):
            matches = urllib.parse.parse_qs(environ['HTTP_X_NOW_ROUTE_MATCHES'])
            if '1' in matches and matches['1']:
                path = matches['1'][0]
                if not path.startswith('/'):
                    path = '/' + path
                environ['PATH_INFO'] = path
        # 3. Check HTTP_X_FORWARDED_URI
        elif environ.get('HTTP_X_FORWARDED_URI'):
            environ['PATH_INFO'] = environ['HTTP_X_FORWARDED_URI'].split('?')[0]
        elif environ.get('PATH_INFO') in ['/api/index', '/api/index.py', '/api', '']:
            environ['PATH_INFO'] = '/'

        return self.wsgi_app(environ, start_response)

app.wsgi_app = VercelPathMiddleware(app.wsgi_app)
application = app
