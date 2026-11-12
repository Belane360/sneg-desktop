"""Snow mass, granular slopes, persistent snowballs and an automatic snowplow."""
from dataclasses import dataclass, field
import math
import random

STEP = 6
MELT_RATE = .00002  # About 0.12% per minute; cleanup is performed by tools.

@dataclass
class Surface:
    key: str
    x: float
    y: float
    width: float
    depth: list[float] = field(default_factory=list)
    ice: list[float] = field(default_factory=list)

    def __post_init__(self): self.resize(self.width)

    @property
    def ground(self): return self.key in ('ground', 'floor')

    def resize(self, width):
        self.width = max(1, width)
        count = math.ceil(self.width / STEP) + 1
        self.depth = (self.depth + [0.] * count)[:count]
        self.ice = (self.ice + [0.] * count)[:count]

    def height(self, x):
        pos = max(0.,min(len(self.depth)-1.,(x-self.x)/STEP))
        i = int(pos); j = min(i+1,len(self.depth)-1)
        return self.depth[i]*(1-pos+i)+self.depth[j]*(pos-i)

    def deposit(self, x, amount=1.):
        center = round((x-self.x)/STEP)
        for i in range(max(0, center-3), min(len(self.depth), center+4)):
            self.depth[i] += amount * math.exp(-((i-center)/1.7)**2)

    def add_mass(self, x, mass):
        center = max(0,min(len(self.depth)-1,round((x-self.x)/STEP)))
        weights = [(i,math.exp(-((i-center)/1.7)**2)) for i in range(max(0,center-3),min(len(self.depth),center+4))]
        total = sum(v for _,v in weights)
        for i,v in weights: self.depth[i] += mass*v/total/STEP

    def scoop(self, x, radius):
        removed = 0.
        for i, d in enumerate(self.depth):
            distance = abs(self.x + min(i*STEP,self.width) - x)
            if distance < radius:
                take = max(0,d-self.ice[i]) * (1-distance/radius)
                self.depth[i] -= take
                removed += take*STEP
        return removed

    def relax(self, dt):
        # Conservative pair transfers create an angle of repose, without a height cap.
        for _ in range(3):
            for i in range(len(self.depth)-1):
                delta = self.depth[i]-self.depth[i+1]
                excess = max(0,abs(delta)-STEP*.55)
                transfer = excess*min(.24,dt*7)
                if delta>0:
                    transfer=min(transfer,max(0,self.depth[i]-self.ice[i]))
                    self.depth[i]-=transfer; self.depth[i+1]+=transfer
                else:
                    transfer=min(transfer,max(0,self.depth[i+1]-self.ice[i+1]))
                    self.depth[i]+=transfer; self.depth[i+1]-=transfer
        runoff=[]
        if not self.ground:
            for index,x,direction in [(0,self.x-3,-1),(-1,self.x+self.width+3,1)]:
                amount=max(0,self.depth[index]-1.5)*min(1,dt*6)
                self.depth[index]-=amount
                if amount: runoff.append((x,amount*STEP,direction))
        return runoff

@dataclass
class Particle:
    x: float
    y: float
    vx: float
    vy: float
    radius: float
    life: float = 1000
    ball: bool = False
    mass: float = 0.
    support: str = ''

@dataclass
class Plow:
    x: float
    direction: int
    load: float = 0.

class World:
    def __init__(self, width, height, seed=None):
        self.width,self.height=width,height
        self.rng=random.Random(seed)
        self.surfaces={}
        self.flakes=[];self.balls=[];self.sparks=[];self.clumps=[]
        self.wind=0;self.intensity=45;self.spawn_credit=0;self.time=0
        self.auto_plow=True
        self.plow_interval=120.
        self.next_plow=120.
        self.plow=None
        self.plow_direction=1
        self.removed_mass=0.
        self.melted_mass=0.
        self.frost=0.

    def set_surfaces(self, rows):
        fresh={}
        for key,x,y,width in rows:
            if width<=0: continue
            s=self.surfaces.get(key) or Surface(key,x,y,width)
            dx,dy=x-s.x,y-s.y
            for b in self.balls:
                if b.support==key: b.x+=dx;b.y+=dy
            s.x,s.y=x,y;s.resize(width);fresh[key]=s
        self.surfaces=fresh

    def clear(self):
        for s in self.surfaces.values():
            s.depth=[0.]*len(s.depth);s.ice=[0.]*len(s.depth)
        self.balls.clear();self.sparks.clear();self.clumps.clear()
        self.plow=None

    def brush(self,x,y,radius=35):
        """Collect snow mass for a held ball; caller owns the removed mass."""
        amount=0.
        for s in self.surfaces.values():
            top=s.y-s.height(x)
            if s.x-radius<=x<=s.x+s.width+radius and top-radius<=y<=s.y+12:
                amount+=s.scoop(x,radius)
        return amount

    def hit_snow(self,x,y):
        if any(math.hypot(b.x-x,b.y-y)<=b.radius+3 for b in self.balls):return True
        for s in self.surfaces.values():
            if s.x<=x<=s.x+s.width and s.height(x)>2:
                if s.y-s.height(x)-3<=y<=s.y+2:return True
        return False

    def pickup(self,x,y):
        for b in reversed(self.balls):
            if math.hypot(b.x-x,b.y-y)<=b.radius+8:
                self.balls.remove(b)
                return math.pi*b.radius*b.radius
        return 0.

    def shovel(self,x,y,direction=1):
        mass=self.brush(x,y,30)
        if mass>0:
            self.clumps.append(Particle(x,y-20,180*direction,-155,3,mass=mass))
        return mass

    def throw(self,x,y,vx,vy,radius):
        for surface in self.surfaces.values():
            if surface.x<=x<=surface.x+surface.width:
                top=surface.y-surface.height(x)
                if top-radius<y<=surface.y+radius:
                    y=top-radius
        self.balls.append(Particle(x,y,max(-900,min(900,vx)),max(-900,min(900,vy)),radius,ball=True))

    def collision(self,p,old_y):
        candidates=[]
        for s in self.surfaces.values():
            if s.x<=p.x<=s.x+s.width:
                top=s.y-s.height(p.x)
                if old_y-p.radius<=top<=p.y+p.radius:
                    candidates.append((top,s))
        return min(candidates,key=lambda item:item[0])[1] if candidates else None

    def start_plow(self):
        if self.plow is None:
            self.plow=Plow(-65 if self.plow_direction>0 else self.width+65,self.plow_direction)
            self.plow_direction*=-1

    def update_plow(self,dt):
        if self.auto_plow:
            self.next_plow-=dt
            if self.next_plow<=0 and self.plow is None: self.start_plow()
        if self.plow is None: return
        p=self.plow;p.x+=p.direction*85*dt
        for s in self.surfaces.values():
            if not s.ground: continue
            blade=p.x+p.direction*31
            for i,d in enumerate(s.depth):
                if abs(s.x+min(i*STEP,s.width)-blade)<=18:
                    remaining=min(d,1.5)
                    p.load+=(d-remaining)*STEP
                    s.depth[i]=remaining;s.ice[i]=remaining
            for b in self.balls[:]:
                if abs(b.x-blade)<=b.radius+18 and b.y+b.radius>=s.y-s.height(b.x)-5:
                    p.load+=math.pi*b.radius*b.radius;self.balls.remove(b)
        if p.x>self.width+80 or p.x<-80:
            self.removed_mass+=p.load
            self.plow=None;self.next_plow=self.plow_interval

    def _move_balls(self,dt):
        # Resolve bottom balls first so piles can support upper balls.
        self.balls.sort(key=lambda b:b.y,reverse=True)
        settled=[]
        for b in self.balls:
            old_y=b.y
            b.vy+=440*dt;b.x+=b.vx*dt;b.y+=b.vy*dt
            b.x=max(b.radius,min(self.width-b.radius,b.x))
            if b.x in (b.radius,self.width-b.radius): b.vx*=-.35
            s=self.collision(b,old_y) if b.vy>=0 else None
            b.support=''
            if s:
                b.y=s.y-s.height(b.x)-b.radius
                b.vy=0
                slope=(s.height(b.x-STEP)-s.height(b.x+STEP))/(2*STEP)
                b.vx=(b.vx+slope*150*dt)*math.exp(-3*dt)
                b.support=s.key
            for other in settled:
                dx=b.x-other.x;limit=b.radius+other.radius
                if abs(dx)<limit and b.vy>=0:
                    top=other.y-math.sqrt(max(0,limit*limit-dx*dx))
                    if old_y<=other.y and b.y>=top:
                        b.y=top;b.vy=0;b.vx*=math.exp(-5*dt)
                        b.support=other.support
                        # Off-centre balls roll down, rather than forming vertical spikes.
                        b.vx+=dx/limit*65*dt
            if b.y+b.radius>self.height:
                b.y=self.height-b.radius;b.vy=0;b.vx*=math.exp(-3*dt)
            settled.append(b)

    def update(self,dt):
        dt=min(.05,max(0,dt));self.time+=dt
        self.frost=min(1,self.frost+dt/90)
        for s in self.surfaces.values():
            for i,d in enumerate(s.depth):
                melt=max(0,d-s.ice[i])*MELT_RATE*dt
                s.depth[i]-=melt;self.melted_mass+=melt*STEP
            for x,mass,direction in s.relax(dt):
                # Accumulate nearby runoff into existing chunks instead of dropping mass.
                match=next((p for p in self.clumps[-12:] if abs(p.x-x)<6 and abs(p.y-s.y)<10 and p.vx*direction>0),None)
                if match: match.mass+=mass
                else: self.clumps.append(Particle(x,s.y+3,25*direction,25,2,mass=mass))
        self.spawn_credit+=dt*self.intensity*self.width/1000
        count=min(int(self.spawn_credit),max(0,1800-len(self.flakes)))
        self.spawn_credit-=int(self.spawn_credit)
        for _ in range(count):
            self.flakes.append(Particle(self.rng.uniform(0,self.width),-6,self.rng.uniform(-10,10),self.rng.uniform(28,75),self.rng.uniform(1.2,3.5)))
        remaining=[]
        for p in self.flakes:
            old_y=p.y
            p.x=(p.x+(p.vx+self.wind+math.sin(self.time+p.y/70)*9)*dt)%self.width
            p.y+=p.vy*dt
            s=self.collision(p,old_y)
            if s: s.deposit(p.x,p.radius*.27)
            elif p.y<self.height+10: remaining.append(p)
        self.flakes=remaining
        remaining=[]
        for p in self.clumps:
            old_y=p.y;p.vy+=300*dt;p.x+=p.vx*dt;p.y+=p.vy*dt
            p.x=max(1,min(self.width-1,p.x))
            s=self.collision(p,old_y) if p.vy>0 else None
            if s: s.add_mass(p.x,p.mass)
            elif p.y>=self.height:
                ground=next((s for s in self.surfaces.values() if s.ground),None)
                if ground: ground.add_mass(p.x,p.mass)
                else: remaining.append(p)
            else: remaining.append(p)
        self.clumps=remaining
        self._move_balls(dt)
        self.update_plow(dt)
