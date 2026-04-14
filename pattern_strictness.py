from __future__ import annotations

from typing_extensions import override
import sublime
import sublime_plugin


class LspAstGrepSetPatternStrictnessSmartCommand(sublime_plugin.WindowCommand):
    def __init__(self, window: sublime.Window) -> None:
        super().__init__(window)
        window.settings().setdefault('lsp_ast_grep_strictness', 'smart')

    @override
    def run(self):
        self.window.settings().set('lsp_ast_grep_strictness', 'smart')

    @override
    def is_checked(self) -> bool:
        return self.window.settings().get('lsp_ast_grep_strictness') == 'smart'


class LspAstGrepSetPatternStrictnessCstCommand(sublime_plugin.WindowCommand):
    @override
    def run(self):
        self.window.settings().set('lsp_ast_grep_strictness', 'cst')

    @override
    def is_checked(self) -> bool:
        return self.window.settings().get('lsp_ast_grep_strictness') == 'cst'


class LspAstGrepSetPatternStrictnessAstCommand(sublime_plugin.WindowCommand):
    @override
    def run(self):
        self.window.settings().set('lsp_ast_grep_strictness', 'ast')

    @override
    def is_checked(self) -> bool:
        return self.window.settings().get('lsp_ast_grep_strictness') == 'ast'

class LspAstGrepSetPatternStrictnessRelaxedCommand(sublime_plugin.WindowCommand):
    @override
    def run(self):
        self.window.settings().set('lsp_ast_grep_strictness', 'relaxed')

    @override
    def is_checked(self) -> bool:
        return self.window.settings().get('lsp_ast_grep_strictness') == 'relaxed'

class LspAstGrepSetPatternStrictnessSignatureCommand(sublime_plugin.WindowCommand):
    @override
    def run(self):
        self.window.settings().set('lsp_ast_grep_strictness', 'signature')

    @override
    def is_checked(self) -> bool:
        return self.window.settings().get('lsp_ast_grep_strictness') == 'signature'
