from __future__ import annotations
import threading
from .plugin import LspAstGrep
from LSP.plugin.core.types import debounced
from typing import Callable, NotRequired, TypedDict
import re
import sublime
import sublime_plugin
import subprocess


class RightPane:
    @staticmethod
    def get_search_view(window: sublime.Window) -> sublime.View | None:
        return next((view for view in window.views() if view.settings().get('lsp-ast-grep.view.id') == 'ast-grep-search-view'), None)

    @staticmethod
    def get_replace_view(window: sublime.Window) -> sublime.View | None:
        return next((view for view in window.views() if view.settings().get('lsp-ast-grep.view.id') == 'ast-grep-replace-view'), None)


class lsp_ast_grep_open_command(sublime_plugin.WindowCommand):
    def run(self) -> None:
        self.window.set_layout({
            'cells': [[0, 0, 1, 2], [1, 0, 2, 1], [1, 1, 2, 2]],
            'cols': [0.0, 0.6, 1.0],
            'rows': [0.0, 0.5, 1.0]}
        )
        for view in self.window.views():
            _group, index = self.window.get_view_index(view)
            self.window.set_view_index(view, 0, index)

        syntax = 'Packages/LSP-ast-grep/AstGrepSearch.sublime-syntax'
        search_view = RightPane.get_search_view(self.window)
        if not search_view:
            search_view = self.window.new_file()
            search_view.settings().set('lsp-ast-grep.view.id', 'ast-grep-search-view')
            search_view.set_syntax_file(syntax)
            search_view.settings().set('is_widget', True) # when pasting this prevents auto-setting the sytnax
            search_view.set_name('Search')
            search_view.set_scratch(True)
        self.window.set_view_index(search_view, 1, 0)

        replace_view = RightPane.get_replace_view(self.window)
        if not replace_view:
            replace_view = self.window.new_file()
            replace_view.settings().set('lsp-ast-grep.view.id', 'ast-grep-replace-view')
            replace_view.settings().set('is_widget', True) # when pasting this prevents auto-setting the sytnax
            replace_view.set_syntax_file(syntax)
            replace_view.set_name('Replace')
            replace_view.set_scratch(True)
        self.window.set_view_index(replace_view, 2, 0)

        self.window.focus_view(search_view)


class AstGrepCli:
    def search(self, search_query:str, *, paths: list[str] | None = None, on_match: Callable[[Match], None] | None =None,
               on_done: Callable[[dict[str, list[Match]]], None] | None =None) -> None:
        [cwd] = sublime.active_window().folders()
        if not cwd:
            return

        def run_search():
            ast_cli = LspAstGrep.binary_path()
            cmd = [ast_cli, 'run', '--pattern', search_query, '--json=stream', *(paths or [])]
            process = subprocess.Popen(
                cmd,
                cwd=cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            matches: dict[str, list[Match]] = {}
            if process.stdout:
                for line in iter(process.stdout.readline, b""):
                    match: Match = sublime.decode_value(line.decode('utf-8'))  # pyright: ignore[reportAssignmentType]
                    if on_match:
                        on_match(match)
                    matches.setdefault(match['file'], []).append(match)
            _ = process.wait()
            if on_done:
                on_done(matches)

        thread = threading.Thread(target=run_search)
        thread.start()

    def replace(self, search_query:str, replace_query: str, paths: list[str] | None = None,
                on_match: Callable[[Match], None] | None =None, on_done: Callable[[dict[str, list[Match]]], None] | None =None) -> None:
        [cwd] = sublime.active_window().folders()
        if not cwd:
            return
        paths = paths or []
        def run_replace():
            ast_cli = LspAstGrep.binary_path()
            process = subprocess.Popen([ast_cli, 'run', '--pattern', search_query,  '--rewrite',  replace_query, '--json=stream', *paths ],
               cwd=cwd,
               stdout=subprocess.PIPE,
               stderr=subprocess.PIPE)
            matches: dict[str, list[Match]] = {}
            if process.stdout:
                for line in iter(process.stdout.readline, b""):
                    match: Match = sublime.decode_value(line.decode('utf-8'))  # pyright: ignore[reportAssignmentType]
                    if on_match:
                        on_match(match)
                    matches.setdefault(match['file'], []).append(match)
            _ = process.wait()
            if on_done:
                on_done(matches)

        thread = threading.Thread(target=run_replace)
        thread.start()

    def higlight_matches(self, view: sublime.View) -> None:
        window = view.window()
        if not window:
            return
        search_view = RightPane.get_search_view(window)
        if not search_view:
            return
        search_query = search_view.substr(sublime.Region(0, search_view.size()))
        active_view = window.active_view_in_group(0)
        if active_view is None:
            return
        file_name = active_view.file_name()
        if file_name is None:
            return

        def on_done(matches: dict[str, list[Match]]) -> None:
            file_matches = matches.get(file_name) or []
            for key in active_view.settings().get('ast-grep-var-key') or []:
                active_view.erase_regions(key)
            match_regions: list[sublime.Region] = []
            single_regions: dict[str, list[sublime.Region]] = {}
            multi_regions: dict[str, list[sublime.Region]] = {}
            for match in file_matches:
                start_point = active_view.text_point(match['range']['start']['line'], match['range']['start']['column'])
                end_point = active_view.text_point(match['range']['end']['line'], match['range']['end']['column'])
                match_regions.append(sublime.Region(start_point, end_point))
                for var_name, meta_var in match.get('metaVariables', {}).get('single', {}).items():
                    start_point = active_view.text_point(meta_var['range']['start']['line'], meta_var['range']['start']['column'])
                    end_point = active_view.text_point(meta_var['range']['end']['line'], meta_var['range']['end']['column'])
                    single_regions.setdefault(var_name, []).append(sublime.Region(start_point, end_point))
                for var_name, meta_vars in match.get('metaVariables', {}).get('multi', {}).items():
                    for meta_var in meta_vars:
                        start_point = active_view.text_point(meta_var['range']['start']['line'], meta_var['range']['start']['column'])
                        end_point = active_view.text_point(meta_var['range']['end']['line'], meta_var['range']['end']['column'])
                        multi_regions.setdefault(var_name, []).append(sublime.Region(start_point, end_point))
            erase_keys = ['lsp-ast-grep.match-line']
            active_view.add_regions('lsp-ast-grep.match-line', match_regions, 'region.bluish', flags=sublime.RegionFlags.DRAW_NO_FILL)
            for key in single_regions:
                regions = single_regions[key]
                erase_keys.append(f'lsp-ast-grep.match-single.{key}')
                active_view.add_regions(f'lsp-ast-grep.match-single.{key}', regions, f'region.bluish lsp-ast-grep.match-single.{key}', flags=sublime.RegionFlags.DRAW_NO_FILL | sublime.RegionFlags.DRAW_STIPPLED_UNDERLINE| sublime.RegionFlags.DRAW_NO_OUTLINE )
            for key in multi_regions:
                regions = multi_regions[key]
                erase_keys.append(f'lsp-ast-grep.match-multi.{key}')
                active_view.add_regions(f'lsp-ast-grep.match-multi.{key}', regions, f'region.bluish lsp-ast-grep.match-multi.{key}', flags=sublime.RegionFlags.DRAW_NO_FILL | sublime.RegionFlags.DRAW_STIPPLED_UNDERLINE| sublime.RegionFlags.DRAW_NO_OUTLINE )
            active_view.settings().set('ast-grep-var-key', erase_keys)

        self.search(search_query, paths=[file_name], on_done=on_done)


class lsp_ast_grep_search_and_replace_command(sublime_plugin.WindowCommand, AstGrepCli):
    def run(self) -> None:
        search_view = next((view for view in self.window.views() if view.settings().get('lsp-ast-grep.view.id') == 'ast-grep-search-view'), None)
        if not search_view:
            return
        search_query = search_view.substr(sublime.Region(0, search_view.size()))
        if not search_query.strip():
            return
        replace_view = next((view for view in self.window.views() if view.settings().get('lsp-ast-grep.view.id') == 'ast-grep-replace-view'), None)
        if not replace_view:
            return
        replace_query = replace_view.substr(sublime.Region(0, replace_view.size()))
        if not replace_query.strip():
            return

        [cwd] = self.window.folders()
        if not cwd:
            return

        panel_name = 'ast-grep diff'
        self.result_view = self.window.find_output_panel(panel_name)
        if self.result_view:
            self.result_view.run_command('lsp_clear_panel')
        else:
            self.result_view = self.window.create_output_panel(panel_name)
            self.result_view.set_syntax_file('Packages/LSP/Syntaxes/References.sublime-syntax')
            self.result_view.set_name('Find Results')
            self.result_view.set_scratch(True)
        PANEL_FILE_REGEX = r"^(\S.*):$"
        PANEL_LINE_REGEX = r"^\s+(\d+):(\d+)"
        settings = self.result_view.settings()
        settings.set("result_base_dir", cwd)
        settings.set("result_file_regex", PANEL_FILE_REGEX)
        settings.set("result_line_regex", PANEL_LINE_REGEX)

        self.result_view.show(0)
        self.window.run_command("show_panel", {"panel": f"output.{panel_name}"})

        self.last_file_name: str | None = None

        old_reference = ''
        def on_match(match: Match) -> None:
            nonlocal old_reference
            self.result_view.set_read_only(False)
            if self.last_file_name != match['file']:
                new_text = match['file'] + ':\n'
                old_reference += new_text
                self.result_view.run_command("append", {"characters": new_text, 'scroll_to_end': False})
                self.last_file_name = match['file']
            old_reference += " {:>4}:{:<4} {}".format(match['range']['start']['line'] + 1, match['range']['start']['column'] + 1, re.sub(r'\s+', ' ', match['text'].replace('\n', ''))) + "\n\n"
            line = " {:>4}:{:<4} {}".format(match['range']['start']['line'] + 1, match['range']['start']['column'] + 1, match['replacement']) + "\n\n"
            self.result_view.run_command("append", {"characters": line, 'scroll_to_end': False})
            self.result_view.set_read_only(True)
            self.result_view.set_reference_document(old_reference)
        def on_done(_):
            selection = self.result_view.sel()
            selection.add(sublime.Region(0, self.result_view.size()))
            self.result_view.run_command('toggle_inline_diff')
            selection.clear()
            self.result_view.set_viewport_position(0)
            if self.result_view:
                # when navigating find next/preview result if a new view needs to be open
                # to this trick to force the new view to be open at group 0
                self.window.focus_group(0)
                self.window.focus_view(self.result_view)

        self.replace(search_query, replace_query, on_match=on_match, on_done=on_done)


class lsp_ast_grep_search_command(sublime_plugin.WindowCommand, AstGrepCli):
    def run(self) -> None:
        search_view = RightPane.get_search_view(self.window)
        if not search_view:
            return
        search_query = search_view.substr(sublime.Region(0, search_view.size()))
        if not search_query.strip():
            return

        [cwd] = self.window.folders()
        if not cwd:
            return

        panel_name = 'ast-grep find results'
        self.result_view = self.window.find_output_panel(panel_name)
        if self.result_view:
            self.result_view.run_command('lsp_clear_panel')
        else:
            self.result_view = self.window.create_output_panel(panel_name)
            self.result_view.set_syntax_file('Packages/LSP/Syntaxes/References.sublime-syntax')
            self.result_view.set_name('Find Results')
            self.result_view.set_scratch(True)
        PANEL_FILE_REGEX = r"^(\S.*):$"
        PANEL_LINE_REGEX = r"^\s+(\d+):(\d+)"
        settings = self.result_view.settings()
        settings.set("result_base_dir", cwd)
        settings.set("result_file_regex", PANEL_FILE_REGEX)
        settings.set("result_line_regex", PANEL_LINE_REGEX)

        self.result_view.show(0)
        self.window.run_command("show_panel", {"panel": f"output.{panel_name}"})

        self.last_file_name: str | None = None

        def on_match(match: Match) -> None:
            is_empty_view = self.result_view.size() > 0
            self.result_view.set_read_only(False)
            if self.last_file_name != match['file']:
                maybe_new_line = '\n' if is_empty_view else ''
                self.result_view.run_command("append", {"characters": maybe_new_line + match['file'] + ':\n'})
                self.last_file_name = match['file']
            line = (" {:>4}:{:<4} {}".format(match['range']['start']['line'] + 1, match['range']['start']['column'] + 1, match['lines'].split('\n')[0].strip()))
            self.result_view.run_command("append", {"characters": line + "\n"})
            self.result_view.set_read_only(True)

        def on_done(matches: dict[str, list[Match]]) -> None:
            if self.result_view:
                # when navigating find next/preview result if a new view needs to be open
                # to this trick to force the new view to be open at group 0
                self.window.focus_group(0)
                self.window.focus_view(self.result_view)

        self.result_view.run_command('lsp_clear_panel')
        self.search(search_query, on_match=on_match, on_done=on_done)


class AstGrepSearchHiglightListener(sublime_plugin.ViewEventListener, AstGrepCli):
    @classmethod
    def is_applicable(cls, settings: sublime.Settings) -> bool:
        return settings.get('lsp-ast-grep.view.id') == 'ast-grep-search-view'

    def on_modified(self) -> None:
        if self.view.is_dirty():
            return
        change_count = self.view.change_count()
        debounced(lambda: self.higlight_matches(self.view), 300, lambda: self.view.is_valid() and change_count == self.view.change_count())


class AstGrepCloseAndQueryContextListener(sublime_plugin.ViewEventListener, AstGrepCli):
    @classmethod
    def is_applicable(cls, settings: sublime.Settings) -> bool:
        return settings.get('lsp-ast-grep.view.id') in ['ast-grep-search-view', 'ast-grep-replace-view']

    def on_query_context(self, key: str, operator: int, operand: Any, match_all: bool) -> bool | None:
        # You can filter key bindings by the precense of a provider,
        if key == "ast-grep.view" and operator == sublime.QueryOperator.EQUAL and \
                isinstance(operand, str):
            return self.view.settings().get('lsp-ast-grep.view.id') == operand
        return None

    def on_pre_close(self) -> None:
        # when you close the search or replace view, close both and restore the layout
        view_id = self.view.settings().get('lsp-ast-grep.view.id')
        if not view_id:
            return
        window = self.view.window()
        if not window:
            return
        if view_id == 'ast-grep-search-view':
            replace_view = RightPane.get_replace_view(window)
            if replace_view:
                sublime.set_timeout(lambda: replace_view.close())
        search_view = RightPane.get_search_view(window)
        if search_view:
            sublime.set_timeout(lambda: search_view.close())

        def layout():
            window.set_layout({'cells': [[0, 0, 1, 1]], 'cols': [0.0, 1.0], 'rows': [0.0, 1.0]})

        sublime.set_timeout(layout)


class AstGrepSearchOpenListener(sublime_plugin.EventListener, AstGrepCli):
    @classmethod
    def is_applicable(cls, settings: sublime.Settings) -> bool:
        # todo
        return True

    def on_activated(self, view: sublime.View) -> None:
        self.higlight_matches(view)

    def on_load(self, view: sublime.View) -> None:
        self.higlight_matches(view)

    def on_clone(self, view: sublime.View) -> None:
        self.higlight_matches(view)


# https://ast-grep.github.io/guide/tools/json.html#match-object-type
class Match(TypedDict):
    text: str
    range: RangeInfo
    file: str # relative path to the file
    # the surrounding lines of the match.
    # It can be more than one line if the match spans multiple ones.
    lines: str
    # optional replacement if the match has a replacement
    replacement: NotRequired[str]
    replacementOffsets: NotRequired[ByteOffset]
    metaVariables: MetaVariables # optional metavars generated in the match


class RangeInfo(TypedDict):
    byteOffset: ByteOffset
    start: Position
    end: Position

# // UTF-8 encoded byte offset
class ByteOffset(TypedDict):
    start: int
    end: int


class Position(TypedDict):
    line: int  # zero-based line number
    column: int #zero-based column number


class MetaVariables(TypedDict):
    single: dict[str, MetaVar]
    multi: dict[str, list[MetaVar]]
    transformed: dict[str, str]


class MetaVar(TypedDict):
    text: str
    range: RangeInfo

