# Symbol and symbol-library import safety (OpenSchematix 1.1.0)

OpenSchematix accepts local custom symbols (`.osym`) and shareable library packages (`.osymlib`). These files are untrusted inputs even when supplied by another engineer. Opening or previewing a package does **not** extract its members into the filesystem.

## Input budgets

| Input property | Maximum |
| --- | ---: |
| Standalone `.osym` file or one package symbol member | 2 MiB (2,097,152 bytes) |
| `manifest.json` | 2 MiB |
| Symbol JSON container nesting | 64 levels |
| Package archive size | 80 MiB |
| Total package uncompressed member size | 64 MiB |
| Package ZIP members | 2,048 |
| Symbol entries in the manifest | 1,000 |
| Folder entries in the manifest | 1,024 |
| ZIP central directory | 512 KiB |
| One package-relative path | 512 characters |
| Package-relative path nesting | 16 segments |
| One folder segment | 80 characters (same as `safe_name`) |

Package member byte limits are checked against ZIP metadata **and** against the actual bounded stream read. The archive and central-directory entry limits are checked before Python's ZIP parser constructs its member table. Duplicate ZIP member names are rejected; repeated references to the same member in a package manifest are skipped and reported. Packages requiring more than the supported number of entries, including ZIP64 sentinel entry counts, are rejected.

Single symbol import and library scanning also enforce the symbol-file byte limit. Invalid UTF-8, unparseable JSON, excessive depth, and malformed `tags`, `properties`, `pins`, `prims`, and primitive-point containers produce `SymbolFormatError` rather than incidental Python exceptions. Legacy documents with omitted or null optional arrays and properties remain valid.

The package preview rejects invalid manifests. Invalid individual entries are skipped and reported in `PackageInfo.problems`; valid entries remain available to preview and import. Package paths must be relative, use forward slashes, and have safe, nonempty components. The exporter applies the same budgets and rejects any package it cannot subsequently import.

## Package import and recovery

Importing a package stages its changes in a temporary sibling directory on the **same filesystem** as the library, validating the selected symbols before changing the original library. When staging succeeds, the prior library directory is moved to a backup and the staged directory takes its place. If a detected write or commit error occurs, the importer attempts to restore the original tree. If a secondary filesystem error prevents that restoration, the prior library is retained in the staging backup for recovery rather than being deleted. Restoration is therefore best-effort under multiple simultaneous filesystem failures.

If an application interruption occurs between the two directory moves, the next `UserLibrary.scan()` recognizes a matching temporary backup and restores it when the original library directory is missing. The recovery marker ties the backup to the original absolute library path, preventing an unrelated missing library from adopting it. Package import rejects a symbolic-link library root and source-library trees containing symbolic links; it does not dereference them into staging. A configuration path with symlinked ancestors must be controlled by the user and is not an isolated security boundary.

This is exception-safe, **not a general multi-process transaction**. Do not import into the same library concurrently from separate application instances. A temporary copy of the entire library requires additional free disk space during the operation. Power-loss durability still depends on filesystem behavior; recovery preserves the preceding library directory when the application can access the backup.

No account, network, telemetry, or remote service is involved.
