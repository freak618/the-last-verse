# Re-lay uneven AI sheets onto a clean 4-column grid for cut2.
# Reads the RGBA sheets prep.py writes and carries their alpha through, so no
# colour has to be "safe" for the character's effects (see tools/README.md).
import os, numpy as np, cv2, sys
from PIL import Image
ROWS={'A':4,'B':4,'C':3}
DROP={}   # row index -> frame indices to drop if a row has extras
ALL={}
for k,nr in ROWS.items():
    src=np.asarray(Image.open(f'raw{k}.png').convert('RGBA'));H,W=src.shape[:2]
    im=src[...,:3].copy();AL=src[...,3]
    fg=(AL>128).astype(np.uint8)
    rs=fg.sum(1)
    for i in range(1,nr):
        b=int(i*H/nr);lo,hi=b-int(H*.08),b+int(H*.08);y=lo+int(np.argmin(rs[lo:hi]));fg[max(0,y-1):y+2]=0
    n,cc,st,cen=cv2.connectedComponentsWithStats(fg,8)
    big=[q for q in range(1,n) if st[q,4]>H*W*0.004]
    small=[q for q in range(1,n) if H*W*0.00004<st[q,4]<=H*W*0.004]
    # rows by y-centre (kmeans 1-D)
    ys=np.array([[cen[q][1]] for q in big],np.float32)
    _,lab,ctr=cv2.kmeans(ys,nr,None,(cv2.TERM_CRITERIA_EPS+cv2.TERM_CRITERIA_MAX_ITER,50,0.5),10,cv2.KMEANS_PP_CENTERS)
    order=np.argsort(ctr[:,0]);rowof={q:int(np.where(order==lab[i][0])[0][0]) for i,q in enumerate(big)}
    # attach small pieces to nearest big blob (bbox gap)
    def gap(a,b):
        ax0,ay0,aw,ah=st[a,:4];bx0,by0,bw,bh=st[b,:4]
        dx=max(0,max(ax0,bx0)-min(ax0+aw,bx0+bw));dy=max(0,max(ay0,by0)-min(ay0+ah,by0+bh));return dx+dy
    owner={q:q for q in big}
    for q in small:
        b=min(big,key=lambda z:gap(q,z))
        if gap(q,b)<W*0.06:owner[q]=b
    frames=[]
    for r in range(nr):
        row=sorted([q for q in big if rowof[q]==r],key=lambda q:cen[q][0])
        drop=DROP.get((k,r),[])
        if len(row)>4:row=[q for i,q in enumerate(row) if i not in drop][:4] if drop else row[:4]
        while len(row)<4:row.append(row[-1])
        print(k,'row',r,'frames',len(row))
        for q in row:
            parts=[p for p,o in owner.items() if o==q]
            m=np.isin(cc,parts)
            ys_,xs_=np.nonzero(m);x0,x1,y0,y1=xs_.min(),xs_.max()+1,ys_.min(),ys_.max()+1
            crop=im[y0:y1,x0:x1].copy();ca=AL[y0:y1,x0:x1].copy();mm=m[y0:y1,x0:x1]
            ca[~mm]=0                       # anything not this frame's art is clear
            frames.append((r,np.dstack([crop,ca])))
    ALL[k]=frames
    continue

# Each source sheet may be drawn at its own pixel density, so ONE pixel scale
# across all of them makes the character a different size per sheet -- that is
# what made Mordemir attack taller than he walked. Normalise on the character
# instead: every sheet is scaled so its typical standing figure is the same
# height, using the interquartile mean so a kick, a flame aura or a knockdown
# cannot drag a sheet's measure around.
def body(frames):
    hs=sorted(c.shape[0] for _,c in frames); n=len(hs)
    core=hs[n//4:max(n//4+1,n-n//4)] or hs
    return sum(core)/len(core)
BODY={k:body(fr) for k,fr in ALL.items()}
# one target: the biggest scaled frame must still fit a 256 cell
T=min(min(228*BODY[k]/c.shape[0],236*BODY[k]/c.shape[1]) for k,fr in ALL.items() for _,c in fr)
SH={k:T/BODY[k] for k in ALL}
for k in sorted(SH): print(f'  {k}: body {BODY[k]:6.1f}px  scale {SH[k]:.4f}  -> body {BODY[k]*SH[k]:.1f}px')
for k,frames in ALL.items():
    SC=SH[k]
    nr=ROWS[k];out=Image.new("RGBA",(1024,256*nr),(0,0,0,0));cnt=[0]*nr
    for r,c in frames:
        i=cnt[r];cnt[r]+=1;im=Image.fromarray(c,'RGBA')
        w,h=round(im.width*SC),round(im.height*SC);im=im.resize((w,h),Image.LANCZOS)
        out.paste(im,(i*256+(256-w)//2,r*256+256-h-10))
    out.save(f'{k}.png')
    # The upscaler only takes RGB, so hand it the colour with transparent areas
    # filled by prep's bleed, and keep the alpha beside it to recombine after.
    arr=np.asarray(out)
    Image.fromarray(arr[...,:3]).save(f'{k}.jpg',quality=95)
    Image.fromarray(arr[...,3]).save(f'{k}_alpha.png')
    print(k,out.size)
