#include "bank.h"
#include <iostream>
#include <iomanip>
#include <sstream>
#include <algorithm>
using namespace std;

// ✅ Add transaction to linked list (history)
void addTransaction(Account& acc, const std::string& type, double amount) {
    Transaction* newT = new Transaction{type, amount, acc.history};
    acc.history = newT;
}

// ✅ Binary search on sorted account numbers
bool binarySearch(long long target) {
    int l = 0, r = (int)sortedAccountNumbers.size() - 1;
    while (l <= r) {
        int m = (l + r) / 2;
        if (sortedAccountNumbers[m] == target) return true;
        if (sortedAccountNumbers[m] < target) l = m + 1;
        else r = m - 1;
    }
    return false;
}

// ✅ Generate formatted debit card
DebitCard generateDebitCard(const std::string& name) {
    DebitCard card;

    // Generate 16-digit card number in xxxx xxxx xxxx xxxx format
    std::string raw = "4"; // Visa prefix
    for (int i = 0; i < 15; i++) raw += to_string(rand() % 10);

    card.cardNumber = "";
    for (int i = 0; i < 16; i++) {
        card.cardNumber += raw[i];
        if ((i + 1) % 4 == 0 && i != 15) card.cardNumber += " ";
    }

    // CVV: 3-digit
    card.cvv = 100 + rand() % 900;

    // Expiry: random MM/YY (next 5 years)
    int month = 1 + rand() % 12;
    int year = 26 + rand() % 5; // 2026–2030
    card.expiry = (month < 10 ? "0" : "") + to_string(month) + "/" + to_string(year);

    // Name on card
    card.nameOnCard = name;

    return card;
}

// ✅ Create system account (with debit card)
void createSystemAccount() {
    Account sys;
    sys.name = "SYSTEM";
    sys.accountNumber = SYSTEM_ACCOUNT_NO;
    sys.balance = 1000000000.0; // 1 Billion for system operations
    sys.loanAmount = 0;
    sys.fixedDeposit = 0;

    sys.hasDebitCard = true;
    sys.card = generateDebitCard(sys.name);
    sys.card.pin = 9999;

    accounts[SYSTEM_ACCOUNT_NO] = sys;
    sortedAccountNumbers.push_back(SYSTEM_ACCOUNT_NO);
    sort(sortedAccountNumbers.begin(), sortedAccountNumbers.end());
}

// ✅ Show test info (for demo)
void showTestInfo() {
    cout << "\n--- Demo Info ---\n";
    cout << "System Account No: " << SYSTEM_ACCOUNT_NO << endl;
    cout << "System UPI ID    : " << SYSTEM_UPI_ID << endl;

    if (accounts.find(SYSTEM_ACCOUNT_NO) != accounts.end()) {
        Account& sysAcc = accounts[SYSTEM_ACCOUNT_NO];
        if (sysAcc.hasDebitCard) {
            cout << "System Debit Card : " << sysAcc.card.cardNumber << endl;
            cout << "Name on Card      : " << sysAcc.card.nameOnCard << endl;
            cout << "Expiry Date       : " << sysAcc.card.expiry << endl;
            cout << "CVV               : " << sysAcc.card.cvv << endl;
            cout << "PIN               : " << sysAcc.card.pin << endl;
        } else {
            cout << "System Debit Card : [Not Assigned]\n";
        }
    }

    cout << "-----------------\n";
}