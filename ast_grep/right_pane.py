from __future__ import annotations

import sublime


class RightPane:
    active_window_id: int | None = None

    @staticmethod
    def pattern_view(window: sublime.Window) -> sublime.View | None:
        return next((v for v in window.views() if v.settings().get('ast-grep.view') == 'pattern-view'), None)

    @staticmethod
    def yaml_rule_view(window: sublime.Window) -> sublime.View | None:
        return next((v for v in window.views() if v.settings().get('ast-grep.view') == 'yaml-rule-view'), None)

    @staticmethod
    def rewrite_view(window: sublime.Window) -> sublime.View | None:
        return next((v for v in window.views() if v.settings().get('ast-grep.view') == 'rewrite-view'), None)
