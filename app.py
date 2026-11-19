"""Cross-platform desktop roulette; selection is independent of animation."""
import math
import re
from urllib.parse import urlencode
import secrets
import sys
from pathlib import Path
from PySide6.QtCore import Qt, QThread, Signal, QTimer, QElapsedTimer, QUrl, QVariantAnimation, QEasingCurve, QRectF, QEvent
from PySide6.QtGui import QColor, QPainter, QPen, QFont, QDesktopServices, QPixmap
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTabWidget, QScrollArea
from data import fetch, fallback, save
from cinejoy import resolve
from details import fetch_details
from platform_support import font_family
from PySide6.QtMultimedia import QSoundEffect


def cinejoy_search_url(title):
    # Letterboxd display names end in a release year; search by the film title.
    title = re.sub(r'\s+\(\d{4}\)$', '', title).strip()
    return 'https://cinejoy.pk/search?' + urlencode({'q': title})


class SpinSound:
    """Qt plays the bundled WAV asynchronously on macOS, Windows, and Linux."""
    def __init__(self):
        self.enabled = True
        self.effect = QSoundEffect()
        self.effect.setSource(QUrl.fromLocalFile(str(Path(__file__).with_name('spin.wav'))))
        self.effect.setVolume(.65)
        self.effect.setLoopCount(1)

    def play(self):
        self.stop()
        if self.enabled:
            self.effect.play()

    def stop(self):
        self.effect.stop()


class DetailsFetcher(QThread):
    ready = Signal(str, object)
    failed = Signal(str, str)

    def __init__(self, url, parent=None):
        super().__init__(parent)
        self.url = url

    def run(self):
        try:
            self.ready.emit(self.url, fetch_details(self.url))
        except Exception as error:
            self.failed.emit(self.url, str(error))


class CinejoyFinder(QThread):
    ready = Signal(str, str)

    def __init__(self, title, parent=None):
        super().__init__(parent)
        self.title = title

    def run(self):
        try:
            url, message = resolve(self.title)
        except Exception:
            url = cinejoy_search_url(self.title)
            message = 'Background search unavailable. Opening search instead. See README for browser setup.'
        self.ready.emit(url, message)


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
                p.setFont(QFont(font_family(), 10))
                p.drawText(int(x)-18, int(y)-9, 36, 18, Qt.AlignmentFlag.AlignCenter, str(i+1))
        p.setBrush(QColor('#0e1721'))
        p.setPen(QPen(QColor('#2c4353'), 2))
        p.drawEllipse(-75, -75, 150, 150)
        p.setPen(QColor('#5ce4bf'))
        p.setFont(QFont(font_family(), 25, QFont.Weight.Bold))
        rank = int(((-self.angle) % 360) / .72) % 500 + 1
        p.drawText(-70, -30, 140, 60, Qt.AlignmentFlag.AlignCenter, f'{rank:03d}')
        p.setFont(QFont(font_family(), 9))
        p.setPen(QColor('#92a3b5'))
        p.drawText(-70, 28, 140, 20, Qt.AlignmentFlag.AlignCenter, 'LETTERBOXD 500')
        p.setPen(QPen(QColor('#ffffff'), 4))
        p.drawLine(0, -int(r)-10, 0, -int(r)+15)
        p.end()


class SoundToggle(QPushButton):
    """Keyboard-accessible sound switch: checked means sound is enabled."""
    def __init__(self):
        super().__init__('Sound')
        self.setCheckable(True)
        self.setChecked(True)
        self.setFixedSize(120, 34)
        self.position = 1.0
        self.slide = QVariantAnimation(self)
        self.slide.setDuration(180)
        self.slide.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self.slide.valueChanged.connect(self.move_knob)
        self.toggled.connect(self.animate_toggle)
        self.setAccessibleName('Sound enabled')
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def animate_toggle(self, enabled):
        self.slide.stop()
        self.slide.setStartValue(self.position)
        self.slide.setEndValue(1.0 if enabled else 0.0)
        self.slide.start()

    def move_knob(self, value):
        self.position = float(value)
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(QColor('#b8c9d8'))
        p.setFont(QFont(font_family(), 11))
        p.drawText(0, 0, 62, 34, Qt.AlignmentFlag.AlignVCenter, 'Sound')
        p.setPen(Qt.PenStyle.NoPen)
        off, on = QColor('#354759'), QColor('#5ce4bf')
        blend = lambda a, b: round(a + (b - a) * self.position)
        track = QColor(blend(off.red(), on.red()), blend(off.green(), on.green()), blend(off.blue(), on.blue()))
        p.setBrush(track)
        p.drawRoundedRect(66, 5, 50, 24, 12, 12)
        p.setBrush(QColor('#e7fff6'))
        p.drawEllipse(QRectF(70 + 24 * self.position, 9, 16, 16))
        if self.hasFocus():
            p.setPen(QPen(QColor('#a9caff'), 1))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(1, 1, 118, 32, 10, 10)
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
        self.revealed = False
        self.detail_jobs = []
        self.detail_cache = {}
        self.detail_loading = set()
        self.sound = SpinSound()
        self.timer = QTimer(self)
        self.timer.setInterval(16)
        self.timer.timeout.connect(self.tick)
        self.clock = QElapsedTimer()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 20, 30, 24)
        layout.setSpacing(14)
        topbar = QHBoxLayout()
        topbar.addStretch()
        self.mute = SoundToggle()
        self.mute.setToolTip('Mute immediately; enabling sound takes effect on the next spin.')
        self.mute.toggled.connect(lambda enabled: self.toggle_sound(not enabled))
        topbar.addWidget(self.mute)
        layout.addLayout(topbar)
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs, 1)
        roulette = QWidget()
        self.tabs.addTab(roulette, 'Roulette')
        layout = QVBoxLayout(roulette)
        layout.setContentsMargins(0, 12, 0, 0)
        layout.setSpacing(14)
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
        actions = QVBoxLayout()
        actions.setSpacing(12)
        actions.addWidget(self.spin)
        row = QHBoxLayout()
        row.setSpacing(12)
        self.open = QPushButton('Letterboxd ↗')
        self.open.setObjectName('letterboxd')
        self.open.setEnabled(False)
        self.open.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(self.selected['url'])))
        self.finder = None
        self.cinejoy = QPushButton('Find film ↗')
        self.cinejoy.setObjectName('findfilm')
        self.cinejoy.setEnabled(False)
        self.cinejoy.setToolTip('Search Cinejoy and open a unique title/year match.')
        self.cinejoy.clicked.connect(self.search_cinejoy)
        row.addWidget(self.open, 1)
        row.addWidget(self.cinejoy, 1)
        actions.addLayout(row)
        self.refresh = QPushButton('↻  Refresh list')
        self.refresh.setObjectName('refresh')
        self.refresh.clicked.connect(self.refresh_list)
        actions.addWidget(self.refresh)
        layout.addLayout(actions)
        self.open.setMinimumHeight(44)
        self.cinejoy.setMinimumHeight(44)
        self.refresh.setMinimumHeight(40)
        for button in (self.spin, self.open, self.cinejoy, self.refresh):
            button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.status = QLabel(self.describe(label))
        self.status.setWordWrap(True)
        self.status.setObjectName('status')
        self.status.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self.status)
        self.worker = None
        self.build_details_tab()
        self.tabs.currentChanged.connect(lambda index: self.load_details() if index == 1 else None)
        QTimer.singleShot(0, self.refresh_list)

    def build_details_tab(self):
        scroll = QScrollArea()
        self.details_scroll = scroll
        self.poster_image = QPixmap()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        content = QWidget()
        box = QVBoxLayout(content)
        box.setContentsMargins(8, 24, 8, 28)
        box.setSpacing(18)
        self.detail_title = QLabel('Your next great film awaits.')
        self.detail_title.setObjectName('detailtitle')
        self.detail_title.setWordWrap(True)
        self.detail_title.setTextFormat(Qt.TextFormat.PlainText)
        box.addWidget(self.detail_title)
        self.poster = QLabel('Spin the wheel to choose a film.')
        self.poster.setFixedSize(350, 525)
        self.poster.setWordWrap(True)
        self.poster.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.poster.setObjectName('poster')
        box.addWidget(self.poster, alignment=Qt.AlignmentFlag.AlignHCenter)
        self.rating = QLabel('Letterboxd rating —')
        self.rating.setObjectName('rating')
        box.addWidget(self.rating)
        self.synopsis = QLabel('The selected film’s synopsis, poster, and community rating will appear here.')
        self.synopsis.setWordWrap(True)
        self.synopsis.setObjectName('synopsis')
        self.synopsis.setTextFormat(Qt.TextFormat.PlainText)
        self.synopsis.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        box.addWidget(self.synopsis)
        self.detail_status = QLabel('Details fetched from Letterboxd when you open this tab.')
        self.detail_status.setWordWrap(True)
        box.addWidget(self.detail_status)
        box.addStretch()
        scroll.setWidget(content)
        scroll.viewport().installEventFilter(self)
        self.tabs.addTab(scroll, 'Movie details')

    def eventFilter(self, watched, event):
        if hasattr(self, 'details_scroll') and watched is self.details_scroll.viewport() and event.type() == QEvent.Type.Resize:
            QTimer.singleShot(0, self.size_details)
        return super().eventFilter(watched, event)

    def size_details(self):
        available = max(240, self.details_scroll.viewport().width() - 16)
        width = min(440, max(240, int(available * .74)))
        width = min(width, available)
        height = round(width * 1.5)
        self.poster.setFixedSize(width, height)
        if not self.poster_image.isNull():
            ratio = self.devicePixelRatioF()
            scaled = self.poster_image.scaled(round(width * ratio), round(height * ratio), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            scaled.setDevicePixelRatio(ratio)
            self.poster.setPixmap(scaled)
        self.synopsis.setMinimumHeight(max(80, self.synopsis.heightForWidth(available)))

    def reset_details(self):
        self.poster_image = QPixmap()
        self.detail_title.setText('Let the wheel decide…')
        self.poster.clear()
        self.poster.setText('Poster appears after the spin.')
        self.rating.setText('Letterboxd rating —')
        self.synopsis.setText('Open this tab after the spin to load the selected film’s details.')
        self.detail_status.setText('')

    def load_details(self, force=False):
        if not self.selected or not self.revealed or self.timer.isActive() or getattr(self, '_closing', False):
            return
        url = self.selected['url']
        self.detail_title.setText(self.selected['title'])
        if url in self.detail_cache and not force:
            self.show_details(url, self.detail_cache[url])
            return
        if url in self.detail_loading:
            return
        self.detail_status.setText('Fetching details from Letterboxd…')
        self.detail_loading.add(url)
        worker = DetailsFetcher(url, self)
        self.detail_jobs.append(worker)
        worker.ready.connect(self.show_details)
        worker.failed.connect(self.details_failed)
        worker.finished.connect(lambda: self.detail_loading.discard(url))
        worker.finished.connect(self.finish_close_if_needed)
        worker.start()

    def finish_close_if_needed(self):
        if getattr(self, '_closing', False):
            self.finish_close()

    def show_details(self, url, info):
        self.detail_cache[url] = info
        if not self.selected or not self.revealed or self.selected['url'] != url or self.timer.isActive():
            return
        self.poster.clear()
        pixmap = QPixmap()
        if info.get('poster') and pixmap.loadFromData(info['poster']):
            self.poster_image = pixmap
        else:
            self.poster_image = QPixmap()
            self.poster.setText('Poster unavailable')
        value = info.get('rating')
        text = f"★ {value} / {info.get('best', 5)}" if value is not None else 'Rating unavailable'
        count = info.get('count')
        if count is not None:
            text += f' · {int(count):,} ratings'
        self.rating.setText(text)
        self.synopsis.setText(info.get('synopsis') or 'Synopsis unavailable.')
        self.size_details()
        self.detail_status.clear()

    def details_failed(self, url, error):
        if self.selected and self.revealed and self.selected['url'] == url and not self.timer.isActive():
            self.detail_status.setText('Could not load details. Check your connection and reopen this tab to retry. ' + error)

    def search_cinejoy(self):
        if not self.selected or (self.finder and self.finder.isRunning()):
            return
        self.cinejoy.setEnabled(False)
        self.cinejoy.setText('Finding title and year…')
        self.spin.setEnabled(False)
        self.finder = CinejoyFinder(self.selected['title'], self)
        self.finder.ready.connect(self.cinejoy_found)
        self.finder.finished.connect(self.cinejoy_finished)
        self.finder.start()

    def cinejoy_found(self, url, message):
        if self.isVisible():
            self.status.setText(message)
            QDesktopServices.openUrl(QUrl(url))

    def cinejoy_finished(self):
        self.cinejoy.setText('Find film ↗')
        self.cinejoy.setEnabled(bool(self.selected) and not self.timer.isActive())
        self.spin.setEnabled(bool(self.snapshot) and not self.timer.isActive())
        if getattr(self, '_closing', False):
            self.finish_close()

    def finish_close(self):
        workers = [self.worker, self.finder] + self.detail_jobs
        if not any(worker and worker.isRunning() for worker in workers):
            QApplication.instance().quit()

    def toggle_sound(self, muted):
        self.sound.enabled = not muted
        self.mute.setAccessibleName('Sound disabled' if muted else 'Sound enabled')
        self.mute.update()
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
        self.spin.setEnabled(not (self.finder and self.finder.isRunning()))
        self.status.setText(self.describe('Live list') + note)

    def failed(self, error):
        self.status.setText(self.describe('Offline fallback') + '\nRefresh failed: ' + error)

    def start_spin(self):
        if not self.snapshot or self.timer.isActive():
            return
        index = secrets.randbelow(500)
        self.revealed = False
        self.selected = dict(self.snapshot['films'][index])
        self.reset_details()
        self.start_angle = self.wheel.angle
        target = (-(index + .5) * .72) % 360
        self.travel = 360 * 7 + (target - self.start_angle) % 360
        self.spin.setEnabled(False)
        self.refresh.setEnabled(False)
        self.open.setEnabled(False)
        self.cinejoy.setEnabled(False)
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
            self.revealed = True
            if self.tabs.currentIndex() == 1:
                self.load_details()
            self.spin.setEnabled(True)
            self.open.setEnabled(True)
            self.cinejoy.setEnabled(True)
            self.refresh.setEnabled(not (self.worker and self.worker.isRunning()))
            if self.pending:
                snapshot, note = self.pending
                self.pending = None
                self.loaded(snapshot, note)

    def closeEvent(self, event):
        self.timer.stop()
        self.sound.stop()
        # Hide immediately, then let both bounded background jobs finish.
        workers = [worker for worker in [self.worker, self.finder] + self.detail_jobs if worker and worker.isRunning()]
        if workers:
            event.ignore()
            self._closing = True
            self.hide()
            for worker in workers:
                worker.finished.connect(self.finish_close)
        else:
            event.accept()


def main():
    app = QApplication(sys.argv)
    app.setApplicationName('Movie Roulette')
    app.setOrganizationName('Movie Roulette')
    stylesheet = Path(__file__).with_name('styles.qss')
    app.setStyleSheet(stylesheet.read_text(encoding='utf-8').replace('@APP_FONT@', font_family()))
    window = Window()
    window.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
