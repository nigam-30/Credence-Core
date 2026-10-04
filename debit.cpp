#include "bank.h"
#include <iostream>
using namespace std;

void debitPayment() {
    long long accNo;
    int pin;
    double amount;

    cout << "Enter account number: ";
    cin >> accNo;
    cout << "Enter PIN: ";
    cin >> pin;
    cout << "Enter payment amount (INR): ";
    cin >> amount;

    if (!binarySearch(accNo)) {
        cout << "\nAccount not found.\n";
        return;
    }

    Account& acc = accounts[accNo];
    if (!acc.hasDebitCard) {
        cout << "\nNo debit card linked to this account.\n";
        return;
    }

    if (acc.card.pin != pin) {
        cout << "\nInvalid PIN.\n";
        return;
    }

    if (acc.balance < amount) {
        cout << "\nInsufficient balance.\n";
        return;
    }

    acc.balance -= amount;
    addTransaction(acc, "Debit Card Payment", amount);

    cout << "\nDebit card payment successful.\n";
    cout << "Card Number : " << acc.card.cardNumber << endl;
    cout << "Name on Card: " << acc.card.nameOnCard << endl;
    cout << "Expiry Date : " << acc.card.expiry << endl;
    cout << "CVV         : " << acc.card.cvv << endl;
}