from __future__ import annotations

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
