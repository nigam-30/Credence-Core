#include "bank.h"
#include <iostream>
using namespace std;

// ✅ Eligibility check
bool checkCreditCardEligibility(Account &acc) {
    int age;
    double income;
    int cibil;
    string citizenship;

    cout << "\n--- Credit Card Eligibility Check ---\n";
    cout << "Enter Age: ";
    cin >> age;
    cout << "Enter Annual Income (₹): ";
    cin >> income;
    cout << "Enter CIBIL Score: ";
    cin >> cibil;
    cout << "Enter Citizenship (e.g. Indian): ";
    cin >> citizenship;

    if (age < 18 || age > 70) {
        cout << "❌ Not eligible: Age criteria not met.\n";
        return false;
    }
    if (income < 100000) {
        cout << "❌ Not eligible: Minimum income ₹1,00,000 required.\n";
        return false;
    }
    if (cibil < 750) {
        cout << "❌ Not eligible: CIBIL score must be ≥ 750.\n";
        return false;
    }
    if (citizenship != "Indian") {
        cout << "❌ Not eligible: Must be Indian resident.\n";
        return false;
    }

    cout << "✅ Eligibility passed! Proceed to application form.\n";
    return true;
}

// ✅ Application form
void applyCreditCard(Account &acc) {
    if (!checkCreditCardEligibility(acc)) return;

    cout << "\n--- Credit Card Application Form ---\n";
    string pan, address, incomeProof;
    cout << "Enter PAN Number: ";
    cin >> pan;
    cin.ignore();
    cout << "Enter Residential Address: ";
    getline(cin, address);
    cout << "Enter Income Proof (Salary Slip/Bank Statement/ITR): ";
    getline(cin, incomeProof);

    // Generate card details
    acc.hasCreditCard = true;
    acc.creditCardNumber = "5100" + to_string(rand() % 90000000 + 10000000);
    acc.creditCardLimit = (acc.balance >= 100000) ? 200000 : 100000;

    cout << "\n🎉 Credit Card issued successfully!\n";
    cout << "Card Number : " << acc.creditCardNumber << endl;
    cout << "Limit       : ₹" << acc.creditCardLimit << endl;
    cout << "PAN Verified: " << pan << endl;
}