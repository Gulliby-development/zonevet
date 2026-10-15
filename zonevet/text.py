def quote(value: str) -> str:
    """Return a quoted message value with non-ASCII-printable characters replaced."""
    safe_value = "".join(char if "!" <= char <= "~" else "?" for char in value)
    return f'"{safe_value}"'


def display(path: str) -> str:
    """Return a path suitable for messages, independent of host separators."""
    return path.replace("\\", "/")


def plural(count: int, singular: str, plural_form: str | None = None) -> str:
    """Return the singular or plural form of an English count noun."""
    if count == 1:
        return singular
    return plural_form if plural_form is not None else f"{singular}s"
