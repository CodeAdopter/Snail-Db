# Snail Db

> [!NOTE]
> **AI disclaimer:** Snail Db's code may be used to train, fine-tune, and evaluate AI models,
> including large language models. The copyright holder grants this in addition to the MPL 2.0,
> and models trained on the code are not covered by the MPL.

An embedded database for Snail programs, built for games, GUIs, and other apps with concurrent
readers and writers.

- Fixed-size records under 64-bit keys, with multiple records per key, text-keyed values, name
  lists, and journals.
- A database is a folder. No external dependencies.
- Lock-free point lookups.
- Writes are visible immediately. `commit()` makes them survive a process crash;
  `sync_writes = true` adds power-cut durability.

## Performance

LevelDB's [`db_bench`](https://github.com/google/leveldb#performance) suite: 1 million entries of a
16-byte key and 100-byte value, stored as 116-byte records under a `u64` key. Every write is
committed. Each cell is the median of three runs.

All benchmarks ran on Windows 11, Intel Core i9-14900KF, 128 GB RAM, at high priority on the 16
performance-core threads.

| Write | What it does | Time | Throughput |
|---|---|---|---|
| fillseq | Fill a new database in key order | 0.264 µs/op | 419.0 MB/s |
| fillsync | 1,000 writes, each flushed to the drive | 501.700 µs/op | 0.2 MB/s |
| fillrandom | Fill a new database in random order | 0.355 µs/op | 312.0 MB/s |
| overwrite | Write random keys into the filled database | 0.364 µs/op | 303.8 MB/s |

| Read | What it does | Time | Throughput |
|---|---|---|---|
| readrandom | Look up random keys (86% present) | 0.164 µs/op | 6.08 M reads/s |
| readseq | Read every entry in key order | 0.077 µs/op | 1,443.6 MB/s |
| readreverse | Read every entry in reverse key order | 0.076 µs/op | 1,463.1 MB/s |
| compact | Merge everything into one segment | 279.3 ms | — |
| readrandom, compacted | Same, after `compact` | 0.434 µs/op | 2.30 M reads/s |
| readseq, compacted | Same, after `compact` | 0.010 µs/op | 11,180.2 MB/s |
| readreverse, compacted | Same, after `compact` | 0.008 µs/op | 13,110.7 MB/s |

- Reads use the ~865,000 keys left by `overwrite`. All data fits in memory.
- Before `compact`, everything sits in the in-memory table, which sequential reads copy and sort.
  After, reads use one mapped segment.

## Comparisons

Workload: 1 million chess positions with 1 to 3 engine evaluations each, giving 2,001,149 records
of 64 bytes keyed by position hash. Each store keeps the deepest evaluation per engine and line.
One run per store, process-crash-safe commits, no power-cut durability, no compression.

| | Snail Db | SQLite | LMDB | libmdbx | RocksDB | LevelDB | Snail Db vs best other |
|---|---|---|---|---|---|---|---|
| insert 2,001,149 records, commit every 10,000 | 398 ms | 29,494 ms | 6,739 ms | 17,749 ms | 3,400 ms | 3,404 ms | **8.5x** |
| lookup right after inserting | 284 ns | 3,097 ns | 744 ns | 863 ns | 4,450 ns | 3,210 ns | **2.6x** |
| settle on disk | 290 ms | 24 ms | 124 ms | 473 ms | 723 ms | 977 ms | 0.08x |
| lookup, key present | 548 ns | 3,019 ns | 747 ns | 927 ns | 2,696 ns | 1,668 ns | **1.4x** |
| lookup, key absent | 20 ns | 2,449 ns | 697 ns | 814 ns | 897 ns | 1,451 ns | **34.4x** |
| range of 100 positions | 2.4 µs | 33.8 µs | 3.7 µs | 5.2 µs | 20.6 µs | 10.7 µs | **1.6x** |
| store one record, commit, read it back | 0.3 µs | 56.4 µs | 34.2 µs | 95.8 µs | 5.2 µs | 4.9 µs | **17.4x** |
| 3 readers + 1 writer: reads a second | 4.89 M | 0.64 M | 3.90 M | 3.37 M | 0.67 M | 0.79 M | **1.3x** |
| the same: writes a second | 3,278 k | 21 k | 118 k | 32 k | 453 k | 285 k | **7.2x** |
| reopen and first lookup | 1.0 ms | 1.5 ms | 3.9 ms | 35.3 ms | 2,357.8 ms | 249.8 ms | **1.5x** |
| size on disk | 125.5 MB | 124.1 MB | 287.2 MB | 512.0 MB | 159.8 MB | 159.2 MB | 0.99x |

| Snail Db is ahead by | SQLite | libmdbx | RocksDB | LevelDB | LMDB |
|---|---|---|---|---|---|
| insert 2,001,149 records, commit every 10,000 | 74.1x | 44.6x | 8.5x | 8.6x | 16.9x |
| lookup right after inserting | 10.9x | 3.0x | 15.7x | 11.3x | 2.6x |
| settle on disk | 0.08x | 1.6x | 2.5x | 3.4x | 0.43x |
| lookup, key present | 5.5x | 1.7x | 4.9x | 3.0x | 1.4x |
| lookup, key absent | 121x | 40.1x | 44.2x | 71.5x | 34.4x |
| range of 100 positions | 14.3x | 2.2x | 8.7x | 4.5x | 1.6x |
| store one record, commit, read it back | 200x | 339x | 18.5x | 17.4x | 121x |
| 3 readers + 1 writer: reads a second | 7.7x | 1.4x | 7.3x | 6.2x | 1.3x |
| the same: writes a second | 158x | 101x | 7.2x | 11.5x | 27.9x |
| reopen and first lookup | 1.5x | 34.6x | 2,310x | 245x | 3.8x |
| size on disk | 0.99x | 4.1x | 1.3x | 1.3x | 2.3x |
| **typical row** | **13.1x** | **9.6x** | **7.8x** | **7.4x** | **5.2x** |

- **First table:** the last column compares Snail Db with the best other store in each row.
- **Second table:** each store's result divided by Snail Db's; above 1 means Snail Db is faster or
  smaller. Columns run from biggest lead to smallest. The typical row is the geometric mean,
  excluding reopen, where RocksDB and LevelDB vary by seconds between runs.

| Store | Configuration |
|---|---|
| Snail Db | Defaults: 256 MB in memory before flushing |
| SQLite 3.45.3 | `WITHOUT ROWID` table keyed by (key, engine, line); WAL with `synchronous=NORMAL`; 256 MB cache; mapped reads; prepared statements; upsert keeps the deeper evaluation; one connection per thread |
| LMDB 1.0.2 | `MDB_NOSYNC`; one read transaction per thread, renewed for each lookup. `MDB_WRITEMAP` increased write throughput by up to 6x but made reads 1.6x slower, so it is disabled |
| libmdbx 0.14.4 | `MDBX_SAFE_NOSYNC`; byte- and time-triggered syncs disabled; file grows in 256 MB increments without shrinking. `MDBX_WRITEMAP` made commits take about 0.7 ms on Windows, so it is disabled |
| RocksDB 11.12 | Bloom filters on the 8-byte position prefix; 256 MB block cache; one background thread per core; level compaction with a 512 MB memtable budget; log sync disabled |
| LevelDB 1.23 | Bloom filters; 256 MB cache; 64 MB write buffer; log sync disabled |

The key-value stores use an 11-byte key (big-endian position, engine, line) and a 64-byte value.
They read before writing to keep the deeper evaluation, and use prefix seeks to fetch a position's
records.

**Caveats**

- SQLite's 24 ms settle is a WAL checkpoint; its records are already in final form, while Snail Db
  still flushes and merges. SQLite also runs general SQL; Snail Db offers key lookups, key ranges,
  and scans.
- Threaded results vary about ±25% between runs. LevelDB varied most: settle took 1.2 to 52 s and
  reopen 151 ms to 43 s.
- Lookups across 2 million records are bound by memory latency. With 40,000 cached records, three
  Snail Db readers reached 15.5 M reads/s (LMDB 5.3 M, libmdbx 4.7 M) and 2.6 M writes/s (125 k,
  82 k). Medians of three runs.

### Running the benchmarks

- `python bench/fetch.py` downloads pinned sources, checks their SHA-256 hashes, and builds LMDB,
  libmdbx, RocksDB, and LevelDB into `bench/vendor`.
- **db_bench:** `snailc build` in `bench/dbbench`, then run `build\dbbench.exe [ENTRIES] [FOLDER] [STORE...]`.
- **Comparison:** `snailc build` in `bench`, then run `build\bench.exe [POSITIONS] [FOLDER] [STORE...]`.
  Stores are `snaildb`, `sqlite`, `lmdb`, `mdbx`, `rocksdb`, and `leveldb`. Default: 1 million
  positions, all stores.
- The results above used `cmd /c start /b /wait /high /affinity FFFF <exe>`. `FFFF` selects this
  CPU's performance cores.

## Current support

| Feature | Support |
|---|---|
| 64-bit key lookups | Memory and mapped sorted segments; typically 100 to 600 ns |
| Concurrent reads and writes | Lock-free point lookups; a shared writer lock; disk I/O runs outside that lock |
| Multiple records per key | `same` bytes identify records within a key; `better` selects the winner |
| Latest-value tables | `newest_table` replaces matching records on each put |
| Text-keyed values | `kv` stores text keys with byte values |
| Deletion | `remove`, `remove_key`, and `unset` |
| Ordered reads | `range` and `each` in key order, `range_back` and `each_back` in reverse, and `each_kv` |
| Name lists | Strings assigned stable numeric IDs |
| Journals | Append-only entries with variable-length byte payloads |
| Crash recovery | Checksummed write-ahead log, written through a memory map and replayed on open |
| Power-cut durability | Optional disk syncs with `sync_writes = true` |
| Write-error reporting | `commit()` returns `bool`; `error` records the first failure |
| Segment checksums | One checksum per 64 KB of records, checked by `verify()` |
| Bloom filters | Skip segments for absent keys; lookups can take 20 to 30 ns |
| Online backup | `backup()` creates a database folder while other threads continue |
| Background flushing and merging | Automatic; `settle()` and `compact()` provide explicit control |
| Setup validation | Incompatible record layouts are rejected on open; API misuse reports an error and stops |

**Not yet supported:** group commit, separate writer locks per table, secondary indexes,
multi-process access, Linux, macOS, compression, or repair.

## Usage

1. Add `libs = ["C:/Snail/Snail Db/snaildb"]` to the project's `snail.toml` or `library.toml`.
2. `use snaildb/snaildb`, register tables, key-value stores, name lists, and journals, then call
   `open()`.
3. Every record starts with a `u64` key. The `same` bytes right after it tell records within a key
   apart; `same = 0` means one record per key.

**Examples:** [scores.snail](examples/scores.snail) covers scores, names, and journals.
[game.snail](examples/game.snail) adds settings, entity updates, ranges, and backup.

## API

Calls are methods on `Db`, except the `db_*` helpers.

### Setup and lifecycle

| Call | Behavior |
|---|---|
| `table(name, size, same, better)` | Register fixed-size records. `better(a, b)` returns whether `a` should replace `b`. `db_keep_first` rejects replacements. |
| `newest_table(name, size, same)` | Register a table where the latest matching put wins. |
| `kv(name, most)` | Register text keys with byte values. `most` is the combined key/value byte limit (1 to 65,535); keys must be nonempty. |
| `name_list(name)` | Register strings with IDs starting at 1, assigned in insertion order. |
| `journal(name, entry_size)` | Register append-only entries. The first 12 bytes hold a data offset (`i64`) and length (`u32`), filled by the journal. Use `DbEntry` when no extra fields are needed. |
| `open(folder)` | Open or create a database. Returns `bool`; details are in `error`. |
| `commit()` | Wait for pending writes to be logged and return success. Successful commits survive a process crash; `sync_writes = true` also requests disk syncs for power-cut durability. |
| `close()` / `release()` | `close` commits pending writes and stops background work, keeping the setup for reopening. `release` frees the setup; call it after closing. Check `commit()` explicitly when save failures must be handled. |

### Records

| Call | Behavior |
|---|---|
| `put(table, rec)` | Insert or update a record according to the table's replacement rule. Returns whether the table changed. |
| `put_held(table, rec)` | As above, with `db.guard.write()` already held. Release it with `db.guard.write_done()`. |
| `remove(table, rec)` | Delete the record matching its key and `same` bytes. |
| `remove_key(table, key)` | Delete a key from a table with `same = 0`. |
| `find(table, key, out)` | Copy the winning records for a key into a byte buffer. Order within the key is unspecified. |
| `range(table, from, to, visit)` | Visit records in key order, including both endpoints. |
| `each(table, visit)` | Visit all records in key order. |
| `range_back(table, from, to, visit)` / `each_back(table, visit)` | As `range` and `each`, in descending key order. |

### Values, names, and journals

| Call | Behavior |
|---|---|
| `set(kv, key, value)` / `get(kv, key, out)` | Replace a value or copy it into a byte buffer. `get` returns whether the key exists. |
| `unset(kv, key)` / `each_kv(kv, visit)` | Delete a key or visit all key-value pairs. Iteration follows hashed key order. |
| `name_id(list, text)` | Return a name's ID, adding it if needed. |
| `known_id(list, text)` / `name_of(list, id, out)` | Look up an existing ID (`0` if absent), or copy a name into a byte buffer. |
| `append(journal, entry, bytes, n)` | Append an entry and payload. Returns a zero-based ID, or `DbNone` on failure. Entries become readable after a successful commit. |
| `entries(journal)` / `entry(journal, id, out)` | Count readable entries or copy one entry. `entry` returns whether the ID exists. |
| `read_entry(journal, id, out, bytes)` | Copy an entry and its payload. Returns success. |

### Maintenance and settings

| Call or setting | Behavior |
|---|---|
| `settle()` | Flush memory and wait for scheduled merges. |
| `compact(table)` | Flush memory, then merge the table into one segment and discard deleted records. |
| `backup(folder)` | Create a database backup while other threads continue. Returns success. |
| `verify()` | Check every segment against its checksums. Returns success. |
| `stats(table)` | Stored record count, segments, memory, disk bytes, flushes, and merges. Record counts include older versions and deletion markers until merged. |
| `error` | First error since open, or `""`. |
| `live_most` | Memory threshold for flushing across tables; 256 MB by default. |
| `sync_writes` | Enable disk syncs for commits; `false` by default. |
| `db_key(text)` / `db_key2(group, item)` | Hash text to a key, or combine two `u32` values so a group's keys are contiguous for range reads. |

## Tests

- **All 17 tests:** `snailc run` in `tests/`.
- **Selected tests:** `snailc run crash model`.
- **Seeded model test** (repo root): `.\build\tests\store_test.exe build/tests/model-seeded model 12345`.

Each test runs in a fresh folder under `build/tests`, with each step as a separate process. Crash
tests exit without closing the database. Output is checked against the test's `.out` file.

| Test | Coverage |
|---|---|
| `crash`, `better`, `remove` | Recovery of committed records, improvements, deletions, journal entries, and names after exit without closing |
| `churn` | 300,000 keys written three times at random depths through repeated flushes and merges; checks winners, absent keys, and checksums |
| `model`, `model-newest` | 200,000 random operations checked against a reference model, including puts, deletions, lookups, ranges in both directions, flushes, merges, compactions, and reopens |
| `race`, `race-update` | Three readers validate records while a writer inserts, replaces, deletes, and re-adds records during flushing |
| `walk` | Ordered iteration returns every winning record exactly once |
| `fail-log`, `fail-flush`, `fail-retry` | Injected log and flush failures; checks write rejection, recovery of committed data, and flush retries |
| `setup`, `leftovers`, `kept` | Incompatible setup and second-opener rejection, resource cleanup, crash leftovers, and preservation of unregistered tables |
| `backup`, `kv` | Backup during writes; latest key-value data survives flushes and crash recovery |

## Limits

- **Windows only.** Other platforms need an OS layer in `snaildb/c/db_os.h`.
- **One open store per folder.** The `LOCK` file is exclusive, so a second opener fails, even in
  the same process.
- **Fixed record layouts.** A `u64` key and fixed-size records. At most 255 tables, counting those
  behind key-value stores but not name lists or journals. No secondary indexes or query language.
- **No transaction isolation or rollback.** Writes are visible before commit, and a commit covers
  all pending writes in the database, not just the calling thread's.
- **Replacement rules must be deterministic.** `better` must depend only on record contents and
  break meaningful ties regardless of arrival order. Use `newest_table` for latest-value semantics.
- **One writer lock across tables.** Disk I/O runs outside it, but `commit()` waits for logging.
  `put()` pauses during a flush once the live table reaches 2x `live_most`, so with the table being
  flushed, memory can approach 3x `live_most`. `set()` and `remove()` don't pause.
- **256 lock-free reader slots.** A thread keeps its slot from its first lookup until `release()`,
  even after it stops reading; threads past the first 256 fall back to a read lock. Stop all
  access before `close()`.
- **Range reads scan memory.** `range()`, `each()`, and their backward forms copy matching
  in-memory records before merging with disk, holding the read lock so writers wait. Small ranges
  can still scan a large memory table; a lower `live_most` helps range-heavy workloads.
- **Recovery needs the registered setup.** Open rejects a log containing an unregistered table or
  an incompatible record layout. Segments of unregistered tables are kept.
- **No compression or repair.** `verify()` detects corruption with segment checksums. Opening a
  segment checks only its header, and normal reads skip checksums.

## License

Copyright (c) 2026 Angelo Wolff. Open source under the [Mozilla Public License 2.0](LICENSE).

- Usable in any project, including closed-source and commercial games and apps.
- Changes to Snail Db's own files must stay available under the MPL 2.0 when shipped.
- `bench/vendor/leveldb`, `lmdb`, `mdbx`, and `rocksdb` come from those projects and keep the
  licenses in each folder. `bench/vendor/sqlite3.def` and `sqlite3.lib` describe SQLite, which is
  public domain.
