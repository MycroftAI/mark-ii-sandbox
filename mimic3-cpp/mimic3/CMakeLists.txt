project(mimic3)

cmake_minimum_required(VERSION 3.13)

find_package(PkgConfig)
pkg_check_modules(ESPEAK_NG REQUIRED espeak-ng)
pkg_check_modules(JSONCPP REQUIRED jsoncpp)
pkg_check_modules(SPDLOG REQUIRED spdlog)
pkg_check_modules(SNDFILE REQUIRED sndfile)

set(ONNXRUNTIME_ROOTDIR "/usr/local/include/onnxruntime")

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

ADD_EXECUTABLE(mimic3 main.cpp)

target_link_libraries(mimic3
                      onnxruntime
                      ${ESPEAK_NG_LIBRARIES}
                      ${JSONCPP_LIBRARIES}
                      ${SPDLOG_LIBRARIES}
                      ${SNDFILE_LIBRARIES})

target_link_directories(mimic3 PUBLIC
                        ${ONNXRUNTIME_ROOTDIR}/lib)

target_include_directories(mimic3 PUBLIC
                           ${ONNXRUNTIME_ROOTDIR}/include
                           ${ESPEAK_NG_INCLUDE_DIRS}
                           ${JSONCPP_INCLUDE_DIRS}
                           ${SPDLOG_INCLUDE_DIRS}
                           ${SNDFILE_INCLUDE_DIRS})

target_compile_options(mimic3 PUBLIC
                       ${ESPEAK_NG_CFLAGS_OTHER}
                       ${JSONCPP_CFLAGS_OTHER}
                       ${SPDLOG_CFLAGS_OTHER}
                       ${SNDFILE_CFLAGS_OTHER})
