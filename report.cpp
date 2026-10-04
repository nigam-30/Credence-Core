//
// Created by Nigam on 01-02-2026.
//
#include "bank.h"
#include <iostream>
#include <iomanip>
using namespace std;

void viewReport() {
    cout << "\n--- Account Report ---\n";
    for (auto& pair : accounts) {
        long long accNo = pair.first;
        auto& acc = pair.second;
        cout << "Account No: " << accNo
             << " | Name: " << acc.name
             << " | Balance: INR " << fixed << setprecision(2) << acc.balance
             << " | Loan: INR " << fixed << setprecision(2) << acc.loanAmount
             << " | FD: INR " << fixed << setprecision(2) << acc.fixedDeposit << endl;
    }
    cout << "----------------------\n";
}