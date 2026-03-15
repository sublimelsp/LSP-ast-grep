from __future__ import annotations

# https://ast-grep.github.io/guide/tools/json.html#match-object-type
from typing import TypedDict
from typing_extensions import NotRequired


class Match(TypedDict):
    text: str
    range: RangeInfo
    file: str  # relative path to the file
    # the surrounding lines of the match.
    # It can be more than one line if the match spans multiple ones.
    lines: str
    # optional replacement if the match has a replacement
    replacement: NotRequired[str]
    replacementOffsets: NotRequired[ByteOffset]
    metaVariables: MetaVariables  # optional metavars generated in the match


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
    column: int  # zero-based column number


class MetaVariables(TypedDict):
    single: dict[str, MetaVar]
    multi: dict[str, list[MetaVar]]
    transformed: dict[str, str]


class MetaVar(TypedDict):
    text: str
    range: RangeInfo
