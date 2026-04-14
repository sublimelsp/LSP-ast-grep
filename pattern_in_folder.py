from __future__ import annotations

from .ast_grep.right_pane import RightPane
import sublime_plugin


class LspAstGrepPatternInFolderCommand(sublime_plugin.WindowCommand):
    def run(self, dirs: list[str] | None = None) -> None:
        if not dirs:
            return
        old = self.window.settings().get('lsp_ast_grep_pattern_in_folder') or []
        self.window.settings().set('lsp_ast_grep_pattern_in_folder', list(set([*old, *dirs])))
        self.window.run_command('lsp_ast_grep_open')


class LspAstGrepPatternClearFoldersCommand(sublime_plugin.WindowCommand):
    def run(self) -> None:
        self.window.settings().set('lsp_ast_grep_pattern_in_folder', [])
        pattern_view = RightPane.pattern_view(self.window)
        if pattern_view:
            pattern_view.erase_phantoms('lsp_ast_grep_where_phantom')

    def is_visible(self):
        return len(self.window.settings().get('lsp_ast_grep_pattern_in_folder', [])) > 0
