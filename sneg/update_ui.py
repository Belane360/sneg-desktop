from PySide6.QtCore import QObject,QThread,Signal,QTimer,QProcess
from PySide6.QtWidgets import QMessageBox
from .updates import latest_release,prepare_update,activate,bootstrap_entry
import sys

class Job(QThread):
    succeeded=Signal(object)
    failed=Signal(str)
    def __init__(self,task,parent=None):super().__init__(parent);self.task=task
    def run(self):
        try:self.succeeded.emit(self.task())
        except Exception as error:self.failed.emit(str(error))

class UpdateController(QObject):
    def __init__(self,panel,app):
        super().__init__(panel);self.panel=panel;self.app=app;self.job=None;self.release=None
        self.timer=QTimer(self);self.timer.timeout.connect(self.check);self.timer.start(6*60*60*1000)
        import os
        if os.environ.get('QT_QPA_PLATFORM')!='offscreen':QTimer.singleShot(5000,self.check)
        app.aboutToQuit.connect(self.finish)

    def finish(self):
        if self.job and self.job.isRunning():self.job.wait()

    def start(self,task,done,manual):
        if self.job and self.job.isRunning():return
        self.panel.update_button.setEnabled(False)
        self.job=Job(task,self)
        self.job.succeeded.connect(done)
        self.job.failed.connect(lambda text:self.failed(text,manual))
        self.job.finished.connect(lambda:self.panel.update_button.setEnabled(True))
        self.job.start()

    def check(self,manual=False):
        self.start(latest_release,lambda release:self.checked(release,manual),manual)

    def checked(self,release,manual):
        self.release=release
        if release:
            self.panel.update_button.setText('Обновить до '+release['version'])
            if manual:self.offer()
        elif manual:QMessageBox.information(self.panel,'Обновления','У вас последняя доступная версия.')

    def clicked(self):
        if self.release:self.offer()
        else:self.check(True)

    def offer(self):
        release=self.release
        if not release:return
        if getattr(sys,'frozen',False):
            QMessageBox.information(self.panel,'Обновления','Для этой сборки скачайте новый установщик на github.com/Belane360/sneg-desktop/releases. Обновление внутри приложения доступно в версии Снег.app с Python-запускателем.')
            return
        answer=QMessageBox.question(self.panel,'Обновление Снега','Установить версию '+release['version']+' и перезапустить приложение? Настройки сохранятся.')
        if answer!=QMessageBox.Yes:return
        self.panel.update_button.setText('Загрузка обновления…')
        self.start(lambda:prepare_update(release),self.install,True)

    def install(self,version):
        from .updates import update_root
        path=update_root()/'active.json'
        before=path.read_bytes() if path.exists() else None
        try:
            activate(version)
            ok,_=QProcess.startDetached(sys.executable,[str(bootstrap_entry())])
            if not ok:raise RuntimeError('Не удалось перезапустить приложение')
        except Exception as error:
            if before is None:path.unlink(missing_ok=True)
            else:path.write_bytes(before)
            self.failed(str(error),True);return
        self.app.quit()

    def failed(self,text,manual):
        self.panel.update_button.setText('Проверить обновления')
        if manual:QMessageBox.warning(self.panel,'Обновление не установлено',text+'\nТекущая версия продолжает работать.')
