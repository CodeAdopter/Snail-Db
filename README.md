# Snail Db

Snail Db is an embedded database for Snail programs, built for games, GUIs, and other
applications with concurrent readers and writers. It stores fixed-size records under 64-bit
keys, with support for multiple records per key, text-keyed values, name lists, and journals.

A database is a folder, and the library has no external dependencies. Point lookups are
lock-free. Writes become visible immediately; a successful `commit()` makes them recoverable
after a process crash. Set `sync_writes = true` for power-cut durability.

## Comparisons

| | Snail Db | SQLite | LMDB | libmdbx | RocksDB | LevelDB | Snail Db vs best other |
|---|---|---|---|---|---|---|---|
| insert 2,001,149 records, commit every 10,000 | 349 ms | 29,281 ms | 7,763 ms | 12,898 ms | 3,600 ms | 3,420 ms | **9.8x** |
| lookup right after inserting | 276 ns | 2,857 ns | 707 ns | 857 ns | 4,527 ns | 3,116 ns | **2.6x** |
| settle on disk | 291 ms | 24 ms | 269 ms | 472 ms | 677 ms | 1,199 ms | 0.08x |
| lookup, key present | 556 ns | 2,827 ns | 690 ns | 845 ns | 2,832 ns | 1,650 ns | **1.2x** |
| lookup, key absent | 22 ns | 2,437 ns | 651 ns | 751 ns | 936 ns | 1,558 ns | **29.6x** |
| range of 100 positions | 2.4 µs | 28.2 µs | 3.6 µs | 4.4 µs | 20.7 µs | 11.0 µs | **1.5x** |
| store one record, commit, read it back | 1.8 µs | 56.0 µs | 35.0 µs | 98.5 µs | 11.3 µs | 5.2 µs | **2.9x** |
| 3 readers + 1 writer: reads a second | 5.06 M | 0.68 M | 4.03 M | 3.06 M | 0.68 M | 0.75 M | **1.3x** |
| the same: writes a second | 2,483 k | 18 k | 115 k | 31 k | 449 k | 273 k | **5.5x** |
| reopen and first lookup | 1.1 ms | 1.4 ms | 5.5 ms | 40.8 ms | 2,459.1 ms | 236.3 ms | **1.3x** |
| size on disk | 124.5 MB | 124.1 MB | 287.2 MB | 512.0 MB | 159.8 MB | 159.2 MB | 1.00x |

| Snail Db is ahead by | SQLite | libmdbx | RocksDB | LevelDB | LMDB |
|---|---|---|---|---|---|
| insert 2,001,149 records, commit every 10,000 | 83.9x | 37.0x | 10.3x | 9.8x | 22.2x |
| lookup right after inserting | 10.4x | 3.1x | 16.4x | 11.3x | 2.6x |
| settle on disk | 0.08x | 1.6x | 2.3x | 4.1x | 0.92x |
| lookup, key present | 5.1x | 1.5x | 5.1x | 3.0x | 1.2x |
| lookup, key absent | 111x | 34.1x | 42.5x | 70.8x | 29.6x |
| range of 100 positions | 11.8x | 1.8x | 8.6x | 4.6x | 1.5x |
| store one record, commit, read it back | 31.1x | 54.7x | 6.3x | 2.9x | 19.4x |
| 3 readers + 1 writer: reads a second | 7.4x | 1.7x | 7.4x | 6.7x | 1.3x |
| the same: writes a second | 138x | 80.1x | 5.5x | 9.1x | 21.6x |
| reopen and first lookup | 1.3x | 37.1x | 2,236x | 215x | 5.0x |
| size on disk | 1.00x | 4.1x | 1.3x | 1.3x | 2.3x |
| **typical row** | **10.4x** | **7.5x** | **6.9x** | **6.3x** | **4.5x** |

Each column is one run of that store on Windows 11 with an Intel Core i9-14900KF and 128 GB of
RAM. LMDB and LevelDB were rerun alone after the shared machine slowed their settle in the full run.
The workload uses 1 million chess positions with 1 to 3 engine evaluations each: 2,001,149
records of 64 bytes, keyed by a position hash. Each store keeps the deepest evaluation for
each engine and line. All stores use process-crash-safe commits without power-cut durability,
and compression is disabled.

| Store | Configuration |
|---|---|
| Snail Db | Defaults: 256 MB in memory before flushing |
| SQLite 3.45.3 | `WITHOUT ROWID` table keyed by (key, engine, line); WAL with `synchronous=NORMAL`; 256 MB cache; mapped reads; prepared statements; upsert keeps the deeper evaluation; one connection per thread |
| LMDB 1.0.2 | `MDB_NOSYNC`; one read transaction per thread, renewed for each lookup. `MDB_WRITEMAP` increased write throughput by up to 6x but made reads 1.6x slower, so it is disabled |
| libmdbx 0.14.4 | `MDBX_SAFE_NOSYNC`; byte- and time-triggered syncs disabled; file grows in 256 MB increments without shrinking. `MDBX_WRITEMAP` made commits take about 0.7 ms on Windows, so it is disabled |
| RocksDB 11.12 | Bloom filters on the 8-byte position prefix; 256 MB block cache; one background thread per core; level compaction with a 512 MB memtable budget; log sync disabled |
| LevelDB 1.23 | Bloom filters; 256 MB cache; 64 MB write buffer; log sync disabled |

The key-value stores use an 11-byte key (big-endian position, engine, line) and a 64-byte value.
They read before writing to retain the deeper evaluation and use prefix seeks to retrieve a
position's records.

The first table's last column compares Snail Db with the best other result in each row. The second
divides each store's result by Snail Db's, so above 1 means Snail Db is faster or smaller. Its typical
row is the geometric mean across rows, leaving out reopen, where RocksDB and LevelDB vary by
seconds between runs, and its columns run from Snail Db's biggest lead to its smallest.

A few qualifications:

- SQLite's 24 ms settle is a WAL checkpoint; its records are already in their final table
  format. Snail Db still has to flush and merge. SQLite also supports general SQL queries;
  Snail Db provides key lookups, key ranges, and table scans.
- Threaded results vary by about +/-25% between runs. LevelDB varied most across five runs:
  settling took 1.2 to 52 seconds, and reopening took 151 ms to 43 seconds, depending on log
  replay and compaction after the concurrent workload.
- Lookups across 2 million records are limited by memory latency. With 40,000 records that fit
  in cache, three Snail Db readers reached 14.3 million reads/s, compared with 6.8 million for
  LMDB and 5.1 million for libmdbx. Write throughput was 2.2 million/s, 98,000/s, and 84,000/s,
  respectively.

To run the comparison from the repository root:

```powershell
python bench/fetch.py
cd bench
snailc build
..\build\bench.exe
```

`fetch.py` downloads pinned sources, verifies their SHA-256 hashes, and builds LMDB, libmdbx,
RocksDB, and LevelDB into `bench/vendor`. The benchmark accepts `[POSITIONS] [FOLDER] [STORE...]`;
store names are `snaildb`, `sqlite`, `lmdb`, `mdbx`, `rocksdb`, and `leveldb`. The default is
1 million positions across all stores.

## Current support

| Feature | Support |
|---|---|
| 64-bit key lookups | Memory and mapped sorted segments; typically 100 to 600 ns |
| Concurrent reads and writes | Lock-free point lookups; a shared writer lock; disk I/O runs outside that lock |
| Multiple records per key | `same` bytes identify records within a key; `better` selects the winner |
| Latest-value tables | `newest_table` replaces matching records on each put |
| Text-keyed values | `kv` stores text keys with byte values |
| Deletion | `remove`, `remove_key`, and `unset` |
| Ordered reads | `range`, `each`, and `each_kv` |
| Name lists | Strings assigned stable numeric IDs |
| Journals | Append-only entries with variable-length byte payloads |
| Crash recovery | Checksummed write-ahead log, replayed on open |
| Power-cut durability | Optional disk syncs with `sync_writes = true` |
| Write-error reporting | `commit()` returns `bool`; `error` records the first failure |
| Segment checksums | One checksum per 64 KB of records, checked by `verify()` |
| Bloom filters | Skip segments for absent keys; lookups can take 20 to 30 ns |
| Online backup | `backup()` creates a database folder while other threads continue |
| Background flushing and merging | Automatic; `settle()` and `compact()` provide explicit control |
| Setup validation | Incompatible record layouts are rejected on open; API misuse reports an error and stops |

Not yet supported: group commit, separate writer locks per table, secondary indexes,
multi-process access, Linux, macOS, compression, or repair.

## API

Add the library path to a project's `snail.toml` or `library.toml`:

```toml
libs = ["C:/Snail/Snail Db/snaildb"]
```

Import `snaildb/snaildb` and register tables, key-value stores, name lists, and journals before
calling `open()`. Every table record starts with a `u64` key. The `same` bytes immediately
after it distinguish records within that key; `same = 0` gives one record per key.

```snail
use snaildb/snaildb

struct Score
    key: u64
    player: u32
    points: i32

fn higher(a: *u8, b: *u8) -> bool
    return (a as *Score).points > (b as *Score).points

fn main()
    var db: Db
    let scores = db.table("scores", sizeof(Score), 4, higher)
    let players = db.name_list("players")
    if not db.open("data/game")
        print("cannot open: {db.error}")
        db.release()
        return

    let ada = db.name_id(players, "Ada")
    var score = Score(key: 1, player: ada, points: 120)
    db.put(scores, &score as *u8)
    if not db.commit()
        print("not saved: {db.error}")

    var bytes: [..]u8
    defer bytes.free()
    db.find(scores, 1, &bytes)    # highest score for each player at key 1
    db.close()
    db.release()
```

[examples/scores.snail](examples/scores.snail) covers scores, names, and journals.
[examples/game.snail](examples/game.snail) adds settings, entity updates, ranges, and backup.
Calls below are methods on `Db`, except for the `db_*` helpers.

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

Run from `tests/`:

```powershell
snailc run
snailc run crash model
```

The first command runs all 17 tests; the second selects two. Each test uses a fresh folder under
`build/tests`, with its steps run as separate processes. Crash tests exit without closing the
database. Output is checked against the corresponding `.out` file embedded in the test runner.

| Test | Coverage |
|---|---|
| `crash`, `better`, `remove` | Recovery of committed records, improvements, deletions, journal entries, and names after exit without closing |
| `churn` | 300,000 keys written three times at random depths through repeated flushes and merges; checks winners, absent keys, and checksums |
| `model`, `model-newest` | 200,000 random operations checked against a reference model, including puts, deletions, lookups, ranges, flushes, merges, compactions, and reopens |
| `race`, `race-update` | Three readers validate records while a writer inserts, replaces, deletes, and re-adds records during flushing |
| `walk` | Ordered iteration returns every winning record exactly once |
| `fail-log`, `fail-flush`, `fail-retry` | Injected log and flush failures; checks write rejection, recovery of committed data, and flush retries |
| `setup`, `leftovers`, `kept` | Incompatible setup and second-opener rejection, resource cleanup, crash leftovers, and preservation of unregistered tables |
| `backup`, `kv` | Backup during writes; latest key-value data survives flushes and crash recovery |

To run a model test with a specific seed from the repository root:

```powershell
.\build\tests\store_test.exe build/tests/model-seeded model 12345
```

## Limits

- **Windows only.** Other platforms need an implementation of the OS layer in `snaildb/c/db_os.h`.
- **One process per folder.** The `LOCK` file prevents a second opener.
- **Fixed record layouts.** Tables require a `u64` key and fixed-size records. A store supports
  at most 255 tables, including those backing key-value stores. There are no secondary indexes
  or general query language.
- **No transaction isolation or rollback.** Writes are visible before commit. A commit covers
  pending writes across the database, rather than a private transaction for the calling thread.
- **Replacement rules must be deterministic.** `better` must depend only on record contents
  and resolve meaningful ties independently of arrival order. Use `newest_table` for latest-value
  semantics.
- **Writers share one lock across tables.** Disk I/O runs outside it, but `commit()` waits for
  logging. `put()` also pauses if memory reaches twice `live_most` while a flush is in progress.
  Group commit and separate writer locks per table are not implemented.
- **Lock-free lookup capacity is 256 threads.** Additional threads fall back to a read lock.
  Stop all database access before calling `close()`.
- **Range reads scan in-memory records.** `range()` and `each()` copy matching records from
  memory before merging them with disk segments. Small ranges can still scan a large memory
  table; a lower `live_most` can help range-heavy workloads.
- **Recovery requires the registered setup.** Open rejects a log containing a table the program
  has not registered, and rejects incompatible record layouts. Segments belonging to unregistered
  tables are preserved.
- **No compression or repair.** Segment checksums detect corruption; automatic repair is not
  available.

## License

Copyright (c) 2026 Angelo Wolff.

Snail Db is open source under the [Mozilla Public License 2.0](LICENSE). It can be used in any
project, including closed-source and commercial games and applications. Changes made to Snail Db's
own files must stay available under the MPL 2.0 when they are shipped.

The files in `bench/vendor/leveldb`, `bench/vendor/lmdb`, `bench/vendor/mdbx`, and
`bench/vendor/rocksdb` come from those projects and keep the licenses found in each folder.
`bench/vendor/sqlite3.def` and `bench/vendor/sqlite3.lib` describe SQLite, which is in the public
domain.

## AI Disclaimer

Snail Db's code may be used to train, fine-tune, and evaluate AI models, including large language
models. This permission is granted by the copyright holder in addition to the MPL 2.0, and models
trained on the code are not covered by the MPL.
