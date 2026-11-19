"""macOS desktop roulette; selection is independent of animation."""
import math
import secrets
import sys
import subprocess
from pathlib import Path
from PySide6.QtCore import Qt, QThread, Signal, QTimer, QElapsedTimer, QUrl
from PySide6.QtGui import QColor, QPainter, QPen, QFont, QDesktopServices
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
from data import fetch, fallback, save


class SpinSound:
    """Play bundled audio with macOS's built-in player; never block the GUI."""
    def __init__(self):
        self.process = None
        self.enabled = True

    def play(self):
        self.stop()
        if self.enabled and sys.platform == 'darwin':
            try:
                self.process = subprocess.Popen(
                    ['/usr/bin/afplay', str(Path(__file__).with_name('spin.wav'))],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except OSError:
                self.process = None  # A missing audio device/player cannot break a spin.

    def stop(self):
        if self.process is not None:
            if self.process.poll() is None:
                try:
                    self.process.terminate()
                except ProcessLookupError:
                    pass
            # poll reaps completed processes; Popen retains terminated ones until
            # the next poll/cleanup without waiting on the GUI thread.
            self.process.poll()


class Fetcher(QThread):
    progress = Signal(str)
    ready = Signal(object, str)
    failed = Signal(str)

    def run(self):
        try:
            result = fetch(self.progress.emit)
            note = ''
            try:
                save(result)
            except OSError:
                note = ' • Could not save offline cache'
            self.ready.emit(result, note)
        except Exception as error:
            self.failed.emit(str(error))


class Wheel(QWidget):
    def __init__(self):
        super().__init__()
        self.angle = 0.0
        self.setMinimumSize(360, 360)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        cx, cy = self.width() / 2, self.height() / 2
        r = min(cx, cy) - 24
        p.translate(cx, cy)
        p.setPen(QPen(QColor('#263343'), 8))
        p.setBrush(QColor('#172331'))
        p.drawEllipse(-int(r), -int(r), int(r*2), int(r*2))
        # Each of 500 ranks has one equal angular slot. Clockwise from noon.
        for i in range(500):
            a = math.radians(self.angle + (i + .5) * .72 - 90)
            color = QColor.fromHsv((i * 7) % 360, 125, 210)
            p.setPen(QPen(color, 1.8))
            inner = r * (.77 if i % 25 == 0 else .87)
            p.drawLine(int(math.cos(a)*inner), int(math.sin(a)*inner), int(math.cos(a)*(r-7)), int(math.sin(a)*(r-7)))
            if i % 25 == 0:
                p.setPen(QColor('#b8c6d6'))
                x, y = math.cos(a)*r*.68, math.sin(a)*r*.68
                p.setFont(QFont('Helvetica Neue', 10))
                p.drawText(int(x)-18, int(y)-9, 36, 18, Qt.AlignmentFlag.AlignCenter, str(i+1))
        p.setBrush(QColor('#0e1721'))
        p.setPen(QPen(QColor('#2c4353'), 2))
        p.drawEllipse(-75, -75, 150, 150)
        p.setPen(QColor('#5ce4bf'))
        p.setFont(QFont('Helvetica Neue', 25, QFont.Weight.Bold))
        rank = int(((-self.angle) % 360) / .72) % 500 + 1
        p.drawText(-70, -30, 140, 60, Qt.AlignmentFlag.AlignCenter, f'{rank:03d}')
        p.setFont(QFont('Helvetica Neue', 9))
        p.setPen(QColor('#92a3b5'))
        p.drawText(-70, 28, 140, 20, Qt.AlignmentFlag.AlignCenter, 'LETTERBOXD 500')
        p.setPen(QPen(QColor('#ffffff'), 4))
        p.drawLine(0, -int(r)-10, 0, -int(r)+15)
        p.end()


class Window(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Movie Roulette')
        self.resize(600, 800)
        self.setMinimumSize(460, 680)
        self.snapshot, label = fallback()
        self.pending = None
        self.selected = None
        self.sound = SpinSound()
        self.timer = QTimer(self)
        self.timer.setInterval(16)
        self.timer.timeout.connect(self.tick)
        self.clock = QElapsedTimer()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(36, 28, 36, 28)
        eyebrow = QLabel('TONIGHT BELONGS TO CHANCE')
        eyebrow.setObjectName('eyebrow')
        layout.addWidget(eyebrow, alignment=Qt.AlignmentFlag.AlignCenter)
        heading = QLabel('Movie Roulette')
        heading.setObjectName('heading')
        layout.addWidget(heading, alignment=Qt.AlignmentFlag.AlignCenter)
        subtitle = QLabel('500 remarkable films. One equal chance each.')
        layout.addWidget(subtitle, alignment=Qt.AlignmentFlag.AlignCenter)
        self.wheel = Wheel()
        layout.addWidget(self.wheel, 1)
        self.result = QLabel('Let the credits begin.')
        self.result.setObjectName('result')
        self.result.setWordWrap(True)
        self.result.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.result.setMinimumHeight(65)
        layout.addWidget(self.result)
        self.spin = QPushButton('Spin for a film  ↻')
        self.spin.setObjectName('spin')
        self.spin.setMinimumHeight(52)
        self.spin.clicked.connect(self.start_spin)
        self.spin.setEnabled(bool(self.snapshot))
        layout.addWidget(self.spin)
        row = QHBoxLayout()
        self.open = QPushButton('Open film on Letterboxd ↗')
        self.open.setEnabled(False)
        self.open.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(self.selected['url'])))
        self.refresh = QPushButton('Refresh list')
        self.refresh.clicked.connect(self.refresh_list)
        row.addWidget(self.open)
        row.addWidget(self.refresh)
        layout.addLayout(row)
        self.mute = QPushButton('Sound: On')
        self.mute.setCheckable(True)
        self.mute.setToolTip('Mute immediately; enabling sound takes effect on the next spin.')
        self.mute.toggled.connect(self.toggle_sound)
        layout.addWidget(self.mute)
        self.status = QLabel(self.describe(label))
        self.status.setWordWrap(True)
        self.status.setObjectName('status')
        self.status.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self.status)
        self.worker = None
        QTimer.singleShot(0, self.refresh_list)

    def toggle_sound(self, muted):
        self.sound.enabled = not muted
        self.mute.setText('Sound: Off' if muted else 'Sound: On')
        if muted:
            self.sound.stop()

    def describe(self, label):
        date = self.snapshot['fetched_at'][:10] if self.snapshot else ''
        return f'{label} • {date} • 500 films' if self.snapshot else label

    def refresh_list(self):
        if self.worker and self.worker.isRunning():
            return
        self.refresh.setEnabled(False)
        self.worker = Fetcher(self)
        self.worker.progress.connect(self.status.setText)
        self.worker.ready.connect(self.loaded)
        self.worker.failed.connect(self.failed)
        self.worker.finished.connect(lambda: self.refresh.setEnabled(not self.timer.isActive()))
        self.worker.start()

    def loaded(self, snapshot, note):
        if self.timer.isActive():
            self.pending = (snapshot, note)
            return
        self.snapshot = snapshot
        self.spin.setEnabled(True)
        self.status.setText(self.describe('Live list') + note)

    def failed(self, error):
        self.status.setText(self.describe('Offline fallback') + '\nRefresh failed: ' + error)

    def start_spin(self):
        if not self.snapshot or self.timer.isActive():
            return
        index = secrets.randbelow(500)
        self.selected = dict(self.snapshot['films'][index])
        self.start_angle = self.wheel.angle
        target = (-(index + .5) * .72) % 360
        self.travel = 360 * 7 + (target - self.start_angle) % 360
        self.spin.setEnabled(False)
        self.refresh.setEnabled(False)
        self.open.setEnabled(False)
        self.result.setText('Finding your next great film…')
        self.sound.play()
        self.clock.start()
        self.timer.start()

    def tick(self):
        t = min(1., self.clock.elapsed() / 5200)
        self.wheel.angle = (self.start_angle + self.travel * (1 - (1-t)**4)) % 360
        self.wheel.update()
        if t >= 1:
            self.timer.stop()
            self.sound.stop()
            self.result.setText(f"#{self.selected['rank']}  ·  {self.selected['title']}")
            self.spin.setEnabled(True)
            self.open.setEnabled(True)
            self.refresh.setEnabled(not (self.worker and self.worker.isRunning()))
            if self.pending:
                snapshot, note = self.pending
                self.pending = None
                self.loaded(snapshot, note)

    def closeEvent(self, event):
        self.timer.stop()
        self.sound.stop()
        # Never destroy a running QThread. Hide immediately, finish bounded fetch,
        # then let Qt exit. No forced thread termination or partially saved cache.
        if self.worker and self.worker.isRunning():
            event.ignore()
            self.hide()
            self.worker.finished.connect(QApplication.instance().quit)
        else:
            event.accept()


def main():
    app = QApplication(sys.argv)
    app.setApplicationName('Movie Roulette')
    app.setOrganizationName('Movie Roulette')
    app.setStyleSheet('''
        QWidget { background: #0c141e; color: #aab9c9; font-family: "Helvetica Neue"; font-size: 14px; }
        QLabel#heading { color: #f6f8fc; font-size: 38px; font-weight: 700; }
        QLabel#eyebrow { color: #5ce4bf; font-size: 11px; letter-spacing: 3px; }
        QLabel#result { color: #f6f8fc; font-size: 23px; font-weight: 600; }
        QLabel#status { color: #8397aa; font-size: 11px; }
        QPushButton { background: #182636; border: 1px solid #2b4054; border-radius: 10px; padding: 12px; }
        QPushButton:hover { background: #24394d; }
        QPushButton:disabled { color: #526375; }
        QPushButton#spin { background: #5ce4bf; color: #09251e; font-size: 19px; font-weight: 700; }
        QPushButton#spin:disabled { background: #27473f; color: #8caaa1; }
    ''')
    window = Window()
    window.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
