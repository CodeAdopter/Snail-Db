#pragma once

__declspec(dllimport) void *__stdcall CreateFileW(const unsigned short *path, unsigned long access, unsigned long share, void *security, unsigned long disposition, unsigned long flags, void *from);
__declspec(dllimport) int __stdcall ReadFile(void *file, void *buffer, unsigned long size, unsigned long *read, void *overlapped);
__declspec(dllimport) int __stdcall WriteFile(void *file, const void *buffer, unsigned long size, unsigned long *written, void *overlapped);
__declspec(dllimport) int __stdcall CloseHandle(void *handle);
__declspec(dllimport) int __stdcall FlushFileBuffers(void *file);
__declspec(dllimport) int __stdcall GetFileSizeEx(void *file, long long *size);
__declspec(dllimport) int __stdcall SetFilePointerEx(void *file, long long distance, long long *moved, unsigned long method);
__declspec(dllimport) int __stdcall SetEndOfFile(void *file);
__declspec(dllimport) void *__stdcall CreateFileMappingW(void *file, void *security, unsigned long protect, unsigned long high, unsigned long low, const unsigned short *name);
__declspec(dllimport) void *__stdcall MapViewOfFile(void *mapping, unsigned long access, unsigned long high, unsigned long low, unsigned long long size);
__declspec(dllimport) int __stdcall UnmapViewOfFile(const void *base);
__declspec(dllimport) int __stdcall FlushViewOfFile(const void *base, unsigned long long size);
__declspec(dllimport) int __stdcall MoveFileExW(const unsigned short *from, const unsigned short *to, unsigned long flags);
__declspec(dllimport) int __stdcall DeleteFileW(const unsigned short *path);
__declspec(dllimport) int __stdcall CreateDirectoryW(const unsigned short *path, void *security);
__declspec(dllimport) int __stdcall MultiByteToWideChar(unsigned int page, unsigned long flags, const char *text, int bytes, unsigned short *wide, int chars);
__declspec(dllimport) void __stdcall AcquireSRWLockExclusive(void **lock);
__declspec(dllimport) void __stdcall ReleaseSRWLockExclusive(void **lock);
__declspec(dllimport) void __stdcall AcquireSRWLockShared(void **lock);
__declspec(dllimport) void __stdcall ReleaseSRWLockShared(void **lock);
__declspec(dllimport) int __stdcall SleepConditionVariableSRW(void **cond, void **lock, unsigned long ms, unsigned long flags);
__declspec(dllimport) void __stdcall WakeAllConditionVariable(void **cond);
__declspec(dllimport) void __stdcall GetSystemTimeAsFileTime(unsigned long long *time);
__declspec(dllimport) unsigned long __stdcall GetLastError(void);
__declspec(dllimport) void *__stdcall FindFirstFileW(const unsigned short *pattern, void *found);
__declspec(dllimport) int __stdcall FindNextFileW(void *find, void *found);
__declspec(dllimport) int __stdcall FindClose(void *find);
__declspec(dllimport) int __stdcall CreateHardLinkW(const unsigned short *link, const unsigned short *existing, void *security);
__declspec(dllimport) int __stdcall CopyFileW(const unsigned short *from, const unsigned short *to, int fail_if_exists);
__declspec(dllimport) int __stdcall WideCharToMultiByte(unsigned int page, unsigned long flags, const unsigned short *wide, int chars, char *text, int bytes, const char *fallback, int *used);

typedef struct sn_db_overlapped {
    unsigned long long internal, internal_high;
    unsigned long offset, offset_high;
    void *event;
} sn_db_overlapped;

#define SN_DB_PATH 1024

static int sn_db_wide(const char *path, int len, unsigned short *wide)
{
    int n = MultiByteToWideChar(65001, 0, path, len, wide, SN_DB_PATH - 1);
    if (n <= 0) return 0;
    for (int i = 0; i < n; i++) if (wide[i] == '/') wide[i] = '\\';
    wide[n] = 0;
    return 1;
}

static void *sn_db_open(const char *path, int len, int mode)
{
    unsigned short wide[SN_DB_PATH];
    if (!sn_db_wide(path, len, wide)) return 0;
    unsigned long access = mode == 0 ? 0x80000000ul : 0xC0000000ul;
    unsigned long share = mode == 4 ? 0 : 7;
    unsigned long disposition = mode == 0 ? 3 : mode == 1 ? 2 : mode == 3 ? 3 : 4;
    void *file = CreateFileW(wide, access, share, 0, disposition, 0x80, 0);
    return file == (void *)(long long)-1 ? 0 : file;
}

static long long sn_db_size(void *file)
{
    long long size = 0;
    if (!GetFileSizeEx(file, &size)) return -1;
    return size;
}

static long long sn_db_read_at(void *file, long long at, void *buffer, long long size)
{
    long long done = 0;
    while (done < size) {
        sn_db_overlapped where = {0};
        long long spot = at + done;
        where.offset = (unsigned long)spot;
        where.offset_high = (unsigned long)(spot >> 32);
        long long left = size - done;
        unsigned long part = left > 0x40000000 ? 0x40000000 : (unsigned long)left;
        unsigned long got = 0;
        if (!ReadFile(file, (char *)buffer + done, part, &got, &where) || got == 0) break;
        done += got;
    }
    return done;
}

static int sn_db_write_at(void *file, long long at, const void *data, long long size)
{
    long long done = 0;
    while (done < size) {
        sn_db_overlapped where = {0};
        long long spot = at + done;
        where.offset = (unsigned long)spot;
        where.offset_high = (unsigned long)(spot >> 32);
        long long left = size - done;
        unsigned long part = left > 0x40000000 ? 0x40000000 : (unsigned long)left;
        unsigned long put = 0;
        if (!WriteFile(file, (const char *)data + done, part, &put, &where) || put == 0) return 0;
        done += put;
    }
    return 1;
}

static int sn_db_sync(void *file) { return FlushFileBuffers(file); }

static int sn_db_truncate(void *file, long long size)
{
    long long moved = 0;
    return SetFilePointerEx(file, size, &moved, 0) && SetEndOfFile(file);
}

static void sn_db_close(void *file) { if (file) CloseHandle(file); }

static void *sn_db_map(void *file, long long size, void **mapping)
{
    *mapping = 0;
    if (size <= 0) return 0;
    void *m = CreateFileMappingW(file, 0, 0x02, (unsigned long)(size >> 32), (unsigned long)size, 0);
    if (!m) return 0;
    void *view = MapViewOfFile(m, 0x0004, 0, 0, (unsigned long long)size);
    if (!view) { CloseHandle(m); return 0; }
    *mapping = m;
    return view;
}

static void *sn_db_map_write(void *file, long long size, void **mapping)
{
    *mapping = 0;
    if (size <= 0) return 0;
    void *m = CreateFileMappingW(file, 0, 0x04, (unsigned long)(size >> 32), (unsigned long)size, 0);
    if (!m) return 0;
    void *view = MapViewOfFile(m, 0x0002, 0, 0, (unsigned long long)size);
    if (!view) { CloseHandle(m); return 0; }
    *mapping = m;
    return view;
}

static int sn_db_flush_view(void *view, long long size) { return FlushViewOfFile(view, (unsigned long long)size); }

static inline void sn_db_prefetch(const void *p) { __builtin_prefetch(p); }

static void sn_db_unmap(void *view, void *mapping)
{
    if (view) UnmapViewOfFile(view);
    if (mapping) CloseHandle(mapping);
}

static int sn_db_rename(const char *from, int from_len, const char *to, int to_len)
{
    unsigned short a[SN_DB_PATH], b[SN_DB_PATH];
    if (!sn_db_wide(from, from_len, a) || !sn_db_wide(to, to_len, b)) return 0;
    return MoveFileExW(a, b, 0x1 | 0x8);
}

static int sn_db_delete(const char *path, int len)
{
    unsigned short wide[SN_DB_PATH];
    return sn_db_wide(path, len, wide) && DeleteFileW(wide);
}

static int sn_db_make_folder(const char *path, int len)
{
    unsigned short wide[SN_DB_PATH];
    return sn_db_wide(path, len, wide) && CreateDirectoryW(wide, 0);
}

static void sn_db_read_lock(void **lock) { AcquireSRWLockShared(lock); }
static void sn_db_read_unlock(void **lock) { ReleaseSRWLockShared(lock); }
static void sn_db_write_lock(void **lock) { AcquireSRWLockExclusive(lock); }
static void sn_db_write_unlock(void **lock) { ReleaseSRWLockExclusive(lock); }

static void sn_db_wait(void **cond, void **lock, int ms) { SleepConditionVariableSRW(cond, lock, (unsigned long)ms, 0); }
static void sn_db_wake(void **cond) { WakeAllConditionVariable(cond); }

static int sn_db_link(const char *from, int from_len, const char *to, int to_len)
{
    unsigned short a[SN_DB_PATH], b[SN_DB_PATH];
    if (!sn_db_wide(from, from_len, a) || !sn_db_wide(to, to_len, b)) return 0;
    DeleteFileW(b);
    return CreateHardLinkW(b, a, 0) || CopyFileW(a, b, 0);
}

static int sn_db_last_error(void) { return (int)GetLastError(); }

typedef struct sn_db_found {
    unsigned long attributes;
    unsigned long times[6];
    unsigned long size_high, size_low, reserved0, reserved1;
    unsigned short name[260];
    unsigned short alternate[14];
} sn_db_found;

static long long sn_db_list(const char *path, int len, char *out, long long room)
{
    unsigned short wide[SN_DB_PATH];
    if (!sn_db_wide(path, len, wide)) return -1;
    int n = 0;
    while (wide[n]) n++;
    if (n + 3 > SN_DB_PATH) return -1;
    wide[n] = '\\';
    wide[n + 1] = '*';
    wide[n + 2] = 0;
    sn_db_found found;
    void *find = FindFirstFileW(wide, &found);
    if (find == (void *)(long long)-1) return -1;
    long long need = 0;
    do {
        if (found.attributes & 0x10) continue;
        char name[1024];
        int bytes = WideCharToMultiByte(65001, 0, found.name, -1, name, sizeof name, 0, 0);
        if (bytes <= 1) continue;
        name[bytes - 1] = '\n';
        if (need + bytes <= room) for (int i = 0; i < bytes; i++) out[need + i] = name[i];
        need += bytes;
    } while (FindNextFileW(find, &found));
    FindClose(find);
    return need;
}

__declspec(dllimport) unsigned long __stdcall GetCurrentThreadId(void);

#define SN_DB_READERS 256

typedef struct sn_db_reader {
    long long epoch;
    unsigned owner;
    unsigned depth;
    char pad[48];
} sn_db_reader;

static void *sn_db_enter(void *block, long long *global)
{
    sn_db_reader *slots = (sn_db_reader *)block;
    unsigned id = (unsigned)GetCurrentThreadId();
    unsigned at = (id * 2654435761u) >> 24;
    sn_db_reader *r = 0;
    for (int i = 0; i < SN_DB_READERS; i++) {
        sn_db_reader *s = &slots[(at + i) & (SN_DB_READERS - 1)];
        unsigned owner = __atomic_load_n(&s->owner, __ATOMIC_RELAXED);
        if (owner == id) { r = s; break; }
        unsigned none = 0;
        if (owner == 0 && __atomic_compare_exchange_n(&s->owner, &none, id, 0, __ATOMIC_ACQ_REL, __ATOMIC_RELAXED)) { r = s; break; }
    }
    if (!r) return 0;
    if (r->depth++ == 0) {
        __atomic_store_n(&r->epoch, __atomic_load_n(global, __ATOMIC_RELAXED), __ATOMIC_RELAXED);
        __atomic_thread_fence(__ATOMIC_SEQ_CST);
    }
    return r;
}

static void sn_db_leave(void *reader)
{
    sn_db_reader *r = (sn_db_reader *)reader;
    if (--r->depth == 0) __atomic_store_n(&r->epoch, 0, __ATOMIC_RELEASE);
}

static long long sn_db_retire_epoch(long long *global)
{
    __atomic_thread_fence(__ATOMIC_SEQ_CST);
    return __atomic_fetch_add(global, 1, __ATOMIC_SEQ_CST);
}

static long long sn_db_oldest_reader(void *block, long long *global)
{
    sn_db_reader *slots = (sn_db_reader *)block;
    __atomic_thread_fence(__ATOMIC_SEQ_CST);
    long long oldest = __atomic_load_n(global, __ATOMIC_SEQ_CST);
    for (int i = 0; i < SN_DB_READERS; i++) {
        long long e = __atomic_load_n(&slots[i].epoch, __ATOMIC_ACQUIRE);
        if (e != 0 && e < oldest) oldest = e;
    }
    return oldest;
}

static int sn_db_top_bit(unsigned long long x) { return 63 - __builtin_clzll(x); }
static void *sn_db_load_ptr(void **p) { return __atomic_load_n(p, __ATOMIC_ACQUIRE); }
static void sn_db_store_ptr(void **p, void *v) { __atomic_store_n(p, v, __ATOMIC_RELEASE); }
static int sn_db_load_i32(int *p) { return __atomic_load_n(p, __ATOMIC_ACQUIRE); }
static void sn_db_store_i32(int *p, int v) { __atomic_store_n(p, v, __ATOMIC_RELEASE); }

static long long sn_db_seq_begin(long long *seq)
{
    long long s;
    while ((s = __atomic_load_n(seq, __ATOMIC_ACQUIRE)) & 1) __builtin_ia32_pause();
    return s;
}

static int sn_db_seq_changed(long long *seq, long long s)
{
    __atomic_thread_fence(__ATOMIC_ACQUIRE);
    return __atomic_load_n(seq, __ATOMIC_RELAXED) != s;
}

static void sn_db_seq_write(long long *seq)
{
    __atomic_store_n(seq, *seq + 1, __ATOMIC_RELAXED);
    __atomic_thread_fence(__ATOMIC_RELEASE);
}

static void sn_db_seq_written(long long *seq)
{
    __atomic_store_n(seq, *seq + 1, __ATOMIC_RELEASE);
}

static unsigned char sn_db_read_record(unsigned char *to, const unsigned char *from, int size, unsigned *version, const unsigned char *mark)
{
    for (;;) {
        unsigned v = __atomic_load_n(version, __ATOMIC_ACQUIRE);
        if (v & 1) { __builtin_ia32_pause(); continue; }
        __builtin_memcpy(to, from, (unsigned long long)size);
        unsigned char m = *(volatile const unsigned char *)mark;
        __atomic_thread_fence(__ATOMIC_ACQUIRE);
        if (__atomic_load_n(version, __ATOMIC_RELAXED) == v) return m;
    }
}

static void sn_db_write_record(unsigned char *to, const unsigned char *from, int size, unsigned *version, unsigned char *mark, unsigned char m)
{
    __atomic_store_n(version, *version + 1, __ATOMIC_RELAXED);
    __atomic_thread_fence(__ATOMIC_RELEASE);
    __builtin_memcpy(to, from, (unsigned long long)size);
    *(volatile unsigned char *)mark = m;
    __atomic_store_n(version, *version + 1, __ATOMIC_RELEASE);
}

static long long sn_db_unix_ms(void)
{
    unsigned long long t = 0;
    GetSystemTimeAsFileTime(&t);
    return (long long)((t - 116444736000000000ull) / 10000);
}
