# Chapter 9C: what we tested

Back to the [chapter](README.md).

The unit tests cover an agent going through the whole flow (quarantine, scan, review, release as a file, audit, and CHANGED after an
edit), and the rules `inherits-all-tools` and `loosens-permissions`. We also ran the scan on this repository's own agents.

Not tested: the `defines-mcp-servers` and `defines-hooks` rules for agents (they follow the same code path as skills, but no
test uses an agent that has them), slash commands, and plugins.
