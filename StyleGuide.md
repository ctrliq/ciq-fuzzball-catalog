
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
- If you need a value derived from an input parameter (e.g. with whitespace
  trimmed of the ends for use in quoted strings, paths assembled from input
  parameters, ...), assign the new value to a variable at the beginning of the
  template and use the new variable in the body.
