"""
============================================================
J.A.R.V.I.S. — HUD (Heads-Up Display)
Layer 8: Iron Man-Style Overlay (PyQt6)
============================================================
Features:
  • Frameless always-on-top transparent overlay
  • Arc reactor animated logo
  • Live system stats (CPU / RAM / Disk) with ring gauges
  • State animations: Idle → Listening → Processing → Speaking → Error
  • Response / AI output text panel
  • Reminders / Timer panel
  • Draggable, minimisable
  • Boot sequence with staggered slide-in
  • Settings panel
"""

import sys
import math
import time
import threading
import logging
from datetime import datetime
from pathlib import Path

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel, QPushButton,
    QVBoxLayout, QHBoxLayout, QGridLayout, QTextEdit, QFrame,
    QGraphicsDropShadowEffect, QSlider, QLineEdit, QCheckBox,
    QStackedWidget, QScrollArea, QSizePolicy
)
from PyQt6.QtCore import (
    Qt, QTimer, QPropertyAnimation, QEasingCurve, pyqtSignal,
    QObject, QThread, QRect, QPoint, QSize, pyqtProperty,
    QSequentialAnimationGroup, QParallelAnimationGroup
)
from PyQt6.QtGui import (
    QPainter, QColor, QPen, QBrush, QLinearGradient, QRadialGradient,
    QFont, QFontDatabase, QPainterPath, QPolygonF, QPalette, QPixmap,
    QKeySequence
)

log = logging.getLogger("jarvis.hud")

# ══════════════════════════════════════════════════════════
# HUD Design Constants (Iron Man palette)
# ══════════════════════════════════════════════════════════
class Colors:
    BG_DARK        = QColor(5, 13, 26)        # #050d1a near-black navy
    BG_PANEL       = QColor(8, 20, 40, 200)   # panel background (semi-transparent)
    BG_PANEL_LIGHT = QColor(12, 30, 58, 220)
    ACCENT_BLUE    = QColor(0, 212, 255)       # #00d4ff electric blue
    ACCENT_GOLD    = QColor(255, 215, 0)       # #ffd700 gold
    ACCENT_RED     = QColor(255, 60, 60)       # error red
    ACCENT_GREEN   = QColor(0, 255, 136)       # #00ff88 success green
    TEXT_PRIMARY   = QColor(200, 230, 255)     # pale blue-white
    TEXT_DIM       = QColor(80, 120, 160)      # dimmed text
    TEXT_LABEL     = QColor(0, 180, 220)       # label blue
    BORDER         = QColor(0, 150, 200, 80)   # subtle border
    GLOW_BLUE      = QColor(0, 212, 255, 60)
    GLOW_GOLD      = QColor(255, 215, 0, 40)
    TRANSPARENT    = QColor(0, 0, 0, 0)


HUD_FONT_MONO   = "Consolas"
HUD_FONT_LABEL  = "Arial"

# Interaction states
class JarvisState:
    IDLE        = "idle"
    LISTENING   = "listening"
    PROCESSING  = "processing"
    SPEAKING    = "speaking"
    ERROR       = "error"


# ══════════════════════════════════════════════════════════
# Signal Bridge — emit signals from non-Qt threads
# ══════════════════════════════════════════════════════════
class HUDSignals(QObject):
    state_changed   = pyqtSignal(str)          # JarvisState
    response_text   = pyqtSignal(str)          # new response text
    stat_update     = pyqtSignal(float, float, float)  # cpu, ram, disk
    text_command    = pyqtSignal(str)
    timer_update    = pyqtSignal(list)          # list of active timers
    reminder_update = pyqtSignal(list)          # list of pending reminders
    boot_complete   = pyqtSignal()

_hud_signals: HUDSignals = None

def get_hud_signals() -> HUDSignals:
    global _hud_signals
    if _hud_signals is None:
        _hud_signals = HUDSignals()
    return _hud_signals


# ══════════════════════════════════════════════════════════
# Arc Reactor Widget
# ══════════════════════════════════════════════════════════
class ArcReactorWidget(QWidget):
    """Animated Iron Man arc reactor logo."""

    def __init__(self, size=80, parent=None):
        super().__init__(parent)
        self._size = size
        self._angle = 0
        self._pulse = 0.0
        self._pulse_dir = 1
        self._state = JarvisState.IDLE
        self.setFixedSize(size, size)

        self._spin_timer = QTimer(self)
        self._spin_timer.timeout.connect(self._tick)
        self._spin_timer.start(33)  # ~30fps

    def set_state(self, state: str):
        self._state = state
        self.update()

    def _tick(self):
        self._angle = (self._angle + 2) % 360
        self._pulse += 0.05 * self._pulse_dir
        if self._pulse >= 1.0:
            self._pulse_dir = -1
        elif self._pulse <= 0.0:
            self._pulse_dir = 1
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        cx = self._size / 2
        cy = self._size / 2
        r = self._size / 2 - 4

        # State-based color
        if self._state == JarvisState.IDLE:
            core_color = Colors.ACCENT_BLUE
        elif self._state == JarvisState.LISTENING:
            core_color = QColor(0, 255, 200)
        elif self._state == JarvisState.PROCESSING:
            core_color = Colors.ACCENT_GOLD
        elif self._state == JarvisState.SPEAKING:
            core_color = QColor(100, 255, 100)
        elif self._state == JarvisState.ERROR:
            core_color = Colors.ACCENT_RED
        else:
            core_color = Colors.ACCENT_BLUE

        # Outer glow ring
        glow_alpha = int(60 + 60 * self._pulse)
        glow_color = QColor(core_color.red(), core_color.green(), core_color.blue(), glow_alpha)
        pen = QPen(glow_color, 3)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(int(cx - r), int(cy - r), int(r * 2), int(r * 2))

        # Spinning ring segments (3 segments, 120° apart)
        spin_color = QColor(core_color.red(), core_color.green(), core_color.blue(), 200)
        pen = QPen(spin_color, 2)
        p.setPen(pen)
        for i in range(3):
            start_angle = (self._angle + i * 120) * 16
            span_angle = 60 * 16
            p.drawArc(
                int(cx - r + 6), int(cy - r + 6),
                int((r - 6) * 2), int((r - 6) * 2),
                start_angle, span_angle
            )

        # Inner hexagon
        hex_r = r * 0.45
        hex_color = QColor(core_color.red(), core_color.green(), core_color.blue(), 180)
        pen = QPen(hex_color, 1.5)
        p.setPen(pen)
        path = QPainterPath()
        for i in range(6):
            angle = math.radians(60 * i + 30)
            x = cx + hex_r * math.cos(angle)
            y = cy + hex_r * math.sin(angle)
            if i == 0:
                path.moveTo(x, y)
            else:
                path.lineTo(x, y)
        path.closeSubpath()
        p.drawPath(path)

        # Core glow
        pulse_alpha = int(150 + 100 * self._pulse)
        grad = QRadialGradient(cx, cy, r * 0.3)
        grad.setColorAt(0, QColor(core_color.red(), core_color.green(), core_color.blue(), pulse_alpha))
        grad.setColorAt(1, QColor(core_color.red(), core_color.green(), core_color.blue(), 0))
        p.setBrush(QBrush(grad))
        p.setPen(Qt.PenStyle.NoPen)
        cr = r * 0.3
        p.drawEllipse(int(cx - cr), int(cy - cr), int(cr * 2), int(cr * 2))

        p.end()


# ══════════════════════════════════════════════════════════
# Circular Gauge Widget
# ══════════════════════════════════════════════════════════
class CircularGauge(QWidget):
    """Circular progress gauge for CPU/RAM/Disk display."""

    def __init__(self, label: str, color: QColor, size=90, parent=None):
        super().__init__(parent)
        self._label = label
        self._color = color
        self._size = size
        self._value = 0.0
        self._display_value = 0.0
        self.setFixedSize(size, size)

    def set_value(self, v: float):
        self._value = max(0.0, min(100.0, v))
        self._display_value = self._value
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        cx = self._size / 2
        cy = self._size / 2
        r = self._size / 2 - 8
        stroke = 5

        # Track
        pen = QPen(QColor(30, 60, 90), stroke, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawArc(int(cx - r), int(cy - r), int(r * 2), int(r * 2), 225 * 16, -270 * 16)

        # Value arc
        span = int(-270 * 16 * (self._display_value / 100.0))
        if span != 0:
            # Color based on value
            if self._display_value > 85:
                arc_color = Colors.ACCENT_RED
            elif self._display_value > 65:
                arc_color = Colors.ACCENT_GOLD
            else:
                arc_color = self._color
            pen = QPen(arc_color, stroke, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
            p.setPen(pen)
            p.drawArc(int(cx - r), int(cy - r), int(r * 2), int(r * 2), 225 * 16, span)

        # Center text (value)
        p.setPen(QPen(Colors.TEXT_PRIMARY))
        font = QFont(HUD_FONT_MONO, 11, QFont.Weight.Bold)
        p.setFont(font)
        p.drawText(
            QRect(int(cx - r), int(cy - 10), int(r * 2), 20),
            Qt.AlignmentFlag.AlignCenter,
            f"{int(self._display_value)}%"
        )

        # Label below center
        p.setPen(QPen(Colors.TEXT_LABEL))
        font = QFont(HUD_FONT_LABEL, 7)
        p.setFont(font)
        p.drawText(
            QRect(int(cx - r), int(cy + 6), int(r * 2), 14),
            Qt.AlignmentFlag.AlignCenter,
            self._label
        )
        p.end()


# ══════════════════════════════════════════════════════════
# Waveform Widget (for speaking animation)
# ══════════════════════════════════════════════════════════
class WaveformWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._bars = [0.0] * 16
        self._active = False
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self.setFixedHeight(30)

    def set_active(self, active: bool):
        self._active = active
        if active:
            self._timer.start(80)
        else:
            self._timer.stop()
            self._bars = [0.0] * 16
            self.update()

    def _tick(self):
        import random
        for i in range(len(self._bars)):
            if self._active:
                self._bars[i] = random.uniform(0.1, 1.0)
            else:
                self._bars[i] = max(0.0, self._bars[i] - 0.1)
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w = self.width()
        h = self.height()
        bar_w = w / len(self._bars) - 2

        for i, v in enumerate(self._bars):
            bar_h = max(2, v * (h - 4))
            x = i * (bar_w + 2)
            y = (h - bar_h) / 2
            alpha = int(100 + 155 * v)
            color = QColor(0, 212, 255, alpha)
            p.setBrush(QBrush(color))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(int(x), int(y), int(bar_w), int(bar_h), 2, 2)
        p.end()


# ══════════════════════════════════════════════════════════
# Hex Grid Background
# ══════════════════════════════════════════════════════════
class HexBackground(QWidget):
    """Animated hexagonal grid background."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._offset = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(50)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

    def _tick(self):
        self._offset = (self._offset + 0.3) % 40
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(QColor(0, 100, 150, 25), 0.8)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)

        hex_size = 20
        w = self.width()
        h = self.height()

        for row in range(-1, int(h / (hex_size * 1.5)) + 2):
            for col in range(-1, int(w / (hex_size * 1.732)) + 2):
                cx = col * hex_size * 1.732 + (row % 2) * hex_size * 0.866 + self._offset
                cy = row * hex_size * 1.5

                path = QPainterPath()
                for i in range(6):
                    angle = math.radians(60 * i)
                    px = cx + hex_size * math.cos(angle)
                    py = cy + hex_size * math.sin(angle)
                    if i == 0:
                        path.moveTo(px, py)
                    else:
                        path.lineTo(px, py)
                path.closeSubpath()
                p.drawPath(path)
        p.end()


# ══════════════════════════════════════════════════════════
# Glassmorphism Panel
# ══════════════════════════════════════════════════════════
class GlassPanel(QFrame):
    """Glassmorphism-style panel with blue glow border."""

    def __init__(self, parent=None, glow_color=None):
        super().__init__(parent)
        self._glow_color = glow_color or Colors.ACCENT_BLUE
        self.setObjectName("GlassPanel")
        self._setup_style()

    def _setup_style(self):
        gc = self._glow_color
        self.setStyleSheet(f"""
            QFrame#GlassPanel {{
                background-color: rgba(8, 20, 40, 180);
                border: 1px solid rgba({gc.red()}, {gc.green()}, {gc.blue()}, 80);
                border-radius: 8px;
            }}
        """)
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(gc.red(), gc.green(), gc.blue(), 80))
        shadow.setOffset(0, 0)
        self.setGraphicsEffect(shadow)


# ══════════════════════════════════════════════════════════
# JARVIS HUD Main Window
# ══════════════════════════════════════════════════════════
class JarvisHUD(QMainWindow):
    """
    Main JARVIS HUD overlay window.
    Always on top, frameless, semi-transparent.
    """

    def __init__(self, jarvis_app=None):
        super().__init__()
        self._jarvis = jarvis_app
        self._state = JarvisState.IDLE
        self._drag_start = None
        self._boot_done = False
        self._opacity_anim = None

        self._setup_window()
        self._build_ui()
        self._connect_signals()
        self._start_stat_poller()
        self._run_boot_sequence()

    def _setup_window(self):
        """Configure frameless, transparent, always-on-top window."""
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)

        # Start minimized, fade in during boot
        self.setWindowOpacity(0.0)

        # Default size and position (right side of screen)
        screen = QApplication.primaryScreen().geometry()
        hud_w = 420
        hud_h = 680
        x = screen.width() - hud_w - 20
        y = 30
        self.setGeometry(x, y, hud_w, hud_h)
        self.setMinimumSize(380, 500)

    def _build_ui(self):
        """Construct the full HUD layout."""
        central = QWidget()
        central.setObjectName("Central")
        central.setStyleSheet("""
            QWidget#Central {
                background: transparent;
            }
            QLabel {
                color: rgba(200, 230, 255, 220);
                background: transparent;
            }
        """)
        self.setCentralWidget(central)

        # Hex background (behind everything)
        self._hex_bg = HexBackground(central)
        self._hex_bg.setGeometry(0, 0, self.width(), self.height())

        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(8)

        # ── Top Bar ──────────────────────────────────────
        top_bar = self._build_top_bar()
        main_layout.addWidget(top_bar)

        # ── Stats Row ────────────────────────────────────
        stats_panel = self._build_stats_panel()
        main_layout.addWidget(stats_panel)

        # ── State / Waveform ─────────────────────────────
        state_panel = self._build_state_panel()
        main_layout.addWidget(state_panel)

        # ── Response Panel ────────────────────────────────
        response_panel = self._build_response_panel()
        main_layout.addStretch(1)
        main_layout.addWidget(response_panel)

        # ── Reminders / Timers Panel ──────────────────────
        alerts_panel = self._build_alerts_panel()
        main_layout.addWidget(alerts_panel)

        # ── Bottom Bar ───────────────────────────────────
        bottom_bar = self._build_bottom_bar()
        main_layout.addWidget(bottom_bar)

    def _build_top_bar(self) -> QWidget:
        panel = GlassPanel()
        layout = QHBoxLayout(panel)
        layout.setContentsMargins(10, 6, 10, 6)

        # Arc reactor
        self._arc = ArcReactorWidget(size=50)
        layout.addWidget(self._arc)

        # JARVIS title
        title_layout = QVBoxLayout()
        title_layout.setSpacing(0)

        title = QLabel("J.A.R.V.I.S.")
        title.setStyleSheet(f"""
            font-family: Consolas;
            font-size: 18px;
            font-weight: bold;
            color: rgb({Colors.ACCENT_BLUE.red()}, {Colors.ACCENT_BLUE.green()}, {Colors.ACCENT_BLUE.blue()});
            letter-spacing: 4px;
        """)
        sub = QLabel("Just A Rather Very Intelligent System")
        sub.setStyleSheet("font-size: 8px; color: rgba(0,180,220,160); letter-spacing: 1px;")
        title_layout.addWidget(title)
        title_layout.addWidget(sub)
        layout.addLayout(title_layout)

        layout.addStretch()

        # Date / Time
        dt_layout = QVBoxLayout()
        dt_layout.setSpacing(0)
        dt_layout.setAlignment(Qt.AlignmentFlag.AlignRight)

        self._time_label = QLabel("00:00")
        self._time_label.setStyleSheet(f"""
            font-family: Consolas; font-size: 20px; font-weight: bold;
            color: rgb({Colors.ACCENT_GOLD.red()}, {Colors.ACCENT_GOLD.green()}, {Colors.ACCENT_GOLD.blue()});
        """)
        self._time_label.setAlignment(Qt.AlignmentFlag.AlignRight)

        self._date_label = QLabel("Mon, Jan 01 2024")
        self._date_label.setStyleSheet("font-size: 9px; color: rgba(200,220,255,150);")
        self._date_label.setAlignment(Qt.AlignmentFlag.AlignRight)

        dt_layout.addWidget(self._time_label)
        dt_layout.addWidget(self._date_label)
        layout.addLayout(dt_layout)

        # Control buttons
        btn_layout = QVBoxLayout()
        btn_layout.setSpacing(2)

        self._min_btn = QPushButton("—")
        self._close_btn = QPushButton("✕")
        for btn in [self._min_btn, self._close_btn]:
            btn.setFixedSize(20, 20)
            btn.setStyleSheet("""
                QPushButton {
                    background: rgba(0,150,200,60);
                    border: 1px solid rgba(0,200,255,80);
                    border-radius: 10px;
                    color: rgba(200,230,255,200);
                    font-size: 10px;
                    font-weight: bold;
                }
                QPushButton:hover { background: rgba(0,200,255,120); }
            """)
        self._min_btn.clicked.connect(self.showMinimized)
        self._close_btn.clicked.connect(self.close)
        btn_layout.addWidget(self._min_btn)
        btn_layout.addWidget(self._close_btn)
        layout.addLayout(btn_layout)

        # Clock timer
        self._clock_timer = QTimer(self)
        self._clock_timer.timeout.connect(self._update_clock)
        self._clock_timer.start(1000)
        self._update_clock()

        return panel

    def _build_stats_panel(self) -> QWidget:
        panel = GlassPanel()
        layout = QHBoxLayout(panel)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(10)

        # Label
        lbl = QLabel("SYSTEM")
        lbl.setStyleSheet("""
            font-family: Consolas; font-size: 9px; letter-spacing: 3px;
            color: rgba(0,180,220,180);
        """)
        lbl.setFixedWidth(45)
        layout.addWidget(lbl)

        # 3 gauges
        self._cpu_gauge  = CircularGauge("CPU",  Colors.ACCENT_BLUE, 80)
        self._ram_gauge  = CircularGauge("RAM",  QColor(0, 200, 140), 80)
        self._disk_gauge = CircularGauge("DISK", QColor(180, 100, 255), 80)

        layout.addWidget(self._cpu_gauge)
        layout.addWidget(self._ram_gauge)
        layout.addWidget(self._disk_gauge)
        layout.addStretch()

        # Separator + extra info
        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)
        self._cpu_freq_label = QLabel("CPU: — GHz")
        self._ram_used_label = QLabel("RAM: — / — GB")
        self._uptime_label   = QLabel("UP: —")
        for lbl2 in [self._cpu_freq_label, self._ram_used_label, self._uptime_label]:
            lbl2.setStyleSheet("font-size: 8px; color: rgba(100,150,200,180);")
        info_layout.addWidget(self._cpu_freq_label)
        info_layout.addWidget(self._ram_used_label)
        info_layout.addWidget(self._uptime_label)
        layout.addLayout(info_layout)

        return panel

    def _build_state_panel(self) -> QWidget:
        panel = GlassPanel()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(4)

        # State row
        state_row = QHBoxLayout()
        self._state_indicator = QLabel("●")
        self._state_indicator.setStyleSheet("font-size: 14px; color: rgb(0,212,255);")
        self._state_label = QLabel("IDLE — READY")
        self._state_label.setStyleSheet("""
            font-family: Consolas; font-size: 11px; font-weight: bold;
            color: rgb(0,212,255); letter-spacing: 2px;
        """)
        self._mode_badge = QLabel("COMMAND MODE")
        self._mode_badge.setStyleSheet("""
            font-size: 8px; padding: 2px 6px;
            background: rgba(0,180,220,40); border: 1px solid rgba(0,180,220,80);
            border-radius: 8px; color: rgba(0,200,255,200); letter-spacing: 1px;
        """)
        state_row.addWidget(self._state_indicator)
        state_row.addWidget(self._state_label)
        state_row.addStretch()
        state_row.addWidget(self._mode_badge)
        layout.addLayout(state_row)

        # Waveform (shown during speaking)
        self._waveform = WaveformWidget()
        layout.addWidget(self._waveform)

        # Last command
        self._last_cmd_label = QLabel("Last: —")
        self._last_cmd_label.setStyleSheet("font-size: 9px; color: rgba(100,160,210,180);")
        layout.addWidget(self._last_cmd_label)

        # Hotkey hint
        hint = QLabel("[ Alt+J ] — Activate Voice   |   Type in terminal for text commands")
        hint.setStyleSheet("font-size: 8px; color: rgba(60,100,140,200);")
        layout.addWidget(hint)

        return panel

    def _build_response_panel(self) -> QWidget:
        panel = GlassPanel()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(4)

        hdr = QLabel("▶ JARVIS OUTPUT")
        hdr.setStyleSheet("""
            font-family: Consolas; font-size: 9px; letter-spacing: 3px;
            color: rgba(0,180,220,180);
        """)
        layout.addWidget(hdr)

        self._response_text = QTextEdit()
        self._response_text.setReadOnly(True)
        self._response_text.setMinimumHeight(120)
        self._response_text.setMaximumHeight(180)
        self._response_text.setStyleSheet("""
            QTextEdit {
                background: rgba(4, 12, 28, 160);
                border: 1px solid rgba(0,150,200,50);
                border-radius: 4px;
                color: rgba(180,220,255,230);
                font-family: Consolas;
                font-size: 11px;
                padding: 6px;
                selection-background-color: rgba(0,180,220,80);
            }
            QScrollBar:vertical {
                background: rgba(0,20,40,100);
                width: 6px;
            }
            QScrollBar::handle:vertical {
                background: rgba(0,150,200,150);
                border-radius: 3px;
            }
        """)
        self._response_text.setPlainText("All systems online. Awaiting your command, Sir.")
        layout.addWidget(self._response_text)

        return panel

    def _build_alerts_panel(self) -> QWidget:
        panel = GlassPanel(glow_color=Colors.ACCENT_GOLD)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(4)

        hdr = QLabel("◈ ALERTS / REMINDERS")
        hdr.setStyleSheet(f"""
            font-family: Consolas; font-size: 9px; letter-spacing: 3px;
            color: rgba({Colors.ACCENT_GOLD.red()},{Colors.ACCENT_GOLD.green()},{Colors.ACCENT_GOLD.blue()},180);
        """)
        layout.addWidget(hdr)

        self._alerts_label = QLabel("No active reminders or timers.")
        self._alerts_label.setStyleSheet("font-size: 9px; color: rgba(180,200,150,200);")
        self._alerts_label.setWordWrap(True)
        layout.addWidget(self._alerts_label)

        return panel

    def _build_bottom_bar(self) -> QWidget:
        panel = GlassPanel()
        layout = QHBoxLayout(panel)
        layout.setContentsMargins(8, 4, 8, 4)

        self._input_field = QLineEdit()
        self._input_field.setPlaceholderText("Enter command...")
        self._input_field.setStyleSheet("background: rgba(0,20,40,100); border: 1px solid rgba(0,150,200,50); border-radius: 4px; color: #fff; padding: 2px;")
        self._input_field.returnPressed.connect(self._on_input_submit)
        layout.addWidget(self._input_field)

        self._send_btn = QPushButton("SEND")
        self._send_btn.setStyleSheet("background: rgba(0,150,200,60); color: #fff; border-radius: 4px; padding: 2px 8px;")
        self._send_btn.clicked.connect(self._on_input_submit)
        layout.addWidget(self._send_btn)

        layout.addStretch()

        self._settings_btn = QPushButton("⚙")
        self._settings_btn.setToolTip("Open Settings")
        self._settings_btn.setFixedSize(24, 24)
        self._settings_btn.setStyleSheet("""
            QPushButton {
                background: rgba(0,100,150,60); border: 1px solid rgba(0,180,220,80);
                border-radius: 12px; color: rgba(0,200,255,200); font-size: 12px;
            }
            QPushButton:hover { background: rgba(0,180,220,100); }
        """)
        self._settings_btn.clicked.connect(self._open_settings)
        layout.addWidget(self._settings_btn)

        return panel

    def _on_input_submit(self):
        text = self._input_field.text().strip()
        if text:
            get_hud_signals().text_command.emit(text)
            self._input_field.clear()

    # ── Clock ─────────────────────────────────────────────
    def _update_clock(self):
        now = datetime.now()
        self._time_label.setText(now.strftime("%I:%M %p").lstrip("0"))
        self._date_label.setText(now.strftime("%a, %b %d %Y"))

    # ── State Updates ─────────────────────────────────────
    def set_state(self, state: str):
        self._state = state
        self._arc.set_state(state)

        state_texts = {
            JarvisState.IDLE:       ("IDLE — READY", "rgb(0,212,255)"),
            JarvisState.LISTENING:  ("LISTENING ...", "rgb(0,255,200)"),
            JarvisState.PROCESSING: ("PROCESSING ...", "rgb(255,215,0)"),
            JarvisState.SPEAKING:   ("SPEAKING", "rgb(100,255,100)"),
            JarvisState.ERROR:      ("ERROR", "rgb(255,60,60)"),
        }
        text, color = state_texts.get(state, ("IDLE", "rgb(0,212,255)"))
        self._state_label.setText(text)
        self._state_label.setStyleSheet(f"""
            font-family: Consolas; font-size: 11px; font-weight: bold;
            color: {color}; letter-spacing: 2px;
        """)
        self._state_indicator.setStyleSheet(f"font-size: 14px; color: {color};")
        self._waveform.set_active(state == JarvisState.SPEAKING)

    def set_response(self, text: str):
        self._response_text.setPlainText(text)
        # Scroll to bottom
        cursor = self._response_text.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        self._response_text.setTextCursor(cursor)

    def set_last_command(self, cmd: str):
        self._last_cmd_label.setText(f"Last: {cmd[:60]}")

    def set_mode(self, mode: str):
        self._mode_badge.setText(f"{mode.upper()} MODE")

    def _update_stats(self, cpu: float, ram: float, disk: float):
        self._cpu_gauge.set_value(cpu)
        self._ram_gauge.set_value(ram)
        self._disk_gauge.set_value(disk)

        # Extra info
        try:
            import psutil
            freq = psutil.cpu_freq()
            ram_info = psutil.virtual_memory()
            freq_str = f"{freq.current/1000:.1f} GHz" if freq else "—"
            used_gb = ram_info.used / (1024**3)
            total_gb = ram_info.total / (1024**3)
            boot_time = datetime.fromtimestamp(psutil.boot_time())
            uptime = datetime.now() - boot_time
            hours, rem = divmod(int(uptime.total_seconds()), 3600)
            mins = rem // 60
            self._cpu_freq_label.setText(f"CPU: {freq_str}")
            self._ram_used_label.setText(f"RAM: {used_gb:.1f} / {total_gb:.0f} GB")
            self._uptime_label.setText(f"UP: {hours}h {mins}m")
        except Exception:
            pass

    def _update_alerts(self, timers: list, reminders: list):
        lines = []
        for t in timers[:3]:
            try:
                from datetime import datetime
                end_dt = datetime.fromisoformat(t.get("end_time", ""))
                remaining = (end_dt - datetime.now()).total_seconds()
                if remaining > 0:
                    m, s = divmod(int(remaining), 60)
                    lines.append(f"⏱ {t.get('name','Timer')}: {m}m {s}s remaining")
            except Exception:
                pass
        for r in reminders[:3]:
            try:
                lines.append(f"🔔 {r.get('task', '')}")
            except Exception:
                pass
        if lines:
            self._alerts_label.setText("\n".join(lines))
        else:
            self._alerts_label.setText("No active reminders or timers.")

    # ── Boot Sequence ─────────────────────────────────────
    def _run_boot_sequence(self):
        """Fade in the HUD over 1.5 seconds after a short delay."""
        def _do_boot():
            time.sleep(0.5)
            # Emit to main thread
            get_hud_signals().boot_complete.emit()

        threading.Thread(target=_do_boot, daemon=True).start()

    def _on_boot_complete(self):
        # Fade in animation
        self._fade_anim = QPropertyAnimation(self, b"windowOpacity")
        self._fade_anim.setDuration(1500)
        self._fade_anim.setStartValue(0.0)
        self._fade_anim.setEndValue(0.93)
        self._fade_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._fade_anim.start()
        self._boot_done = True

    # ── Signal Connections ────────────────────────────────
    def _connect_signals(self):
        sigs = get_hud_signals()
        sigs.state_changed.connect(self.set_state)
        sigs.response_text.connect(self.set_response)
        sigs.stat_update.connect(self._update_stats)
        sigs.boot_complete.connect(self._on_boot_complete)
        sigs.timer_update.connect(lambda t: self._update_alerts(t, []))
        sigs.reminder_update.connect(lambda r: self._update_alerts([], r))

    # ── Stats Poller ──────────────────────────────────────
    def _start_stat_poller(self):
        """Poll system stats every 2 seconds, emit via signal."""
        def _poll():
            import psutil
            while True:
                try:
                    cpu = psutil.cpu_percent(interval=1)
                    ram = psutil.virtual_memory().percent
                    disk = psutil.disk_usage("/").percent
                    get_hud_signals().stat_update.emit(cpu, ram, disk)
                except Exception:
                    pass
                time.sleep(2)

        t = threading.Thread(target=_poll, daemon=True, name="HUDStatPoller")
        t.start()

    # ── Settings Panel ────────────────────────────────────
    def _open_settings(self):
        if not hasattr(self, '_settings_win') or not self._settings_win.isVisible():
            self._settings_win = SettingsPanel(self)
            self._settings_win.show()

    # ── Window Dragging ───────────────────────────────────
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if self._drag_start and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_start)

    def mouseReleaseEvent(self, event):
        self._drag_start = None

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, '_hex_bg'):
            self._hex_bg.setGeometry(0, 0, self.width(), self.height())


# ══════════════════════════════════════════════════════════
# Settings Panel
# ══════════════════════════════════════════════════════════
class SettingsPanel(QWidget):
    """Floating settings panel."""

    def __init__(self, parent=None):
        super().__init__(parent, Qt.WindowType.Window | Qt.WindowType.WindowStaysOnTopHint)
        self.setWindowTitle("JARVIS — Settings")
        self.setFixedSize(380, 480)
        self._setup()

    def _setup(self):
        self.setStyleSheet("""
            QWidget {
                background-color: rgb(8, 20, 40);
                color: rgb(180, 220, 255);
                font-family: Consolas;
                font-size: 11px;
            }
            QLabel { color: rgb(0, 180, 220); font-size: 10px; letter-spacing: 1px; }
            QLineEdit {
                background: rgba(0, 30, 60, 180);
                border: 1px solid rgba(0,150,200,100);
                border-radius: 4px; padding: 4px; color: rgb(200,230,255);
            }
            QCheckBox { color: rgb(180,220,255); }
            QPushButton {
                background: rgba(0,100,150,100);
                border: 1px solid rgba(0,180,220,120);
                border-radius: 4px; padding: 6px 14px; color: rgb(0,200,255);
                font-weight: bold;
            }
            QPushButton:hover { background: rgba(0,180,220,140); }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        # Title
        title = QLabel("⚙ JARVIS SETTINGS")
        title.setStyleSheet("font-size: 14px; font-weight: bold; letter-spacing: 3px; color: rgb(0,212,255);")
        layout.addWidget(title)

        # Settings fields
        fields = [
            ("USERNAME", "user.name", "Sir"),
            ("HOTKEY", "activation.hotkey", "alt+j"),
            ("WHISPER MODEL", "voice.whisper_model", "base"),
            ("OLLAMA MODEL", "ai.model", "qwen2.5-coder:7b"),
            ("WEATHER CITY", "weather.location", ""),
            ("NEWS API KEY (.env)", "NEWS_API_KEY", ""),
            ("WEATHER API KEY (.env)", "WEATHER_API_KEY", ""),
        ]

        self._fields = {}
        for label, key, default in fields:
            row = QHBoxLayout()
            lbl = QLabel(f"{label}:")
            lbl.setFixedWidth(140)
            field = QLineEdit()
            field.setPlaceholderText(default)
            self._fields[key] = field
            row.addWidget(lbl)
            row.addWidget(field)
            layout.addLayout(row)

        # Toggles
        self._voice_toggle = QCheckBox("Voice Output Enabled")
        self._voice_toggle.setChecked(True)
        self._boot_anim_toggle = QCheckBox("Boot Animation")
        self._boot_anim_toggle.setChecked(True)
        self._notif_toggle = QCheckBox("System Notifications")
        self._notif_toggle.setChecked(True)
        layout.addWidget(self._voice_toggle)
        layout.addWidget(self._boot_anim_toggle)
        layout.addWidget(self._notif_toggle)

        layout.addStretch()

        # Buttons
        btn_row = QHBoxLayout()
        save_btn = QPushButton("SAVE")
        cancel_btn = QPushButton("CANCEL")
        save_btn.clicked.connect(self._save)
        cancel_btn.clicked.connect(self.close)
        btn_row.addWidget(save_btn)
        btn_row.addWidget(cancel_btn)
        layout.addLayout(btn_row)

    def _save(self):
        """Save settings to YAML and .env."""
        try:
            from config import Config
            import yaml
            from pathlib import Path

            # Update settings
            settings_path = Config.root_dir / "config" / "settings.yaml"
            if settings_path.exists():
                with open(settings_path, "r", encoding="utf-8") as f:
                    settings = yaml.safe_load(f) or {}
            else:
                settings = {}

            for key, field in self._fields.items():
                val = field.text().strip()
                if not val:
                    continue
                if "." in key:
                    section, subkey = key.split(".", 1)
                    if section not in settings:
                        settings[section] = {}
                    settings[section][subkey] = val

            with open(settings_path, "w", encoding="utf-8") as f:
                yaml.dump(settings, f, allow_unicode=True, default_flow_style=False)

            self.close()
        except Exception as e:
            log.error("Settings save error: %s", e)


# ══════════════════════════════════════════════════════════
# HUD Application Singleton
# ══════════════════════════════════════════════════════════
_hud_app: QApplication = None
_hud_window: JarvisHUD = None


def get_hud() -> JarvisHUD | None:
    return _hud_window


def launch_hud(jarvis_app=None) -> JarvisHUD:
    """
    Launch the HUD in the current thread.
    Call this from the main thread.
    Returns the HUD window instance.
    """
    global _hud_app, _hud_window

    if QApplication.instance() is None:
        _hud_app = QApplication(sys.argv)
    else:
        _hud_app = QApplication.instance()

    _hud_window = JarvisHUD(jarvis_app=jarvis_app)
    _hud_window.show()
    return _hud_window


def update_hud_state(state: str):
    """Thread-safe: update HUD state from any thread."""
    try:
        get_hud_signals().state_changed.emit(state)
    except Exception:
        pass


def update_hud_response(text: str):
    """Thread-safe: update HUD response text from any thread."""
    try:
        get_hud_signals().response_text.emit(text)
    except Exception:
        pass


# ══════════════════════════════════════════════════════════
# Standalone Test / Demo
# ══════════════════════════════════════════════════════════
if __name__ == "__main__":
    import sys
    app = QApplication(sys.argv)

    hud = JarvisHUD()
    hud.show()

    # Demo state cycling
    states = [
        JarvisState.IDLE, JarvisState.LISTENING,
        JarvisState.PROCESSING, JarvisState.SPEAKING,
        JarvisState.ERROR, JarvisState.IDLE
    ]
    demo_responses = [
        "All systems online. Good morning, Sir. How can I assist?",
        "Listening, Sir...",
        "Processing your request...",
        "Opening Chrome, Sir. Volume set to 70%.",
        "Error: Could not connect to AI backend. Running in offline mode.",
        "Ready for your next command, Sir.",
    ]
    state_index = [0]

    def cycle_state():
        i = state_index[0]
        hud.set_state(states[i])
        hud.set_response(demo_responses[i])
        hud.set_last_command(f"Demo command #{i+1}")
        state_index[0] = (i + 1) % len(states)

    demo_timer = QTimer()
    demo_timer.timeout.connect(cycle_state)
    demo_timer.start(2500)

    sys.exit(app.exec())
