"""Examples for source-aware zone-file tokenization."""

import pytest

from zonevet.lexer import Entry, LexError, Token, tokenize


def shape(entries: list[Entry]) -> list[tuple[list[tuple[str, int, bool]], int, bool]]:
    return [
        ([(token.value, token.line, token.quoted) for token in entry.tokens], entry.line, entry.indented)
        for entry in entries
    ]


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("", []),
        (" \t\n\n", []),
        ("; comment only\n", []),
        (
            "example.com. 300 IN A 192.0.2.1 ; ignored words\n",
            [
                (
                    [
                        ("example.com.", 1, False),
                        ("300", 1, False),
                        ("IN", 1, False),
                        ("A", 1, False),
                        ("192.0.2.1", 1, False),
                    ],
                    1,
                    False,
                )
            ],
        ),
        (
            "alpha:beta?=/x\n",
            [([("alpha:beta?=/x", 1, False)], 1, False)],
        ),
        (
            "a\rb\tc\n",
            [([("a", 1, False), ("b", 1, False), ("c", 1, False)], 1, False)],
        ),
        (
            "first\r\nsecond\r\n",
            [([("first", 1, False)], 1, False), ([ ("second", 2, False)], 2, False)],
        ),
        (
            "\ufeff$ORIGIN example.com.\n",
            [([("$ORIGIN", 1, False), ("example.com.", 1, False)], 1, False)],
        ),
        (
            "  www IN A 192.0.2.1\nmail IN A 192.0.2.2\n",
            [
                (
                    [("www", 1, False), ("IN", 1, False), ("A", 1, False), ("192.0.2.1", 1, False)],
                    1,
                    True,
                ),
                (
                    [("mail", 2, False), ("IN", 2, False), ("A", 2, False), ("192.0.2.2", 2, False)],
                    2,
                    False,
                ),
            ],
        ),
        (
            "x TXT \"left ; ( middle ) right\" ; discarded\n",
            [
                (
                    [("x", 1, False), ("TXT", 1, False), ("left ; ( middle ) right", 1, True)],
                    1,
                    False,
                )
            ],
        ),
        (
            r'x TXT "say \"hi\" and \\"',
            [([("x", 1, False), ("TXT", 1, False), ('say "hi" and \\', 1, True)], 1, False)],
        ),
        (
            "x A 192.0.2.1 ( 300 IN )\n",
            [
                (
                    [("x", 1, False), ("A", 1, False), ("192.0.2.1", 1, False), ("300", 1, False), ("IN", 1, False)],
                    1,
                    False,
                )
            ],
        ),
        (
            "@ SOA ns hostmaster (\n  1 2 3 4 5 )\nnext A 192.0.2.1\n",
            [
                (
                    [
                        ("@", 1, False),
                        ("SOA", 1, False),
                        ("ns", 1, False),
                        ("hostmaster", 1, False),
                        ("1", 2, False),
                        ("2", 2, False),
                        ("3", 2, False),
                        ("4", 2, False),
                        ("5", 2, False),
                    ],
                    1,
                    False,
                ),
                ([ ("next", 3, False), ("A", 3, False), ("192.0.2.1", 3, False)], 3, False),
            ],
        ),
        (
            "x A 192.0.2.1 (\n  300 )\n",
            [
                (
                    [("x", 1, False), ("A", 1, False), ("192.0.2.1", 1, False), ("300", 2, False)],
                    1,
                    False,
                )
            ],
        ),
        (
            "(\n)\n",
            [],
        ),
        (
            "x A 192.0.2.1 ; ( ignored\nnext A 192.0.2.2\n",
            [
                ([ ("x", 1, False), ("A", 1, False), ("192.0.2.1", 1, False)], 1, False),
                ([ ("next", 2, False), ("A", 2, False), ("192.0.2.2", 2, False)], 2, False),
            ],
        ),
        (
            "x\n\n; blank entry\n  y\n",
            [([("x", 1, False)], 1, False), ([ ("y", 4, False)], 4, True)],
        ),
        (
            "last A 192.0.2.1",
            [([("last", 1, False), ("A", 1, False), ("192.0.2.1", 1, False)], 1, False)],
        ),
        (
            '"one"two\n',
            [([("one", 1, True), ("two", 1, False)], 1, False)],
        ),
        (
            'x TXT "first" "second"\n',
            [([("x", 1, False), ("TXT", 1, False), ("first", 1, True), ("second", 1, True)], 1, False)],
        ),
        (
            'x TXT "a\tb"\n',
            [([("x", 1, False), ("TXT", 1, False), ("a\tb", 1, True)], 1, False)],
        ),
        (
            "x ( ignored\n other ) y\n",
            [
                (
                    [("x", 1, False), ("ignored", 1, False), ("other", 2, False), ("y", 2, False)],
                    1,
                    False,
                )
            ],
        ),
        (
            "\ufeff\ufeffx\n",
            [([("\ufeffx", 1, False)], 1, False)],
        ),
        (
            'x TXT "CR\rLF"\n',
            [([("x", 1, False), ("TXT", 1, False), ("CR LF", 1, True)], 1, False)],
        ),
    ],
)
def test_tokenize_entries_preserve_tokens_and_source_metadata(source: str, expected: list[object]) -> None:
    assert shape(list(tokenize(source))) == expected


@pytest.mark.parametrize(
    ("source", "line", "message"),
    [
        ('x TXT "unterminated', 1, "unterminated string"),
        ('x TXT "unterminated\nnext', 1, "unterminated string"),
        ('x TXT "bad\\q"', 1, "invalid escape in string"),
        ('x TXT "bad\\\n', 1, "unterminated string"),
        ("x )\n", 1, 'unbalanced ")"'),
        ("x ( y ( z ) )\n", 1, 'nested "("'),
        ("x A (\n1\n", 1, 'unterminated "("'),
        ("x A 1\n)\n", 2, 'unbalanced ")"'),
        ("x A 1\n(\n  (\n", 3, 'nested "("'),
    ],
)
def test_lexical_errors_have_exact_message_and_source_line(source: str, line: int, message: str) -> None:
    with pytest.raises(LexError) as caught:
        list(tokenize(source))

    assert caught.value.line == line
    assert caught.value.message == message
    assert str(caught.value) == message


def test_tokenizer_yields_earlier_entries_before_a_later_lexical_error() -> None:
    entries = tokenize("good A 192.0.2.1\nnext )\n")

    assert next(entries) == Entry((Token("good", 1), Token("A", 1), Token("192.0.2.1", 1)), 1, False)
    with pytest.raises(LexError) as caught:
        next(entries)
    assert caught.value.message == 'unbalanced ")"'
