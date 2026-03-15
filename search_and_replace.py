from __future__ import annotations

from .plugin import LspAstGrep
from functools import partial
from LSP.plugin.core.types import debounced
from typing import Any
from typing import Callable
from typing import NotRequired
from typing import TypedDict
from typing_extensions import override
import re
import sublime
import sublime_plugin
import subprocess
import threading

BUTTONS_TEMPLATE = """
<style>
    html {{
        background-color: transparent;
        margin-top: 1.5rem;
        margin-bottom: 0.5rem;
    }}
    a {{
        line-height: 1.6rem;
        padding-left: 0.6rem;
        padding-right: 0.6rem;
        border-width: 1px;
        border-style: solid;
        border-color: #fff4;
        border-radius: 4px;
        color: #cccccc;
        background-color: #3f3f3f;
        text-decoration: none;
    }}
    html.light a {{
        border-color: #000a;
        color: white;
        background-color: #636363;
    }}
    a.primary, html.light a.primary {{
        background-color: color(var(--accent) min-contrast(white 6.0));
    }}
</style>
<body id='lsp-buttons'>
    <a href='{apply}' class='primary'>Apply</a>&nbsp;
    <a href='{discard}'>Discard</a>
</body>"""


class RightPane:
    active_window_id: int| None= None
    @staticmethod
    def get_pattern_view(window: sublime.Window) -> sublime.View | None:
        return next((v for v in window.views() if v.settings().get('ast-grep.view') == 'pattern-view'), None)

    @staticmethod
    def get_yaml_rule_view(window: sublime.Window) -> sublime.View | None:
        return next((v for v in window.views() if v.settings().get('ast-grep.view') == 'yaml-rule-view'), None)

    @staticmethod
    def get_rewrite_view(window: sublime.Window) -> sublime.View | None:
        return next((v for v in window.views() if v.settings().get('ast-grep.view') == 'rewrite-view'), None)


class lsp_ast_grep_open_command(sublime_plugin.WindowCommand):
    @override
    def run(self) -> None:
        active_view = self.window.active_view()
        self.window.set_layout({
            'cells': [[0, 0, 1, 2], [1, 0, 2, 1], [1, 1, 2, 2]],
            'cols': [0.0, 0.6, 1.0],
            'rows': [0.0, 0.5, 1.0]}
        )
        for view in self.window.views():
            _group, index = self.window.get_view_index(view)
            self.window.set_view_index(view, 0, index)

        pattern_syntax = 'Packages/LSP-ast-grep/AstGrepPattern.sublime-syntax'
        pattern_view = RightPane.get_pattern_view(self.window)
        if not pattern_view:
            pattern_view = self.window.new_file()
            pattern_view.settings().set('ast-grep.view', 'pattern-view')
            pattern_view.set_syntax_file(pattern_syntax)
            pattern_view.settings().set('is_widget', True) # when pasting this prevents auto-setting the sytnax
            pattern_view.set_name('Pattern')
            pattern_view.set_scratch(True)
        self.window.set_view_index(pattern_view, 1, 0)

        yaml_syntax = 'Packages/LSP-ast-grep/AstGrepYaml.sublime-syntax'
        yaml_rule_view = RightPane.get_yaml_rule_view(self.window)
        if not yaml_rule_view:
            yaml_rule_view = self.window.new_file()
            yaml_rule_view.settings().set('ast-grep.view', 'yaml-rule-view')
            yaml_rule_view.set_syntax_file(yaml_syntax)
            yaml_rule_view.set_name('Advanced')
            yaml_rule_view.run_command("append", {"characters": get_yaml_content(active_view)})
            yaml_rule_view.set_scratch(True)
        self.window.set_view_index(yaml_rule_view, 1, 1)

        rewrite_view = RightPane.get_rewrite_view(self.window)
        if not rewrite_view:
            rewrite_view = self.window.new_file()
            rewrite_view.settings().set('ast-grep.view', 'rewrite-view')
            rewrite_view.settings().set('is_widget', True) # when pasting this prevents auto-setting the sytnax
            rewrite_view.set_syntax_file(pattern_syntax)
            rewrite_view.set_name('Rewrite')
            rewrite_view.set_scratch(True)
        self.window.set_view_index(rewrite_view, 2, 0)

        self.window.focus_view(pattern_view)
        RightPane.active_window_id = self.window.id()


class AstGrepCli:
    process: subprocess.Popen[bytes] | None = None

    def ast_tree(self, file_content: str, language: str, on_done: Callable[[str], None] | None = None) -> None:
        if AstGrepCli.process:
            AstGrepCli.process.kill()
            AstGrepCli.process = None
        folders = sublime.active_window().folders()
        if not folders:
            return
        cwd = folders[0]
        def run_search() -> None:
            ast_cli = LspAstGrep.binary_path()
            cmd = [ast_cli, "-p", file_content, "--lang", language, "--debug-query=cst"]
            process = subprocess.Popen(
                cmd,
                cwd=cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            AstGrepCli.process = process
            matches: list[str] = []
            pattern = r"\((\d+),(\d+)\)-\((\d+),(\d+)\)"
            if process.stderr:
                for line in process.stderr:
                    zero_based_output = line.decode("utf-8")
                    if "Cannot parse query" in zero_based_output:
                        break
                    # Convert ast-grep's 0-based rows to 1-based coordinates
                    # Example: "future_import_statement (0,0)-(0,34)" -> "(1,0)-(1,34)"
                    one_based_row = re.sub(
                        pattern,
                        lambda m: f"({int(m.group(1)) + 1},{m.group(2)})-({int(m.group(3)) + 1},{m.group(4)})",
                        zero_based_output,
                    )
                    matches.append(one_based_row)
            _ = process.wait()
            if on_done:
                sublime.set_timeout(partial(on_done,"".join(matches)), 100)

        thread = threading.Thread(target=run_search)
        thread.start()


    def pattern_search(self, search_query:str, *, paths: list[str] | None = None,
        on_match: Callable[[Match], None] | None =None,
        on_done: Callable[[dict[str, list[Match]]], None] | None =None
    ) -> None:
        if AstGrepCli.process:
            AstGrepCli.process.kill()
            AstGrepCli.process = None
        folders = sublime.active_window().folders()
        if not folders:
            return
        cwd = folders[0]
        search_paths = paths or folders
        def run_search() -> None:
            ast_cli = LspAstGrep.binary_path()
            cmd = [ast_cli, 'run', '--pattern', search_query, '--json=stream', *search_paths]
            process = subprocess.Popen(
                cmd,
                cwd=cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            AstGrepCli.process = process
            matches: dict[str, list[Match]] = {}
            if process.stdout:
                for line in process.stdout:
                    match: Match = sublime.decode_value(line.decode('utf-8'))  # pyright: ignore[reportAssignmentType]
                    if on_match:
                        on_match(match)
                    matches.setdefault(match['file'], []).append(match)
            exit_code = process.wait()
            if exit_code != 0 and process.stderr:
                error_msg = process.stderr.read().decode("utf-8")
                raise Exception(f"Process failed with code {exit_code}: {error_msg}")
            if on_done:
                sublime.set_timeout(partial(on_done,matches), 100)

        thread = threading.Thread(target=run_search)
        thread.start()

    def rewrite(self, search_query:str, replace_query: str, paths: list[str] | None = None,
        on_match: Callable[[Match], None] | None =None,
        on_done: Callable[[dict[str, list[Match]]], None] | None =None,
        update_all: bool =False
    ) -> None:
        if AstGrepCli.process:
            AstGrepCli.process.kill()
            AstGrepCli.process = None
        folders = sublime.active_window().folders()
        if not folders:
            return
        cwd = folders[0]
        search_paths = paths or folders

        def run_replace() -> None:
            ast_cli = LspAstGrep.binary_path()
            cmd = [ast_cli, 'run', '--pattern', search_query,  '--rewrite',  replace_query]
            if update_all:
                cmd.append('--update-all')
            else:
                cmd.append('--json=stream') # looks like it is not possivle to use --update-all with --json=stream
            cmd.extend(search_paths)
            process = subprocess.Popen(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            AstGrepCli.process = process
            matches: dict[str, list[Match]] = {}
            if on_match and process.stdout:
                for line in process.stdout:
                    if AstGrepCli.process != process:
                        return
                    match: Match = sublime.decode_value(line.decode('utf-8'))  # pyright: ignore[reportAssignmentType]
                    on_match(match)
                    matches.setdefault(match['file'], []).append(match)
            exit_code = process.wait()
            if exit_code != 0 and process.stderr:
                error_msg = process.stderr.read().decode("utf-8")
                raise Exception(f"Process failed with code {exit_code}: {error_msg}")
            if on_done:
                sublime.set_timeout(partial(on_done,matches), 100)

        thread = threading.Thread(target=run_replace)
        thread.start()

    def rewrite_inline_rule(self, inline_rules:str, paths: list[str] | None = None,
        on_match: Callable[[Match], None] | None =None,
        on_done: Callable[[dict[str, list[Match]]], None] | None =None,
        update_all: bool = False # TODO: Implement update all
    ) -> None:
        if AstGrepCli.process:
            AstGrepCli.process.kill()
            AstGrepCli.process = None
        folders = sublime.active_window().folders()
        if not folders:
            return
        cwd = folders[0]
        search_paths = paths or folders

        def run_replace() -> None:
            ast_cli = LspAstGrep.binary_path()
            cmd = [ast_cli, 'scan', '--json=stream', '--inline-rules', 'id: inline-rule\n' + inline_rules]
            cmd.extend(search_paths)
            process = subprocess.Popen(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            AstGrepCli.process = process
            matches: dict[str, list[Match]] = {}

            if process.stdout:
                for line in process.stdout:
                    if AstGrepCli.process != process:
                        return
                    match: Match = sublime.decode_value(line.decode('utf-8'))  # pyright: ignore[reportAssignmentType]
                    if on_match:
                        on_match(match)
                    matches.setdefault(match['file'], []).append(match)
            exit_code = process.wait()
            if exit_code != 0 and process.stderr:
                error_msg = process.stderr.read().decode("utf-8")
                raise Exception(f"Process failed with code {exit_code}: {error_msg}")
            if on_done:
                sublime.set_timeout(partial(on_done,matches), 100)

        thread = threading.Thread(target=run_replace)
        thread.start()

    def highlight_matches(self, view: sublime.View) -> None:
        window = view.window()
        if not window:
            return
        pattern_view = RightPane.get_pattern_view(window)
        if not pattern_view:
            return
        search_query = pattern_view.substr(sublime.Region(0, pattern_view.size()))
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
            active_view.add_regions('lsp-ast-grep.match-line', match_regions, 'region.bluish', flags=sublime.RegionFlags.DRAW_NO_FILL | sublime.RegionFlags.NO_UNDO)
            for key in single_regions:
                regions = single_regions[key]
                erase_keys.append(f'lsp-ast-grep.match-single.{key}')
                active_view.add_regions(f'lsp-ast-grep.match-single.{key}', regions, f'region.bluish lsp-ast-grep.match-single.{key}', flags=sublime.RegionFlags.DRAW_NO_FILL | sublime.RegionFlags.DRAW_STIPPLED_UNDERLINE| sublime.RegionFlags.DRAW_NO_OUTLINE | sublime.RegionFlags.NO_UNDO )
            for key in multi_regions:
                regions = multi_regions[key]
                erase_keys.append(f'lsp-ast-grep.match-multi.{key}')
                active_view.add_regions(f'lsp-ast-grep.match-multi.{key}', regions, f'region.bluish lsp-ast-grep.match-multi.{key}', flags=sublime.RegionFlags.DRAW_NO_FILL | sublime.RegionFlags.DRAW_STIPPLED_UNDERLINE| sublime.RegionFlags.DRAW_NO_OUTLINE | sublime.RegionFlags.NO_UNDO )
            active_view.settings().set('ast-grep-var-key', erase_keys)
        self.pattern_search(search_query, paths=[file_name], on_done=on_done)

    def highlight_matches_yaml_rule(self, view: sublime.View) -> None:
        window = view.window()
        if not window:
            return
        yaml_rule_view = RightPane.get_yaml_rule_view(window)
        if not yaml_rule_view:
            return

        start = yaml_rule_view.find("^language:", 0)
        end = yaml_rule_view.find("^fix:", 0)
        search_query = yaml_rule_view.substr(sublime.Region(start.begin() or 0, end.begin() or yaml_rule_view.size()))
        active_view = window.active_view_in_group(0)
        if active_view is None:
            return
        file_name = active_view.file_name()
        if file_name is None:
            return

        def on_done(matches: dict[str, list[Match]]) -> None:
            file_matches = matches.get(file_name) or []
            for key in active_view.settings().get("ast-grep-var-key") or []:
                active_view.erase_regions(key)
            match_regions: list[sublime.Region] = []
            single_regions: dict[str, list[sublime.Region]] = {}
            multi_regions: dict[str, list[sublime.Region]] = {}
            for match in file_matches:
                start_point = active_view.text_point(match["range"]["start"]["line"], match["range"]["start"]["column"])
                end_point = active_view.text_point(match["range"]["end"]["line"], match["range"]["end"]["column"])
                match_regions.append(sublime.Region(start_point, end_point))
                for var_name, meta_var in match.get("metaVariables", {}).get("single", {}).items():
                    start_point = active_view.text_point(
                        meta_var["range"]["start"]["line"], meta_var["range"]["start"]["column"]
                    )
                    end_point = active_view.text_point(
                        meta_var["range"]["end"]["line"], meta_var["range"]["end"]["column"]
                    )
                    single_regions.setdefault(var_name, []).append(sublime.Region(start_point, end_point))
                for var_name, meta_vars in match.get("metaVariables", {}).get("multi", {}).items():
                    for meta_var in meta_vars:
                        start_point = active_view.text_point(
                            meta_var["range"]["start"]["line"], meta_var["range"]["start"]["column"]
                        )
                        end_point = active_view.text_point(
                            meta_var["range"]["end"]["line"], meta_var["range"]["end"]["column"]
                        )
                        multi_regions.setdefault(var_name, []).append(sublime.Region(start_point, end_point))
            erase_keys = ["lsp-ast-grep.match-line"]
            active_view.add_regions(
                "lsp-ast-grep.match-line",
                match_regions,
                "region.bluish",
                flags=sublime.RegionFlags.DRAW_NO_FILL | sublime.RegionFlags.NO_UNDO,
            )
            for key in single_regions:
                regions = single_regions[key]
                erase_keys.append(f"lsp-ast-grep.match-single.{key}")
                active_view.add_regions(
                    f"lsp-ast-grep.match-single.{key}",
                    regions,
                    f"region.bluish lsp-ast-grep.match-single.{key}",
                    flags=sublime.RegionFlags.DRAW_NO_FILL
                    | sublime.RegionFlags.DRAW_STIPPLED_UNDERLINE
                    | sublime.RegionFlags.DRAW_NO_OUTLINE
                    | sublime.RegionFlags.NO_UNDO,
                )
            for key in multi_regions:
                regions = multi_regions[key]
                erase_keys.append(f"lsp-ast-grep.match-multi.{key}")
                active_view.add_regions(
                    f"lsp-ast-grep.match-multi.{key}",
                    regions,
                    f"region.bluish lsp-ast-grep.match-multi.{key}",
                    flags=sublime.RegionFlags.DRAW_NO_FILL
                    | sublime.RegionFlags.DRAW_STIPPLED_UNDERLINE
                    | sublime.RegionFlags.DRAW_NO_OUTLINE
                    | sublime.RegionFlags.NO_UNDO,
                )
            active_view.settings().set("ast-grep-var-key", erase_keys)

        self.rewrite_inline_rule(search_query, paths=[file_name], on_done=on_done)

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
        panel_name = 'ast-grep (ast)'
        file_name = self.view.file_name()

        preselect_row = 1
        sel = self.view.sel()
        if sel:
            preselect_row = self.view.rowcol(sel[0].b)[0] + 1
        self.result_view = window.find_output_panel(panel_name)
        if self.result_view:
            self.result_view.set_read_only(False)
            self.result_view.run_command('lsp_ast_grep_clear_panel')
        else:
            self.result_view = window.create_output_panel(panel_name)
            self.result_view.set_name('Find Results')
            self.result_view.set_scratch(True)
        self.result_view.set_read_only(False)
        PANEL_FILE_REGEX = r"^(\S.*): Debug \w+:$"
        PANEL_LINE_REGEX = r"\((\d+),(\d+)\)-\(\d+,\d+\)$"
        settings = self.result_view.settings()
        settings.set("result_base_dir", cwd)
        settings.set("ast-grep.view", "ast-grep-ast-output-view")
        settings.set("result_file_regex", PANEL_FILE_REGEX)
        settings.set("result_line_regex", PANEL_LINE_REGEX)
        self.result_view.set_read_only(False)

        self.result_view.show(0)
        window.run_command("show_panel", {"panel": f"output.{panel_name}"})
        content = self.view.substr(sublime.Region(0,self.view.size()))
        base_scope = 'DEFAULT'
        if self.view and (syntax := self.view.syntax()):
            base_scope = syntax.scope
        _, language = scope_to_schema[base_scope] if base_scope in scope_to_schema else scope_to_schema["DEFAULT"]

        def on_done(ast: str) -> None:
            self.result_view.run_command(
                "append",
                {"characters": (file_name or '') + ": ", "scroll_to_end": False},
            )
            self.result_view.run_command("append", {"characters": ast, "scroll_to_end": False})
            self.result_view.set_read_only(True)
            self.result_view.clear_undo_stack()
            found_region = self.result_view.find(f" ({preselect_row},", 0, sublime.FindFlags.LITERAL) or 0
            self.result_view.show(found_region)

        self.ast_tree(content, language, on_done)

class AstGrepHighlightTreeNodeccListener(sublime_plugin.EventListener):
    def on_hover(self, view: sublime.View, point: int, hover_zone: sublime.HoverZone):
        if RightPane.active_window_id is None:
            return
        if view.settings().get("ast-grep.view") != "ast-grep-ast-output-view":
            return
        if hover_zone != sublime.HoverZone.TEXT:
            return
        self.highlight_node_at_point(view, point)

    def on_selection_modified(self, view: sublime.View) -> None:
        if view.settings().get("ast-grep.view") != "ast-grep-ast-output-view":
            return
        change_count = view.change_count()
        point = get_point(view)
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
        source_view = view.window().find_open_file(file_name)
        if not source_view:
            return
        if match:
            row_start = int(match.group(1)) - 1
            col_start = int(match.group(2))
            row_end = int(match.group(3)) - 1
            col_end = int(match.group(4))
            region = sublime.Region(
                source_view.text_point(row_start, col_start),
                source_view.text_point(row_end, col_end)
            )
            source_view.add_regions(
                "ast_grep_highlight_ast_node", [region], "region.yellowish", flags=sublime.DRAW_NO_OUTLINE
            )
            sublime.set_timeout(lambda: source_view.erase_regions("ast_grep_highlight_ast_node"), 1000)


class lsp_ast_grep_pattern_and_rewrite_command(sublime_plugin.WindowCommand, AstGrepCli):
    @override
    def run(self) -> None:
        pattern_view = RightPane.get_pattern_view(self.window)
        if not pattern_view:
            return
        search_query = pattern_view.substr(sublime.Region(0, pattern_view.size()))
        if not search_query.strip():
            return
        rewrite_view = RightPane.get_rewrite_view(self.window)
        if not rewrite_view:
            return
        replace_query = rewrite_view.substr(sublime.Region(0, rewrite_view.size()))
        if not replace_query.strip():
            return

        folders = self.window.folders()
        if not folders:
            return
        cwd=folders[0]

        panel_name = 'ast-grep (search and replace)'
        self.result_view = self.window.find_output_panel(panel_name)
        if self.result_view:
            self.result_view.run_command('lsp_ast_grep_clear_panel')
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

        self.phantom_set = sublime.PhantomSet(self.result_view, "lsp_ast_grep_accept_buttons")
        old_reference = ''
        def on_match(match: Match) -> None:
            nonlocal old_reference
            if 'replacement' not in match:
                print('LSP-ast-grep: "replacement" key is missing in match dict. Skipping.')
                return
            self.result_view.set_read_only(False)
            if not self.result_view.size():
                # add one extra new line, when the view is clear for the phantom button
                old_reference = '\n'
                self.result_view.run_command("append", {"characters": '\n', 'scroll_to_end': False})
            if self.last_file_name != match['file']:
                new_text = match['file'] + ':\n'
                old_reference += new_text
                self.result_view.run_command("append", {"characters": new_text, 'scroll_to_end': False})
                self.last_file_name = match['file']
            old_reference += " {:>4}:{:<4} {}".format(match['range']['start']['line'] + 1, match['range']['start']['column'] + 1, re.sub(r'\s+', ' ', match['text'].replace('\n', ''))) + "\n\n"
            line =           " {:>4}:{:<4} {}".format(match['range']['start']['line'] + 1, match['range']['start']['column'] + 1, re.sub(r'\s+', ' ', match['replacement'].replace('\n', ''))) + "\n\n"

            self.result_view.run_command("append", {"characters": line, 'scroll_to_end': False})
            self.result_view.set_read_only(True)
            self.result_view.set_reference_document(old_reference)
            self.result_view.clear_undo_stack()

        def on_done(matches: dict[str, list[Match]]) -> None:
            nonlocal old_reference
            def toggle_diff():
                selection = self.result_view.sel()
                selection.add(sublime.Region(0, self.result_view.size()))
                self.result_view.run_command('toggle_inline_diff')
                selection.clear()
                if self.result_view:
                    self.result_view.show(0, show_surrounds=False, keep_to_left=False, animate=False)
            sublime.set_timeout(toggle_diff, 0)
            file_count = len(matches)
            total_changes = sum(len(value) for value in matches.values())
            characters = f"Apply {total_changes} changes across {file_count} files?\n"
            old_reference = characters + old_reference
            self.result_view.run_command('lsp_ast_grep_insert', {
                "point": 0,
                "characters": characters
            })
            self.result_view.set_reference_document(old_reference)
            buttons_html = BUTTONS_TEMPLATE.format(
                apply=sublime.command_url('chain', {
                    'commands': [
                        ['hide_panel', {}],
                        ['lsp_ast_grep_accept_replace', {
                            'search_query': search_query,
                            'replace_query': replace_query
                        }]
                    ]
                }),
                discard=sublime.command_url('chain', {
                    'commands': [
                        ['hide_panel', {}],
                    ]
                })
            )
            self.phantom_set.update([
                sublime.Phantom(sublime.Region(-1, -1), buttons_html, sublime.PhantomLayout.BLOCK)
            ])


        self.result_view.set_read_only(False)
        self.result_view.run_command('lsp_ast_grep_clear_panel')
        self.result_view.set_reference_document('')
        self.rewrite(search_query, replace_query, on_match=on_match, on_done=on_done)


class lsp_ast_grep_accept_replace_command(sublime_plugin.WindowCommand, AstGrepCli):
    def run(self, search_query: str, replace_query: str) -> None:
        def on_done(_matches: dict[str, list[Match]]) -> None:
            self.window.status_message("LSP-ast-grep: Edits applied.")

        self.rewrite(search_query, replace_query, on_done=on_done, update_all=True)


class lsp_ast_grep_pattern_command(sublime_plugin.WindowCommand, AstGrepCli):
    def run(self) -> None:
        pattern_view = RightPane.get_pattern_view(self.window)
        if not pattern_view:
            return
        search_query = pattern_view.substr(sublime.Region(0, pattern_view.size()))
        if not search_query.strip():
            return

        folders = self.window.folders()
        if not folders:
            return
        cwd = folders[0]

        panel_name = 'ast-grep (search)'
        self.result_view = self.window.find_output_panel(panel_name)
        if self.result_view:
            self.result_view.run_command('lsp_ast_grep_clear_panel')
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
            self.result_view.clear_undo_stack()

        def on_done(matches: dict[str, list[Match]]) -> None:
            if self.result_view:
                self.result_view.show(0)
            file_count = len(matches)
            total_changes = sum(len(value) for value in matches.values())
            characters = f"Found {total_changes} matches across {file_count} files\n\n"
            self.result_view.run_command('lsp_ast_grep_insert', {
                "point": 0,
                "characters": characters
            })

        self.result_view.set_read_only(False)
        self.result_view.run_command('lsp_ast_grep_clear_panel')
        self.pattern_search(search_query, on_match=on_match, on_done=on_done)


class AstGrepSearchHighlightListener(sublime_plugin.ViewEventListener, AstGrepCli):
    @classmethod
    @override
    def is_applicable(cls, settings: sublime.Settings) -> bool:
        return settings.get("ast-grep.view") in ["pattern-view", "yaml-rule-view"]

    def on_modified(self) -> None:
        if self.view.is_dirty():
            return
        view_id = self.view.settings().get("ast-grep.view")
        if view_id == 'pattern-view':
            change_count = self.view.change_count()
            debounced(lambda: self.highlight_matches(self.view), 300, lambda: self.view.is_valid() and change_count == self.view.change_count())
        if view_id == "yaml-rule-view":
            change_count = self.view.change_count()
            debounced(
                lambda: self.highlight_matches_yaml_rule(self.view),
                300,
                lambda: self.view.is_valid() and change_count == self.view.change_count(),
            )


class AstGrepCloseAndQueryContextListener(sublime_plugin.ViewEventListener, AstGrepCli):
    @classmethod
    @override
    def is_applicable(cls, settings: sublime.Settings) -> bool:
        return settings.get('ast-grep.view') in ['pattern-view', 'rewrite-view', 'yaml-rule-view']

    def on_query_context(self, key: str, operator: int, operand: Any, match_all: bool) -> bool | None:
        # You can filter key bindings by the precense of a provider,
        if key == "ast-grep.view" and operator == sublime.QueryOperator.EQUAL and \
                isinstance(operand, str):
            return self.view.settings().get('ast-grep.view') == operand
        return None

    def on_pre_close(self) -> None:
        # when you close the search or replace view, close both and restore the layout
        view_id = self.view.settings().get('ast-grep.view')
        if not view_id:
            return
        window = self.view.window()
        if not window:
            return
        rewrite_view = RightPane.get_rewrite_view(window)
        if rewrite_view:
            sublime.set_timeout(lambda: rewrite_view.close())
        yaml_rule_view = RightPane.get_yaml_rule_view(window)
        if yaml_rule_view:
            sublime.set_timeout(lambda: yaml_rule_view.close())
        pattern_view = RightPane.get_pattern_view(window)
        if pattern_view:
            sublime.set_timeout(lambda: pattern_view.close())

        # clear highlight regions on pane close
        for v in window.views():
            for key in v.settings().get('ast-grep-var-key') or []:
                v.erase_regions(key)

        def layout():
            window.set_layout({'cells': [[0, 0, 1, 1]], 'cols': [0.0, 1.0], 'rows': [0.0, 1.0]})

        sublime.set_timeout(layout)
        RightPane.active_window_id = None


class AstGrepSearchOpenListener(sublime_plugin.EventListener, AstGrepCli):
    @classmethod
    def is_applicable(cls, settings: sublime.Settings) -> bool:
        return bool(RightPane.active_window_id)

    def on_activated(self, view: sublime.View) -> None:
        self.highlight_matches(view)

    def on_load(self, view: sublime.View) -> None:
        self.highlight_matches(view)
        window = view.window()
        if window and window.active_group() != 0 and window.id() == RightPane.active_window_id:
            window.set_view_index(view, 0, -1)

    def on_clone(self, view: sublime.View) -> None:
        self.highlight_matches(view)

    def on_post_save(self, view: sublime.View) -> None:
        self.highlight_matches(view)


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


class LspAstGrepClearPanelCommand(sublime_plugin.TextCommand):
    """
    A clear_panel command to clear the error panel.
    """
    @override
    def run(self, edit: sublime.Edit) -> None:
        self.view.erase(edit, sublime.Region(0, self.view.size()))


class LspAstGrepInsertCommand(sublime_plugin.TextCommand):
    @override
    def run(self, edit: sublime.Edit, point: int = 0 , characters: str = ""):
        self.view.set_read_only(False)
        _ = self.view.insert(edit, point, characters)
        self.view.set_read_only(True)

scope_to_schema = {
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
    "source.yaml": ("yaml_rule.json", "yaml")
}


def get_yaml_content(view: sublime.View | None):
    base_scope = 'DEFAULT'
    tab_size = 4
    if view and (syntax := view.syntax()):
        base_scope = syntax.scope
        tab_size= view.settings().get('tab_size', 4)
    json_schema, language = (
        scope_to_schema[base_scope] if base_scope in scope_to_schema else scope_to_schema['DEFAULT']
    )
    indentation = str(" " * tab_size)
    content = f"""# YAML Rule is more powerful! - https://ast-grep.github.io/guide/rule-config.html#rule
# yaml-language-server: $schema=https://raw.githubusercontent.com/ast-grep/ast-grep/main/schemas/{json_schema}
language: {language}
rule:
{indentation}any:
{indentation}{indentation}- pattern: console.log($A)
{indentation}{indentation}- pattern: console.debug($A)
fix:
{indentation}logger.log($A)
"""
    return content


class lsp_ast_grep_run_rule_command(sublime_plugin.WindowCommand, AstGrepCli):
    @override
    def run(self) -> None:
        yaml_rule_view = RightPane.get_yaml_rule_view(self.window)
        if not yaml_rule_view:
            return

        # the yaml rule view has some comments at the top
        # we need to strip comments out, because the inline_rules_query will be send to the cli command
        # and the cli command will throw an error
        begin_of_yaml_rule = yaml_rule_view.find("$language:", 0)
        inline_rules_query = yaml_rule_view.substr(sublime.Region(begin_of_yaml_rule.begin() or 0, yaml_rule_view.size()))
        if not inline_rules_query.strip():
            return
        folders = self.window.folders()
        if not folders:
            return
        cwd=folders[0]

        panel_name = 'ast-grep (search and replace)'
        self.result_view = self.window.find_output_panel(panel_name)
        if self.result_view:
            self.result_view.run_command('lsp_ast_grep_clear_panel')
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

        self.phantom_set = sublime.PhantomSet(self.result_view, "lsp_ast_grep_accept_buttons")
        old_reference = ''
        def on_match(match: Match) -> None:
            nonlocal old_reference
            if 'replacement' not in match:
                print('LSP-ast-grep: "replacement" key is missing in match dict. Skipping.')
                return
            self.result_view.set_read_only(False)
            if not self.result_view.size():
                # add one extra new line, when the view is clear for the phantom button
                old_reference = '\n'
                self.result_view.run_command("append", {"characters": '\n', 'scroll_to_end': False})
            if self.last_file_name != match['file']:
                new_text = match['file'] + ':\n'
                old_reference += new_text
                self.result_view.run_command("append", {"characters": new_text, 'scroll_to_end': False})
                self.last_file_name = match['file']
            old_reference += " {:>4}:{:<4} {}".format(match['range']['start']['line'] + 1, match['range']['start']['column'] + 1, re.sub(r'\s+', ' ', match['text'].replace('\n', ''))) + "\n\n"
            line =           " {:>4}:{:<4} {}".format(match['range']['start']['line'] + 1, match['range']['start']['column'] + 1, match['replacement']) + "\n\n"

            self.result_view.run_command("append", {"characters": line, 'scroll_to_end': False})
            self.result_view.set_read_only(True)
            self.result_view.set_reference_document(old_reference)
            self.result_view.clear_undo_stack()

        def on_done(matches: dict[str, list[Match]]) -> None:
            nonlocal old_reference
            def toggle_diff():
                selection = self.result_view.sel()
                selection.add(sublime.Region(0, self.result_view.size()))
                self.result_view.run_command('toggle_inline_diff')
                selection.clear()
                if self.result_view:
                    self.result_view.show(0, show_surrounds=False, keep_to_left=False, animate=False)
            sublime.set_timeout(toggle_diff, 0)
            file_count = len(matches)
            total_changes = sum(len(value) for value in matches.values())
            characters = f"Apply {total_changes} changes across {file_count} files?\n"
            old_reference = characters + old_reference
            self.result_view.run_command('lsp_ast_grep_insert', {
                "point": 0,
                "characters": characters
            })
            self.result_view.set_reference_document(old_reference)
            buttons_html = BUTTONS_TEMPLATE.format(
                apply=sublime.command_url('chain', {
                    'commands': [
                        ['hide_panel', {}]
                    ]
                }),
                discard=sublime.command_url('chain', {
                    'commands': [
                        ['hide_panel', {}],
                    ]
                })
            )
            self.phantom_set.update([
                sublime.Phantom(sublime.Region(-1, -1), buttons_html, sublime.PhantomLayout.BLOCK)
            ])


        self.result_view.set_read_only(False)
        self.result_view.run_command('lsp_ast_grep_clear_panel')
        self.result_view.set_reference_document('')
        self.rewrite_inline_rule(inline_rules_query, on_match=on_match, on_done=on_done)


def get_point(view: sublime.View) -> int | None:
    sel = view.sel()
    region = sel[0] if sel else None
    if region is None:
        return
    return region.b
