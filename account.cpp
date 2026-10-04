#include "bank.h"
#include <iostream>
#include <algorithm>   // ✅ for sort()
#include <random>
using namespace std;

// ✅ Unique 14-digit Account Number Generator
long long generateUniqueAccountNumber() {
    static random_device rd;
    static mt19937_64 rng(rd());
    uniform_int_distribution<long long> dist(10000000000000LL, 99999999999999LL);
    long long newAccNo;
    do {
        newAccNo = dist(rng);
    } while (accounts.find(newAccNo) != accounts.end() || newAccNo == SYSTEM_ACCOUNT_NO);
    return newAccNo;
}

// ✅ Create Account
void createAccount() {
    Account acc;
    cout << "Enter name: ";
    cin.ignore();
    getline(cin, acc.name);

    // ✅ System generates 14-digit random unique account number
    acc.accountNumber = generateUniqueAccountNumber();
    cout << "Your new Account Number is: " << acc.accountNumber << endl;

    // ✅ Initial deposit
    cout << "Enter initial deposit amount: ";
    cin >> acc.balance;

    acc.loanAmount = 0;
    acc.fixedDeposit = 0;
    acc.history = nullptr;

    char choice;
    cout << "Do you want a debit card? (y/n): ";
    cin >> choice;

    if (choice == 'y' || choice == 'Y') {
        // ✅ User sets PIN, rest system generates
        cout << "Set 4-digit PIN for debit card: ";
        cin >> acc.card.pin;
        acc.card = generateDebitCard(acc.name);
        acc.hasDebitCard = true;

        cout << "\nDebit Card issued successfully!\n";
        cout << "Card Number : " << acc.card.cardNumber << endl;
        cout << "Name on Card: " << acc.card.nameOnCard << endl;
        cout << "Expiry Date : " << acc.card.expiry << endl;
        cout << "CVV         : " << acc.card.cvv << endl;
    } else {
        acc.hasDebitCard = false;
    }

    accounts[acc.accountNumber] = acc;
    sortedAccountNumbers.push_back(acc.accountNumber);
    sort(sortedAccountNumbers.begin(), sortedAccountNumbers.end());

    cout << "\nAccount created successfully with initial deposit of INR "
         << acc.balance << ".\n";
}

// ✅ Check Balance
void checkBalance() {
    long long accNo;
    cout << "Enter account number: ";
    cin >> accNo;

    if (!binarySearch(accNo)) {
        cout << "\nAccount not found.\n";
        return;
    }

    cout << "Balance for account " << accNo << " : INR " << accounts[accNo].balance << endl;
}

// ✅ Transfer Money
void transferMoney() {
    long long fromAcc, toAcc;
    double amount;

    cout << "Enter sender account number: ";
    cin >> fromAcc;
    cout << "Enter receiver account number: ";
    cin >> toAcc;
    cout << "Enter amount: ";
    cin >> amount;

    if (!binarySearch(fromAcc) || !binarySearch(toAcc)) {
        cout << "\nInvalid account number(s).\n";
        return;
    }

    if (accounts[fromAcc].balance < amount) {
        cout << "\nInsufficient balance.\n";
        return;
    }

    accounts[fromAcc].balance -= amount;
    accounts[toAcc].balance += amount;

    addTransaction(accounts[fromAcc], "Transfer Out", amount);
    addTransaction(accounts[toAcc], "Transfer In", amount);

    cout << "\nTransfer successful.\n";
}
