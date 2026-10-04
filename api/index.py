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
        candidates = [
            environ.get('HTTP_X_FORWARDED_URI'),
            environ.get('HTTP_X_ORIGINAL_URL'),
            environ.get('RAW_URI'),
            environ.get('REQUEST_URI'),
            environ.get('HTTP_X_MATCHED_PATH')
        ]
        
        orig_path = None
        for cand in candidates:
            if cand and not any(ch in cand for ch in ['*', '(', ')', '\\']):
                orig_path = cand.split('?')[0]
                break
                
        if orig_path and orig_path not in ['/api/index', '/api/index.py', '/api']:
            environ['PATH_INFO'] = orig_path
        elif environ.get('PATH_INFO') in ['/api/index', '/api/index.py', '/api', '']:
            environ['PATH_INFO'] = '/'

        return self.wsgi_app(environ, start_response)

app.wsgi_app = VercelPathMiddleware(app.wsgi_app)
application = app
