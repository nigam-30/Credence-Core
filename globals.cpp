#include "bank.h"
#include <unordered_map>
#include <vector>

// ✅ Define global containers
std::unordered_map<long long, Account> accounts;
std::vector<long long> sortedAccountNumbers;
std::unordered_map<std::string, long long> upiMap;

// Additional globals
int nextChequeStart = 100000;