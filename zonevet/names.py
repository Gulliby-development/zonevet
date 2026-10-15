"""DNS name validation and zone-membership helpers."""

from zonevet.text import quote


def _invalid_name(value: str) -> ValueError:
    return ValueError(f"invalid name {quote(value)}")


def _labels(name: str) -> list[str]:
    """Return labels from a validated absolute name, excluding the final dot."""
    if name == ".":
        return []
    return name[:-1].split(".")


def resolve_name(
    name: str, origin: str | None, allow_wildcard: bool = False
) -> str:
    """Resolve a master-file name to its lowercase absolute form.

    Relative names are resolved against *origin*. A wildcard label is accepted
    only as the first label when the caller explicitly allows owner names.
    """
    original_name = name
    if name == "@":
        if origin is None:
            raise _invalid_name(original_name)
        name = origin
    elif name != ".":
        absolute = name.endswith(".")
        body = name[:-1] if absolute else name
        labels = body.split(".")
        if not body or any(not label for label in labels):
            raise _invalid_name(original_name)

        for index, label in enumerate(labels):
            if label == "*" and allow_wildcard and index == 0:
                continue
            if not (1 <= len(label) <= 63) or any(
                character not in
                "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-"
                for character in label
            ):
                raise _invalid_name(original_name)

        if len(body) > 253:
            raise _invalid_name(original_name)
        if not absolute:
            if origin is None:
                raise _invalid_name(original_name)
            if origin == ".":
                name = f"{body}."
            else:
                name = f"{body}.{origin}"
        else:
            name = f"{body}."

    name = name.lower()
    if name != ".":
        body = name[:-1]
        if len(body) > 253 or any(not 1 <= len(label) <= 63 for label in body.split(".")):
            raise _invalid_name(original_name)
    return name


def in_zone(name: str, apex: str) -> bool:
    """Return whether an absolute name is the apex or one of its descendants."""
    normalized_name = name.lower()
    normalized_apex = apex.lower()
    if normalized_apex == ".":
        return normalized_name.endswith(".")
    return normalized_name == normalized_apex or normalized_name.endswith(
        f".{normalized_apex}"
    )
