from __future__ import annotations
from typing import override

import sublime_plugin
import sublime


class LspAstGrepOpenGuideCommand(sublime_plugin.WindowCommand):
    @override
    def run(self, file: str) -> None:
        self.window.focus_group(0)
        content = sublime.load_resource(file)
        view = self.window.new_file()
        view.run_command("append", {"characters": content, 'scroll_to_end': False})
        view.set_scratch(True)
        view.set_syntax_file('Packages/Markdown/Markdown.sublime-syntax')
        view.set_read_only(True)



