"""Shared light/dark colors for styled widgets and custom-painted content."""

from PySide6.QtGui import QColor, QPalette

STYLE = """
QMainWindow, QWidget#workspace { background: #f5f6fa; }
QWidget { color: #172b4d; font-family: 'Segoe UI'; font-size: 11px; }
QFrame#fileHeader, QFrame#viewBar { background: white; border-bottom: 1px solid #e0e4ed; }
QLabel#fileName { font-size: 15px; font-weight: 600; }
QLabel#filePath, QLabel#muted { color: #73809a; font-size: 10px; }
QLabel#readOnly { color: #385172; background: #edf0f6; border-radius: 9px; padding: 3px 9px; font-size: 10px; }
QLabel#fileBadge { background: #3e50ce; color: white; border-radius: 8px; font-weight: bold; }
QPushButton, QToolButton { background: white; border: 1px solid #dce1eb; border-radius: 5px; padding: 7px 12px; }
QPushButton:hover, QToolButton:hover { background: #f0f3ff; border-color: #c7d0ed; }
QPushButton:disabled, QToolButton:disabled { color: #a1a8b6; background: #f8f9fb; }
QPushButton#primaryButton { background: #3d50ca; border-color: #3d50ca; color: white; font-weight: 600; padding: 8px 17px; }
QPushButton#primaryButton:hover { background: #3042b8; }
QPushButton#linkButton { color: #475ce0; border: none; background: transparent; padding: 2px 0; font-size: 10px; }
QPushButton#iconButton { color: #68768f; border: none; background: transparent; padding: 2px 5px; }
QFrame#viewSwitch { background: #eef0f6; border-radius: 6px; }
QToolButton#viewTab { background: transparent; border: 1px solid transparent; padding: 5px 14px; }
QToolButton#viewTab:checked { background: white; border-color: #dce1eb; }
QLineEdit { background: white; border: 1px solid #cdd5e5; border-radius: 5px; padding: 7px 10px; selection-background-color: #dce3ff; }
QLineEdit:focus { border-color: #687cdb; }
QCheckBox { spacing: 5px; color: #53617c; }
QCheckBox#caseToggle::indicator { width: 0; height: 0; }
QCheckBox#caseToggle { border: 1px solid transparent; border-radius: 4px; padding: 5px; }
QCheckBox#caseToggle:checked { background: #e9edff; border-color: #c9d2fa; color: #334ac0; }
QComboBox { background: #f8f9fc; border: 1px dashed #cbd2e0; border-radius: 3px; padding: 2px 7px; font-size: 10px; }
QComboBox::drop-down { border: none; width: 14px; }
QTableView { background: white; alternate-background-color: #ffffff; border: none; gridline-color: #edf0f7; selection-background-color: #e5eaff; selection-color: #1c3161; }
QTableView::item { padding: 7px 6px; border-bottom: 1px solid #edf0f7; }
QHeaderView::section { background: #f7f8fc; color: #34486e; border: none; border-bottom: 1px solid #dce2ef; padding: 7px 6px; font-weight: 500; font-size: 10px; }
QHeaderView { background: #f7f8fc; }
QTableCornerButton::section { background: #f7f8fc; border: none; border-bottom: 1px solid #dce2ef; }
QFrame#tableCard, QScrollArea#detailsPanel { border: 1px solid #d9deea; border-radius: 9px; background: white; }
QWidget#detailsBody { background: white; }
QLabel#detailTitle { font-size: 16px; font-weight: 600; }
QLabel#detailValue, QLabel#sectionTitle { font-weight: 600; }
QLabel#warning { padding: 9px; border-radius: 5px; background: #fff6da; color: #805f14; }
QLabel#notice { padding: 8px 14px; background: #fff6da; color: #805f14; }
QToolButton#infoChip { border: none; background: transparent; color: #73809a; padding: 2px 5px; font-size: 10px; }
QToolButton#warningChip { border: none; background: #fff3cf; color: #805f14; border-radius: 5px; padding: 3px 7px; font-size: 10px; }
QTableView#totals { background: #f7f8fc; font-weight: 600; }
QTableView#totals::item { border: none; }
QPlainTextEdit { font-family: 'Consolas'; font-size: 12px; background: white; color: #253753; border: 1px solid #d9deea; border-radius: 7px; selection-background-color: #dce3ff; }
QSplitter::handle { background: transparent; width: 12px; }
QScrollBar:vertical { background: #f5f6fa; width: 10px; margin: 0; }
QScrollBar::handle:vertical { background: #d3d9e6; border-radius: 4px; min-height: 30px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar:horizontal { background: #f5f6fa; height: 10px; margin: 0; }
QScrollBar::handle:horizontal { background: #d3d9e6; border-radius: 4px; min-width: 30px; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
QMenu { background: white; border: 1px solid #d8dfed; padding: 5px; }
QMenu::item { padding: 5px 20px; }
QMenu::item:selected { background: #edf1ff; }
QStatusBar { background: white; border-top: 1px solid #e0e4ed; color: #74829c; font-size: 10px; }
QStatusBar QLabel { color: #74829c; font-size: 10px; }
"""

# One stylesheet keeps spacing, typography, and layout identical in both modes.
_DARK_REPLACEMENTS = {
    "#f5f6fa": "#141b27", "#172b4d": "#e1e8f5", "white": "#1c2533",
    "#e0e4ed": "#334156", "#73809a": "#a5b3c9", "#385172": "#c2d2f0",
    "#edf0f6": "#2a374d", "#dce1eb": "#3b4b64", "#f0f3ff": "#2b3952",
    "#c7d0ed": "#6f87bb", "#a1a8b6": "#7e8da5", "#f8f9fb": "#202a39",
    "#3d50ca": "#4b62dc", "#3042b8": "#5b72ee", "#475ce0": "#acbaff",
    "#68768f": "#a9bad4", "#eef0f6": "#151d2a", "#cdd5e5": "#455773",
    "#dce3ff": "#354c79", "#687cdb": "#9aafff", "#53617c": "#b4c1d7",
    "#e9edff": "#354267", "#c9d2fa": "#5b72a4", "#334ac0": "#c4d1ff",
    "#f8f9fc": "#253146", "#cbd2e0": "#526580", "#ffffff": "#1c2533",
    "#edf0f7": "#303d52", "#e5eaff": "#3b5080", "#1c3161": "#ffffff",
    "#f7f8fc": "#222e40", "#34486e": "#bdcce4", "#dce2ef": "#3a4b64",
    "#d9deea": "#3b4b64", "#fff6da": "#463a23", "#805f14": "#ffda83",
    "#fff3cf": "#463a23", "#253753": "#e1e8f5", "#d3d9e6": "#4c5d79",
    "#d8dfed": "#3b4b64", "#edf1ff": "#35476b", "#74829c": "#a5b3c9",
}

LIGHT = dict(surface="#ffffff", text="#172b4d", muted="#778596", workspace="#f5f6fa",
             selection="#e5eaff", active="#edf0ff", warning="#fff3cd", warning_text="#714d00",
             link="#3954ca", pill="#edf0ff", pill_text="#3c52bd", accent="#4256cc",
             gutter="#f1f4f7", active_tint="#14586cff", warning_tint="#28ffbb20")
DARK = dict(surface="#1c2533", text="#e1e8f5", muted="#a5b3c9", workspace="#141b27",
            selection="#3b5080", active="#303e61", warning="#463a23", warning_text="#ffda83",
            link="#acbaff", pill="#354267", pill_text="#d0daff", accent="#9aafff",
            gutter="#222e40", active_tint="#287e9aff", warning_tint="#28ffbb20")


def colors_for(mode):
    return DARK if mode == "dark" else LIGHT


def stylesheet_for(mode):
    if mode != "dark":
        return STYLE
    import re
    # Replace original color tokens once, never the replacements themselves.
    pattern = "|".join(re.escape(key) for key in _DARK_REPLACEMENTS)
    dark = re.sub(pattern, lambda match: _DARK_REPLACEMENTS[match.group()], STYLE)
    # Primary action text must remain white on its blue background.
    return dark + "\nQPushButton#primaryButton { color: #ffffff; }\n"


def palette_for(mode):
    colors = colors_for(mode)
    palette = QPalette()
    for role, key in ((QPalette.ColorRole.Window, "workspace"), (QPalette.ColorRole.WindowText, "text"),
                      (QPalette.ColorRole.Base, "surface"), (QPalette.ColorRole.AlternateBase, "surface"),
                      (QPalette.ColorRole.Text, "text"), (QPalette.ColorRole.Button, "surface"),
                      (QPalette.ColorRole.ButtonText, "text"), (QPalette.ColorRole.Highlight, "selection"),
                      (QPalette.ColorRole.HighlightedText, "text"), (QPalette.ColorRole.ToolTipBase, "surface"),
                      (QPalette.ColorRole.ToolTipText, "text"), (QPalette.ColorRole.PlaceholderText, "muted"),
                      (QPalette.ColorRole.Light, "muted"), (QPalette.ColorRole.Dark, "workspace"),
                      (QPalette.ColorRole.Mid, "gutter")):
        palette.setColor(role, QColor(colors[key]))
    for role in (QPalette.ColorRole.Text, QPalette.ColorRole.ButtonText, QPalette.ColorRole.WindowText):
        palette.setColor(QPalette.ColorGroup.Disabled, role, QColor(colors["muted"]))
    return palette
