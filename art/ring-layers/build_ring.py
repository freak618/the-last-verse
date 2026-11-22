"""Cut the supplied ring painting into fixed-geometry layers.
Every layer is the same size as the painting (1672x941) and shares its coordinates,
so drawing them in order with one uniform scale rebuilds the original exactly."""
import numpy as np,json,cv2,os
from PIL import Image
SRC='src.png';OUT='layers';os.makedirs(OUT,exist_ok=True)
im=np.asarray(Image.open(SRC).convert('RGB'));H,W=im.shape[:2]
f=im.astype(np.float32);R,G,B=f[...,0],f[...,1],f[...,2]
FEET_Y=688          # the row the fighters stand on (half way across the mat)
DEPTH=(FEET_Y-608)/(772-608)   # 0 = back edge of the mat, 1 = front edge
yy,xx=np.mgrid[0:H,0:W].astype(np.float32)

def capsule(x0,y0,x1,y1,r=None):
    """a rounded box (a turnbuckle pad seen side on), soft 1px edge"""
    r=r if r is not None else (y1-y0)/2
    cx=np.clip(xx,x0+r,x1-r);cy=np.clip(yy,y0+r,y1-r)
    d=np.hypot(xx-cx,yy-cy)-r
    return np.clip(.5-d,0,1)
def box(x0,y0,x1,y1):
    a=np.clip(np.minimum.reduce([xx-x0+.5,x1-xx+.5,yy-y0+.5,y1-yy+.5]),0,1);return a
redness=np.clip((R-np.maximum(G,B)*1.5-30)/40,0,1)
def rope(p0,p1,half=None):
    """a rope from p0 to p1: its centre is found column by column from the painted red, then
    the band is cut at the rope's own measured thickness (plus its dark outline)"""
    (x0,y0),(x1,y1)=p0,p1
    if x1<x0:(x0,y0),(x1,y1)=(x1,y1),(x0,y0)
    m=np.zeros((H,W),np.float32);cs=[];hs=[]
    for x in range(int(np.floor(x0)),int(np.ceil(x1))+1):
        yn=y0+(y1-y0)*(x-x0)/max(1,(x1-x0));lo,hi=int(yn-14),int(yn+15)
        col=redness[lo:hi,x]
        if col.sum()<2:cs.append(yn);hs.append(None);continue
        ys=np.arange(lo,hi);c=float((ys*col).sum()/col.sum());on=ys[col>.5]
        cs.append(c);hs.append((on.max()-on.min()+1)/2 if len(on) else None)
    cs=np.array(cs);xs=np.arange(int(np.floor(x0)),int(np.ceil(x1))+1)
    # smooth the centre line: a straight rope stays straight (fit a line, it is a taut rope)
    k=np.polyfit(xs,cs,1);cl=np.polyval(k,xs)
    hv=[h for h in hs if h];hw=(half or float(np.median(hv)))+2.0   # +2: the dark outline around the red
    for i,x in enumerate(xs):
        d=np.abs(yy[:,x]-cl[i]);m[:,x]=np.clip(hw+.5-d,0,1)
    return m,dict(fit=[float(k[0]),float(k[1])],half=round(hw,2),x=[int(xs[0]),int(xs[-1])])

L={};info={}
# --- ropes: back ropes (between the back turnbuckles) and side ropes (back turnbuckle -> front turnbuckle)
ROPES={'top':dict(back=((360,413),(1315,413)),left=((110,428),(305,413)),right=((1375,413),(1565,430))),
       'middle':dict(back=((360,493),(1315,493)),left=((112,532),(305,493)),right=((1375,492),(1565,535))),
       'bottom':dict(back=((360,567),(1315,567)),left=((105,632),(305,565)),right=((1375,567),(1565,635)))}
for nm,segs in ROPES.items():
    for side,(a,b) in segs.items():
        m,inf=rope(a,b);L[f'rope_{nm}_{side}']=m;info[f'rope_{nm}_{side}']=inf
# split each side rope where it crosses the fighters' depth: the far part is behind them, the near part in front
SPLIT={}
for nm,segs in ROPES.items():
    (lx0,_),(lx1,_)=segs['left'][1],segs['left'][0]          # back end x=305, front end x=110
    sl=lx0+(lx1-lx0)*DEPTH;(rx0,_),(rx1,_)=segs['right'][0],segs['right'][1]
    sr=rx0+(rx1-rx0)*DEPTH;SPLIT[nm]=(sl,sr)
    lm=L.pop(f'rope_{nm}_left');rm=L.pop(f'rope_{nm}_right')
    L[f'rope_{nm}_left_back']=lm*np.clip(xx-sl+.5,0,1);L[f'rope_{nm}_left_front']=lm*np.clip(sl-xx+.5,0,1)
    L[f'rope_{nm}_right_back']=rm*np.clip(sr-xx+.5,0,1);L[f'rope_{nm}_right_front']=rm*np.clip(xx-sr+.5,0,1)
# --- turnbuckle pads (with the hook into the post)
PADS={'front_left':[(47,408,113,447),(45,516,114,556),(42,619,106,661)],
      'front_right':[(1566,410,1622,447),(1563,517,1622,557),(1561,619,1622,660)],
      'back_left':[(285,394,362,434),(285,474,362,514),(285,548,362,592)],
      'back_right':[(1313,394,1390,434),(1313,474,1390,514),(1313,548,1390,592)]}
for k,lst in PADS.items():
    m=np.zeros((H,W),np.float32)
    for (x0,y0,x1,y1) in lst:m=np.maximum(m,capsule(x0,y0,x1,y1,r=(y1-y0)*.42))
    L[f'turnbuckles_{k}']=m
# --- the four corner posts
POSTS={'front_left':(0,388,50,770),'front_right':(1621,388,1666,770),'back_left':(237,376,290,608),'back_right':(1388,376,1444,610)}
for k,b in POSTS.items():L[f'post_{k}']=box(*b)
# --- the mat (canvas and platform): from the back edge to the front lip
mat=np.zeros((H,W),np.uint8);cv2.fillPoly(mat,[np.array([[255,604],[1425,604],[1640,770],[30,770]],np.int32)],1)
L['mat']=cv2.GaussianBlur(mat.astype(np.float32),(3,3),0)
# --- the apron (front skirt with the logo) and the mat's front lip: everything below the lip
L['apron']=np.clip(yy-766+.5,0,1)
info['split_x']=SPLIT;info['feet_y']=FEET_Y;info['depth']=DEPTH
# --- what goes in front of the fighters
FRONT=['post_front_left','post_front_right','turnbuckles_front_left','turnbuckles_front_right','apron']+[k for k in L if k.endswith('_front') and k.startswith('rope_')]
front=np.zeros((H,W),np.float32)
for k in FRONT:front=np.maximum(front,L[k])
ring=np.zeros((H,W),np.float32)
for k,v in L.items():ring=np.maximum(ring,v)
# background: the painting with the ring taken out and the hole filled from its surroundings
hole=(ring>.02).astype(np.uint8)*255;hole=cv2.dilate(hole,np.ones((3,3),np.uint8))
bg=cv2.inpaint(cv2.cvtColor(im,cv2.COLOR_RGB2BGR),hole,9,cv2.INPAINT_TELEA);bg=cv2.cvtColor(bg,cv2.COLOR_BGR2RGB)
def save(name,alpha,src=im,method=4):
    a=(np.clip(alpha,0,1)*255+.5).astype(np.uint8);rgb=src.copy();rgb[a==0]=0;rgba=np.dstack([rgb,a])
    Image.fromarray(rgba,'RGBA').save(f'{OUT}/{name}.webp','WEBP',lossless=True,quality=100,method=method)
Image.fromarray(bg).save(f'{OUT}/background.webp','WEBP',lossless=True,quality=100,method=4)
for k,v in L.items():save(k,v)
save('front',front)
json.dump({'size':[W,H],'front':FRONT,'layers':['background','mat']+[k for k in L if k not in('mat',)],'info':info},open(f'{OUT}/layers.json','w'),indent=1)
np.save('/tmp/front_alpha.npy',front);np.save('/tmp/ring_alpha.npy',ring)
print('split',SPLIT);print({k:v for k,v in info.items() if k.startswith('rope_')})
