#include "bank.h"
#include <iostream>
using namespace std;

void orderCheque() {
    long long accNo;
    cout << "Enter account number: ";
    cin >> accNo;

    if (!binarySearch(accNo)) {
        cout << "\nInvalid account.\n";
        return;
    }

    Account& acc = accounts[accNo];
    if (acc.hasChequeBook) {
        cout << "\nCheque book already issued.\n";
        return;
    }

    acc.hasChequeBook = true;
    acc.chequeBook.startCheque = nextChequeStart;
    acc.chequeBook.used = 0;
    nextChequeStart += 25;

    cout << "\nCheque book ordered successfully.\n";
    cout << "Starting Cheque No: " << acc.chequeBook.startCheque << endl;
}
