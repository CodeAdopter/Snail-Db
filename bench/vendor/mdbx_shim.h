#pragma once
#include <winerror.h>

#ifndef _WIN32_WINNT
#define _WIN32_WINNT 0x0A00
#endif
#ifndef MDBX_BUILD_SHARED_LIBRARY
#define MDBX_BUILD_SHARED_LIBRARY 0
#endif

typedef void *HANDLE;
typedef unsigned long DWORD;
typedef void *PVOID;

#ifndef _WINDOWS_
#define _WINDOWS_
#define MDBX_SHIM_SKIPPED_WINDOWS_H
#endif
#ifndef _WINNT_
#define _WINNT_
#define MDBX_SHIM_SKIPPED_WINNT_H
#endif

#include "mdbx.h"

typedef struct MDBX_version_info MDBX_version_info;

#ifdef MDBX_SHIM_SKIPPED_WINDOWS_H
#undef _WINDOWS_
#undef MDBX_SHIM_SKIPPED_WINDOWS_H
#endif
#ifdef MDBX_SHIM_SKIPPED_WINNT_H
#undef _WINNT_
#undef MDBX_SHIM_SKIPPED_WINNT_H
#endif
