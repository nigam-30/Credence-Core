#include "bank.h"
#include <iostream>
using namespace std;

void createUPI() {
    long long accNo;
    string upiId;

    cout << "Enter account number: ";
    cin >> accNo;
    cout << "Enter desired UPI ID: ";
    cin >> upiId;

    if (!binarySearch(accNo)) {
        cout << "\nAccount not found.\n";
        return;
    }

    if (upiMap.find(upiId) != upiMap.end()) {
        cout << "\nUPI ID already exists.\n";
        return;
    }

    upiMap[upiId] = accNo;
    cout << "\nUPI ID created successfully: " << upiId << endl;
}

void payUPI() {
    string fromUPI, toUPI;
    double amount;

    cout << "Enter your UPI ID: ";
    cin >> fromUPI;
    cout << "Enter recipient UPI ID: ";
    cin >> toUPI;
    cout << "Enter amount (INR): ";
    cin >> amount;

    if (upiMap.find(fromUPI) == upiMap.end() || upiMap.find(toUPI) == upiMap.end()) {
        cout << "\nInvalid UPI ID(s).\n";
        return;
    }

    long long fromAcc = upiMap[fromUPI];
    long long toAcc = upiMap[toUPI];

    if (accounts[fromAcc].balance < amount) {
        cout << "\nInsufficient balance.\n";
        return;
    }

    accounts[fromAcc].balance -= amount;
    accounts[toAcc].balance += amount;

    addTransaction(accounts[fromAcc], "UPI Payment Out", amount);
    addTransaction(accounts[toAcc], "UPI Payment In", amount);

    cout << "\nUPI payment successful.\n";
}