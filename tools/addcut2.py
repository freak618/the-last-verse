import json,base64,io,re,sys
import numpy as np
from PIL import Image, ImageFilter
cid,src,after,entry,oldcount,newcount=sys.argv[1:7]
s=open('/home/claude/lastverse.html',encoding='utf-8').read()
i=s.index('const ASSET=');j=s.index('\n',i);line=s[i:j]
A=json.loads(line[len('const ASSET='):].rstrip(';'));cm=A['cutsMeta'];orig_meta=json.loads(json.dumps(cm))
assert ('"cutsMeta":'+json.dumps(cm,separators=(',',':'))) in line and cid not in cm['chars']
cuts=Image.open(io.BytesIO(base64.b64decode(A['cuts'].split(',',1)[1]))).convert('RGBA')

F=cm['frames'];HH=276;HIP=138
yF=max(f[1] for f in F if f[3]==HH);yU=yF+HH+2;yL=yU+146+2
x=max(f[0]+f[2] for f in F if f[1]==yF)+4
NEED_BAND=False
def normal_map(im):
    a=np.asarray(im).astype(np.float32)/255;al=a[...,3]
    lum=(a[...,0]*.3+a[...,1]*.59+a[...,2]*.11)*al
    h_al=np.asarray(Image.fromarray((al*255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(3))).astype(np.float32)/255
    h_lu=np.asarray(Image.fromarray((lum*255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.2))).astype(np.float32)/255
    h=h_al*.65+h_lu*.35;gx=np.zeros_like(h);gy=np.zeros_like(h)
    gx[:,1:-1]=(h[:,2:]-h[:,:-2]);gy[1:-1,:]=(h[2:,:]-h[:-2,:])
    nx=-gx*3;ny=gy*3;nz=np.ones_like(h);L=np.sqrt(nx*nx+ny*ny+nz*nz)
    out=np.stack([nx/L*.5+.5,ny/L*.5+.5,nz/L*.5+.5],-1)*255
    out=np.where((al>0.05)[...,None],out,np.array([128,128,255],np.float32))
    return Image.fromarray(out.clip(0,255).astype(np.uint8),'RGB')
im=Image.open(src).convert('RGBA');al=np.asarray(im)[...,3]
tp=(al<20).mean();print('transparent %',round(tp*100,1))
assert tp>0.3,'background is not transparent'
ys,xs=np.where(al>20);im=im.crop((xs.min(),ys.min(),xs.max()+1,ys.max()+1))
w=round(im.width*HH/im.height);im=im.resize((w,HH),Image.LANCZOS)
a=np.asarray(im)[...,3].astype(np.float32)/255;cols=np.arange(w)
feet=a[int(HH*.92):];fx=np.where(feet.max(0)>.3)[0];ax=round(float(((fx.min()+fx.max())/2+(a*cols).sum()/a.sum())/2),1)
# The tile crops this square out of the full slice. It must not be wider than
# the cutout: the atlas packs fighters side by side, so a box that overhangs
# reads the next fighter's pixels into this one's tile.
top=a[:int(HH*.2)];hx=float((top*cols).sum()/max(top.sum(),1));hs=float(min(150,w));hxl=round(max(0,min(w-hs,hx-hs/2)),1)
if x+w>cuts.width:
    yF=cuts.height+4;yU=yF+HH+2;yL=yU+146+2;x=0;NH=yL+138+2
    c2=Image.new('RGBA',(cuts.width,NH),(0,0,0,0));c2.paste(cuts,(0,0));cuts=c2
    print('started a new sheet band at y',yF)
# The band must fit whole. PIL clips a paste past the edge in silence, and the
# slices that fall off are upper and lower -- the two the game draws. The tile
# uses full, so the select screen looks right while the fighter does not appear.
need=yL+138+2
if need>cuts.height:
    c2=Image.new('RGBA',(cuts.width,need),(0,0,0,0));c2.paste(cuts,(0,0));cuts=c2
    print('grew the atlas %d -> %d so the band fits'%(cuts.height,need))
nm=normal_map(im);base=len(F)
for yy,sl in ((yF,(0,HH)),(yU,(0,146)),(yL,(HIP,HH))):
    cuts.paste(im.crop((0,sl[0],w,sl[1])),(x,yy));F.append([x,yy,w,sl[1]-sl[0]])
cm['chars'][cid]={'full':base,'upper':base+1,'lower':base+2,'hip':HIP,'ax':ax,'h':HH,'w':w,'scale':0.7692307692307692,'head':[hxl,0,hs,hs]}
print(cid,'w',w,'ax',ax,'head',hxl,'sheet room left',cuts.width-x-w)
b=io.BytesIO();cuts.save(b,'WEBP',quality=94,method=6);cd='data:image/webp;base64,'+base64.b64encode(b.getvalue()).decode()
nd=A['cutsN']  # lighting maps are no longer used
nl=line.replace('"cuts":"'+A['cuts']+'"','"cuts":"'+cd+'"',1)
nl=nl.replace('"cutsMeta":'+json.dumps(orig_meta,separators=(',',':')),'"cutsMeta":'+json.dumps(cm,separators=(',',':')),1)
assert f'"{cid}":' in nl and cd in nl and nd in nl
s=s[:i]+nl+s[j:]
m=re.search(r" \{id:'%s',(?:cameo:true,)?cut:'%s'"%(after,after),s)
assert m,'no roster entry to insert after: '+after
e=s.index('\n',m.start())
s=s[:e]+"\n "+entry+s[e:]
pass
open('/home/claude/lastverse.html','w',encoding='utf-8').write(s);print('size',len(s.encode()))
