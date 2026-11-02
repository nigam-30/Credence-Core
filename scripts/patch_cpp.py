import re

# 1. Update bank.h
with open('bank.h', 'r', encoding='utf-8') as f:
    bh = f.read()
if 'freeAccountHistory' not in bh:
    bh = bh.replace(
        'long long generateUniqueAccountNumber();',
        'long long generateUniqueAccountNumber();\nvoid freeAccountHistory(Account& acc);\nvoid cleanupAllAccounts();'
    )
    with open('bank.h', 'w', encoding='utf-8') as f:
        f.write(bh)

# 2. Update utils.cpp
with open('utils.cpp', 'r', encoding='utf-8') as f:
    u = f.read()

u = re.sub(
    r'cout << "CVV\s+: " << sysAcc\.card\.cvv << endl;',
    'cout << "CVV               : [PROTECTED]" << endl;',
    u
)
u = re.sub(
    r'cout << "PIN\s+: " << sysAcc\.card\.pin << endl;',
    'cout << "PIN               : [PROTECTED]" << endl;',
    u
)
if 'freeAccountHistory' not in u:
    u += '\n\nvoid freeAccountHistory(Account& acc) {\n    Transaction* curr = acc.history;\n    while (curr) {\n        Transaction* next = curr->next;\n        delete curr;\n        curr = next;\n    }\n    acc.history = nullptr;\n}\n\nvoid cleanupAllAccounts() {\n    for (auto& pair : accounts) {\n        freeAccountHistory(pair.second);\n    }\n}\n'

with open('utils.cpp', 'w', encoding='utf-8') as f:
    f.write(u)

# 3. Update credit.cpp
with open('credit.cpp', 'r', encoding='utf-8') as f:
    cred = f.read()

cred = re.sub(
    r'bool checkCreditCardEligibility\(Account &acc\) \{',
    'bool checkCreditCardEligibility(Account &acc) {\n    (void)acc;',
    cred
)
cred = re.sub(
    r'acc\.creditCardNumber = "5100" \+ to_string\(rand\(\) % 90000000 \+ 10000000\);',
    'acc.creditCardNumber = "5100 " + to_string(1000 + rand() % 9000) + " " + to_string(1000 + rand() % 9000) + " " + to_string(1000 + rand() % 9000);',
    cred
)
with open('credit.cpp', 'w', encoding='utf-8') as f:
    f.write(cred)

# 4. Update account.cpp
with open('account.cpp', 'r', encoding='utf-8') as f:
    acc_c = f.read()

acc_c = re.sub(
    r'cin >> acc\.balance;',
    'cin >> acc.balance;\n    if (acc.balance < 0.0) {\n        cout << "Negative initial deposit rejected. Setting balance to 0.00." << endl;\n        acc.balance = 0.0;\n    }',
    acc_c
)

old_pin = '''        cout << "Set 4-digit PIN for debit card: ";
        cin >> acc.card.pin;
        acc.card = generateDebitCard(acc.name);
        acc.hasDebitCard = true;'''

new_pin = '''        int userPin = 1234;
        cout << "Set 4-digit PIN for debit card: ";
        cin >> userPin;
        if (userPin < 1000 || userPin > 9999) userPin = 1000 + rand() % 9000;
        acc.card = generateDebitCard(acc.name);
        acc.card.pin = userPin;
        acc.hasDebitCard = true;'''

acc_c = acc_c.replace(old_pin, new_pin)
with open('account.cpp', 'w', encoding='utf-8') as f:
    f.write(acc_c)

# 5. Update debit.cpp
with open('debit.cpp', 'r', encoding='utf-8') as f:
    deb = f.read()

deb = re.sub(
    r'cout << "CVV\s+: " << acc\.card\.cvv << endl;',
    'cout << "CVV         : [PROTECTED]" << endl;',
    deb
)
deb = re.sub(
    r'cin >> amount;',
    'cin >> amount;\n    if (amount <= 0.0) {\n        cout << endl << "Invalid payment amount." << endl;\n        return;\n    }',
    deb
)
with open('debit.cpp', 'w', encoding='utf-8') as f:
    f.write(deb)

# 6. Update fd.cpp
with open('fd.cpp', 'r', encoding='utf-8') as f:
    fd_c = f.read()

fd_c = re.sub(
    r'cin >> amount;',
    'cin >> amount;\n    if (amount <= 0.0) {\n        cout << endl << "Invalid FD amount." << endl;\n        return;\n    }',
    fd_c
)
with open('fd.cpp', 'w', encoding='utf-8') as f:
    f.write(fd_c)

# 7. Update loan.cpp
with open('loan.cpp', 'r', encoding='utf-8') as f:
    ln = f.read()

ln = re.sub(
    r'cin >> amount;',
    'cin >> amount;\n    if (amount <= 0.0) {\n        cout << endl << "Invalid loan amount." << endl;\n        return;\n    }',
    ln
)
with open('loan.cpp', 'w', encoding='utf-8') as f:
    f.write(ln)

# 8. Update upi.cpp
with open('upi.cpp', 'r', encoding='utf-8') as f:
    up = f.read()

up = re.sub(
    r'cin >> amount;',
    'cin >> amount;\n    if (amount <= 0.0) {\n        cout << endl << "Invalid UPI payment amount." << endl;\n        return;\n    }',
    up
)
with open('upi.cpp', 'w', encoding='utf-8') as f:
    f.write(up)

# 9. Update main.cpp
with open('main.cpp', 'r', encoding='utf-8') as f:
    mn = f.read()

mn = mn.replace('case 14: return 0;', 'case 14: cleanupAllAccounts(); return 0;')
with open('main.cpp', 'w', encoding='utf-8') as f:
    f.write(mn)

print("C++ patch completed successfully.")
