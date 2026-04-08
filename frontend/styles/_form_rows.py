from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QSizePolicy, QWidget


def make_separator(style: str) -> QFrame:
    sep = QFrame()
    sep.setFrameShape(QFrame.Shape.HLine)
    sep.setStyleSheet(style)
    return sep


def make_pill(text: str, height: int, style: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setFixedHeight(height)
    lbl.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
    lbl.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignHCenter)
    lbl.setStyleSheet(style)
    return lbl


def make_section_divider(
    title: str,
    frame_style: str,
    label_style: str,
    *,
    margins: tuple[int, int, int, int],
    fixed_height: int | None = None,
    expanding: bool = False,
) -> QFrame:
    fr = QFrame()
    if fixed_height is not None:
        fr.setFixedHeight(fixed_height)
    if expanding:
        fr.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    fr.setStyleSheet(frame_style)
    row = QHBoxLayout(fr)
    row.setContentsMargins(*margins)
    lbl = QLabel(title.upper())
    lbl.setStyleSheet(label_style)
    row.addWidget(lbl)
    row.addStretch()
    return fr


def make_labeled_row(
    label_text: str,
    widget: QWidget,
    *,
    height: int,
    frame_style: str,
    label_style: str,
    label_width: int,
    margins: tuple[int, int, int, int],
    spacing: int,
) -> QFrame:
    fr = QFrame()
    fr.setFixedHeight(height)
    fr.setStyleSheet(frame_style)
    row = QHBoxLayout(fr)
    row.setContentsMargins(*margins)
    row.setSpacing(spacing)
    lb = QLabel(label_text)
    lb.setFixedWidth(label_width)
    lb.setAlignment(Qt.AlignmentFlag.AlignVCenter)
    lb.setStyleSheet(label_style)
    row.addWidget(lb)
    row.addWidget(widget, stretch=1)
    return fr
