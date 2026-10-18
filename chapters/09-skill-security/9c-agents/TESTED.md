# Chapter 9C: what we tested

Back to the [chapter](README.md).

**Tested**

- The unit tests cover an agent going through the whole flow (quarantine, scan, review, release as a file, audit, and CHANGED
  after an edit), and the rules `inherits-all-tools` and `loosens-permissions`.
- Frontmatter written other ways: a quoted `permissionMode`, one followed by a `# comment`, a tool list in YAML list form and in
  `[Read, Write]` form, and an empty `tools:` line. One test covers them, and it fails on the code before the fix.
- We also ran the scan on this repository's own four agents: three medium notes for broad tools, and the `skill-reviewer`
  false positive (9C.4).

**Not tested**

- The `defines-mcp-servers` and `defines-hooks` rules for agents. They follow the same code path as skills, but no test uses an
  agent that has them.
- Slash commands and plugins.
- Frontmatter forms the parser does not read: multi-line values, anchors, and other YAML beyond `key: value` and simple lists.

**How much to trust it**

The tests show the agent rules read the common ways of writing frontmatter, but the parser is not a YAML library, so a file
written to confuse it may still get through; read the frontmatter of any agent you install.
