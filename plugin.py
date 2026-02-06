from lsp_utils import NpmClientHandler
import os


def plugin_loaded() -> None:
    LspAstGrep.setup()


def plugin_unloaded() -> None:
    LspAstGrep.cleanup()


class LspAstGrep(NpmClientHandler):
    package_name = __package__
    server_directory = "server"
    server_binary_path = os.path.join(server_directory, "node_modules", "@ast-grep", "cli", "ast-grep")
