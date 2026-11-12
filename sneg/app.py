import argparse
import sys
from PySide6.QtCore import Qt, QTimer, QSettings, QSize
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap, QAction, QFont
from PySide6.QtWidgets import (QApplication, QWidget, QLabel, QPushButton, QVBoxLayout,
    QHBoxLayout, QSlider, QComboBox, QFrame, QSystemTrayIcon, QMenu, QScrollArea, QCheckBox)
from .canvas import SnowCanvas
from .platforms import WindowProvider
from .audio import Soundscape

STYLE = '''
QWidget { background: #f6f4ed; color: #213e37; font-family: "Segoe UI", "Helvetica Neue", sans-serif; font-size: 13px; }
QLabel#eyebrow { color: #77857a; font-size: 10px; font-weight: 600; letter-spacing: 2px; }
QLabel#title { font-family: Georgia, serif; font-size: 42px; }
QLabel#muted { color: #748078; font-size: 12px; }
QLabel#heading { font-size: 16px; font-weight: 600; }
QPushButton { border: 1px solid #d9ded2; border-radius: 9px; padding: 10px 16px; background: #fdfcf8; }
QPushButton:hover { background: #e7ece2; }
QPushButton:checked, QPushButton#primary { color: #fffdf7; background: #254d40; border-color: #254d40; }
QPushButton#primary:hover { background: #376651; }
QSlider::groove:horizontal { height: 5px; background: #d9dfd3; border-radius: 2px; }
QSlider::sub-page:horizontal { background: #456b54; border-radius: 2px; }
QSlider::handle:horizontal { background: #254d40; width: 15px; margin: -5px 0; border-radius: 7px; }
QComboBox { padding: 8px 12px; border: 1px solid #d9ded2; border-radius: 8px; background: #fdfcf8; }
QComboBox QAbstractItemView { background: #fdfcf8; selection-background-color: #dce7d9; }
QFrame#line { background: #dfe3d7; max-height: 1px; }
'''

def label(text, name=None):
    widget = QLabel(text)
    if name: widget.setObjectName(name)
    return widget

def icon():
    pix = QPixmap(64,64);pix.fill(Qt.transparent)
    p = QPainter(pix);p.setRenderHint(QPainter.Antialiasing)
    p.setBrush(QColor('#254d40'));p.setPen(Qt.NoPen);p.drawRoundedRect(0,0,64,64,16,16)
    p.setPen(QColor('#fffdf7'));p.setFont(QFont('Sans Serif',35));p.drawText(pix.rect(),Qt.AlignCenter,'❄');p.end()
    return QIcon(pix)

class Panel(QWidget):
    def __init__(self, controller):
        super().__init__()
        self.c = controller
        self.setProperty("snegPanel",True)
        self.setWindowTitle('Снег 0.4.2 — маленькая зима')
        self.setWindowIcon(icon())
        self.setStyleSheet(STYLE)
        self.setMinimumWidth(630)
        outer = QVBoxLayout(self);outer.setContentsMargins(0,0,0,0)
        scroll = QScrollArea();scroll.setWidgetResizable(True);scroll.setFrameShape(QFrame.NoFrame)
        content = QWidget();scroll.setWidget(content);outer.addWidget(scroll)
        root = QVBoxLayout(content);root.setContentsMargins(32,24,32,24);root.setSpacing(14)
        top = QHBoxLayout();top.addWidget(label('❄   СНЕГ / DESKTOP WINTER','eyebrow'));top.addStretch()
        self.badge = label('●  Снег идёт','muted');top.addWidget(self.badge);root.addLayout(top)
        root.addWidget(label('Пусть идёт снег.','title'))
        root.addWidget(label('Немного зимнего волшебства между обычными делами.','muted'))
        self.preview = SnowCanvas(preview=True)
        root.addWidget(self.preview)
        row = QHBoxLayout();row.addWidget(label('Ваша погода','heading'));row.addStretch()
        self.pause_button = QPushButton('Пауза');self.pause_button.clicked.connect(controller.toggle_pause)
        row.addWidget(self.pause_button);root.addLayout(row)
        presets = QHBoxLayout()
        self.preset_buttons = []
        for text,value in [('Тихий вечер',20),('Снегопад',45),('Метель',100)]:
            b=QPushButton(text);b.setCheckable(True);b.clicked.connect(lambda checked=False,v=value:self.intensity.setValue(v))
            presets.addWidget(b);self.preset_buttons.append((b,value))
        root.addLayout(presets)
        self.intensity = self.slider(root,'Сила снегопада',0,120,controller.settings.value('intensity',45,type=int),controller.set_intensity)
        self.wind = self.slider(root,'Ветер   ←  /  →',-100,100,controller.settings.value('wind',0,type=int),controller.set_wind)
        line=QFrame();line.setObjectName('line');line.setFixedHeight(1);root.addWidget(line)
        row=QHBoxLayout();row.addWidget(label('Звуки зимы','heading'));row.addStretch()
        self.sound = QComboBox()
        for title,key in [('Без звука','off'),('Колокольчики','bells'),('У камина','fire'),('Зимний ветер','wind')]: self.sound.addItem(title,key)
        self.sound.currentIndexChanged.connect(lambda _:controller.choose_sound(self.sound.currentData()))
        row.addWidget(self.sound);root.addLayout(row)
        self.volume = self.slider(root,'Громкость',0,100,controller.settings.value('volume',25,type=int),controller.set_volume)
        row=QHBoxLayout()
        for text,mode in [('Лопата','shovel'),('Слепить снежок','ball')]:
            b=QPushButton(text);b.clicked.connect(lambda checked=False,m=mode:controller.interact(m));row.addWidget(b)
        clear=QPushButton('Снегоуборщик');clear.clicked.connect(controller.start_plow);row.addWidget(clear);root.addLayout(row)
        cleanup=QHBoxLayout()
        self.auto_plow=QCheckBox('Автоматическая уборка')
        self.auto_plow.setChecked(controller.settings.value('auto_plow',True,type=bool))
        self.auto_plow.toggled.connect(controller.set_auto_plow)
        cleanup.addWidget(self.auto_plow);cleanup.addStretch()
        self.plow_interval=QComboBox()
        for title,seconds in [('Каждые 30 секунд',30),('Каждую минуту',60),('Каждые 2 минуты',120),('Каждые 5 минут',300),('Каждые 10 минут',600)]:self.plow_interval.addItem(title,seconds)
        self.plow_interval.setCurrentIndex(max(0,self.plow_interval.findData(controller.settings.value('plow_interval',120,type=int))))
        self.plow_interval.currentIndexChanged.connect(lambda _:controller.set_plow_interval(self.plow_interval.currentData()))
        cleanup.addWidget(self.plow_interval);root.addLayout(cleanup)
        self.hint=label('Зажмите любой сугроб или шар и катите мышью — выбор режима не нужен. Лопата перебрасывает снег; снегоуборщик оставляет наледь.','muted')
        self.hint.setWordWrap(True);root.addWidget(self.hint)
        from . import __version__
        updates_row=QHBoxLayout();updates_row.addWidget(label('Версия '+__version__,'muted'));updates_row.addStretch()
        self.update_button=QPushButton('Проверить обновления')
        self.update_button.clicked.connect(lambda:controller.updater.clicked())
        updates_row.addWidget(self.update_button);root.addLayout(updates_row)
        bottom=QHBoxLayout()
        self.status=label('Клики проходят сквозь снег · Работает без интернета','muted')
        self.status.setWordWrap(True);bottom.addWidget(self.status,1)
        self.hide_button=QPushButton('Свернуть в трей');self.hide_button.setObjectName('primary')
        self.hide_button.clicked.connect(controller.hide_panel);bottom.addWidget(self.hide_button);root.addLayout(bottom)
        self.resize(670,min(950,QApplication.primaryScreen().availableGeometry().height()-60))

    def slider(self,root,title,minimum,maximum,value,callback):
        row=QHBoxLayout();row.addWidget(label(title));row.addStretch();number=label(str(value),'muted');row.addWidget(number);root.addLayout(row)
        slider=QSlider(Qt.Horizontal);slider.setRange(minimum,maximum);slider.setValue(value)
        slider.setAccessibleName(title)
        slider.valueChanged.connect(lambda v:number.setText(str(v)));slider.valueChanged.connect(callback)
        root.addWidget(slider);return slider

    def closeEvent(self,event):
        if self.c.tray.isVisible(): self.c.hide_panel();event.ignore()
        else: self.c.app.quit();event.accept()

class Controller:
    def __init__(self, app, preview_only=False):
        self.app=app
        self.settings=QSettings('Sneg','Sneg')
        self.provider=WindowProvider()
        self.preview_only=preview_only
        self.overlays=[]
        self.paused=False
        self.audio=Soundscape()
        self.panel=Panel(self)
        self.tray=QSystemTrayIcon(icon(),self.panel)
        self.tray.setToolTip('Снег — маленькая зима')
        menu=QMenu()
        def action(title,fn):
            a=QAction(title,menu);a.triggered.connect(fn);menu.addAction(a);return a
        action('Открыть настройки',self.show_panel)
        self.pause_action=action('Пауза',self.toggle_pause)
        menu.addSeparator()
        action('Лопата',lambda:self.interact('shovel'))
        action('Вызвать снегоуборщик',self.start_plow)
        action('Слепить снежок',lambda:self.interact('ball'))
        action('Закончить игру',self.end_interaction)
        action('Сбросить весь снег',self.clear)
        menu.addSeparator();action('Выйти',app.quit)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(lambda reason:self.show_panel() if reason in (QSystemTrayIcon.Trigger,QSystemTrayIcon.DoubleClick) else None)
        if QSystemTrayIcon.isSystemTrayAvailable(): self.tray.show()
        else:
            self.panel.hide_button.setText('Выйти')
            self.panel.hide_button.clicked.disconnect()
            self.panel.hide_button.clicked.connect(app.quit)
        self.interaction_timer=QTimer();self.interaction_timer.setSingleShot(True);self.interaction_timer.timeout.connect(self.end_interaction)
        self.poll=QTimer();self.poll.timeout.connect(self.refresh_surfaces);self.poll.start(250)
        app.screenAdded.connect(self.rebuild_screens);app.screenRemoved.connect(self.rebuild_screens)
        for screen in app.screens(): screen.geometryChanged.connect(self.rebuild_screens)
        self.rebuild_screens()
        self.set_intensity(self.panel.intensity.value());self.set_wind(self.panel.wind.value());self.set_volume(self.panel.volume.value())
        sound_index=self.panel.sound.findData(self.settings.value('sound','off'))
        self.panel.sound.setCurrentIndex(max(0,sound_index))
        self.set_auto_plow(self.panel.auto_plow.isChecked())
        self.set_plow_interval(self.panel.plow_interval.currentData())
        from .update_ui import UpdateController
        self.updater=UpdateController(self.panel,app)
        self.panel.show()

    def hide_panel(self):
        self.panel.hide()
        # Keep independent overlay windows alive without rebuilding their worlds.
        for overlay in self.overlays:
            if not overlay.isVisible(): overlay.show()

    def start_plow(self):
        if self.paused: self.toggle_pause()
        for canvas in self.canvases(): canvas.world.start_plow()

    def set_auto_plow(self,enabled):
        for canvas in self.canvases():
            canvas.world.auto_plow=enabled
            if enabled: canvas.world.next_plow=canvas.world.plow_interval
        self.settings.setValue('auto_plow',enabled)

    def set_plow_interval(self,seconds):
        for canvas in self.canvases():
            canvas.world.plow_interval=seconds;canvas.world.next_plow=seconds
        self.settings.setValue('plow_interval',seconds)

    def show_panel(self):
        self.end_interaction();self.panel.show();self.panel.raise_();self.panel.activateWindow()

    def canvases(self): return [self.panel.preview]+self.overlays

    def rebuild_screens(self,*args):
        self.end_interaction()
        old={overlay.screen_ref.name():overlay for overlay in self.overlays}
        self.overlays=[]
        if not self.preview_only:
            for screen in self.app.screens():
                try: screen.geometryChanged.disconnect(self.rebuild_screens)
                except RuntimeError: pass
                screen.geometryChanged.connect(self.rebuild_screens)
                overlay=old.pop(screen.name(),None)
                if overlay is None:
                    overlay=SnowCanvas(screen)
                    overlay.exit_interaction.connect(self.end_interaction)
                    overlay.world.auto_plow=self.panel.auto_plow.isChecked()
                    overlay.world.plow_interval=self.panel.plow_interval.currentData()
                    overlay.world.next_plow=overlay.world.plow_interval
                overlay.screen_ref=screen
                overlay.setGeometry(screen.geometry())
                overlay.running=not self.paused
                overlay.world.intensity=self.panel.intensity.value()
                overlay.world.wind=self.panel.wind.value()
                overlay.show();self.overlays.append(overlay)
        for overlay in old.values():
            overlay.timer.stop();overlay.close();overlay.deleteLater()
        self.refresh_surfaces()

    def refresh_surfaces(self):
        try:
            rows=self.provider.windows() if not self.preview_only else []
            for overlay in self.overlays:
                screen=overlay.screen_ref
                g,a=screen.geometry(),screen.availableGeometry()
                ground=max(1,a.bottom()-g.y()+1)
                overlay.top_clearance=max(0,a.top()-g.top())
                edges=self.provider.edges_for(screen,rows)
                overlay.world.set_surfaces([('ground',0,ground,g.width())]+edges)
                overlay.frames=self.provider.frames_for(screen,rows)
            self.panel.status.setText('Предпросмотр · окна здесь демонстрационные' if self.preview_only else self.provider.status)
        except Exception as error:
            self.panel.status.setText('Окна недоступны: '+str(error)[:100])
            for overlay in self.overlays:
                overlay.world.set_surfaces([('ground',0,overlay.height(),overlay.width())])
                overlay.frames=[]

    def set_intensity(self,value):
        for canvas in self.canvases(): canvas.world.intensity=value
        self.settings.setValue('intensity',value)
        for b,v in self.panel.preset_buttons: b.setChecked(v==value)

    def set_wind(self,value):
        for canvas in self.canvases(): canvas.world.wind=value
        self.settings.setValue('wind',value)

    def set_volume(self,value):
        self.audio.effect.setVolume(value/100);self.settings.setValue('volume',value)

    def choose_sound(self,kind):
        self.audio.select(kind);self.settings.setValue('sound',kind)

    def toggle_pause(self):
        self.paused=not self.paused
        for canvas in self.canvases(): canvas.running=not self.paused
        self.audio.pause(self.paused)
        text='Продолжить' if self.paused else 'Пауза'
        self.panel.pause_button.setText(text);self.pause_action.setText(text)
        self.panel.badge.setText('Ⅱ  Зима на паузе' if self.paused else '●  Снег идёт')

    def interact(self,mode):
        if self.paused: self.toggle_pause()
        for canvas in self.canvases(): canvas.set_mode(mode)
        if self.overlays:
            self.hide_panel()
            # Safety exit even if a desktop environment fails to deliver Escape.
            self.interaction_timer.start(60000)

    def end_interaction(self):
        self.interaction_timer.stop()
        for overlay in self.overlays: overlay.set_mode('normal')

    def clear(self):
        for canvas in self.canvases():
            canvas.held=None;canvas.gathered=0;canvas.world.clear()


def main():
    parser=argparse.ArgumentParser(description='Снег — маленькая зима на рабочем столе')
    parser.add_argument('--preview',action='store_true',help='Only open settings and interactive preview')
    parser.add_argument('--screenshot',help='Save panel PNG and exit (for smoke tests)')
    args=parser.parse_args()
    app=QApplication(sys.argv[:1]);app.setApplicationName('Sneg');app.setOrganizationName('Sneg')
    app.setQuitOnLastWindowClosed(False)
    controller=Controller(app,args.preview)
    if args.screenshot:
        controller.panel.resize(670,960)
        def capture():
            controller.panel.grab().save(args.screenshot);app.quit()
        QTimer.singleShot(800,capture)
    return app.exec()
