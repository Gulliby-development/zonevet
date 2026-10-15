"""Source-aware tokenization for DNS master-file entries."""

from collections.abc import Iterator
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Token:
    """One lexical value and its source location."""

    value: str
    line: int
    quoted: bool = False


@dataclass(frozen=True, slots=True)
class Entry:
    """Tokens belonging to one logical zone-file entry."""

    tokens: tuple[Token, ...]
    line: int
    indented: bool


class LexError(Exception):
    """A lexical error with the physical source line that caused it."""

    def __init__(self, line: int, message: str) -> None:
        self.line = line
        self.message = message
        super().__init__(message)


def tokenize(text: str) -> Iterator[Entry]:
    """Yield logical entries while preserving token lines and owner indentation.

    The iterator is intentionally incremental: a parser can report an earlier
    invalid entry before tokenization reaches a later lexical error.
    """
    text = text.removeprefix("\ufeff")
    text = text.replace("\r", " ")

    line = 1
    column = 0
    index = 0
    depth = 0
    opening_line = 0
    tokens: list[Token] = []
    entry_indented = False

    while index < len(text):
        char = text[index]

        if column == 0 and depth == 0:
            entry_indented = char in " \t"

        if char == "\n":
            if depth == 0:
                if tokens:
                    token_tuple = tuple(tokens)
                    yield Entry(token_tuple, token_tuple[0].line, entry_indented)
                tokens.clear()
                entry_indented = False
            line += 1
            column = 0
            index += 1
            continue

        if char == ";":
            while index < len(text) and text[index] != "\n":
                index += 1
                column += 1
            continue

        if char in " \t":
            index += 1
            column += 1
            continue

        if char == "(":
            if depth:
                raise LexError(line, 'nested "("')
            depth = 1
            opening_line = line
            index += 1
            column += 1
            continue

        if char == ")":
            if not depth:
                raise LexError(line, 'unbalanced ")"')
            depth = 0
            opening_line = 0
            index += 1
            column += 1
            continue

        if char == '"':
            token_line = line
            index += 1
            column += 1
            value: list[str] = []
            while index < len(text):
                char = text[index]
                if char == '"':
                    index += 1
                    column += 1
                    tokens.append(Token("".join(value), token_line, True))
                    break
                if char == "\n":
                    raise LexError(token_line, "unterminated string")
                if char == "\\":
                    if index + 1 >= len(text) or text[index + 1] == "\n":
                        raise LexError(token_line, "unterminated string")
                    escaped = text[index + 1]
                    if escaped not in {'"', "\\"}:
                        raise LexError(token_line, "invalid escape in string")
                    value.append(escaped)
                    index += 2
                    column += 2
                    continue
                value.append(char)
                index += 1
                column += 1
            else:
                raise LexError(token_line, "unterminated string")
            continue

        token_line = line
        start = index
        while index < len(text) and text[index] not in ' \t\n;()"':
            index += 1
            column += 1
        tokens.append(Token(text[start:index], token_line))
    
    if depth:
        raise LexError(opening_line, 'unterminated "("')
    if tokens:
        token_tuple = tuple(tokens)
        yield Entry(token_tuple, token_tuple[0].line, entry_indented)
