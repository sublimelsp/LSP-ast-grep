from __future__ import annotations

SCOPE_TO_SCHEMA = {
    "DEFAULT": ("rule.json", "''"),
    "source.shell": ("bash_rule.json", "bash"),
    "source.c": ("c_rule.json", "c"),
    "source.c++": ("cpp_rule.json", "c++"),
    "source.cs": ("csharp_rule.json", "csharp"),
    "source.css": ("css_rule.json", "css"),
    "source.elixir": ("elixir_rule.json", "elixir"),
    "source.go": ("go_rule.json", "go"),
    "source.haskell": ("haskell_rule.json", "haskell"),
    "text.html.basic": ("html_rule.json", "html"),
    "source.java": ("java_rule.json", "java"),
    "source.js": ("javascript_rule.json", "javascript"),
    "source.jsx": ("javascript_rule.json", "jsx"),
    "source.json": ("json_rule.json", "json"),
    "source.Kotlin": ("kotlin_rule.json", "kotlin"),
    "source.lua": ("lua_rule.json", "lua"),
    "embedding.php": ("php_rule.json", "php"),
    "source.python": ("python_rule.json", "python"),
    "source.ruby": ("ruby_rule.json", "ruby"),
    "source.rust": ("rust_rule.json", "rust"),
    "source.scala": ("scala_rule.json", "scala"),
    "source.swift": ("swift_rule.json", "swift"),
    "source.tsx": ("tsx_rule.json", "tsx"),
    "source.ts": ("typescript_rule.json", "typescript"),
    "source.yaml": ("yaml_rule.json", "yaml"),
}

def get_language(base_scope: str) -> str:
    _, language = SCOPE_TO_SCHEMA[base_scope] if base_scope in SCOPE_TO_SCHEMA else SCOPE_TO_SCHEMA["DEFAULT"]
    return language


def get_json_schema(base_scope: str) -> str:
    json_schema, _ = SCOPE_TO_SCHEMA[base_scope] if base_scope in SCOPE_TO_SCHEMA else SCOPE_TO_SCHEMA["DEFAULT"]
    return json_schema
