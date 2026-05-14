from __future__ import annotations

import sublime
import sublime_plugin


class lsp_ast_grep_run_rule_phantom_command(sublime_plugin.TextCommand):
    def run(self, edit):
        inline_rules = self.view.substr(sublime.Region(0, self.view.size()))
        print('inline_rules', inline_rules)
        self.view.window().run_command('lsp_ast_grep_run_rule', {
            'inline_rules': inline_rules
        })


class EEListener(sublime_plugin.ViewEventListener):
    def on_activated(self) -> None:
        if not self.view.match_selector(0, 'source.yaml'):
            return
        first_10_lines = self.view.substr(sublime.Region(0, self.view.text_point(10, 0)))
        if not "id:" in first_10_lines or not 'language:' in first_10_lines:
            return
        self.view.erase_phantoms('ast-grep-run-rule')
        self.view.add_phantom('ast-grep-run-rule', sublime.Region(0,0), f"<a href='{sublime.command_url('lsp_ast_grep_run_rule_phantom')}'>▷ Run rule</a>", 3)
