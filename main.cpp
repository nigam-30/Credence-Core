#include "bank.h"
#include <iostream>
using namespace std;

int main() {
    createSystemAccount();
    showTestInfo();

    int choice;
    while (true) {
        cout << "\n--- Banking Menu ---\n";
        cout << "1. Create Account\n";
        cout << "2. Check Balance\n";
        cout << "3. Transfer Money\n";
        cout << "4. Apply Loan\n";
        cout << "5. Repay Loan\n";
        cout << "6. Calculate FD Maturity\n";
        cout << "7. Create FD\n";
        cout << "8. Withdraw FD\n";
        cout << "9. View Report\n";
        cout << "10. Create UPI\n";
        cout << "11. Pay via UPI\n";
        cout << "12. Debit Card Payment\n";
        cout << "13. Apply Credit Card\n";
        cout << "14. Exit\n";
        cout << "Enter choice: ";
        cin >> choice;

        switch (choice) {
            case 1: createAccount(); break;
            case 2: checkBalance(); break;
            case 3: transferMoney(); break;
            case 4: applyLoan(); break;
            case 5: repayLoan(); break;
            case 6: calculateFDMaturity(); break;
            case 7: manageFD(); break;
            case 8: withdrawFD(); break;
            case 9: viewReport(); break;
            case 10: createUPI(); break;
            case 11: payUPI(); break;
            case 12: debitPayment(); break;
            case 13: {
                long long accNo;
                cout << "Enter account number: ";
                cin >> accNo;
                if (!binarySearch(accNo)) {
                    cout << "Account not found.\n";
                    break;
                }
                applyCreditCard(accounts[accNo]);
                break;
            }
            case 14: return 0;
            default: cout << "Invalid choice.\n";
        }
    }
}