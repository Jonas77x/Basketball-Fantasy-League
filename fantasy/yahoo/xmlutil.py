"""Helpers for Yahoo's XML responses (namespaces removed so paths stay readable)."""

import xml.etree.ElementTree as ET


def parse(text: str) -> ET.Element:
    root = ET.fromstring(text.encode("utf-8") if isinstance(text, str) else text)
    for element in root.iter():
        if isinstance(element.tag, str) and "}" in element.tag:
            element.tag = element.tag.split("}", 1)[1]
    return root


def txt(element: ET.Element | None, path: str, default: str = "") -> str:
    if element is None:
        return default
    found = element.find(path)
    if found is None or found.text is None:
        return default
    return found.text.strip()


def num(element: ET.Element | None, path: str) -> float | None:
    value = txt(element, path)
    try:
        return float(value)
    except ValueError:
        return None  # Yahoo uses "-" for unknown values


def integer(element: ET.Element | None, path: str) -> int | None:
    value = num(element, path)
    return int(value) if value is not None else None
