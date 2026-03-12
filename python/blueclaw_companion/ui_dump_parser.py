from __future__ import annotations

from dataclasses import dataclass
import re
from pathlib import Path
from typing import Iterable
import xml.etree.ElementTree as ET


BOUNDS_RE = re.compile(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]")


@dataclass(frozen=True)
class Bounds:
    left: int
    top: int
    right: int
    bottom: int

    @property
    def center(self) -> tuple[int, int]:
        return ((self.left + self.right) // 2, (self.top + self.bottom) // 2)


@dataclass(frozen=True)
class UiNode:
    index: int
    text: str
    content_desc: str
    resource_id: str
    class_name: str
    package_name: str
    bounds: Bounds | None
    clickable: bool
    enabled: bool

    @property
    def labels(self) -> list[str]:
        labels: list[str] = []
        for value in (self.text, self.content_desc):
            value = value.strip()
            if value:
                labels.append(value)
        return labels


@dataclass(frozen=True)
class UiDump:
    path: Path
    nodes: list[UiNode]

    @property
    def visible_texts(self) -> list[str]:
        values: list[str] = []
        seen: set[str] = set()
        for node in self.nodes:
            for text in node.labels:
                normalized = normalize_text(text)
                if normalized and normalized not in seen:
                    values.append(text.strip())
                    seen.add(normalized)
        return values

    @property
    def package_names(self) -> list[str]:
        packages = {
            node.package_name.strip()
            for node in self.nodes
            if node.package_name and node.package_name.strip()
        }
        return sorted(packages)

    def find_first_node(self, labels: Iterable[str]) -> UiNode | None:
        normalized_targets = [normalize_text(label) for label in labels if normalize_text(label)]
        if not normalized_targets:
            return None

        for node in self.nodes:
            haystack = " ".join(normalize_text(label) for label in node.labels)
            if not haystack:
                continue
            for target in normalized_targets:
                if target in haystack:
                    return node
        return None

    @property
    def ui_elements(self) -> list[dict[str, object]]:
        elements: list[dict[str, object]] = []
        for node in self.nodes:
            if not node.bounds:
                continue
            text_labels = node.labels
            if not text_labels and not node.clickable:
                continue

            element: dict[str, object] = {
                "class": node.class_name.split(".")[-1] if node.class_name else "",
                "bounds": [node.bounds.left, node.bounds.top, node.bounds.right, node.bounds.bottom],
            }
            if text_labels:
                element["text"] = " | ".join(text_labels)
            if node.clickable:
                element["clickable"] = True
            if node.resource_id:
                element["id"] = node.resource_id.split("/")[-1]
            
            elements.append(element)
        return elements


def normalize_text(value: str) -> str:
    return " ".join(value.casefold().split())


def parse_bounds(raw: str | None) -> Bounds | None:
    if not raw:
        return None
    match = BOUNDS_RE.fullmatch(raw.strip())
    if not match:
        return None
    left, top, right, bottom = (int(group) for group in match.groups())
    return Bounds(left=left, top=top, right=right, bottom=bottom)


def load_ui_dump(path: str | Path) -> UiDump:
    xml_path = Path(path)
    root = ET.fromstring(xml_path.read_text(encoding="utf-8"))

    nodes: list[UiNode] = []
    for index, element in enumerate(root.iter("node")):
        nodes.append(
            UiNode(
                index=index,
                text=(element.attrib.get("text") or "").strip(),
                content_desc=(element.attrib.get("content-desc") or "").strip(),
                resource_id=(element.attrib.get("resource-id") or "").strip(),
                class_name=(element.attrib.get("class") or "").strip(),
                package_name=(element.attrib.get("package") or "").strip(),
                bounds=parse_bounds(element.attrib.get("bounds")),
                clickable=(element.attrib.get("clickable") == "true"),
                enabled=(element.attrib.get("enabled") != "false"),
            )
        )

    return UiDump(path=xml_path, nodes=nodes)
