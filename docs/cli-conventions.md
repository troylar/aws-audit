# CLI Option Naming Conventions

Reference for contributors adding or modifying `awsinv` CLI commands.

## Standard Option Names

Every command that uses one of these concepts MUST use the canonical name and short flag listed here.

| Concept | Long Name | Short | Type | Input Pattern | Envvars |
|---------|-----------|-------|------|---------------|---------|
| Snapshot (filter) | `--snapshot` | `-s` | str | Single value | `AWSINV_SNAPSHOT_ID` |
| Snapshot (subject) | positional arg | -- | Argument | Single value | `AWSINV_SNAPSHOT_ID` |
| Region | `--region` | `-r` | List[str] | Repeatable | `AWSINV_REGION`, `AWS_REGION` |
| Resource type | `--type` | `-t` | List[str] | Repeatable | -- |
| Output format | `--format` | `-f` | str | Choice: table, json, csv, yaml | -- |
| Output file | `--output` | `-o` | str | File path | -- |
| Profile | `--profile` | `-p` | str | Single value | `AWSINV_PROFILE`, `AWS_PROFILE` |
| Confirmation skip | `--yes` | `-y` | bool | Flag | -- |
| Verbose | `--verbose` | `-v` | bool | Flag | -- |
| Quiet | `--quiet` | `-q` | bool | Flag | -- |
| Result limit | `--limit` | `-l` | int | Single value (default 100) | -- |
| Collection | `--collection` | `-i` | str | Single value | `AWSINV_COLLECTION_ID` |
| Description | `--description` | `-d` | str | Single value | -- |
| Storage path | `--storage-path` | -- | str | Single value | `AWSINV_STORAGE_PATH` |
| LLM provider | `--provider` | -- | str | Choice: bedrock, openai | `AWSINV_LLM_PROVIDER` |
| OpenAI model | `--openai-model` | -- | str | Single value | `AWSINV_OPENAI_MODEL` |
| OpenAI API key | `--openai-api-key` | -- | str | Single value | `AWSINV_OPENAI_API_KEY` |
| OpenAI base URL | `--openai-base-url` | -- | str | Single value | `AWSINV_OPENAI_BASE_URL` |

## Short Flag Assignments

Each letter has exactly ONE meaning across the entire CLI.

| Flag | Meaning | Scope |
|------|---------|-------|
| `-a` | `--all` | lambda list |
| `-c` | `--category` | guardrails list, guardrails export |
| `-d` | `--description` | collection create, groups create |
| `-e` | `--env` | guardrails check, guardrails list |
| `-f` | `--format` | All commands with output format |
| `-g` | `--group-by` | query stats |
| `-h` | `--help` | Reserved (Typer built-in) |
| `-i` | `--collection` | All commands with collection filter |
| `-l` | `--limit` | All commands with result limits |
| `-m` | `--model-id` | generate, diff verify |
| `-n` | `--count` | guardrails generate |
| `-o` | `--output` | All commands with file output |
| `-p` | `--profile` | Global (all commands) |
| `-q` | `--quiet` | Global (all commands) |
| `-r` | `--region` | All commands with region filter |
| `-s` | `--snapshot` | All non-snapshot-group commands |
| `-t` | `--type` | All commands with type filter |
| `-v` | `--verbose` | Global (all commands) |
| `-x` | `--exclude-names` | cleanup scan-all |
| `-y` | `--yes` | All destructive commands |

Unassigned: `b`, `j`, `k`, `u`, `w`, `z`

## Rules

1. **One meaning per letter**: A short flag letter must mean the same thing on every command that uses it. If a command has an option that does not match the canonical meaning, omit the short flag.

2. **Repeatable lists**: Use `List[str]` with Typer's repeatable option pattern (`-r us-east-1 -r us-west-2`), not comma-separated strings.

3. **Destructive commands**: All commands that delete, purge, restore, or execute destructive changes must use `--yes / -y` for confirmation skip.

4. **Snapshot argument pattern**: Commands in the `snapshot` group accept the snapshot name as a positional argument. Commands outside the group use `--snapshot / -s`.

5. **Envvar consistency**: If an option supports an envvar on one command, it must support the same envvar on every command that accepts that option.

6. **No legacy aliases**: When renaming an option, replace it fully. Do not keep old names as hidden aliases.
