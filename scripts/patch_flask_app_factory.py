with open('flask_app.py', 'r', encoding='utf-8') as f:
    c = f.read()

target = 'app = Flask(__name__, static_folder=BASE_DIR, static_url_path="")'
replacement = '''from backend.app import create_app
app = create_app()
app.static_folder = BASE_DIR
app.static_url_path = ""'''

c_norm = c.replace('\r\n', '\n')
target_norm = target.replace('\r\n', '\n')
if target_norm in c_norm:
    c_norm = c_norm.replace(target_norm, replacement.replace('\r\n', '\n'), 1)
    with open('flask_app.py', 'w', encoding='utf-8') as f:
        f.write(c_norm)
    print('Replaced app in flask_app.py with create_app() successfully')
else:
    print('Target not found in flask_app.py')
