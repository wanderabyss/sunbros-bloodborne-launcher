"""Qt Quick front end for the Windows Bloodborne launcher."""
import os
from pathlib import Path
import sys

from PySide6.QtCore import QTimer, QUrl
from PySide6.QtGui import QIcon
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuick import QQuickWindow
from PySide6.QtQuickControls2 import QQuickStyle
from PySide6.QtWidgets import QApplication

from bbport_launcher_backend import LauncherBackend
import bbport_launcher_win as launcher_core
import bbport_startup

# How long the "Launching Bloodborne" toast stays up if the game does not report running sooner.
SPLASH_MS = 8000
# A direct launch waits this long first, so Shift or a click on the toast can still open the
# launcher instead (issue #11: the game started too soon to notice the hint).
GRACE_S = 3


def follow_zoom_with_text(window):
    """The sharpest text for the window's zoom (Main.qml scales its stage as one design). At 1 that is
    native text, hinted to the pixel grid: curve text is visibly softer there. Native text blurs when
    scaled, so an enlarged window uses curve text, which stays sharp at any scale."""
    native = [True]

    def set_items(item, value):
        if item.metaObject().indexOfProperty('renderType') >= 0:
            item.setProperty('renderType', value)
        for child in item.childItems():
            set_items(child, value)

    def apply():
        wanted = abs(float(window.property('zoom')) - 1) < 0.001
        if wanted == native[0]:
            return
        native[0] = wanted
        kind = QQuickWindow.TextRenderType
        # New items take the window default; existing ones are set here. 1 and 2 are Qt's values of
        # Text.NativeRendering and Text.CurveRendering, the same for text inputs and edits.
        QQuickWindow.setTextRenderType(kind.NativeTextRendering if wanted else kind.CurveTextRendering)
        set_items(window.contentItem(), 1 if wanted else 2)

    window.zoomChanged.connect(apply)
    apply()


def qt_arguments(argv, environ=os.environ, platform=sys.platform):
    """Grey text with clean pixel edges: ClearType's colour fringes assume an RGB stripe, and read
    as blur on panels without one (OLED). An argument, not QT_QPA_PLATFORM: the game inherits the
    launcher's environment. Qt prefers an argument to QT_QPA_PLATFORM, so it is left out when the
    platform was chosen already (offscreen, for a scripted run)."""
    if platform != 'win32' or environ.get('QT_QPA_PLATFORM') or '-platform' in argv:
        return argv
    return argv + ['-platform', 'windows:fontengine=freetype']


def run_ui(route=None):
    """ROUTE comes from bbport_startup.route(); without one the launcher opens on Home."""
    QQuickStyle.setStyle('Basic')
    QQuickWindow.setTextRenderType(QQuickWindow.TextRenderType.NativeTextRendering)
    app = QApplication(qt_arguments(sys.argv))
    app.setApplicationName('Bloodborne')
    icon_path = (Path(sys.executable).resolve().parent / 'launcher' / 'assets' / 'hunter-icon.ico') if getattr(sys, 'frozen', False) else (Path(__file__).resolve().parent / 'assets' / 'hunter-icon.ico')
    app.setWindowIcon(QIcon(str(icon_path)))
    font_path = (Path(sys.executable).resolve().parent / 'launcher' / 'assets' / 'ui' / 'bloodborne-font.ttf') if getattr(sys, 'frozen', False) else (Path(__file__).resolve().parent / 'assets' / 'ui' / 'bloodborne-font.ttf')
    from PySide6.QtGui import QFontDatabase
    if font_path.exists():
        QFontDatabase.addApplicationFont(str(font_path))
    for face in sorted((font_path.parent.parent / 'fonts').glob('IBMPlexSans-*.ttf')):
        QFontDatabase.addApplicationFont(str(face))
    backend = LauncherBackend(route)
    backend.connect_workers()
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty('launcher', backend)
    qml = Path(__file__).resolve().parent / 'qml'
    if getattr(sys, 'frozen', False):
        import bbport_launcher_win as core
        qml = core.PORT_DIR / 'launcher' / 'qml'

    def load(name):
        loaded = len(engine.rootObjects())
        engine.load(QUrl.fromLocalFile(str(qml / name)))
        if len(engine.rootObjects()) == loaded:
            # Check for warnings/errors on the context
            import sys
            print(f"Failed to load: {qml / name}", file=sys.stderr)
            raise RuntimeError(f'Could not load Qt Quick launcher: {qml / name}')
        return engine.rootObjects()[-1]

    launcher_window = []

    def open_launcher(page=None, step=0):
        if launcher_window:
            return
        if page:
            backend.open_at(page, step)
        backend.start_background_checks()
        window = load('Main.qml')
        follow_zoom_with_text(window)
        launcher_window.append(window)
        backend.closeRequested.connect(window.close)
        app.aboutToQuit.connect(backend.shutdown_coop)
        app.aboutToQuit.connect(backend.shutdown_build_ahead)
        app.setQuitOnLastWindowClosed(True)

    if not route or route['mode'] != 'direct':
        open_launcher()
        return app.exec()

    # Direct launch: no launcher window, only a toast while the game starts. Shift/Ctrl or a
    # click on the toast opens the launcher; so does a game that fails before it is running.
    app.setQuitOnLastWindowClosed(False)
    splash = load('Splash.qml')
    keys = QTimer()
    keys.setInterval(100)

    def close_splash():
        keys.stop()
        countdown.stop()
        splash.close()

    def show_launcher(page='Home'):
        close_splash()
        open_launcher(page)

    def check_keys():
        if bbport_startup.launcher_keys_held():
            show_launcher()

    def finished(code, started):
        close_splash()
        if launcher_window:
            return  # the launcher is open; the user decides when to quit
        if started or code == 0:
            app.quit()
        else:
            open_launcher('Log')

    def start():
        if launcher_window:
            return  # the player chose the launcher during the countdown
        close_timer.start()
        backend.play()
        if not backend.running:  # refused or could not start; the notice says why
            show_launcher()

    keys.timeout.connect(check_keys)
    # The update check waits until the game is running and only remembers what it finds.
    backend.gameStarted.connect(lambda: launcher_core.start_quiet_update_check(backend.app))
    splash.openLauncher.connect(show_launcher)
    backend.gameStarted.connect(close_splash)
    backend.gameFinished.connect(finished)
    keys.start()
    close_timer = QTimer()
    close_timer.setSingleShot(True)
    close_timer.setInterval(SPLASH_MS)
    close_timer.timeout.connect(close_splash)
    remaining = [GRACE_S]
    countdown = QTimer()
    countdown.setInterval(1000)

    def tick():
        remaining[0] -= 1
        splash.setProperty('countdown', remaining[0])
        if remaining[0] <= 0:
            countdown.stop()
            start()

    countdown.timeout.connect(tick)
    splash.setProperty('countdown', GRACE_S)
    if GRACE_S > 0:
        countdown.start()
    else:
        QTimer.singleShot(0, start)
    return app.exec()

if __name__ == "__main__":
    sys.exit(run_ui())
