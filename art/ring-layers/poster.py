"""Paint a weathered 'SUPPORT THE UNDERGROUND' poster onto the fence over the MUSIC LIVES graffiti."""
import numpy as np,cv2
from PIL import Image,ImageDraw,ImageFont,ImageFilter
rng=np.random.default_rng(11)
S=4                                   # work at 4x, then scale down into the painting
PW,PH=146*S,138*S                     # poster size in painting px * S
FONT='/usr/share/fonts/opentype/inter/InterDisplay-Black.otf'
# ---- paper: aged off-white, blotchy, darker toward the edges
yy,xx=np.mgrid[0:PH,0:PW].astype(np.float32)
def blob(sig,amp):
    n=rng.normal(0,1,(PH//8+2,PW//8+2)).astype(np.float32);n=cv2.resize(n,(PW,PH),interpolation=cv2.INTER_CUBIC);n=cv2.GaussianBlur(n,(0,0),sig);return n/np.abs(n).max()*amp
paper=np.dstack([np.full((PH,PW),v,np.float32) for v in (226,214,188)])
paper+=blob(10,18)[...,None]+blob(3,7)[...,None]
edge=np.minimum.reduce([xx,yy,PW-1-xx,PH-1-yy]);paper*=(.78+.22*np.clip(edge/(28*S/4*3),0,1))[...,None]
# water stain rings and grime
for _ in range(3):
    cx,cy,r=rng.uniform(.1,.9)*PW,rng.uniform(.3,.95)*PH,rng.uniform(.08,.2)*PW
    d=np.hypot(xx-cx,yy-cy);ring=np.exp(-((d-r)/(2.2*S))**2)*.16+np.clip(1-d/r,0,1)*.05
    paper*=(1-ring)[...,None]
paper*=(1-np.clip(blob(2,1),0,1)*.22)[...,None]
paper*=(1-np.clip(blob(6,1),0,1)*.18)[...,None]
# a fold crease across the middle and one down: a light ridge beside a dark line
for (a,b,c) in [(0.0,1.0,-PH*.52),(1.0,0.04,-PW*.5)]:
    d=(a*xx+b*yy+c)/np.hypot(a,b);paper*=(1-.20*np.exp(-(d/(1.2*S))**2)+.07*np.exp(-((d-2.5*S)/(2*S))**2))[...,None]
img=Image.fromarray(np.clip(paper,0,255).astype(np.uint8),'RGB')
# ---- print: heavy black condensed type, red middle word, rough ink
d=ImageDraw.Draw(img)
def put(text,y,h,col,squeeze=.78,pad=12*S):
    f=ImageFont.truetype(FONT,int(h*1.32));bb=f.getbbox(text);tw,th=bb[2]-bb[0],bb[3]-bb[1]
    t=Image.new('L',(tw+8,th+8),0);ImageDraw.Draw(t).text((4-bb[0],4-bb[1]),text,font=f,fill=255)
    tw2=min(int(t.width*squeeze),PW-2*pad);t=t.resize((tw2,h),Image.LANCZOS)
    ink=Image.new('RGB',t.size,col);img.paste(ink,((PW-tw2)//2,y),t);return y+h
# a black frame line, then the words
d.rectangle([6*S,6*S,PW-6*S,PH-6*S],outline=(22,18,18),width=int(2.2*S))
y=put('SUPPORT',int(14*S),int(34*S),(20,16,16))
y=put('— THE —',y+int(5*S),int(17*S),(170,18,24),squeeze=.95)
y=put('UNDERGROUND',y+int(6*S),int(30*S),(20,16,16),squeeze=.62)
d.text((PW//2,PH-int(15*S)),'NO SPONSORS · NO REFS · NO RULES',font=ImageFont.truetype(FONT,int(6.4*S)),fill=(60,40,38),anchor='mm')
# wear the ink: speckle holes where the print rubbed off, scuffs along the fold
a=np.asarray(img).astype(np.float32);base=paper
wear=(np.clip(blob(1.2,1),0,1)>.55)|(rng.random((PH,PW))<.018)
wear=cv2.dilate(wear.astype(np.uint8),np.ones((3,3),np.uint8)).astype(bool)
a[wear]=a[wear]*.35+base[wear]*.65
# ---- shape: torn edges, a torn-off bottom-right corner, everything a little uneven
al=np.ones((PH,PW),np.float32)
tear=np.abs(blob(.8,1))*6*S+np.abs(blob(4,1))*4*S
al[edge<tear]=0
al[(xx+yy*1.15)>(PW+PH*1.15-30*S)+np.abs(blob(.7,1))*5*S]=0        # missing corner
al=cv2.GaussianBlur(al,(0,0),.6*S)
# ---- tape strips over the two top corners
tape=np.zeros((PH,PW),np.float32)
for cx,ang in [(PW*.12,-28),(PW*.88,28)]:
    rect=np.zeros((PH,PW),np.uint8);c=((cx,10*S),(34*S,11*S),ang);pts=cv2.boxPoints(c).astype(np.int32);cv2.fillPoly(rect,[pts],1);tape=np.maximum(tape,rect)
tape=cv2.GaussianBlur(tape,(0,0),.5*S)
a=a*(1-tape[...,None]*.35)+np.array([200,196,170],np.float32)*tape[...,None]*.35
al=np.maximum(al,tape*.9)
# ---- the painting's ink outline around the paper, like everything else in the scene
o=cv2.dilate((al>.5).astype(np.uint8),np.ones((5,5),np.uint8))-(al>.5).astype(np.uint8)
a[o>0]*=.25;al=np.maximum(al,o.astype(np.float32)*.85)
poster=np.dstack([np.clip(a,0,255),al*255]).astype(np.uint8)
P=Image.fromarray(poster,'RGBA').rotate(-2.2,resample=Image.BICUBIC,expand=True)
P=P.resize((P.width//S,P.height//S),Image.LANCZOS)
P.save('/tmp/poster_flat.png');print(P.size)
# ---- place it on the fence and light it like the fence around it
src=np.asarray(Image.open('src_orig.png').convert('RGB')).astype(np.float32)
X0,Y0=1148,266
pa=np.asarray(P).astype(np.float32);h,w=pa.shape[:2];alpha=pa[...,3:]/255
region=src[Y0:Y0+h,X0:X0+w]
# light falling on this patch of fence: the scene is dim and purple-red, brighter toward the top (the rig lights) and the right (the speaker's red rim)
gy=np.linspace(1,0,h)[:,None];gx=np.linspace(0,1,w)[None,:]
light=np.dstack([.47+.14*gy+.06*gx,.33+.07*gy+0*gx,.42+.09*gy+.02*gx]).astype(np.float32)
lit=pa[...,:3]*light
# a soft drop shadow on the fence below-right of the paper
sh=cv2.GaussianBlur(alpha[...,0],(0,0),2.2);sh=np.roll(np.roll(sh,3,0),3,1)[...,None]
out=region*(1-.55*sh)
ring=np.load('/tmp/ring_alpha.npy')[Y0:Y0+h,X0:X0+w][...,None]
alpha=alpha*(1-np.clip(ring*1.5,0,1));sh=sh*(1-np.clip(ring*1.5,0,1))
out=region*(1-.55*sh)
out=out*(1-alpha)+lit*alpha
res=src.copy();res[Y0:Y0+h,X0:X0+w]=out
Image.fromarray(np.clip(res,0,255).astype(np.uint8)).save('src_poster.png')
c=Image.fromarray(np.clip(res,0,255).astype(np.uint8)).crop((1100,230,1340,430));c.resize((c.width*3,c.height*3),Image.LANCZOS).save('/tmp/poster_view.png')
