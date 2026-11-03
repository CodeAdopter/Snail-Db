#pragma once
typedef struct sqlite3 sqlite3;
typedef struct sqlite3_stmt sqlite3_stmt;
__declspec(dllimport) int sqlite3_open_v2(const char *name, sqlite3 **db, int flags, const char *vfs);
__declspec(dllimport) int sqlite3_close_v2(sqlite3 *db);
__declspec(dllimport) int sqlite3_exec(sqlite3 *db, const char *sql, void *callback, void *arg, void *error);
__declspec(dllimport) int sqlite3_prepare_v2(sqlite3 *db, const char *sql, int bytes, sqlite3_stmt **stmt, const char **tail);
__declspec(dllimport) int sqlite3_bind_int64(sqlite3_stmt *stmt, int at, long long value);
__declspec(dllimport) int sqlite3_bind_blob(sqlite3_stmt *stmt, int at, const void *data, int bytes, void *destructor);
__declspec(dllimport) int sqlite3_step(sqlite3_stmt *stmt);
__declspec(dllimport) int sqlite3_reset(sqlite3_stmt *stmt);
__declspec(dllimport) long long sqlite3_column_int64(sqlite3_stmt *stmt, int column);
__declspec(dllimport) int sqlite3_finalize(sqlite3_stmt *stmt);
__declspec(dllimport) const char *sqlite3_errmsg(sqlite3 *db);
__declspec(dllimport) const char *sqlite3_libversion(void);
__declspec(dllimport) int sqlite3_initialize(void);
