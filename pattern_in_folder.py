from __future__ import annotations

import sublime_plugin


class LspAstGrepPatternInFolderCommand(sublime_plugin.WindowCommand):
    def run(self, dirs: list[str] | None = None) -> None:
        if not dirs:
            return
        self.window.settings().set('lsp_ast_grep_pattern_in_folder', dirs)
        self.window.run_command('lsp_ast_grep_open')


class LspAstGrepPatternClearFoldersCommand(sublime_plugin.WindowCommand):
    def run(self) -> None:
        self.window.settings().set('lsp_ast_grep_pattern_in_folder', None)

    def is_visible(self):
        return len(self.window.settings().get('lsp_ast_grep_pattern_in_folder', [])) > 0
