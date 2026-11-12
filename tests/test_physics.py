from sneg.physics import World, Particle
from sneg.platforms import Rect, exposed_edges


def test_flake_lands_on_first_surface_not_floor():
    w=World(800,600,seed=1);w.intensity=0
    w.set_surfaces([('floor',0,590,800),('window',100,300,400)])
    w.flakes=[Particle(200,297,0,80,2)]
    w.update(.05)
    assert not w.flakes
    assert max(w.surfaces['window'].depth)>0
    assert max(w.surfaces['floor'].depth)==0


def test_snow_follows_window_and_disappears_on_close():
    w=World(800,600);w.set_surfaces([('window',100,300,400)])
    w.surfaces['window'].deposit(200,12)
    depths=w.surfaces['window'].depth.copy()
    w.set_surfaces([('window',220,180,400)])
    assert w.surfaces['window'].depth==depths
    assert w.surfaces['window'].x==220
    w.set_surfaces([])
    assert not w.surfaces


def test_brush_only_affects_nearby_snow():
    w=World(800,600);w.set_surfaces([('floor',0,590,800)])
    s=w.surfaces['floor'];s.deposit(200,20)
    before=sum(s.depth)
    assert w.brush(200,200)==0
    assert w.brush(200,580)>0
    assert sum(s.depth)<before


def test_ball_lands_without_disappearing_and_clear_removes_it():
    w=World(800,600);w.intensity=0;w.set_surfaces([('floor',0,590,800)])
    w.throw(300,550,0,100,15)
    for _ in range(20): w.update(.05)
    assert len(w.balls)==1
    assert abs(w.balls[0].y-575)<.1
    assert w.balls[0].radius==15
    w.clear()
    assert max(w.surfaces['floor'].depth)==0
    assert not w.sparks


def test_hidden_window_edges_are_removed():
    edges=exposed_edges([Rect('front',200,100,200,300),Rect('back',100,200,500,250)])
    back=[(x,y,width) for key,x,y,width in edges if key.startswith('back:')]
    assert back==[(100,200,100),(400,200,200)]
    assert exposed_edges([Rect('front',0,0,800,600),Rect('back',100,200,300,100)])==[('front:0',0,0,800)]


def test_long_running_simulation_stays_bounded():
    w=World(1920,1080,seed=5);w.intensity=120
    w.set_surfaces([('floor',0,1080,1920)])
    for _ in range(2400): w.update(.05)
    assert len(w.flakes)<=1800
    assert all(d>=0 for d in w.surfaces['floor'].depth)


def mass(world):
    return (sum(sum(s.depth)*6 for s in world.surfaces.values())
            +sum(p.mass for p in world.clumps)
            +sum(3.141592653589793*b.radius*b.radius for b in world.balls)
            +(world.plow.load if world.plow else 0)+world.removed_mass+world.melted_mass)


def quiet_world():
    w=World(800,600,seed=8);w.intensity=0;w.auto_plow=False
    w.set_surfaces([('ground',0,590,800)])
    return w


def test_ground_has_no_old_height_cap_and_slopes_relax_without_loss():
    w=quiet_world();s=w.surfaces['ground']
    s.depth[60]=200
    before=mass(w)
    for _ in range(100):w.update(.05)
    assert abs(mass(w)-before)<1e-6
    assert max(s.depth)<200
    s.depth=[90.]*len(s.depth)
    w.update(.05)
    assert max(s.depth)>89


def test_runoff_falls_from_window_to_ground_without_destroying_snow():
    w=quiet_world();w.set_surfaces([('ground',0,590,800),('window',200,250,200)])
    s=w.surfaces['window'];s.depth=[35.]*len(s.depth)
    before=mass(w)
    for _ in range(300):w.update(.05)
    assert sum(w.surfaces['ground'].depth)>0
    assert abs(mass(w)-before)<1e-5
    assert s.depth[0]<s.depth[len(s.depth)//2]


def test_shovel_relocates_snow_instead_of_deleting_it():
    w=quiet_world();s=w.surfaces['ground'];s.deposit(250,35)
    before=mass(w)
    assert w.shovel(250,575,1)>0
    assert w.clumps
    for _ in range(160):w.update(.05)
    assert abs(mass(w)-before)<1e-5
    assert sum(s.depth[50:])>0


def test_balls_persist_stack_and_can_be_picked_up():
    w=quiet_world();w.throw(300,500,0,0,20)
    for _ in range(80):w.update(.05)
    w.throw(300,450,0,0,15)
    for _ in range(400):w.update(.05)
    assert len(w.balls)==2
    assert sorted(round(b.y) for b in w.balls)==[535,570]
    before=mass(w);collected=w.pickup(300,535)
    assert abs(mass(w)+collected-before)<1e-5
    assert len(w.balls)==1


def test_releasing_ball_inside_deep_drift_keeps_it_above_surface():
    w=quiet_world();s=w.surfaces['ground'];s.depth=[100.]*len(s.depth)
    w.throw(300,580,0,0,20)
    assert w.balls[0].y==470
    for _ in range(10):w.update(.05)
    assert w.balls[0].y<471


def test_automatic_plow_leaves_ice_and_hauls_mass_away():
    w=quiet_world();s=w.surfaces['ground'];s.depth=[30.]*len(s.depth)
    w.auto_plow=True;w.plow_interval=2;w.next_plow=.1
    before=mass(w)
    for _ in range(245):w.update(.05)
    assert w.plow is None
    assert w.removed_mass>0
    assert max(s.depth)<=1.51
    assert min(s.ice)>=1.49
    assert abs(mass(w)-before)<1e-4
    for _ in range(45):w.update(.05)
    assert w.plow is not None
    assert w.plow.direction==-1


def test_disabled_auto_plow_does_not_run_and_manual_start_works():
    w=quiet_world();w.next_plow=0
    for _ in range(30):w.update(.05)
    assert w.plow is None
    w.start_plow();assert w.plow is not None


def test_snowball_follows_its_supporting_window():
    w=quiet_world();w.set_surfaces([('ground',0,590,800),('win',100,200,400)])
    w.throw(200,100,0,0,20)
    for _ in range(50):w.update(.05)
    assert w.balls[0].support=='win'
    w.set_surfaces([('ground',0,590,800),('win',180,230,400)])
    assert w.balls[0].x==280
    assert w.balls[0].y==210


def test_mac_rejects_system_invisible_and_bar_windows():
    from sneg.platforms import mac_window_rects
    base={'kCGWindowOwnerPID':123,'kCGWindowOwnerName':'Safari','kCGWindowLayer':0,
          'kCGWindowAlpha':1,'kCGWindowIsOnscreen':True,'kCGWindowNumber':9,
          'kCGWindowBounds':{'X':100,'Y':150,'Width':800,'Height':600}}
    assert len(mac_window_rects([base],999))==1
    for changes in ({'kCGWindowOwnerName':'Dock'}, {'kCGWindowIsOnscreen':False},
                    {'kCGWindowOwnerPID':999}, {'kCGWindowAlpha':0},
                    {'kCGWindowBounds':{'X':0,'Y':0,'Width':2000,'Height':45}}):
        assert not mac_window_rects([{**base,**changes}],999)


def test_natural_hit_test_only_accepts_accumulated_snow():
    w=quiet_world();s=w.surfaces['ground'];s.deposit(300,25)
    assert w.hit_snow(300,580)
    assert not w.hit_snow(300,200)
    assert not w.hit_snow(600,580)
    w.throw(500,200,0,0,20)
    assert w.hit_snow(500,200)
