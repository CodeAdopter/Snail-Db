import argparse
import datetime
import hashlib
import os
import re
import shutil
import subprocess
import sys
import tarfile
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

BENCH = Path(__file__).resolve().parent
ROOT = BENCH.parent
VENDOR = BENCH / "vendor"
WORK = ROOT / "build" / "vendor-src"

@dataclass
class Source:
    url: str
    sha256: str
    root: str
    file: str = ""

    @property
    def name(self) -> str:
        return self.file or self.url.rsplit("/", 1)[-1]

@dataclass
class Library:
    name: str
    version: str
    prefix: str
    sources: list[Source]
    flags: list[str]
    files: dict[str, str] = field(default_factory=dict)

LMDB = Library(
    name="lmdb",
    version="1.0.2",
    prefix="mdb_",
    sources=[
        Source("https://git.openldap.org/openldap/openldap/-/archive/LMDB_1.0.2/openldap-LMDB_1.0.2.tar.gz",
               "38a029bb3e29820380e18a2dfdbe906bbc5b322132c63274c5e4ed7833821752",
               "openldap-LMDB_1.0.2/libraries/liblmdb"),
        Source("https://github.com/LMDB/lmdb/archive/refs/tags/LMDB_1.0.2.tar.gz",
               "17e4cb8e80874fccc1ff6f7d5fdb62f029624967d001ff40c47c0fb7a5b42d7d",
               "lmdb-LMDB_1.0.2/libraries/liblmdb", "lmdb-LMDB_1.0.2.tar.gz"),
    ],
    flags=["-O2", "-DNDEBUG", "-mno-incremental-linker-compatible", "-D_CRT_SECURE_NO_WARNINGS",
           "-Wno-deprecated-declarations"],
    files={"include/lmdb.h": "lmdb.h", "LICENSE": "LICENSE", "COPYRIGHT": "COPYRIGHT"},
)

MDBX = Library(
    name="mdbx",
    version="0.14.4",
    prefix="mdbx_",
    sources=[
        Source("https://libmdbx.dqdkfa.ru/release/libmdbx-amalgamated-0.14.4.tar.xz",
               "0dd6bf6048d5d208bc20d325cf93c8f88beda95802e9e3aa7958346611c36922", ""),
    ],
    flags=["-O2", "-DNDEBUG", "-mno-incremental-linker-compatible", "-DMDBX_BUILD_SHARED_LIBRARY=0",
           "-D_WIN32_WINNT=0x0A00",
           "-DMDBX_BUILD_TIMESTAMP=\"2026-09-18T22:53:42+03:00\"",
           "-DMDBX_HAVE_BUILTIN_CPU_SUPPORTS=0",
           "-Xclang", "--dependent-lib=ntdll", "-Xclang", "--dependent-lib=user32",
           "-DMDBX_BUILD_TYPE=\"Release\"", "-DMDBX_BUILD_FLAGS=\"-O2 -DNDEBUG\""],
    files={"include/mdbx.h": "mdbx.h", "LICENSE": "LICENSE", "NOTICE": "NOTICE", "COPYRIGHT": "COPYRIGHT",
           "VERSION.json": "VERSION.json"},
)

ROCKSDB = Library(
    name="rocksdb",
    version="11.12",
    prefix="rocksdb_",
    sources=[
        Source("https://github.com/facebook/rocksdb/archive/refs/tags/v11.12.tar.gz",
               "d8a9d46f9182b47a8d4611c351d622518b1890b9e4e150d81478ab2f45ecd340",
               "rocksdb-11.12", "rocksdb-11.12.tar.gz"),
    ],
    flags=[
        "-DCMAKE_BUILD_TYPE=Release",
        "-DROCKSDB_BUILD_SHARED=ON",
        "-DWITH_MD_LIBRARY=OFF",
        "-DWITH_RUNTIME_DEBUG=OFF",
        "-DPORTABLE=0",
        "-DFAIL_ON_WARNINGS=OFF",
        "-DROCKSDB_SKIP_THIRDPARTY=ON",
        "-DWITH_GFLAGS=OFF", "-DWITH_SNAPPY=OFF", "-DWITH_LZ4=OFF", "-DWITH_ZLIB=OFF", "-DWITH_ZSTD=OFF",
        "-DWITH_XPRESS=OFF", "-DWITH_JEMALLOC=OFF", "-DWITH_LIBURING=OFF", "-DWITH_NUMA=OFF",
        "-DUSE_FOLLY=OFF", "-DUSE_FOLLY_LITE=OFF", "-DUSE_COROUTINES=OFF",
        "-DWITH_TESTS=OFF", "-DWITH_ALL_TESTS=OFF", "-DWITH_TOOLS=OFF", "-DWITH_CORE_TOOLS=OFF",
        "-DWITH_BENCHMARK_TOOLS=OFF", "-DWITH_TRACE_TOOLS=OFF", "-DWITH_BENCHMARK=OFF", "-DWITH_EXAMPLES=OFF",
        "-DWITH_JNI=OFF",
    ],
    files={"include/rocksdb/c.h": "include/rocksdb/c.h", "COPYING": "COPYING", "LICENSE.Apache": "LICENSE.Apache",
           "LICENSE.leveldb": "LICENSE.leveldb"},
)

LEVELDB = Library(
    name="leveldb",
    version="1.23",
    prefix="leveldb_",
    sources=[
        Source("https://github.com/google/leveldb/archive/refs/tags/1.23.tar.gz",
               "9a37f8a6174f09bd622bc723b55881dc541cd50747cbd08831c2a82d620f6d76",
               "leveldb-1.23", "leveldb-1.23.tar.gz"),
    ],
    flags=[
        "-DCMAKE_BUILD_TYPE=Release",
        "-DBUILD_SHARED_LIBS=ON",
        "-DCMAKE_POLICY_DEFAULT_CMP0091=NEW", "-DCMAKE_MSVC_RUNTIME_LIBRARY=MultiThreaded",
        "-DLEVELDB_BUILD_TESTS=OFF", "-DLEVELDB_BUILD_BENCHMARKS=OFF", "-DLEVELDB_INSTALL=OFF",
        "-DHAVE_SNAPPY=0", "-DHAVE_CRC32C=0", "-DHAVE_TCMALLOC=0",
    ],
    files={"include/leveldb/c.h": "include/leveldb/c.h", "include/leveldb/export.h": "include/leveldb/export.h",
           "LICENSE": "LICENSE"},
)

LIBRARIES = {lib.name: lib for lib in (LMDB, MDBX, ROCKSDB, LEVELDB)}

def say(text: str) -> None:
    print(text, flush=True)

def run(args: list, cwd: Path, env: dict | None = None, capture: bool = False) -> str:
    args = [str(a) for a in args]
    say("  > " + subprocess.list2cmdline(args))
    result = subprocess.run(args, cwd=cwd, env=env, text=True, errors="replace",
                            stdout=subprocess.PIPE if capture else None, stderr=subprocess.STDOUT if capture else None)
    if result.returncode != 0:
        if capture: say(result.stdout)
        sys.exit(f"fetch: failed ({result.returncode}): {args[0]}")
    return result.stdout if capture else ""

def llvm_tool(name: str) -> str:
    found = shutil.which(name)
    if found: return found
    candidate = Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "LLVM" / "bin" / (name + ".exe")
    if candidate.exists(): return str(candidate)
    sys.exit(f"fetch: cannot find {name}; install LLVM (winget install LLVM.LLVM)")

_msvc: dict | None = None

def msvc() -> dict:
    global _msvc
    if _msvc is not None: return _msvc
    roots = []
    vswhere = Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "Microsoft Visual Studio" / "Installer" / "vswhere.exe"
    if vswhere.exists():
        out = subprocess.run([str(vswhere), "-latest", "-products", "*", "-requires",
                              "Microsoft.VisualStudio.Component.VC.Tools.x86.x64", "-property", "installationPath"],
                             capture_output=True, text=True, errors="replace")
        roots += [Path(line.strip()) for line in out.stdout.splitlines() if line.strip()]
    roots.append(Path(r"C:\Program Files\Microsoft Visual Studio\18\Community"))
    root = next((r for r in roots if (r / "VC" / "Auxiliary" / "Build" / "vcvars64.bat").exists()), None)
    if root is None: sys.exit("fetch: cannot find Visual Studio with the C++ tools (vcvars64.bat)")
    vcvars = root / "VC" / "Auxiliary" / "Build" / "vcvars64.bat"
    out = subprocess.run(f'cmd /d /s /c ""{vcvars}" >nul 2>&1 && set"', capture_output=True, text=True, errors="replace")
    env = {}
    for line in out.stdout.splitlines():
        key, eq, value = line.partition("=")
        if eq and key: env[key] = value
    if "VCToolsVersion" not in env: sys.exit(f"fetch: {vcvars} did not set up the MSVC environment")
    cmake_dir = root / "Common7" / "IDE" / "CommonExtensions" / "Microsoft" / "CMake"
    cmake = cmake_dir / "CMake" / "bin" / "cmake.exe"
    ninja = cmake_dir / "Ninja" / "ninja.exe"
    path = env.get("Path") or env.get("PATH") or ""
    cmake = str(cmake) if cmake.exists() else shutil.which("cmake", path=path)
    ninja = str(ninja) if ninja.exists() else shutil.which("ninja", path=path)
    if not cmake or not ninja: sys.exit("fetch: cannot find CMake and Ninja (Visual Studio's C++ CMake tools)")
    cl = shutil.which("cl", path=path)
    if not cl: sys.exit("fetch: vcvars64.bat put no cl.exe on the PATH")
    banner = subprocess.run([cl], env=env, capture_output=True, text=True, errors="replace").stderr.splitlines()
    cmake_version = subprocess.run([cmake, "--version"], capture_output=True, text=True).stdout.splitlines()[0]
    _msvc = {"env": env, "cmake": cmake, "ninja": ninja, "cl": banner[0].strip() if banner else "cl",
             "cmake_version": cmake_version, "toolset": env["VCToolsVersion"]}
    return _msvc

def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""): h.update(block)
    return h.hexdigest()

def download(lib: Library, work: Path) -> tuple[Source, Path]:
    folder = work / "archive"
    for source in lib.sources:
        target = folder / source.name
        if target.exists():
            if sha256_of(target) == source.sha256:
                say(f"  have {target.name} (sha256 ok)")
                return source, target
            say(f"  {target.name} has the wrong hash, fetching it again")
    if folder.exists(): shutil.rmtree(folder)
    folder.mkdir(parents=True)
    for source in lib.sources:
        target = folder / source.name
        part = target.with_name(target.name + ".part")
        say(f"  downloading {source.url}")
        try:
            request = urllib.request.Request(source.url, headers={"User-Agent": "snaildb-bench-fetch"})
            h = hashlib.sha256()
            with urllib.request.urlopen(request, timeout=120) as response, open(part, "wb") as out:
                for block in iter(lambda: response.read(1 << 20), b""):
                    h.update(block)
                    out.write(block)
        except OSError as e:
            say(f"  failed: {e}")
            part.unlink(missing_ok=True)
            continue
        digest = h.hexdigest()
        if digest != source.sha256:
            say(f"  sha256 mismatch: got {digest}, pinned {source.sha256}")
            part.unlink()
            continue
        part.rename(target)
        say(f"  sha256 ok: {digest}")
        return source, target
    sys.exit(f"fetch: no source for {lib.name} {lib.version} downloaded with its pinned hash")

def unpack(archive: Path, source: Source, work: Path) -> Path:
    folder = work / "src"
    stamp = work / "src.sha256"
    if folder.exists() and stamp.exists() and stamp.read_text().strip() == source.sha256:
        return folder / source.root
    if folder.exists(): shutil.rmtree(folder)
    stamp.unlink(missing_ok=True)
    folder.mkdir()
    say(f"  unpacking {archive.name}")
    with tarfile.open(archive) as t:
        t.extractall(folder, filter="data")
    stamp.write_text(source.sha256 + "\n")
    return folder / source.root

def build_clang_lib(lib: Library, src: Path, build: Path, units: list[str]) -> tuple[dict[str, Path], list[str]]:
    clang, llvm_lib = llvm_tool("clang"), llvm_tool("llvm-lib")
    objects = []
    for unit in units:
        obj = build / (Path(unit).stem + ".o")
        run([clang, *lib.flags, "-c", src / unit, "-o", obj], cwd=build)
        objects.append(obj)
    out = build / f"{lib.name}.lib"
    out.unlink(missing_ok=True)
    run([llvm_lib, "/nologo", f"/out:{out}", *objects], cwd=build)
    version = subprocess.run([clang, "--version"], capture_output=True, text=True).stdout.splitlines()[0]
    how = [f"compiler: {version}", f"flags: {' '.join(lib.flags)}",
           f"kind: static library ({', '.join(units)}), C runtime left to the program (snailc: static libcmt)"]
    return {f"{lib.name}.lib": out}, how

def build_lmdb(lib: Library, src: Path, build: Path):
    return build_clang_lib(lib, src, build, ["mdb.c", "midl.c", "module.c"])

def build_mdbx(lib: Library, src: Path, build: Path):
    return build_clang_lib(lib, src, build, ["mdbx.c"])

def build_cmake(lib: Library, src: Path, build: Path, target: str, dll: str, implib: str):
    tools = msvc()
    env = dict(tools["env"])
    configure = [tools["cmake"], "-G", "Ninja", "-Wno-dev", f"-DCMAKE_MAKE_PROGRAM={tools['ninja']}",
                 "-DCMAKE_C_COMPILER=cl", "-DCMAKE_CXX_COMPILER=cl", *lib.flags, "-S", src, "-B", build]
    stamp = build / "fetch-configure.txt"
    said = subprocess.list2cmdline([str(a) for a in configure])
    if not (build / "build.ninja").exists() or not stamp.exists() or stamp.read_text() != said:
        shutil.rmtree(build)
        build.mkdir()
        run(configure, cwd=build, env=env)
        stamp.write_text(said)
    jobs = str(os.cpu_count() or 4)
    run([tools["cmake"], "--build", build, "--target", target, "--parallel", jobs], cwd=build, env=env)
    how = [f"compiler: {tools['cl']} (toolset {tools['toolset']})",
           f"build: {tools['cmake_version']}, Ninja, target {target}",
           f"cmake: {' '.join(lib.flags)}",
           "kind: DLL exporting the C API, C runtime linked in (/MT)"]
    return {dll: build / dll, implib: build / implib}, how

def build_rocksdb(lib: Library, src: Path, build: Path):
    return build_cmake(lib, src, build, "rocksdb-shared", "rocksdb-shared.dll", "rocksdb-shared.lib")

def build_leveldb(lib: Library, src: Path, build: Path):
    return build_cmake(lib, src, build, "leveldb", "leveldb.dll", "leveldb.lib")

BUILDERS = {"lmdb": build_lmdb, "mdbx": build_mdbx, "rocksdb": build_rocksdb, "leveldb": build_leveldb}

def dll_exports(dll: Path) -> set[str]:
    out = run([llvm_tool("llvm-readobj"), "--coff-exports", dll], cwd=dll.parent, capture=True)
    return {line.split(":", 1)[1].strip() for line in out.splitlines() if line.strip().startswith("Name:")}

def dll_imports(dll: Path) -> list[str]:
    out = run([llvm_tool("llvm-readobj"), "--coff-imports", dll], cwd=dll.parent, capture=True)
    names = []
    for line in out.splitlines():
        line = line.strip()
        if line.startswith("Name:") and line.lower().endswith(".dll"): names.append(line.split(":", 1)[1].strip())
    return names

def lib_defines(lib_file: Path) -> set[str]:
    out = run([llvm_tool("llvm-nm"), "--defined-only", "--extern-only", "--format=just-symbols", lib_file],
              cwd=lib_file.parent, capture=True)
    return {line.strip() for line in out.splitlines() if line.strip() and not line.endswith(":")}

def bound_functions(lib: Library) -> list[str]:
    binding = BENCH / f"bind_{lib.name}.snail"
    if not binding.exists(): return []
    names = []
    for line in binding.read_text().splitlines():
        m = re.match(r'extern\s+(?:"(\w+)"\s+)?fn\s+(\w+)', line)
        if m and (m.group(1) or m.group(2)) not in names: names.append(m.group(1) or m.group(2))
    return names

def check(lib: Library, outputs: dict[str, Path]) -> list[str]:
    notes = []
    wanted = bound_functions(lib)
    for name, path in outputs.items():
        if name.endswith(".dll"):
            exports = dll_exports(path)
            missing = [f for f in wanted if f not in exports]
            if missing: sys.exit(f"fetch: {name} does not export {', '.join(missing)}")
            c_api = [e for e in exports if e.startswith(lib.prefix)]
            imports = dll_imports(path)
            notes.append(f"exports: {len(c_api)} {lib.prefix}* C functions of {len(exports)} names, "
                         f"including the {len(wanted)} bench/bind_{lib.name}.snail declares")
            notes.append(f"imports: {', '.join(imports)}")
            runtime = [d for d in imports if d.lower().startswith(("msvcp", "vcruntime", "ucrtbase", "api-ms-win-crt"))]
            if runtime: say(f"  warning: {name} needs the C runtime DLLs {', '.join(runtime)}")
        elif name.endswith(".lib") and not any(n.endswith(".dll") for n in outputs):
            defined = lib_defines(path)
            missing = [f for f in wanted if f not in defined]
            if missing: sys.exit(f"fetch: {name} does not define {', '.join(missing)}")
            notes.append(f"defines: {len([d for d in defined if d.startswith(lib.prefix)])} {lib.prefix}* functions, "
                         f"including the {len(wanted)} bench/bind_{lib.name}.snail declares")
    return notes

def recipe_of(lib: Library) -> str:
    text = repr((lib.name, lib.version, [(s.url, s.sha256, s.root) for s in lib.sources], lib.flags, lib.files))
    return hashlib.sha256(text.encode()).hexdigest()[:16]

def installed(lib: Library) -> bool:
    info = VENDOR / lib.name / "BUILD-INFO.txt"
    if not info.exists(): return False
    lines = info.read_text().splitlines()
    if f"recipe: {recipe_of(lib)}" not in lines: return False
    files = [line.split()[0] for line in lines if line.startswith("  ") and line.strip()]
    return all((VENDOR / lib.name / f).exists() for f in files)

def install(lib: Library, source: Source, src: Path, outputs: dict[str, Path], how: list[str], notes: list[str]) -> None:
    out = VENDOR / lib.name
    if out.exists(): shutil.rmtree(out)
    out.mkdir(parents=True)
    copies = {**{k: src / v for k, v in lib.files.items()}, **outputs}
    for name, path in copies.items():
        target = out / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
    lines = [f"{lib.name} {lib.version}, installed by bench/fetch.py",
             f"recipe: {recipe_of(lib)}",
             f"source: {source.url}",
             f"sha256: {source.sha256}",
             f"built: {datetime.datetime.now().astimezone().isoformat(timespec='seconds')}",
             *how, *notes, "files:"]
    lines += [f"  {name} {(out / name).stat().st_size} bytes" for name in sorted(copies)]
    (out / "BUILD-INFO.txt").write_text("\n".join(lines) + "\n")

def fetch(lib: Library, force: bool) -> None:
    say(f"{lib.name} {lib.version}")
    if not force and installed(lib):
        say(f"  installed in {VENDOR / lib.name}, nothing to do")
        return
    work = WORK / f"{lib.name}-{lib.version}"
    work.mkdir(parents=True, exist_ok=True)
    source, archive = download(lib, work)
    src = unpack(archive, source, work)
    build = work / "build"
    if force and build.exists(): shutil.rmtree(build)
    build.mkdir(exist_ok=True)
    outputs, how = BUILDERS[lib.name](lib, src, build)
    notes = check(lib, outputs)
    install(lib, source, src, outputs, how, notes)
    for note in notes: say(f"  {note}")
    say(f"  installed in {VENDOR / lib.name}")

def fetch_sqlite() -> None:
    to = VENDOR / "sqlite3.dll"
    if to.exists():
        say("sqlite: vendor/sqlite3.dll is there")
        return
    dll = Path(sys.base_prefix) / "DLLs" / "sqlite3.dll"
    if not dll.exists(): sys.exit(f"fetch: {dll} is missing, and the benchmark links SQLite through it")
    shutil.copy2(dll, to)
    say(f"sqlite: copied {dll}")

def main() -> None:
    if sys.version_info < (3, 12): sys.exit("fetch: needs Python 3.12 or later (tarfile's data filter)")
    parser = argparse.ArgumentParser(description="Fetch, build and install the benchmark's competitor stores.")
    parser.add_argument("names", nargs="*", metavar="name", help=f"which to fetch: {', '.join(LIBRARIES)} (default all)")
    parser.add_argument("--force", action="store_true", help="build again even when installed")
    args = parser.parse_args()
    unknown = [n for n in args.names if n not in LIBRARIES]
    if unknown: parser.error(f"unknown {', '.join(unknown)}; choose from {', '.join(LIBRARIES)}")
    if not args.names: fetch_sqlite()
    for name in args.names or list(LIBRARIES):
        fetch(LIBRARIES[name], args.force)

if __name__ == "__main__":
    main()
