#include "bank.h"
#include <iostream>
using namespace std;

void manageFD() {
    long long accNo;
    double amount;
    cout << "Enter account number: ";
    cin >> accNo;
    cout << "Enter FD amount: ";
    cin >> amount;

    if (!binarySearch(accNo)) {
        cout << "\nAccount not found.\n";
        return;
    }

    if (accounts[accNo].balance < amount) {
        cout << "\nInsufficient balance.\n";
        return;
    }

    accounts[accNo].fixedDeposit += amount;
    accounts[accNo].balance -= amount;
    addTransaction(accounts[accNo], "FD Created", amount);

    cout << "\nFD created successfully.\n";
}

void withdrawFD() {
    long long accNo;
    cout << "Enter account number: ";
    cin >> accNo;

    if (!binarySearch(accNo)) {
        cout << "\nAccount not found.\n";
        return;
    }

    double amount = accounts[accNo].fixedDeposit;
    if (amount <= 0) {
        cout << "\nNo FD available.\n";
        return;
    }

    accounts[accNo].balance += amount;
    accounts[accNo].fixedDeposit = 0;
    addTransaction(accounts[accNo], "FD Withdrawn", amount);

    cout << "\nFD withdrawn successfully.\n";
}

void calculateFDMaturity() {
    long long accNo;
    cout << "Enter account number: ";
    cin >> accNo;

    if (!binarySearch(accNo)) {
        cout << "\nAccount not found.\n";
        return;
    }

    double amount = accounts[accNo].fixedDeposit;
    if (amount <= 0) {
        cout << "\nNo FD available.\n";
        return;
    }

    double maturity = amount * 1.05; // 5% simple interest demo
    cout << "\nFD Maturity Amount for account " << accNo << " : INR " << maturity << endl;
}