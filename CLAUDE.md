do not edit the project or any files on your own. you may only edit the project if i directly ask you to. you may also ask for permission but it is ultimately up to my own (the prompter's) discretion.

When giving me curl commands to run in my PowerShell terminal, format them so I can paste and run directly:

Use curl.exe explicitly, never bare curl (it's aliased to Invoke-WebRequest, which has different flags).
Keep the whole command on one line — no \ line continuation (that's bash-only).
For JSON bodies with -d, wrap the JSON in single quotes AND escape every inner double-quote with \", e.g. -d '{\"key\":\"value\"}'. This is required due to how Windows passes arguments to native executables (embedded " gets stripped otherwise) — plain single-quoted JSON without escaping will break.