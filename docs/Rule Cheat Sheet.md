# Rule Cheat Sheet

This cheat sheet provides a concise overview of rule object configuration, covering Atomic, Relational, and Composite rules, along with notes on Utility rules. It's designed as a handy reference for common usage.

## Atomic Rules Cheat Sheet

These are your precision tools, matching individual AST nodes based on their inherent properties.

```yaml
pattern: console.log($ARG)
```
🧩 Match a node by code structure. e.g. `console.log` call with a single `$ARG`

```yaml
pattern:
  context: '{ key: value }'
  selector: pair
```
🧩 To parse ambiguous patterns, use `context` and specify `selector` AST to search.

```yaml
kind: if_statement
```
🏷️ Match an AST node by its `kind` name

```yaml
regex: ^regex.+$
```
🔍 Matches node text content against a [Rust regular expression](https://docs.rs/regex/latest/regex/)

```yaml
nthChild: 1
```
🔢 Find a node by its 1-based index among its _named siblings_

```yaml
nthChild:
  position: 2
  reverse: true
  ofRule: { kind: argument_list }
```
🔢 Advanced positional control: `position`, `reverse` (count from end), or filter siblings using `ofRule`

```yaml
range:
  start: { line: 0, column: 0 }
  end: { line: 0, column: 13 }
```
🎯 Matches a node based on its character span: 0-based, inclusive start, exclusive end

## Relational Rules Cheat Sheet

These powerful rules define how nodes relate to each other structurally. Think of them as your AST GPS!

```yaml
inside:
  kind: function_declaration
```
🏠 Target node must appear inside its _parent/ancestor_ node matching the sub-rule

```yaml
has:
  kind: method_definition
```
🌳 Target node must have a _child/descendant_ node matching the sub-rule

```yaml
has:
  kind: statement_block
  field: body
```
🌳 `field` makes `has`/`inside` match nodes by their [semantic role](/advanced/core-concepts.html#kind-vs-field)

```yaml
precedes:
  pattern: function $FUNC() { $$ }
```
◀️ Target node must appear _before_ another node matching the sub-rule

```yaml
follows:
  pattern: let x = 10;
```
▶️ Target node must appear _after_ another node matching the sub-rule.

```yaml
inside:
  kind: function_declaration
  stopBy: end
```
🏠 `stopBy` makes relational rules search all the way to the end, not just immediate neighbors.

## Composite Rules Cheat Sheet

Combine multiple rules using Boolean logic. Crucially, these operations apply to a single target node!

```yaml
all:
  - pattern: const $VAR = $VALUE
  - has: { kind: string_literal }
```
✅ Node must satisfy ALL the rules in the list.

```yaml
any:
  - pattern: let $X = $Y
  - pattern: const $X = $Y
```
🧡 Node must satisfy AT LEAST ONE of the rules in the list.

```yaml
not:
  pattern: console.log($$)
```
🚫 Node must NOT satisfy the specified sub-rule.

```yaml
matches: is-function-call
```
🔄 Matches the node if that utility rule matches it. Your gateway to modularity!

## Utility Rules Cheat Sheet

Define reusable rule definitions to cut down on duplication and build complex, maintainable rule sets.

```yaml
rules:
  - id: find-my-pattern
    rule:
      matches: my-local-check
utils:
  my-local-check:
    kind: identifier
    regex: '^my'
```
🏡 Defined within the `utils` field of your current config file. Only accessible within that file.

```yaml
# In utils/my-global-check.yml
id: my-global-check
language: javascript
rule:
  kind: variable_declarator
  has:
    kind: number_literal
```
🌍 Defined in separate YAML files in global `utilsDirs` folders, accessible across your entire project.

Up to date version can be found:
https://github.com/ast-grep/ast-grep.github.io/blob/main/website/cheatsheet/rule.md
