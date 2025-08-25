
## Fuzzball application template style guide

Workflows should follow these suggestions.

- Prefer `script:` over `command:` for new workflows for better readability and
  maintainability for complex operations.
- Do not make hardware assumptions. For example, hardcoding `threads: true` in
  the resources selection will make a workflow less portable by preventing it
  from running on systems that do not enable hardware threads.
- Use explicit tags in container URIs for reproducibility.
- The heavy analytical jobs in a workflow should have configurable runtime limits.
- Use strings with explicit units for memory and runtime specifications (e.g. "8GiB", "30m")
- Interactive services listening on a port should listen on localhost for security.
- Use consistent template variable formatting without spaces: `{{.Variable}}`
  rather than `{{ .Variable }}`
