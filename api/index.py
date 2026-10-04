import sys
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from flask_app import app

class VercelPathMiddleware:
    def __init__(self, wsgi_app):
        self.wsgi_app = wsgi_app

    def __call__(self, environ, start_response):
        path = environ.get('PATH_INFO', '')
        # Vercel may rewrite path or pass original in headers
        orig = environ.get('HTTP_X_FORWARDED_URI') or environ.get('HTTP_X_MATCHED_PATH') or environ.get('HTTP_X_NOW_ROUTE_MATCHES')
        if orig:
            clean_orig = orig.split('?')[0]
            if clean_orig and not clean_orig.startswith('/api/index'):
                environ['PATH_INFO'] = clean_orig
        elif path in ['/api/index', '/api/index.py', '/api', '']:
            environ['PATH_INFO'] = '/'
            
        return self.wsgi_app(environ, start_response)

app.wsgi_app = VercelPathMiddleware(app.wsgi_app)
application = app
