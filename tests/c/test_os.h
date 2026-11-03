#pragma once

__declspec(dllimport) void *__stdcall CreateFileW(const unsigned short *path, unsigned long access, unsigned long share, void *security, unsigned long disposition, unsigned long flags, void *from);
__declspec(dllimport) int __stdcall CloseHandle(void *handle);
__declspec(dllimport) unsigned long __stdcall WaitForSingleObject(void *handle, unsigned long ms);
__declspec(dllimport) int __stdcall MultiByteToWideChar(unsigned int page, unsigned long flags, const char *text, int bytes, unsigned short *wide, int chars);
__declspec(dllimport) int __stdcall WideCharToMultiByte(unsigned int page, unsigned long flags, const unsigned short *wide, int chars, char *text, int bytes, const char *fallback, int *used);
__declspec(dllimport) int __stdcall CreateProcessW(const unsigned short *app, unsigned short *command, void *process_security, void *thread_security, int inherit, unsigned long flags, void *environment, const unsigned short *folder, void *startup, void *info);
__declspec(dllimport) int __stdcall GetExitCodeProcess(void *process, unsigned long *code);
__declspec(dllimport) int __stdcall TerminateProcess(void *process, unsigned int code);
__declspec(dllimport) unsigned long __stdcall GetModuleFileNameW(void *module, unsigned short *name, unsigned long size);

typedef struct sn_test_security {
    unsigned long length;
    void *descriptor;
    int inherit;
} sn_test_security;

typedef struct sn_test_startup {
    unsigned long cb;
    unsigned short *reserved, *desktop, *title;
    unsigned long x, y, width, height, columns, rows, fill, flags;
    unsigned short show, reserved2;
    unsigned char *reserved3;
    void *input, *output, *error;
} sn_test_startup;

typedef struct sn_test_process {
    void *process, *thread;
    unsigned long process_id, thread_id;
} sn_test_process;

#define SN_TEST_COMMAND 8192

static int sn_test_run(const char *command, int command_len, const char *out, int out_len, int ms)
{
    unsigned short wide_command[SN_TEST_COMMAND], wide_out[1024];
    int n = MultiByteToWideChar(65001, 0, command, command_len, wide_command, SN_TEST_COMMAND - 1);
    int m = MultiByteToWideChar(65001, 0, out, out_len, wide_out, 1023);
    if (n <= 0 || m <= 0) return -1;
    wide_command[n] = 0;
    wide_out[m] = 0;
    sn_test_security inherited = { sizeof inherited, 0, 1 };
    void *file = CreateFileW(wide_out, 0x40000000ul, 1, &inherited, 2, 0x80, 0);
    if (file == (void *)(long long)-1) return -1;
    sn_test_startup startup = {0};
    startup.cb = sizeof startup;
    startup.flags = 0x100;
    startup.output = file;
    startup.error = file;
    sn_test_process info = {0};
    if (!CreateProcessW(0, wide_command, 0, 0, 1, 0, 0, 0, &startup, &info)) {
        CloseHandle(file);
        return -1;
    }
    int code;
    if (WaitForSingleObject(info.process, (unsigned long)ms) != 0) {
        TerminateProcess(info.process, 1);
        WaitForSingleObject(info.process, 0xFFFFFFFFul);
        code = -2;
    } else {
        unsigned long c = 0;
        GetExitCodeProcess(info.process, &c);
        code = (int)c;
    }
    CloseHandle(info.thread);
    CloseHandle(info.process);
    CloseHandle(file);
    return code;
}

static int sn_test_self(char *out, int room)
{
    unsigned short wide[1024];
    unsigned long n = GetModuleFileNameW(0, wide, 1024);
    if (n == 0 || n >= 1024) return 0;
    int bytes = WideCharToMultiByte(65001, 0, wide, (int)n, out, room, 0, 0);
    return bytes > 0 ? bytes : 0;
}
