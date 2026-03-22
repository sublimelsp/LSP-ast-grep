# LSP-ast-grep

An LSP server for ast-grep that provides code structural search, lint and rewriting.

Provided through [ast-grep](https://github.com/ast-grep/ast-grep).

### Requirements

Install [LSP](https://packagecontrol.io/packages/LSP) via Package Control.

### Installation

1. Install [LSP-ast-grep](https://packagecontrol.io/packages/LSP-ast-grep) from Package Control.
1. Restart Sublime.

### Getting started

* **Command Palette:** Select `LSP-ast-grep: Search by Code`.
* **Keybinding:** Add this to your settings:
    ```json
    { "keys": ["ctrl+alt+f"], "command": "lsp_ast_grep_open" }
    ```
* **Context Menu**: Right-click and select `Show Tree-sitter AST (ast-grep)` while the pane is open. This extracts node kind information for writing advanced rules.

### Configuration

You may customize settings by running `Preferences: LSP-ast-grep Settings` from the Command Palette.
