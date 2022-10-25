cmake_minimum_required(VERSION 3.13)

# Project
project(mimic3 C CXX)
string(APPEND CMAKE_CXX_FLAGS " -Wall -Wextra")
string(APPEND CMAKE_C_FLAGS " -Wall -Wextra")

add_subdirectory(mimic3)
