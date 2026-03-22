from __future__ import annotations

from LSP.plugin import ClientConfig
from LSP.plugin import WorkspaceFolder
from lsp_utils import NpmClientHandler
from pathlib import Path
from typing import final
from typing_extensions import override
import sublime


def plugin_loaded() -> None:
    LspAstGrep.setup()


def plugin_unloaded() -> None:
    LspAstGrep.cleanup()


@final
class LspAstGrep(NpmClientHandler):
    package_name = str(__package__)
    server_directory = "server"
    server_binary_path = str(Path(server_directory) / "node_modules" / "@ast-grep" / "cli" / "ast-grep")

    @classmethod
    @override
    def can_start(
        cls,
        window: sublime.Window,
        initiating_view: sublime.View,
        workspace_folders: list[WorkspaceFolder],
        configuration: ClientConfig,
    ) -> str | None:
        if workspace_folders:
            folder = workspace_folders[0]
            config_name = configuration.settings.get('astGrep.configurationPath') or 'sgconfig.yml'
            config = find_config(folder.path, config_name)
            if config:
                return None
        return "scanning complete"  # a better error message like "lsp not started because sgconfig.yml was not found"


def find_config(start_path: str, config_name: str) -> Path | None:
    """
    Traverses up the directory tree starting from start_path to find config_name.
    Returns the Path object if found, otherwise None.
    """
    current = Path(start_path).resolve()
    while True:
        target = (current / config_name).resolve()
        if target.is_file():
            return target
        parent = current.parent
        if parent == current:
            break
        current = parent
    return None
