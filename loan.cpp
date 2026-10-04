//
// Created by Nigam on 01-02-2026.
//
#include "bank.h"
#include <iostream>
using namespace std;

void applyLoan() {
    long long accNo;
    double amount;
    cout << "Enter account number: ";
    cin >> accNo;
    cout << "Enter loan amount: ";
    cin >> amount;

    if (!binarySearch(accNo)) {
        cout << "\nAccount not found.\n";
        return;
    }

    accounts[accNo].loanAmount += amount;
    accounts[accNo].balance += amount;
    addTransaction(accounts[accNo], "Loan Applied", amount);

    cout << "\nLoan approved and credited.\n";
}

void repayLoan() {
    long long accNo;
    double amount;
    cout << "Enter account number: ";
    cin >> accNo;
    cout << "Enter repayment amount: ";
    cin >> amount;

    if (!binarySearch(accNo)) {
        cout << "\nAccount not found.\n";
        return;
    }

    if (accounts[accNo].balance < amount) {
        cout << "\nInsufficient balance.\n";
        return;
    }

    if (amount > accounts[accNo].loanAmount) amount = accounts[accNo].loanAmount;

    accounts[accNo].balance -= amount;
    accounts[accNo].loanAmount -= amount;
    addTransaction(accounts[accNo], "Loan Repayment", amount);

    cout << "\nLoan repayment successful.\n";
}