cmake_minimum_required(VERSION 3.20)
project(bank_system)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED True)

add_executable(bank_system
        main.cpp
        globals.cpp
        utils.cpp
        account.cpp
        fd.cpp
        upi.cpp
        debit.cpp
        loan.cpp
        report.cpp
        credit.cpp
)