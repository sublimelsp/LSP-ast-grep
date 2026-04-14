from __future__ import annotations

from .ast_grep.cli_client import AstGrepCli
from .ast_grep.confirm_panel import BUTTONS_TEMPLATE
from .ast_grep.languages import get_json_schema
from .ast_grep.languages import get_language
from .ast_grep.right_pane import RightPane
from .ast_grep.types import Match
from LSP.plugin.core.types import debounced
from pathlib import Path
from typing import cast
from typing import Literal
from typing_extensions import override
import re
import sublime
import sublime_plugin


class HiglightMatcher(AstGrepCli):
    def highlight_matches(self, view: sublime.View) -> None:
        window = view.window()
        if not window:
            return
        mode: Literal["pattern", "advanced"] = 'pattern'
        view_id = view.settings().get("ast-grep.view")
        mode = 'pattern'
        if view_id == "yaml-rule-view":
            mode = "advanced"
        query_view = RightPane.pattern_view(window) if mode == 'pattern' else RightPane.yaml_rule_view(window)
        if not query_view:
            return
        search_query = query_view.substr(sublime.Region(0, query_view.size()))
        active_view = window.active_view_in_group(0)
        if active_view is None:
            return
        file_name = active_view.file_name()
        if file_name is None:
            return

        def on_done(matches: dict[str, list[Match]]) -> None:
            for key in cast(list[str], active_view.settings().get('ast-grep-var-key', [])):
                active_view.erase_regions(key)
            file_matches = matches.get(file_name) or []
            match_regions: list[sublime.Region] = []
            single_regions: dict[str, list[sublime.Region]] = {}
            multi_regions: dict[str, list[sublime.Region]] = {}
            for match in file_matches:
                start_point = active_view.text_point(match['range']['start']['line'], match['range']['start']['column'])
                end_point = active_view.text_point(match['range']['end']['line'], match['range']['end']['column'])
                match_regions.append(sublime.Region(start_point, end_point))
                for var_name, meta_var in match.get('metaVariables', {}).get('single', {}).items():
                    start_point = active_view.text_point(
                        meta_var['range']['start']['line'], meta_var['range']['start']['column']
                    )
                    end_point = active_view.text_point(
                        meta_var['range']['end']['line'], meta_var['range']['end']['column']
                    )
                    single_regions.setdefault(var_name, []).append(sublime.Region(start_point, end_point))
                for var_name, meta_vars in match.get('metaVariables', {}).get('multi', {}).items():
                    for meta_var in meta_vars:
                        start_point = active_view.text_point(
                            meta_var['range']['start']['line'], meta_var['range']['start']['column']
                        )
                        end_point = active_view.text_point(
                            meta_var['range']['end']['line'], meta_var['range']['end']['column']
                        )
                        multi_regions.setdefault(var_name, []).append(sublime.Region(start_point, end_point))
            erase_keys = ['lsp-ast-grep.match-line']
            active_view.add_regions(
                'lsp-ast-grep.match-line',
                match_regions,
                'region.bluish',
                flags=sublime.RegionFlags.DRAW_NO_FILL | sublime.RegionFlags.NO_UNDO,
            )
            for key in single_regions:
                regions = single_regions[key]
                erase_keys.append(f'lsp-ast-grep.match-single.{key}')
                active_view.add_regions(
                    f'lsp-ast-grep.match-single.{key}',
                    regions,
                    f'region.bluish lsp-ast-grep.match-single.{key}',
                    flags=sublime.RegionFlags.DRAW_NO_FILL
                    | sublime.RegionFlags.DRAW_STIPPLED_UNDERLINE
                    | sublime.RegionFlags.DRAW_NO_OUTLINE
                    | sublime.RegionFlags.NO_UNDO,
                )
            for key in multi_regions:
                regions = multi_regions[key]
                erase_keys.append(f'lsp-ast-grep.match-multi.{key}')
                active_view.add_regions(
                    f'lsp-ast-grep.match-multi.{key}',
                    regions,
                    f'region.bluish lsp-ast-grep.match-multi.{key}',
                    flags=sublime.RegionFlags.DRAW_NO_FILL
                    | sublime.RegionFlags.DRAW_STIPPLED_UNDERLINE
                    | sublime.RegionFlags.DRAW_NO_OUTLINE
                    | sublime.RegionFlags.NO_UNDO,
                )
            active_view.settings().set('ast-grep-var-key', erase_keys)

        def on_error(message: str) -> None:
            for key in cast(list[str], active_view.settings().get('ast-grep-var-key', [])):
                active_view.erase_regions(key)
            if not message:
                return
            caused_part = message.split("Caused by")[1].strip() if "Caused by" in message else message
            clean_lines = [line.strip(" ╰▻") for line in caused_part.splitlines()]
            result = "<br>".join(clean_lines)
            query_view.show_popup(f"<pre class='error'>{result}</pre>")

        if mode == 'pattern':
            self.pattern_search(search_query, paths=[file_name], on_done=on_done, on_error=on_error)
            return

        self.rewrite_inline_rule(search_query, paths=[file_name], on_done=on_done, on_error=on_error)


class lsp_ast_grep_open_command(sublime_plugin.WindowCommand):
    @override
    def run(self) -> None:
        active_view = self.window.active_view()
        self.window.set_layout(
            {'cells': [[0, 0, 1, 2], [1, 0, 2, 1], [1, 1, 2, 2]], 'cols': [0.0, 0.6, 1.0], 'rows': [0.0, 0.5, 1.0]}
        )
        for view in self.window.views():
            _group, index = self.window.get_view_index(view)
            self.window.set_view_index(view, 0, index)

        folders = self.window.folders()
        if not folders:
            return
        cwd = folders[0]


        pattern_syntax = 'Packages/LSP-ast-grep/AstGrepPattern.sublime-syntax'
        pattern_view = RightPane.pattern_view(self.window)
        if not pattern_view:
            pattern_view = self.window.new_file()
            pattern_view.settings().set('ast-grep.view', 'pattern-view')
            pattern_view.settings().set('line_numbers', False)
            pattern_view.settings().set('gutter', False)
            pattern_view.settings().set('margin', 10)
            pattern_view.settings().set("context_menu", 'Context Pattern.sublime-menu')
            pattern_view.set_syntax_file(pattern_syntax)
            pattern_view.settings().set('is_widget', True)  # when pasting this prevents auto-setting the sytnax
            pattern_view.set_name('Pattern')
            pattern_view.set_scratch(True)
        folders = self.window.settings().get('lsp_ast_grep_pattern_in_folder') or []
        if isinstance(folders, list) and folders:
            relative_folder_names= [Path(f).relative_to(cwd) for f in folders]
            html = "<div style='color: color(var(--foreground) alpha(0.50))'>Pattern in Folder: " + " ".join([
                f'<span style="background-color: color(var(--foreground) alpha(0.20)); color: var(--foreground); padding: 4px; border-radius: 10px; margin-right: 5px;">{f}</span>'
                for f in relative_folder_names
            ]) + '</div>'
            pattern_view.erase_phantoms('lsp_ast_grep_where_phantom')
            pattern_view.add_phantom(
                "lsp_ast_grep_where_phantom",
                sublime.Region(0, 0),
                html,
                sublime.LAYOUT_BLOCK
            )
        self.window.set_view_index(pattern_view, 1, 0)

        yaml_syntax = 'Packages/LSP-ast-grep/AstGrepYaml.sublime-syntax'
        yaml_rule_view = RightPane.yaml_rule_view(self.window)
        if not yaml_rule_view:
            yaml_rule_view = self.window.new_file()
            yaml_rule_view.settings().set('ast-grep.view', 'yaml-rule-view')
            yaml_rule_view.settings().set('line_numbers', False)
            yaml_rule_view.settings().set('gutter', False)
            yaml_rule_view.settings().set('margin', 10)
            yaml_rule_view.settings().set("context_menu", 'Context Yaml Rule.sublime-menu')
            yaml_rule_view.set_syntax_file(yaml_syntax)
            yaml_rule_view.set_name('Advanced')
            yaml_rule_view.run_command("append", {"characters": get_yaml_content(active_view)})
            yaml_rule_view.set_scratch(True)
        self.window.set_view_index(yaml_rule_view, 1, 1)

        rewrite_view = RightPane.rewrite_view(self.window)
        if not rewrite_view:
            rewrite_view = self.window.new_file()
            rewrite_view.settings().set('ast-grep.view', 'rewrite-view')
            rewrite_view.settings().set('line_numbers', False)
            rewrite_view.settings().set('gutter', False)
            rewrite_view.settings().set('margin', 10)
            rewrite_view.settings().set('is_widget', True)  # when pasting this prevents auto-setting the sytnax
            rewrite_view.set_syntax_file(pattern_syntax)
            rewrite_view.set_name('Rewrite')
            rewrite_view.set_scratch(True)
        self.window.set_view_index(rewrite_view, 2, 0)

        self.window.focus_view(pattern_view)


class lsp_ast_grep_pattern_and_rewrite_command(sublime_plugin.WindowCommand, AstGrepCli):
    def __init__(self, window: sublime.Window):
        super().__init__(window)
        self.phantom_set: sublime.PhantomSet

    @override
    def run(self) -> None:
        pattern_view = RightPane.pattern_view(self.window)
        if not pattern_view:
            return
        search_query = pattern_view.substr(sublime.Region(0, pattern_view.size()))
        if not search_query.strip():
            return
        rewrite_view = RightPane.rewrite_view(self.window)
        if not rewrite_view:
            return
        replace_query = rewrite_view.substr(sublime.Region(0, rewrite_view.size()))
        if not replace_query.strip():
            return

        folders = self.window.folders()
        if not folders:
            return
        cwd = folders[0]

        panel_name = 'ast-grep (rewrite)'
        result_view = self.window.find_output_panel(panel_name)
        if result_view:
            result_view.run_command('lsp_ast_grep_clear_panel')
        else:
            result_view = self.window.create_output_panel(panel_name)
            result_view.set_syntax_file('Packages/LSP/Syntaxes/References.sublime-syntax')
            result_view.set_name('Find Results')
            result_view.set_scratch(True)
        PANEL_FILE_REGEX = r"^(\S.*):$"
        PANEL_LINE_REGEX = r"^\s+(\d+):(\d+)"
        settings = result_view.settings()
        settings.set("result_base_dir", cwd)
        settings.set("result_file_regex", PANEL_FILE_REGEX)
        settings.set("result_line_regex", PANEL_LINE_REGEX)

        result_view.show(0)
        self.window.run_command("show_panel", {"panel": f"output.{panel_name}"})

        last_file_name: str | None = None

        self.phantom_set = sublime.PhantomSet(result_view, "lsp_ast_grep_accept_buttons")
        old_reference = ''

        def on_match(match: Match) -> None:
            nonlocal old_reference
            nonlocal last_file_name
            if 'replacement' not in match:
                print('LSP-ast-grep: "replacement" key is missing in match dict. Skipping.')
                return
            result_view.set_read_only(False)
            if not result_view.size():
                # add one extra new line, when the view is clear for the phantom button
                old_reference = '\n'
                result_view.run_command("append", {"characters": '\n', 'scroll_to_end': False})
            if last_file_name != match['file']:
                new_text = match['file'] + ':\n'
                old_reference += new_text
                result_view.run_command("append", {"characters": new_text, 'scroll_to_end': False})
                last_file_name = match['file']
            old_reference += (
                " {:>4}:{:<4} {}".format(
                    match['range']['start']['line'] + 1,
                    match['range']['start']['column'] + 1,
                    re.sub(r'\s+', ' ', match['text'].replace('\n', '')),
                )
                + "\n\n"
            )
            line = (
                " {:>4}:{:<4} {}".format(
                    match['range']['start']['line'] + 1,
                    match['range']['start']['column'] + 1,
                    re.sub(r'\s+', ' ', match['replacement'].replace('\n', '')),
                )
                + "\n\n"
            )

            result_view.run_command("append", {"characters": line, 'scroll_to_end': False})
            result_view.set_read_only(True)
            result_view.set_reference_document(old_reference)
            result_view.clear_undo_stack()

        def on_done(matches: dict[str, list[Match]]) -> None:
            nonlocal old_reference

            def toggle_diff():
                selection = result_view.sel()
                selection.add(sublime.Region(0, result_view.size()))
                result_view.run_command('toggle_inline_diff')
                selection.clear()
                if result_view:
                    result_view.show(0, show_surrounds=False, keep_to_left=False, animate=False)

            sublime.set_timeout(toggle_diff, 0)
            file_count = len(matches)
            total_changes = sum(len(value) for value in matches.values())
            characters = f"Apply {total_changes} changes across {file_count} files?\n"
            old_reference = characters + old_reference
            result_view.run_command('lsp_ast_grep_insert', {"point": 0, "characters": characters})
            result_view.set_reference_document(old_reference)
            buttons_html = BUTTONS_TEMPLATE.format(
                apply=sublime.command_url(
                    'chain',
                    {
                        'commands': [
                            ['hide_panel', {}],
                            [
                                'lsp_ast_grep_accept_replace',
                                {'search_query': search_query, 'replace_query': replace_query},
                            ],
                        ]
                    },
                ),
                discard=sublime.command_url(
                    'chain',
                    {
                        'commands': [
                            ['hide_panel', {}],
                        ]
                    },
                ),
            )
            self.phantom_set.update(
                [sublime.Phantom(sublime.Region(-1, -1), buttons_html, sublime.PhantomLayout.BLOCK)]
            )

        result_view.set_read_only(False)
        result_view.run_command('lsp_ast_grep_clear_panel')
        result_view.set_reference_document('')
        self.rewrite(search_query, replace_query, on_match=on_match, on_done=on_done)


class lsp_ast_grep_accept_replace_command(sublime_plugin.WindowCommand, AstGrepCli):
    @override
    def run(self, search_query: str, replace_query: str) -> None:  # pyright: ignore[reportIncompatibleMethodOverride]
        def on_done(_matches: dict[str, list[Match]]) -> None:
            self.window.status_message("LSP-ast-grep: Edits applied.")

        self.rewrite(search_query, replace_query, on_done=on_done, update_all=True)


class lsp_ast_grep_accept_yaml_rule_command(sublime_plugin.WindowCommand, AstGrepCli):
    @override
    def run(self, inline_rules: str) -> None:  # pyright: ignore[reportIncompatibleMethodOverride]
        def on_done(_matches: dict[str, list[Match]]) -> None:
            self.window.status_message("LSP-ast-grep: Edits applied.")

        self.rewrite_inline_rule(inline_rules, on_done=on_done, update_all=True)


class lsp_ast_grep_pattern_command(sublime_plugin.WindowCommand, AstGrepCli):
    @override
    def run(self) -> None:
        pattern_view = RightPane.pattern_view(self.window)
        if not pattern_view:
            return
        search_query = pattern_view.substr(sublime.Region(0, pattern_view.size()))
        if not search_query.strip():
            return

        folders = self.window.folders()
        if not folders:
            return
        cwd = folders[0]

        panel_name = 'ast-grep (pattern)'
        result_view = self.window.find_output_panel(panel_name)
        if result_view:
            result_view.run_command('lsp_ast_grep_clear_panel')
        else:
            result_view = self.window.create_output_panel(panel_name)
            result_view.set_syntax_file('Packages/LSP/Syntaxes/References.sublime-syntax')
            result_view.set_name('Find Results')
            result_view.set_scratch(True)
        PANEL_FILE_REGEX = r"^(\S.*):$"
        PANEL_LINE_REGEX = r"^\s+(\d+):(\d+)"
        settings = result_view.settings()
        settings.set("result_base_dir", cwd)
        settings.set("result_file_regex", PANEL_FILE_REGEX)
        settings.set("result_line_regex", PANEL_LINE_REGEX)

        result_view.show(0)
        self.window.run_command("show_panel", {"panel": f"output.{panel_name}"})

        last_file_name: str | None = None

        def on_match(match: Match) -> None:
            nonlocal last_file_name
            is_empty_view = result_view.size() > 0
            result_view.set_read_only(False)
            if last_file_name != match['file']:
                maybe_new_line = '\n' if is_empty_view else ''
                result_view.run_command("append", {"characters": maybe_new_line + match['file'] + ':\n'})
                last_file_name = match['file']
            line = " {:>4}:{:<4} {}".format(
                match['range']['start']['line'] + 1,
                match['range']['start']['column'] + 1,
                match['lines'].split('\n')[0].strip(),
            )
            result_view.run_command("append", {"characters": line + "\n"})
            result_view.set_read_only(True)
            result_view.clear_undo_stack()

        def on_done(matches: dict[str, list[Match]]) -> None:
            if result_view:
                result_view.show(0)
            file_count = len(matches)
            total_changes = sum(len(value) for value in matches.values())
            characters = f"Found {total_changes} matches across {file_count} files\n\n"
            result_view.run_command('lsp_ast_grep_insert', {"point": 0, "characters": characters})

        result_view.set_read_only(False)
        result_view.run_command('lsp_ast_grep_clear_panel')
        self.pattern_search(search_query, on_match=on_match, on_done=on_done)


class AstGrepHighlightMatchesListener(sublime_plugin.ViewEventListener, HiglightMatcher):
    @classmethod
    @override
    def is_applicable(cls, settings: sublime.Settings) -> bool:
        return settings.get("ast-grep.view") in ["pattern-view", "yaml-rule-view"]

    def on_modified(self) -> None:
        if self.view.is_dirty():
            return
        change_count = self.view.change_count()
        debounced(
            lambda: self.highlight_matches(self.view),
            300,
            lambda: self.view.is_valid() and change_count == self.view.change_count(),
        )


class AstGrepCloseAndQueryContextListener(sublime_plugin.ViewEventListener, AstGrepCli):
    @classmethod
    @override
    def is_applicable(cls, settings: sublime.Settings) -> bool:
        return settings.get('ast-grep.view') in ['pattern-view', 'rewrite-view', 'yaml-rule-view']

    def on_query_context(self, key: str, operator: int, operand: object, _match_all: bool) -> bool | None:
        # You can filter key bindings by the precense of a provider,
        if key == "ast-grep.view" and operator == sublime.QueryOperator.EQUAL and isinstance(operand, str):
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
        rewrite_view = RightPane.rewrite_view(window)
        if rewrite_view:
            sublime.set_timeout(lambda: rewrite_view.close())
        yaml_rule_view = RightPane.yaml_rule_view(window)
        if yaml_rule_view:
            sublime.set_timeout(lambda: yaml_rule_view.close())
        pattern_view = RightPane.pattern_view(window)
        if pattern_view:
            sublime.set_timeout(lambda: pattern_view.close())

        # clear highlight regions on pane close
        for v in window.views():
            for key in cast(list[str], v.settings().get('ast-grep-var-key', [])):
                v.erase_regions(key)

        def layout():
            window.set_layout({'cells': [[0, 0, 1, 1]], 'cols': [0.0, 1.0], 'rows': [0.0, 1.0]})

        sublime.set_timeout(layout)


class AstGrepSearchOpenListener(sublime_plugin.EventListener, HiglightMatcher):
    @classmethod
    def is_applicable(cls, _settings: sublime.Settings) -> bool:
        return RightPane.is_active()

    def on_exit(self) -> None:
        if AstGrepCli.process is not None:
            AstGrepCli.process.kill()

    def on_activated(self, view: sublime.View) -> None:
        self.highlight_matches(view)

    def on_load(self, view: sublime.View) -> None:
        self.highlight_matches(view)
        window = view.window()
        if window and RightPane.is_active() and window.get_view_index(view)[0] != 0:
            window.set_view_index(view, 0, -1)

    def on_clone(self, view: sublime.View) -> None:
        self.highlight_matches(view)

    def on_post_save(self, view: sublime.View) -> None:
        self.highlight_matches(view)


class LspAstGrepClearPanelCommand(sublime_plugin.TextCommand):
    """
    A clear_panel command to clear the error panel.
    """

    @override
    def run(self, edit: sublime.Edit) -> None:
        self.view.set_read_only(False)
        self.view.erase(edit, sublime.Region(0, self.view.size()))
        self.view.set_read_only(True)


class LspAstGrepInsertCommand(sublime_plugin.TextCommand):
    @override
    def run(self, edit: sublime.Edit, point: int = 0, characters: str = ""):
        self.view.set_read_only(False)
        _ = self.view.insert(edit, point, characters)
        self.view.set_read_only(True)


def get_yaml_content(view: sublime.View | None):
    base_scope = 'DEFAULT'
    tab_size = 4
    if view and (syntax := view.syntax()):
        base_scope = syntax.scope
        tab_size = int(cast(int, view.settings().get('tab_size', 4)))
    json_schema = get_json_schema(base_scope)
    language = language = get_language(base_scope)
    indentation = " " * tab_size
    content = f"""# YAML Rule is more powerful! - https://ast-grep.github.io/guide/rule-config.html#rule
# yaml-language-server: $schema=https://raw.githubusercontent.com/ast-grep/ast-grep/main/schemas/{json_schema}
language: {language}
rule:
{indentation}pattern: TYPE_HERE
# fix:
# {indentation}logger.log($A)
# files:
#     - src/**/*
# ignores:
#     - build/**/*
"""
    return content


class lsp_ast_grep_run_rule_command(sublime_plugin.WindowCommand, AstGrepCli):
    def __init__(self, window: sublime.Window):
        super().__init__(window)
        self.phantom_set: sublime.PhantomSet

    @override
    def run(self) -> None:
        yaml_rule_view = RightPane.yaml_rule_view(self.window)
        if not yaml_rule_view:
            return

        # the yaml rule view has some comments at the top
        # we need to strip comments out, because the inline_rules_query will be send to the cli command
        # and the cli command will throw an error
        begin_of_yaml_rule = yaml_rule_view.find("$language:", 0)
        inline_rules_query = yaml_rule_view.substr(
            sublime.Region(begin_of_yaml_rule.begin() or 0, yaml_rule_view.size())
        )
        if not inline_rules_query.strip():
            return
        folders = self.window.folders()
        if not folders:
            return
        cwd = folders[0]

        has_fix_specified = bool(re.search(r"^fix:", inline_rules_query, re.M))
        panel_name = 'ast-grep (advanced)'
        result_view = self.window.find_output_panel(panel_name)
        if result_view:
            result_view.run_command('lsp_ast_grep_clear_panel')
        else:
            result_view = self.window.create_output_panel(panel_name)
            result_view.set_syntax_file('Packages/LSP/Syntaxes/References.sublime-syntax')
            result_view.set_name('Find Results')
            result_view.set_scratch(True)
        PANEL_FILE_REGEX = r"^(\S.*):$"
        PANEL_LINE_REGEX = r"^\s+(\d+):(\d+)"
        settings = result_view.settings()
        settings.set("result_base_dir", cwd)
        settings.set("result_file_regex", PANEL_FILE_REGEX)
        settings.set("result_line_regex", PANEL_LINE_REGEX)

        result_view.show(0)
        self.window.run_command("show_panel", {"panel": f"output.{panel_name}"})

        last_file_name: str | None = None

        self.phantom_set = sublime.PhantomSet(result_view, "lsp_ast_grep_accept_buttons")
        old_reference = ''

        def on_match(match: Match) -> None:
            nonlocal old_reference
            nonlocal last_file_name
            result_view.set_read_only(False)
            new_lines_at_end = "\n\n" if has_fix_specified else '\n'
            if not result_view.size() and has_fix_specified:
                # add one extra new line, when the view is clear for the phantom button
                old_reference = '\n'
                result_view.run_command("append", {"characters": '\n', 'scroll_to_end': False})
            if last_file_name != match['file']:
                new_text = match['file'] + ':\n'
                if last_file_name:
                    new_text = '\n' + new_text
                old_reference += new_text
                result_view.run_command("append", {"characters": new_text, 'scroll_to_end': False})
                last_file_name = match['file']
            old_reference += (
                " {:>4}:{:<4} {}".format(
                    match['range']['start']['line'] + 1,
                    match['range']['start']['column'] + 1,
                    re.sub(r'\s+', ' ', match['text'].replace('\n', '')),
                )
                + new_lines_at_end
            )
            line = (
                " {:>4}:{:<4} {}".format(
                    match['range']['start']['line'] + 1, match['range']['start']['column'] + 1, match.get('replacement') or match['text']
                )
                + new_lines_at_end
            )

            result_view.run_command("append", {"characters": line, 'scroll_to_end': False})
            result_view.set_read_only(True)
            result_view.set_reference_document(old_reference)
            result_view.clear_undo_stack()

        def on_done(matches: dict[str, list[Match]]) -> None:
            nonlocal old_reference

            def toggle_diff():
                selection = result_view.sel()
                selection.add(sublime.Region(0, result_view.size()))
                result_view.run_command('toggle_inline_diff')
                selection.clear()
                if result_view:
                    result_view.show(0, show_surrounds=False, keep_to_left=False, animate=False)

            sublime.set_timeout(toggle_diff, 0)
            file_count = len(matches)
            total_changes = sum(len(value) for value in matches.values())
            if has_fix_specified:
                characters = f"Apply {total_changes} changes across {file_count} files?\n"
                old_reference = characters + old_reference
                result_view.run_command('lsp_ast_grep_insert', {"point": 0, "characters": characters})
                result_view.set_reference_document(old_reference)
                buttons_html = BUTTONS_TEMPLATE.format(
                    apply=sublime.command_url(
                        'chain',
                        {
                            'commands': [
                                ['hide_panel', {}],
                                ['lsp_ast_grep_accept_yaml_rule', {'inline_rules': inline_rules_query}],
                            ]
                        },
                    ),
                    discard=sublime.command_url(
                        'chain',
                        {
                            'commands': [
                                ['hide_panel', {}],
                            ]
                        },
                    ),
                )
                self.phantom_set.update(
                    [sublime.Phantom(sublime.Region(-1, -1), buttons_html, sublime.PhantomLayout.BLOCK)]
                )

        result_view.set_read_only(False)
        result_view.run_command('lsp_ast_grep_clear_panel')
        result_view.set_reference_document('')
        self.rewrite_inline_rule(inline_rules_query, on_match=on_match, on_done=on_done)
