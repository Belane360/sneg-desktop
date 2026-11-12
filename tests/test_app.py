import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtCore import Qt, QPoint, QSettings
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from sneg.app import Controller


def test_panel_controls_and_mouse_snowball(tmp_path):
    app=QApplication.instance() or QApplication([])
    QSettings.setDefaultFormat(QSettings.IniFormat)
    QSettings.setPath(QSettings.NativeFormat,QSettings.UserScope,str(tmp_path))
    c=Controller(app,preview_only=True)
    app.processEvents()
    canvas=c.panel.preview
    c.panel.intensity.setValue(100)
    assert canvas.world.intensity==100
    c.toggle_pause();assert not canvas.running
    c.toggle_pause();assert canvas.running
    c.interact('ball')
    s=canvas.world.surfaces['window']
    s.deposit(s.x+60,30)
    point=QPoint(int(s.x+60),int(s.y-4))
    QTest.mousePress(canvas,Qt.LeftButton,pos=point)
    assert canvas.held is not None
    QTest.mouseRelease(canvas,Qt.LeftButton,pos=point)
    assert len(canvas.world.balls)==1
    c.clear();assert not canvas.world.balls
    assert all(not any(s.depth) for s in canvas.world.surfaces.values())
    c.poll.stop();c.interaction_timer.stop();canvas.timer.stop();c.tray.hide();c.panel.hide()


def test_overlay_normal_mode_passes_clicks_and_escape_exits(tmp_path):
    app=QApplication.instance() or QApplication([])
    c=Controller(app)
    app.processEvents()
    assert c.overlays
    overlay=c.overlays[0]
    assert overlay.windowFlags() & Qt.WindowTransparentForInput
    c.interact('brush')
    assert not overlay.windowFlags() & Qt.WindowTransparentForInput
    QTest.keyClick(overlay,Qt.Key_Escape)
    assert overlay.windowFlags() & Qt.WindowTransparentForInput
    c.poll.stop();c.interaction_timer.stop();c.panel.preview.timer.stop();c.tray.hide();c.panel.hide()
    for item in c.overlays: item.timer.stop();item.close()


def test_hiding_panel_preserves_world_and_overlay_and_geometry_refresh(tmp_path):
    app=QApplication.instance() or QApplication([])
    c=Controller(app);app.processEvents()
    overlay=c.overlays[0];world=overlay.world
    world.surfaces['ground'].deposit(100,30)
    before=sum(world.surfaces['ground'].depth)
    c.hide_panel()
    assert not c.panel.isVisible()
    assert overlay.isVisible() and overlay.timer.isActive() and overlay.running
    assert overlay.testAttribute(Qt.WA_MacAlwaysShowToolWindow)
    assert sum(world.surfaces['ground'].depth)==before
    c.rebuild_screens()
    assert c.overlays[0] is overlay and c.overlays[0].world is world
    assert sum(world.surfaces['ground'].depth)==before
    old_time=world.time;QTest.qWait(100)
    assert world.time>old_time
    c.poll.stop();c.interaction_timer.stop();c.panel.preview.timer.stop();c.tray.hide();c.panel.hide()
    for item in c.overlays:item.timer.stop();item.close()


def test_escape_returns_held_snow_and_plow_controls(tmp_path):
    app=QApplication.instance() or QApplication([])
    c=Controller(app,preview_only=True);app.processEvents()
    canvas=c.panel.preview;canvas.held=(200,100,20)
    QTest.keyClick(canvas,Qt.Key_Escape)
    assert canvas.held is None and len(canvas.world.balls)==1
    c.panel.auto_plow.setChecked(False)
    assert not canvas.world.auto_plow
    c.panel.plow_interval.setCurrentIndex(0)
    assert canvas.world.plow_interval==30
    c.start_plow();assert canvas.world.plow is not None
    c.poll.stop();c.interaction_timer.stop();canvas.timer.stop();c.tray.hide();c.panel.hide()


def test_natural_snowball_requires_no_mode_selection(tmp_path):
    app=QApplication.instance() or QApplication([])
    c=Controller(app,preview_only=True);app.processEvents()
    canvas=c.panel.preview
    assert canvas.mode=='normal'
    s=canvas.world.surfaces['window'];s.deposit(s.x+50,30)
    point=QPoint(int(s.x+50),int(s.y-3))
    QTest.mousePress(canvas,Qt.LeftButton,pos=point)
    assert canvas.held is not None
    QTest.mouseRelease(canvas,Qt.LeftButton,pos=point)
    assert canvas.held is None and canvas.world.balls
    c.poll.stop();c.interaction_timer.stop();canvas.timer.stop();c.tray.hide();c.panel.hide()


def test_overlay_has_no_system_shadow_and_leaves_top_bar_clear(tmp_path):
    from sneg.physics import Particle
    app=QApplication.instance() or QApplication([])
    c=Controller(app);app.processEvents()
    overlay=c.overlays[0];overlay.timer.stop()
    assert overlay.windowFlags() & Qt.NoDropShadowWindowHint
    overlay.top_clearance=30
    overlay.world.flakes=[Particle(50,12,0,0,5)]
    overlay.frames=[]
    image=overlay.grab().toImage()
    assert image.pixelColor(50,12).alpha()==0
    c.poll.stop();c.interaction_timer.stop();c.panel.preview.timer.stop();c.tray.hide();c.panel.hide()
    for item in c.overlays:item.timer.stop();item.close()


def test_frost_does_not_outline_invisible_window_rectangles():
    from PySide6.QtGui import QImage,QPainter
    from sneg.canvas import SnowCanvas
    app=QApplication.instance() or QApplication([])
    canvas=SnowCanvas(preview=True);canvas.timer.stop()
    canvas.frames=[(10,10,300,200,[])]
    canvas.world.set_surfaces([])
    image=QImage(400,300,QImage.Format_ARGB32);image.fill(Qt.transparent)
    painter=QPainter(image);canvas.paint_frost(painter);painter.end()
    assert all(image.pixelColor(x,y).alpha()==0 for x,y in [(10,10),(10,100),(300,10),(100,210)])
    canvas.world.set_surfaces([('window',10,10,300)])
    canvas.world.surfaces['window'].depth=[12.]*len(canvas.world.surfaces['window'].depth)
    painter=QPainter(image);canvas.paint_frost(painter);painter.end()
    assert image.pixelColor(22,10).alpha()>0
    assert image.pixelColor(10,100).alpha()==0
    assert image.pixelColor(100,210).alpha()==0
    canvas.close()


def test_window_snow_cap_tapers_to_pointed_tips():
    from sneg.canvas import snow_path
    from sneg.physics import Surface
    from PySide6.QtCore import QPointF
    s=Surface('window',100,200,300);s.depth=[20.]*len(s.depth)
    path=snow_path(s)
    assert path.boundingRect().left()>=100
    assert path.boundingRect().right()<=400
    assert path.contains(QPointF(250,185))
    assert not path.contains(QPointF(101,195))
    assert not path.contains(QPointF(399,195))
    assert path.contains(QPointF(120,195))
    assert path.contains(QPointF(380,195))
    assert path.boundingRect().bottom()==200
