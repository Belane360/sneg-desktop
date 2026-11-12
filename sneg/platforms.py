"""Only window geometry is collected; no titles, screenshots or window content."""
from dataclasses import dataclass
import os
import sys

@dataclass
class Rect:
    key: str
    x: float
    y: float
    w: float
    h: float



SYSTEM_OWNERS = {'Window Server', 'Dock', 'WindowManager', 'Control Center',
                 'SystemUIServer', 'Notification Center', 'NotificationCenter',
                 'Spotlight', 'Wallpaper'}

def mac_window_rects(rows, own_pid):
    result=[]
    for row in rows:
        if (row.get('kCGWindowOwnerPID') == own_pid
            or row.get('kCGWindowOwnerName') in SYSTEM_OWNERS
            or row.get('kCGWindowLayer',0) != 0
            or row.get('kCGWindowAlpha',1) < .95
            or not row.get('kCGWindowIsOnscreen',False)):
            continue
        b=row.get('kCGWindowBounds',{})
        if b.get('Width',0)>=100 and b.get('Height',0)>=100:
            result.append(Rect(str(row['kCGWindowNumber']),b['X'],b['Y'],b['Width'],b['Height']))
    return result

def exposed_edges(rects, inset=0):
    """Front-to-back rectangles; remove edges hidden by nearer windows."""
    occluders = []
    edges = []
    for r in rects:
        spans = [(r.x+inset, r.x+r.w-inset)]
        for front in occluders:
            if front.y <= r.y < front.y+front.h:
                next_spans = []
                for a,b in spans:
                    if front.x > a:
                        next_spans.append((a,min(b,front.x)))
                    if front.x+front.w < b:
                        next_spans.append((max(a,front.x+front.w),b))
                spans = [(a,b) for a,b in next_spans if b>a]
        # Local offset gives stable identifiers while a window is moved.
        for a,b in spans:
            if b-a >= 12:
                edges.append((f'{r.key}:{round(a-r.x)}', a, r.y, b-a))
        occluders.append(r)
    return edges

class WindowProvider:
    def __init__(self):
        self.status = ''
        self.monitors = {}
        if sys.platform == 'win32':
            self._init_windows()

    def _init_windows(self):
        import ctypes as c
        from ctypes import wintypes as w
        self.c, self.w = c,w
        self.user = c.WinDLL('user32', use_last_error=True)
        self.dwm = c.WinDLL('dwmapi')
        self.callback = c.WINFUNCTYPE(w.BOOL,w.HWND,w.LPARAM)
        self.user.EnumWindows.argtypes = [self.callback,w.LPARAM]
        self.user.GetWindowRect.argtypes = [w.HWND,c.POINTER(w.RECT)]
        self.user.IsWindowVisible.argtypes = [w.HWND]
        self.user.IsIconic.argtypes = [w.HWND]
        self.user.GetWindowThreadProcessId.argtypes = [w.HWND,c.POINTER(w.DWORD)]
        self.dwm.DwmGetWindowAttribute.argtypes = [w.HWND,w.DWORD,c.c_void_p,w.DWORD]

    def windows(self):
        if sys.platform == 'darwin':
            from .macos import window_info
            rows = window_info()
            result = mac_window_rects(rows, os.getpid())
            self.status = 'Границы окон macOS подключены'
            return result
        if sys.platform == 'win32':
            c,w = self.c,self.w
            result = []
            @self.callback
            def visit(hwnd, _):
                if not self.user.IsWindowVisible(hwnd) or self.user.IsIconic(hwnd):
                    return True
                pid = w.DWORD()
                self.user.GetWindowThreadProcessId(hwnd,c.byref(pid))
                if pid.value == os.getpid():
                    return True
                cloaked = w.DWORD()
                self.dwm.DwmGetWindowAttribute(hwnd,14,c.byref(cloaked),c.sizeof(cloaked))
                if cloaked.value:
                    return True
                r = w.RECT()
                if self.dwm.DwmGetWindowAttribute(hwnd,9,c.byref(r),c.sizeof(r)) != 0:
                    self.user.GetWindowRect(hwnd,c.byref(r))
                if r.right-r.left >= 80 and r.bottom-r.top >= 40:
                    result.append(Rect(str(hwnd),r.left,r.top,r.right-r.left,r.bottom-r.top))
                return True
            self.user.EnumWindows(visit,0)
            self.status = 'Границы окон Windows подключены'
            return result
        self.status = 'Linux: предпросмотр и снег внизу экрана; окна — на Mac / Windows'
        return []

    def screen_bounds(self, screen):
        """Windows geometry uses physical pixels; Qt uses per-screen logical ones."""
        g = screen.geometry()
        if sys.platform != 'win32':
            return g.x(),g.y(),g.width(),g.height()
        c,w = self.c,self.w
        class MonitorInfo(c.Structure):
            _fields_ = [('cbSize',w.DWORD),('rcMonitor',w.RECT),('rcWork',w.RECT),('dwFlags',w.DWORD),('szDevice',w.WCHAR*32)]
        callback_type = c.WINFUNCTYPE(w.BOOL,w.HMONITOR,w.HDC,c.POINTER(w.RECT),w.LPARAM)
        self.user.GetMonitorInfoW.argtypes = [w.HMONITOR,c.POINTER(MonitorInfo)]
        self.user.EnumDisplayMonitors.argtypes = [w.HDC,c.POINTER(w.RECT),callback_type,w.LPARAM]
        found = []
        @callback_type
        def visit(hmon, hdc, rect, data):
            info = MonitorInfo(); info.cbSize = c.sizeof(info)
            if self.user.GetMonitorInfoW(hmon,c.byref(info)) and info.szDevice == screen.name():
                r = info.rcMonitor
                found.append((r.left,r.top,r.right-r.left,r.bottom-r.top))
            return True
        self.user.EnumDisplayMonitors(None,None,visit,0)
        if not found:
            raise RuntimeError('Не удалось сопоставить монитор Windows')
        return found[0]

    def edges_for(self, screen, rows):
        x,y,w,h = self.screen_bounds(screen)
        g = screen.geometry()
        sx,sy = g.width()/w,g.height()/h
        edges = []
        for key,a,b,length in exposed_edges(rows,inset=12):
            left,right = max(x,a),min(x+w,a+length)
            if max(y+4,screen.availableGeometry().top()+18) <= b < y+h and right > left:
                edges.append((key,(left-x)*sx,(b-y)*sy,(right-left)*sx))
        return edges

    def frames_for(self, screen, rows):
        """Local full frame geometry with nearer windows for painter clipping."""
        x,y,w,h=self.screen_bounds(screen)
        g=screen.geometry();sx,sy=g.width()/w,g.height()/h
        result=[];front=[]
        for r in rows:
            rect=((r.x-x)*sx,(r.y-y)*sy,r.w*sx,r.h*sy)
            a,b,c,d=rect
            if a+c>0 and a<g.width() and b+d>0 and b<g.height():
                result.append((*rect,list(front)))
            front.append(rect)
        return result
