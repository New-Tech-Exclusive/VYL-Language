# VYL Language Cheatsheet

A quick reference guide for the VYL programming language (current with networking and HTTP built-ins).

## Types

| Type | Description | Example |
| :--- | :--- | :--- |
| **Integer** | 64-bit signed integer | `var int x = 10;` |
| **Decimal** | 64-bit floating point | `var dec pi = 3.14;` |
| **String** | Null-terminated string | `var string s = "Hello";` |
| **Boolean** | True or false value | `var bool active = true;` |
| **Struct** | User-defined data structure | `struct Point { var int x; }` |
| **Implicit** | Type inferred from expression | `var count = 0;` |

## Variable Declarations

```vyl
var [type] <name> = <expression>;
```
Example:
```vyl
var int score = 100;
var dec price = 19.99;
var string user = "Bentley";
var is_valid = true; // inferred as bool
```

## Structs

```vyl
struct <Name> {
    var <type> <field>;
    ...
}
```
Structs are declarations only today (no field access in codegen yet).

## Control Flow

### If/Else/Elif
```vyl
if (condition) {
    // code
} elif (other_condition) {
    // code
} else {
    // code
}
```

### While Loop
```vyl
while (condition) {
    // code
}
```

### For Loop
```vyl
for i in 1..10 {
    // code
}
```

## Functions

```vyl
Function <name>(<params>) [-> <return_type>] {
    // code
    return <expression>;
}
```

## Built-in Functions (by area)

| Area | Function | Return | Description |
| :--- | :--- | :--- | :--- |
| IO/FS 
|  | `Print(any)` | `void` | Print to stdout |
|  | `Exists(path)` | `bool` | Check if a path exists |
|  | `CreateFolder(path)` | `int` | Make a directory |
|  | `Open(path, mode)` | `int` | Open a file (fd) |
|  | `Close(fd)` | `int` | Close file descriptor |
|  | `Read(path)` | `string` | Read an entire file |
|  | `Write(fd, data)` | `int` | Write to descriptor |
|  | `ReadFilesize(path)` | `int` | File size in bytes |
|  | `Remove(path)` | `int` | Remove a file |
|  | `MkdirP(path)` | `int` | mkdir -p |
|  | `RemoveAll(path)` | `int` | rm -rf |
|  | `CopyFile(src, dst)` | `int` | Copy a file |
| Process 
|  | `Argc()` / `GetArg(i)` | `int` / `string` | CLI args |
|  | `Sys(cmd)` | `int` | Run a shell command |
|  | `Exit(code)` | `void` | Exit the process |
|  | `Input()` | `string` | Read stdin line |
|  | `GC()` | `void` | Trigger GC |
| Time/Random 
|  | `Clock()` | `int` | Monotonic clock ticks |
|  | `Sleep(ms)` | `int` | Sleep milliseconds |
|  | `Now()` | `int` | Unix timestamp |
|  | `RandInt()` | `int` | Random 64-bit int |
| Crypto 
|  | `SHA256(data)` | `string` | SHA-256 hex digest |
| Networking 
|  | `TcpConnect(host, port)` | `int` | Open TCP socket |
|  | `TcpSend(fd, data)` | `int` | Send bytes |
|  | `TcpRecv(fd, max_bytes)` | `string` | Receive bytes |
|  | `TcpClose(fd)` | `int` | Close socket |
|  | `TcpResolve(host)` | `string` | IPv4 string |
|  | `TlsConnect(host, port)` | `int` | TLS over TCP |
|  | `TlsSend(fd, data)` | `int` | Send TLS data |
|  | `TlsRecv(fd, max_bytes)` | `string` | Receive TLS data |
|  | `TlsClose(fd)` | `int` | Close TLS session |
| HTTP 
|  | `HttpGet(host, path, use_tls)` | `string` | Fetch body |
|  | `HttpDownload(host, path, use_tls, dest)` | `int` | Stream to file |
| Arrays/Math |
|  | `Array(len)` | `array` | Allocate int array |
|  | `Length(arr)` | `int` | Array length |
|  | `Sqrt(n)` | `int` | Integer floor sqrt |
| Manual mem 
|  | `Malloc(n)` | `int` | Allocate raw bytes |
|  | `Free(ptr)` | `int` | Free raw pointer |
|  | `Memcpy(dst, src, n)` | `int` | Copy bytes |
|  | `Memset(ptr, val, n)` | `int` | Set bytes |

## Program Structure

VYL programs start at `Function Main(argc, argv)`.

```vyl
Function Main(argc, argv) {
    var start = Clock();
    Print("Live from VYL");
    // ... work ...
    var end = Clock();
    Print(end - start);
}
```

### Quick networking samples

## Memory Model

- Default heap is managed; user code does not free managed arrays/strings. Array indexing is null/bounds-checked and aborts on violation.
- Struct assignments copy by value; arrays/strings are references.
- Manual memory built-ins (`Malloc/Free/Memcpy/Memset`) return raw addresses (as `int`) and are not tracked by the runtime GC. Mixing managed objects with manual buffers is unsafe unless you copy bytes explicitly.

```vyl
// Plain TCP echo
var int fd = TcpConnect("example.com", 80);
TcpSend(fd, "GET / HTTP/1.1\r\nHost: example.com\r\n\r\n");
var string resp = TcpRecv(fd, 4096);
TcpClose(fd);

// HTTP download to disk (use_tls: 0 = http, 1 = https)
HttpDownload("example.com", "/", 0, "/tmp/example.html");
```

## Special Syntax

- **Newlines**: Use `\n` inside strings for a literal newline character.
- **Comments**: Use `//` for single-line comments.
- **Semicolons**: Required after statements; omit for block headers.

## Language Limitations (v0.2.4)

- Structs are declarations only (no field storage yet).
- Arrays are int-only; indexing is null/bounds-checked and aborts on violation.
- Includes inline files; no modules/packages yet.
- Blocking networking APIs (TCP/TLS/HTTP) and IPv4-focused.
- No exception handling or operator overloading.

## Optimization Tips
- VYL uses **Peephole Optimization** for `i = i + 1` (converted to a single `inc` instruction).
- Binary operations with integer literals (e.g., `x + 5`) avoid stack traffic.
- Loop structures are optimized to minimize branch overhead.
