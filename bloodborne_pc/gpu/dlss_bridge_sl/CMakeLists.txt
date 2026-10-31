# SPDX-FileCopyrightText: Copyright 2026 bbport contributors
# SPDX-License-Identifier: MIT
#
# bbport_dlss_sl.dll: the DLSS bridge on NVIDIA Streamline (bbport_dlss_sl_bridge.cpp). Built
# separately from the port, like ../dlss_bridge:
#   cmake -S gpu/dlss_bridge_sl -B out/dlss-sl-vs17 -G "Visual Studio 17 2022" -A x64 \
#         -DSTREAMLINE_SDK_ROOT=<Streamline SDK release> -DVULKAN_INCLUDE=<Vulkan-Headers include>
#   cmake --build out/dlss-sl-vs17 --config Release

cmake_minimum_required(VERSION 3.20)
project(bbport_dlss_sl LANGUAGES CXX)

set(STREAMLINE_SDK_ROOT "" CACHE PATH "NVIDIA Streamline SDK root (contains include/ and bin/x64)")
set(VULKAN_INCLUDE "" CACHE PATH "Vulkan-Headers include directory")

if (NOT WIN32 OR NOT CMAKE_SIZEOF_VOID_P EQUAL 8)
    message(FATAL_ERROR "The Streamline DLSS bridge is Windows x64 only")
endif()
if (NOT EXISTS "${STREAMLINE_SDK_ROOT}/include/sl.h")
    message(FATAL_ERROR "Set STREAMLINE_SDK_ROOT to the NVIDIA Streamline SDK (github.com/NVIDIA-RTX/Streamline releases)")
endif()

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_MSVC_RUNTIME_LIBRARY "MultiThreaded")

# Streamline is loaded at run time (sl.interposer.dll): nothing to link.
add_library(bbport_dlss_sl SHARED bbport_dlss_sl_bridge.cpp ../dlss_bridge/bbport_dlss_bridge.h)
target_include_directories(bbport_dlss_sl PRIVATE "${STREAMLINE_SDK_ROOT}/include" "${VULKAN_INCLUDE}")
target_compile_definitions(bbport_dlss_sl PRIVATE NOMINMAX WIN32_LEAN_AND_MEAN)
