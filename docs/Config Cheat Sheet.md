# Config Cheat Sheet

This cheat sheet provides a concise overview of ast-grep's linter rule YAML configuration.  It's designed as a handy reference for common usage.

## Basic Information

Core details that identify and define your rule and miscellaneous keys for documentation and custom data.

```yaml
id: no-console-log
```
🆔 A unique, descriptive identifier for the rule.

```yaml
language: JavaScript
```
🌐 The programming language the rule applies to.

```yaml
url: 'https://doc.link/'
```
🔗 A URL to the rule's documentation.

```yaml
metadata: { author: 'John Doe' }
```
📓 metadata  A dictionary for custom data related to the rule.

## Finding

Keys for specifying what code to search for.

```yaml
rule:
  pattern: 'console.log($$$ARGS)'
```
🎯 The core `rule` to find matching AST nodes.

```yaml
constraints:
  ARG: { kind: 'string' } }
```
⚙️ Additional `constraints` rules to filter meta-variable matches.

```yaml
utils:
  is-react:
    kind: function_declaration
    has: { kind: jsx_element }
```
🛠️ A dictionary of reusable utility rules. Use them in `matches` to modularize your rules.

## Patching

Keys for defining how to automatically fix the found code.

```yaml
transform:
  NEW_VAR:
    substring: {endChar: 1, source: $V}
```
🎩 `transform` meta-variables before they are used in `fix`.

```yaml
transform:
  NEW_VAR: substring($V, endChar=1)
```
🎩 `transform` also accepts string form.

```yaml
fix: "logger.log($$$ARGS)"
```
🔧 A `fix` string to auto-fix the matched code.

```yaml
fix:
  template: "logger.log($$$ARGS)"
  expandEnd: rule
```
🔧 Fix also accepts `FixConfig` object.

```yaml
rewriters:
- id: remove-quotes
  rule: { pattern: "'$A'" }
  fix: "$A"
```
✍️ A list of `rewriters` for complex transformations.

## Linting

Keys for configuring the messages and severity of reported issues.

```yaml
severity: warning
```
⚠️ The `severity` level of the linting message.

```yaml
message: "Avoid using $MATCH in production."
```
💬 A concise `message` explaining the rule. Matched $VAR can be used.

```yaml
note:
  Use a _logger_ instead of `console`
```
📌 More detailed `note`. It supports Markdown format.

```yaml
labels:
  ARG:
    style: 'primary'
    message: 'The argument to log'
```
🎨 Customized `labels` for highlighting parts of the matched code.

```yaml
files: ['src/**/*.js']
```
✅ Glob `files` patterns to include files for the rule.

```yaml
files:
  - glob: 'README.md'
    caseInsensitive: true
```
✅ Use object syntax for case-insensitive glob matching.

```yaml
ignores: ['test/**/*.js']
```
❌ Glob patterns to exclude files from the rule.


Up to date version can be found:
https://github.com/ast-grep/ast-grep.github.io/blob/main/website/cheatsheet/yaml.md
