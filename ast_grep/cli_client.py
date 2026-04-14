from __future__ import annotations

from ..plugin import LspAstGrep
from .types import Match
from functools import partial
from typing import Callable
import re
import sublime
import subprocess
import threading


class AstGrepCli:
    process: subprocess.Popen[str] | None = None

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
            cmd = [ast_cli, "-p", file_content, "--lang", language, "--debug-query=cst", '--threads', '1']
            process = subprocess.Popen(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            AstGrepCli.process = process
            matches: list[str] = []
            pattern = r"\((\d+),(\d+)\)-\((\d+),(\d+)\)"
            if process.stderr:
                for line in process.stderr:
                    if "Cannot parse query" in line:
                        break
                    # Convert ast-grep's 0-based rows to 1-based coordinates
                    # Example: "future_import_statement (0,0)-(0,34)" -> "(1,0)-(1,34)"
                    one_based_row = re.sub(
                        pattern,
                        lambda m: f"({int(m.group(1)) + 1},{m.group(2)})-({int(m.group(3)) + 1},{m.group(4)})",
                        line,
                    )
                    matches.append(one_based_row)
            _ = process.wait()
            if on_done:
                sublime.set_timeout(partial(on_done, "".join(matches)), 100)

        thread = threading.Thread(target=run_search)
        thread.start()

    def pattern_search(
        self,
        search_query: str,
        *,
        paths: list[str] | None = None,
        on_match: Callable[[Match], None] | None = None,
        on_done: Callable[[dict[str, list[Match]]], None] | None = None,
        on_error: Callable[[str], None] | None = None,
    ) -> None:
        if AstGrepCli.process:
            AstGrepCli.process.kill()
            AstGrepCli.process = None
        window = sublime.active_window()
        folders = window.folders()
        strictness = window.settings().get('lsp_ast_grep_strictness') or 'smart'
        pattern_in_folder = window.settings().get('lsp_ast_grep_pattern_in_folder') or []
        if not folders:
            return
        cwd = folders[0]
        search_paths = pattern_in_folder or paths or folders

        def run_search() -> None:
            ast_cli = LspAstGrep.binary_path()
            cmd = [ast_cli, 'run', '--pattern', search_query, f'--strictness={strictness}', '--json=stream', '--threads', '1', *search_paths]
            process = subprocess.Popen(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            AstGrepCli.process = process
            matches: dict[str, list[Match]] = {}
            if process.stdout:
                for line in process.stdout:
                    match: Match = sublime.decode_value(line)  # pyright: ignore[reportAssignmentType]
                    if on_match:
                        on_match(match)
                    matches.setdefault(match['file'], []).append(match)
            exit_code = process.wait()
            if exit_code != 0 and process.stderr:
                error_msg = process.stderr.read()
                if on_error:
                    on_error(error_msg.strip())
                    return
                raise Exception(f"Process failed with code {exit_code}: {error_msg}")
            if on_done:
                sublime.set_timeout(partial(on_done, matches), 100)

        thread = threading.Thread(target=run_search)
        thread.start()

    def rewrite(
        self,
        search_query: str,
        replace_query: str,
        paths: list[str] | None = None,
        on_match: Callable[[Match], None] | None = None,
        on_done: Callable[[dict[str, list[Match]]], None] | None = None,
        on_error: Callable[[str], None] | None = None,
        update_all: bool = False,
    ) -> None:
        if AstGrepCli.process:
            AstGrepCli.process.kill()
            AstGrepCli.process = None
        window = sublime.active_window()
        folders = window.folders()
        strictness = window.settings().get('lsp_ast_grep_strictness') or 'smart'
        pattern_in_folder = window.settings().get('lsp_ast_grep_pattern_in_folder') or []
        if not folders:
            return
        cwd = folders[0]
        search_paths = pattern_in_folder or paths or folders

        def run_replace() -> None:
            ast_cli = LspAstGrep.binary_path()
            cmd = [ast_cli, 'run', '--threads', '1', '--pattern', search_query, f'--strictness={strictness}', '--rewrite', replace_query]
            print('cmd', cmd)
            if update_all:
                cmd.append('--update-all')
            else:
                cmd.append('--json=stream')  # looks like it is not possivle to use --update-all with --json=stream
            cmd.extend(search_paths)
            process = subprocess.Popen(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            AstGrepCli.process = process
            matches: dict[str, list[Match]] = {}
            if on_match and process.stdout:
                for line in process.stdout:
                    if AstGrepCli.process != process:
                        return
                    match: Match = sublime.decode_value(line)  # pyright: ignore[reportAssignmentType]
                    on_match(match)
                    matches.setdefault(match['file'], []).append(match)
            exit_code = process.wait()
            if exit_code != 0 and process.stderr:
                error_msg = process.stderr.read()
                if on_error:
                    on_error(error_msg.strip())
                    return
                raise Exception(f"Process failed with code {exit_code}: {error_msg}")
            if on_done:
                sublime.set_timeout(partial(on_done, matches), 100)

        thread = threading.Thread(target=run_replace)
        thread.start()

    def rewrite_inline_rule(
        self,
        inline_rules: str,
        paths: list[str] | None = None,
        on_match: Callable[[Match], None] | None = None,
        on_done: Callable[[dict[str, list[Match]]], None] | None = None,
        on_error: Callable[[str], None] | None = None,
        update_all: bool = False,
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
            cmd = [ast_cli, 'scan', '--threads', '1', '--inline-rules', 'id: inline-rule\n' + inline_rules]
            if update_all:
                cmd.append('--update-all')
            else:
                cmd.append('--json=stream')  # looks like it is not possivle to use --update-all with --json=stream
            cmd.extend(search_paths)
            process = subprocess.Popen(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            AstGrepCli.process = process
            matches: dict[str, list[Match]] = {}

            if process.stdout:
                for line in process.stdout:
                    if AstGrepCli.process != process:
                        return
                    match: Match = sublime.decode_value(line)  # pyright: ignore[reportAssignmentType]
                    if on_match:
                        on_match(match)
                    matches.setdefault(match['file'], []).append(match)
            exit_code = process.wait()
            if exit_code != 0 and process.stderr:
                error_msg = process.stderr.read()
                if on_error:
                    on_error(error_msg.strip())
                    return
                raise Exception(f"Process failed with code {exit_code}: {error_msg}")
            if on_done:
                sublime.set_timeout(partial(on_done, matches), 100)

        thread = threading.Thread(target=run_replace)
        thread.start()
