with open('flask_app.py', 'r', encoding='utf-8') as f:
    c = f.read()

target = '''def load_profiles():
    if not os.path.exists(PROFILES_JSON):
        base_file = os.path.join(BASE_DIR, "user_profiles.json")
        if os.path.exists(base_file):
            try:
                with open(base_file, "r") as f:
                    data = json.load(f)
                with open(PROFILES_JSON, "w") as f:
                    json.dump(data, f, indent=4)
                return data
            except Exception:
                pass
        return {}
    try:
        with open(PROFILES_JSON, "r") as f:
            return json.load(f)
    except Exception:
        return {}'''

replacement = '''def load_profiles():
    data = {}
    if not os.path.exists(PROFILES_JSON):
        base_file = os.path.join(BASE_DIR, "user_profiles.json")
        if os.path.exists(base_file):
            try:
                with open(base_file, "r") as f:
                    data = json.load(f)
                with open(PROFILES_JSON, "w") as f:
                    json.dump(data, f, indent=4)
            except Exception:
                pass
    else:
        try:
            with open(PROFILES_JSON, "r") as f:
                data = json.load(f)
        except Exception:
            data = {}

    try:
        from database import get_db
        from models import AccountBalance
        with get_db() as db:
            balances = db.query(AccountBalance).all()
            for b in balances:
                if b.account_number in data:
                    data[b.account_number]["balance"] = f"{b.balance_paise / 100:.2f}"
    except Exception:
        pass
    return data'''

c_norm = c.replace('\r\n', '\n')
target_norm = target.replace('\r\n', '\n')
if target_norm in c_norm:
    c_norm = c_norm.replace(target_norm, replacement.replace('\r\n', '\n'), 1)
    with open('flask_app.py', 'w', encoding='utf-8') as f:
        f.write(c_norm)
    print('Updated load_profiles successfully')
else:
    print('Target not found in flask_app.py')
