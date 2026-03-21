from __future__ import annotations

from .ast_grep.cli_client import AstGrepCli
from .ast_grep.languages import get_language
from .ast_grep.right_pane import RightPane
from LSP.plugin.core.types import debounced
from typing_extensions import override
import re
import sublime
import sublime_plugin


class lsp_ast_grep_show_ast_command(sublime_plugin.TextCommand, AstGrepCli):
    @override
    def is_visible(self) -> bool:
        window = self.view.window()
        return bool(window and window.id() == RightPane.active_window_id)

    @override
    def run(self, edit: sublime.Edit) -> None:
        window = self.view.window()
        if not window:
            return
        folders = window.folders()
        if not folders:
            return
        cwd = folders[0]
        panel_name = 'ast-grep (ast output)'
        file_name = self.view.file_name()

        preselect_row = 1
        sel = self.view.sel()
        if sel:
            preselect_row = self.view.rowcol(sel[0].b)[0] + 1
        result_view = window.find_output_panel(panel_name)
        if result_view:
            result_view.set_read_only(False)
            result_view.run_command('lsp_ast_grep_clear_panel')
        else:
            result_view = window.create_output_panel(panel_name)
            result_view.set_name('Find Results')
            result_view.set_scratch(True)
        result_view.set_read_only(False)
        PANEL_FILE_REGEX = r"^(\S.*): Debug \w+:$"
        PANEL_LINE_REGEX = r"\((\d+),(\d+)\)-\(\d+,\d+\)$"
        settings = result_view.settings()
        settings.set("result_base_dir", cwd)
        settings.set("ast-grep.view", "ast-grep-ast-output-view")
        settings.set("result_file_regex", PANEL_FILE_REGEX)
        settings.set("result_line_regex", PANEL_LINE_REGEX)
        result_view.set_read_only(False)

        result_view.show(0)
        window.run_command("show_panel", {"panel": f"output.{panel_name}"})
        content = self.view.substr(sublime.Region(0, self.view.size()))
        base_scope = 'DEFAULT'
        if self.view and (syntax := self.view.syntax()):
            base_scope = syntax.scope
        language = get_language(base_scope)

        def on_done(ast: str) -> None:
            result_view.run_command(
                "append",
                {"characters": (file_name or '') + ": ", "scroll_to_end": False},
            )
            result_view.run_command("append", {"characters": ast, "scroll_to_end": False})
            result_view.set_read_only(True)
            result_view.clear_undo_stack()
            found_region = result_view.find(f" ({preselect_row},", 0, sublime.FindFlags.LITERAL) or 0
            result_view.show(found_region)

        self.ast_tree(content, language, on_done)


class AstGrepHighlightTreeNodeListener(sublime_plugin.EventListener):
    def on_hover(self, view: sublime.View, point: int, hover_zone: sublime.HoverZone):
        if RightPane.active_window_id is None:
            return
        if view.settings().get("ast-grep.view") != "ast-grep-ast-output-view":
            return
        if hover_zone != sublime.HoverZone.TEXT:
            return
        self.highlight_node_at_point(view, point)

    def on_selection_modified(self, view: sublime.View) -> None:
        if RightPane.active_window_id is None:
            return
        if view.settings().get("ast-grep.view") != "ast-grep-ast-output-view":
            return
        change_count = view.change_count()
        point = get_point(view)
        if point is None:
            return
        debounced(
            lambda: self.highlight_node_at_point(view, point),
            300,
            lambda: change_count == view.change_count(),
        )

    def highlight_node_at_point(self, view: sublime.View, point: int):
        line_text = view.substr(view.line(point))
        pattern = r"\((\d+),(\d+)\)-\((\d+),(\d+)\)"
        match = re.compile(pattern).search(line_text)
        file_name = view.substr(view.line(0)).split(":")[0]
        window = view.window()
        if not window:
            return
        source_view = window.find_open_file(file_name)
        if not source_view:
            return
        if match:
            row_start = int(match.group(1)) - 1
            col_start = int(match.group(2))
            row_end = int(match.group(3)) - 1
            col_end = int(match.group(4))
            region = sublime.Region(
                source_view.text_point(row_start, col_start), source_view.text_point(row_end, col_end)
            )
            source_view.add_regions(
                "ast_grep_highlight_ast_node", [region], "region.yellowish", flags=sublime.DRAW_NO_OUTLINE
            )
            sublime.set_timeout(lambda: source_view.erase_regions("ast_grep_highlight_ast_node"), 1000)


def get_point(view: sublime.View) -> int | None:
    sel = view.sel()
    region = sel[0] if sel else None
    if region is None:
        return
    return region.b
