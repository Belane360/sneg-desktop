import math
import time
from PySide6.QtCore import Qt, QTimer, QPointF, QRectF, QRect, Signal
from PySide6.QtGui import QColor, QPainter, QPainterPath, QLinearGradient, QFont, QPen, QRegion, QCursor
from PySide6.QtWidgets import QWidget, QApplication
from .physics import World, STEP

class SnowCanvas(QWidget):
    exit_interaction = Signal()

    def __init__(self, screen=None, preview=False, parent=None):
        super().__init__(parent)
        self.preview = preview
        self.screen_ref = screen
        self.mode = 'normal'
        self.passthrough = True
        self.top_clearance = 0
        self.frames = []
        self.pointer = None
        self.running = True
        self.gathered = 0
        self.held = None
        self.last_pointer = None
        self.throw_velocity = (0,0)
        self.last_time = time.monotonic()
        self.world = World(600,340,seed=7 if preview else None)
        if preview:
            self.setMinimumSize(530,290)
            self.setMouseTracking(True)
        else:
            self.setWindowFlags(Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.WindowTransparentForInput | Qt.WindowDoesNotAcceptFocus | Qt.NoDropShadowWindowHint)
            self.setAttribute(Qt.WA_TranslucentBackground)
            self.setAttribute(Qt.WA_ShowWithoutActivating, True)
            # Qt.Tool windows on macOS normally disappear when the app deactivates.
            self.setAttribute(Qt.WA_MacAlwaysShowToolWindow, True)
            self.setAttribute(Qt.WA_QuitOnClose, False)
            self.setMouseTracking(True)
            self.setGeometry(screen.geometry())
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(33)

    def resizeEvent(self, event):
        self.world.width,self.world.height = max(1,self.width()),max(1,self.height())
        if self.preview:
            w,h = self.width(),self.height()
            self.world.set_surfaces([('ground',0,h-12,w),('window',w*.13,h*.36,w*.55),('small',w*.62,h*.61,w*.28)])
            self.frames = [(w*.13,h*.36,w*.55,h*.48,[(w*.62,h*.61,w*.28,h*.28)]),(w*.62,h*.61,w*.28,h*.28,[])]
            for s in self.world.surfaces.values():
                s.depth = [8+6*math.sin(i*.19)**2 for i in range(len(s.depth))]
            if not self.world.flakes:
                from .physics import Particle
                self.world.flakes = [Particle(self.world.rng.uniform(0,w),self.world.rng.uniform(0,h),0,40,self.world.rng.uniform(1,3)) for _ in range(65)]
        super().resizeEvent(event)

    def set_mode(self, mode):
        self.release_held()
        self.mode = 'shovel' if mode == 'brush' else mode
        self.passthrough = mode == 'normal'
        self.held = None
        self.last_pointer = None
        if not self.preview:
            self.setWindowFlag(Qt.WindowTransparentForInput, mode == 'normal')
            self.setWindowFlag(Qt.WindowDoesNotAcceptFocus, mode == 'normal')
            self.show()
            if mode != 'normal':
                self.activateWindow(); self.setFocus()
        self.setCursor(Qt.CrossCursor if mode == 'ball' else Qt.OpenHandCursor if mode in ('brush','shovel') else Qt.ArrowCursor)

    def tick(self):
        now = time.monotonic()
        if self.running: self.world.update(now-self.last_time)
        if not self.preview and self.mode == 'normal' and self.held is None:
            cursor=self.mapFromGlobal(QCursor.pos())
            x,y=cursor.x(),cursor.y()
            hit=self.running and y>=self.top_clearance and self.world.hit_snow(x,y)
            for widget in QApplication.topLevelWidgets():
                if widget.property('snegPanel') and widget.isVisible() and widget.frameGeometry().contains(QCursor.pos()):hit=False
            transparent=not hit
            if transparent != self.passthrough:
                self.passthrough=transparent
                self.setWindowFlag(Qt.WindowTransparentForInput,transparent)
                self.show()
        self.last_time = now
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w,h = self.width(),self.height()
        if not self.preview:
            p.setClipRect(QRect(0,self.top_clearance,w,max(0,h-self.top_clearance)))
        if self.preview:
            gradient = QLinearGradient(0,0,w,h)
            gradient.setColorAt(0,QColor('#172e35')); gradient.setColorAt(1,QColor('#314b49'))
            p.setBrush(gradient); p.setPen(Qt.NoPen); p.drawRoundedRect(self.rect(),18,18)
            p.setPen(QColor('#a4bdb7')); p.setFont(QFont('Sans Serif',9))
            p.drawText(22,28,'ВАШ МАЛЕНЬКИЙ ЗИМНИЙ МИР')
            for x,y,ww,hh in [(w*.13,h*.36,w*.55,h*.48),(w*.62,h*.61,w*.28,h*.28)]:
                p.setPen(QColor('#627875'));p.setBrush(QColor('#e7e8df'));p.drawRoundedRect(QRectF(x,y,ww,hh),8,8)
                p.setPen(Qt.NoPen)
                for i,c in enumerate(['#c58270','#d7b96e','#94ae91']):
                    p.setBrush(QColor(c));p.drawEllipse(QPointF(x+14+i*13,y+15),3,3)
                p.setBrush(QColor('#c6cdc4'))
                for i in range(3): p.drawRoundedRect(QRectF(x+16,y+37+i*15,ww*(.6-i*.1),4),2,2)
            p.setPen(QColor('#b6ccc4'));p.setFont(QFont('Sans Serif',9))
            p.drawText(22,h-32,'Проведите по сугробу — здесь уже можно играть')
        self.paint_frost(p)
        for s in self.world.surfaces.values():
            # A quadratic spline rounds the granular height field and the end caps.
            path = QPainterPath(QPointF(s.x,s.y+1))
            points = [QPointF(s.x+min(i*STEP,s.width),s.y-d) for i,d in enumerate(s.depth)]
            if not s.ground:
                path.quadTo(QPointF(s.x,s.y), points[0])
            else:
                path.lineTo(points[0])
            for a,b in zip(points,points[1:]):
                path.quadTo(a,QPointF((a.x()+b.x())/2,(a.y()+b.y())/2))
            path.quadTo(points[-1],QPointF(s.x+s.width,s.y+1))
            path.closeSubpath()
            gradient = QLinearGradient(0,s.y-25,0,s.y+1)
            gradient.setColorAt(0,QColor('#ffffff')); gradient.setColorAt(1,QColor('#c3dde8'))
            p.setPen(Qt.NoPen);p.setBrush(gradient);p.drawPath(path)
            p.setPen(QPen(QColor(159,213,233,180),1.5))
            for i,d in enumerate(s.ice[:-1]):
                if d > .1:
                    x=s.x+i*STEP
                    p.drawLine(QPointF(x,s.y-.5),QPointF(min(s.x+s.width,x+STEP),s.y-.5))
        for particle in self.world.flakes + self.world.clumps + self.world.balls:
            p.setPen(Qt.NoPen)
            if particle.ball:
                gradient=QLinearGradient(particle.x,particle.y-particle.radius,particle.x,particle.y+particle.radius)
                gradient.setColorAt(0,QColor('#ffffff'));gradient.setColorAt(1,QColor('#c3dfec'))
                p.setBrush(gradient)
            else: p.setBrush(QColor(246,252,255,200))
            if particle.mass:
                # An irregular soft slab, visibly different from round snowflakes.
                radius=max(3,math.sqrt(particle.mass/math.pi))
                path=QPainterPath()
                for index in range(10):
                    angle=index*math.tau/10
                    wobble=1+.13*math.sin(index*2.7+particle.mass)
                    point=QPointF(particle.x+math.cos(angle)*radius*wobble,
                                 particle.y+math.sin(angle)*radius*.7*wobble)
                    if index==0:path.moveTo(point)
                    else:path.lineTo(point)
                path.closeSubpath()
                p.setBrush(QColor('#eef8fc'));p.drawPath(path)
            else:
                p.drawEllipse(QPointF(particle.x,particle.y),particle.radius,particle.radius)
        self.paint_plow(p)
        if self.pointer and self.mode == 'shovel':
            x,y=self.pointer
            p.setPen(QPen(QColor('#b78b5c'),4));p.drawLine(QPointF(x,y),QPointF(x+17,y-32))
            p.setPen(QPen(QColor('#71838c'),2));p.setBrush(QColor('#c9d9dd'))
            p.drawRoundedRect(QRectF(x-13,y-5,26,17),4,4)
        if self.held:
            x,y,r = self.held
            p.setBrush(QColor('#ffffff'));p.drawEllipse(QPointF(x,y),r,r)
        if not self.preview and self.mode != 'normal':
            p.setBrush(QColor('#183c37'));p.setPen(Qt.NoPen)
            p.drawRoundedRect(QRectF(w/2-260,24,520,54),14,14)
            p.setPen(QColor('white'));p.setFont(QFont('Sans Serif',11))
            text = 'Зажмите мышь и сгребайте снег лопатой' if self.mode == 'shovel' else 'Катайте шар по снегу; отпустите, чтобы поставить' 
            p.drawText(QRectF(w/2-250,24,500,54),Qt.AlignCenter,text+'   ·   Esc — готово')

    def paint_frost(self,p):
        # Never trace full window rectangles: invisible utility windows can be
        # reported by the OS. Attach small ice crystals to actual snow caps only.
        alpha=int(25+90*self.world.frost)
        p.save()
        p.setPen(QPen(QColor(225,247,255,alpha),1))
        for surface in self.world.surfaces.values():
            if surface.ground: continue
            for offset in range(12,int(surface.width)-10,31):
                x=surface.x+offset
                if surface.height(x)<2: continue
                y=surface.y
                p.drawLine(QPointF(x,y),QPointF(x+2,y+5))
                p.drawLine(QPointF(x+2,y+5),QPointF(x+4,y+2))
        p.restore()

    def paint_plow(self,p):
        truck=self.world.plow
        if truck is None:return
        ground=next((s for s in self.world.surfaces.values() if s.ground),None)
        if ground is None:return
        p.save();p.translate(truck.x,ground.y-5);p.scale(truck.direction,1)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor('#df9b36'));p.drawRoundedRect(QRectF(-25,-28,48,20),4,4)
        p.setBrush(QColor('#f0ba58'));p.drawRoundedRect(QRectF(-14,-49,26,25),4,4)
        p.setBrush(QColor('#264d5b'));p.drawRoundedRect(QRectF(-10,-45,18,16),2,2)
        p.setBrush(QColor('#24323a'))
        for x in (-16,17):
            p.drawEllipse(QPointF(x,-5),10,10)
            p.setBrush(QColor('#b3c5c9'));p.drawEllipse(QPointF(x,-5),4,4);p.setBrush(QColor('#24323a'))
        p.setPen(QPen(QColor('#a9c8d4'),5));p.drawLine(QPointF(31,-24),QPointF(36,2))
        p.setPen(Qt.NoPen);p.setBrush(QColor('#fff1b3'));p.drawEllipse(QPointF(21,-22),3,3)
        p.setBrush(QColor('#e9f7fa'));p.drawRoundedRect(QRectF(-26,-30,15,min(8,truck.load/600)),3,3)
        p.setBrush(QColor('#ffce69'));p.drawEllipse(QPointF(0,-53),4,3)
        p.restore()

    def release_held(self):
        if self.held:
            x,y,r=self.held
            self.world.throw(x,y,0,0,r)
            self.held=None

    def mousePressEvent(self,event):
        if event.button() != Qt.LeftButton:return
        x,y=event.position().x(),event.position().y()
        self.pointer=(x,y)
        self.last_pointer=(x,y,time.monotonic());self.throw_velocity=(0,0)
        if self.mode in ('ball','normal'):
            self.gathered=self.world.pickup(x,y)+self.world.brush(x,y,25)
            if self.gathered>0:self.held=(x,y,math.sqrt(self.gathered/math.pi))
        elif self.mode == 'shovel':self.world.shovel(x,y)

    def mouseMoveEvent(self,event):
        x,y=event.position().x(),event.position().y()
        self.pointer=(x,y)
        now=time.monotonic()
        if event.buttons() & Qt.LeftButton:
            if self.mode == 'shovel':
                direction=-1 if self.last_pointer and x<self.last_pointer[0] else 1
                self.world.shovel(x,y,direction)
            if self.mode in ('ball','normal'):
                # Roll against the snow at the bottom of the held ball.
                radius=self.held[2] if self.held else 0
                for surface in self.world.surfaces.values():
                    if surface.x<=x<=surface.x+surface.width:
                        top=surface.y-surface.height(x)
                        if top-radius<=y<=surface.y+radius+12:y=top-radius
                self.gathered+=self.world.brush(x,y+radius,25)
                if self.gathered>0:
                    radius=math.sqrt(self.gathered/math.pi)
                    self.held=(max(radius,min(self.width()-radius,x)),min(y,self.height()-radius),radius)
            if self.last_pointer:
                px,py,t=self.last_pointer;dt=max(.016,now-t)
                self.throw_velocity=((x-px)/dt,(y-py)/dt)
        self.last_pointer=(x,y,now)

    def mouseReleaseEvent(self,event):
        if event.button()==Qt.LeftButton and self.held:
            x,y,r=self.held;vx,vy=self.throw_velocity
            if self.last_pointer and time.monotonic()-self.last_pointer[2]>.15:vx,vy=0,0
            self.world.throw(x,y,vx,vy,r);self.held=None

    def keyPressEvent(self,event):
        if event.key()==Qt.Key_Escape:
            self.release_held();self.exit_interaction.emit()
