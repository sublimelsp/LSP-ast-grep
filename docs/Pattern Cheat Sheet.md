# Pattern Syntax Cheat Sheet

This cheat sheet provides a concise overview of ast-grep's pattern syntax. It covers structural matching, meta-variables, and capturing logic.

## Structural Matching

Patterns are code templates that match the AST (Abstract Syntax Tree). They are formatting-insensitive and match nested expressions.

```javascript
a + 1
```
🔍 Match a node by code structure. Matches `const b = a + 1` or `func(a + 1)`.

## Meta Variables

Meta variables start with the $ sign, followed by a name composed of upper case letters A-Z, underscore _ or digits 1-9. $META_VARIABLE is a wildcard expression that can match any single AST node.

```javascript
console.log($ARG)
```
🧩 Match a single named AST node. Similar to a regex `.` but for code structures.

```javascript
$_
```
⚡ Non-capturing match. Starting with an underscore ignores identity and boosts performance.

```javascript
console.log($$$ARGS)
```
🔢 Multi Meta Variables. Match zero or more arguments, perfect for functions with varying inputs.

```javascript
$_FUNC($_FUNC)
```
🥷 Non Capturing Match. Meta variables with name starting with underscore _ will not be captured.

```javascript
$$VAR
```
🧩 Capture Unnamed Nodes.

A meta variable pattern $META will capture named nodes by default.
To capture unnamed nodes, you can use double dollar sign $$VAR.

It is possible to convert CST to AST if we don't care about punctuation and whitespaces. Tree-sitter has two types of nodes: named nodes and unnamed nodes(anonymous nodes).

The more important named nodes are defined with a regular name in the grammar rules, such as binary_expression or identifier. The less important unnamed nodes are defined with literal strings such as "," or "+".


