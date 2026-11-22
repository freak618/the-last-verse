"""Extend the kill room sideways by image quilting: new strips are stitched from patches of the painting's own plastic sheeting,
ceiling, floor and front lip (never its objects), each patch picked to match what is already beside and above it, joined along
the least visible seam."""
import numpy as np,cv2,sys
rng=np.random.default_rng(int(sys.argv[2]) if len(sys.argv)>2 else 5)
E=int(sys.argv[1]) if len(sys.argv)>1 else 176
src=cv2.imread('src.png').astype(np.float32);H,W=src.shape[:2]
T,O=40,12
def rects(lst):
    m=np.zeros((H,W),np.uint8)
    for x0,y0,x1,y1 in lst:m[y0:y1,x0:x1]=1
    return m
# where each kind of surface can be sampled from (no shelves, table, cart, door, knives, chains, lights)
CLS={'ceil':rects([(440,0,590,34),(440,60,590,92),(800,0,960,90),(80,0,200,35)]),
     'wall':rects([(250,192,300,392),(300,95,722,272),(845,95,866,390),(978,100,1016,400),(255,95,300,190)]),
     'floor':rects([(0,430,1019,512),(0,405,330,430),(700,412,1019,430)]),
     'lip':rects([(0,514,1019,572)])}
def side(img,J):
    """grow img to the right by E px; J = the row where the wall meets the floor at that edge"""
    can=np.zeros((H,W+E,3),np.float32);can[:,:W]=img;known=np.zeros((H,W+E),bool);known[:,:W]=True
    bands=[('ceil',0,92),('wall',92,J),('floor',J,514),('lip',514,H)]
    srcs=[(img,{k:v for k,v in CLSF.items()})]
    for cls,b0,b1 in bands:
        # valid tile positions: the whole tile's in-band part lies inside allowed area (use the tile top-left)
        y=b0
        while y<b1:
            th=min(T,H-y)
            x=W-O*2 if False else W-24
            while x<W+E:
                tw=min(T,W+E-x)
                tpl=can[y:y+th,x:x+tw];m=known[y:y+th,x:x+tw].astype(np.float32)
                best=None
                for S,cm in srcs:
                    allow=cm[cls];hh=min(th,b1-y)
                    # a source position is valid if the rows of the tile that fall in this band are all allowed
                    v=cv2.erode(allow,np.ones((hh,tw),np.uint8),anchor=(0,0),borderType=cv2.BORDER_CONSTANT,borderValue=0)
                    v=v[:H-th+1,:W-tw+1].astype(bool)
                    if not v.any():continue
                    if m.sum()<1:err=np.zeros(v.shape,np.float32)
                    else:err=cv2.matchTemplate(S,tpl,cv2.TM_SQDIFF,mask=np.repeat(m[...,None],3,2))
                    err=np.where(v,err,np.inf)
                    if best is None or np.min(err)<best[0]:best=(np.min(err),err,S)
                e0,err,S=best;cand=np.argwhere(err<=e0*1.12+1e-3);py,px=cand[rng.integers(len(cand))]
                patch=S[py:py+th,px:px+tw]
                # min-error boundary cut through the known overlap
                cut=np.ones((th,tw),np.float32)
                if m.any():
                    d=((patch-tpl)**2).sum(2)
                    ol=int(m[:,:O].all(0).sum()) if tw>O else 0
                    if ol:
                        c=d[:,:ol].copy()
                        for r in range(1,th):
                            for j in range(ol):c[r,j]+=c[r-1,max(0,j-1):min(ol,j+2)].min()
                        j=int(np.argmin(c[-1]))
                        for r in range(th-1,-1,-1):
                            cut[r,:j]=0
                            if r:lo=max(0,j-1);j=lo+int(np.argmin(c[r-1,lo:min(ol,j+2)]))
                    ot=int(m[:O,:].all(1).sum())
                    if ot and y>0:
                        c=d[:ot,:].T.copy()
                        for r in range(1,tw):
                            for j in range(ot):c[r,j]+=c[r-1,max(0,j-1):min(ot,j+2)].min()
                        j=int(np.argmin(c[-1]))
                        for r in range(tw-1,-1,-1):
                            cut[:j,r]=0
                            if r:lo=max(0,j-1);j=lo+int(np.argmin(c[r-1,lo:min(ot,j+2)]))
                    cut=np.where(m>0,cut,1.0)
                cut=cv2.GaussianBlur(cut,(3,3),0)
                can[y:y+th,x:x+tw]=tpl*(1-cut[...,None])+patch*cut[...,None] if m.any() else patch
                known[y:y+th,x:x+tw]=True
                x+=T-O
            y+=T-O if y+T<b1 else (b1-y)
    return can
CLSF=CLS
right=side(src,406)
# the left side: mirror the painting, grow it the same way, mirror back (so the new strip is on the left)
CLSF={k:np.ascontiguousarray(v[:,::-1]) for k,v in CLS.items()}
left=side(np.ascontiguousarray(src[:,::-1]),424)[:,::-1]
out=np.concatenate([left[:,:E],src,right[:,W:]],1)
# tone each new strip to the edge of the painting it continues (its texture comes from the brighter middle of the room)
for side in ('L','R'):
    ref=out[:,E:E+50] if side=='L' else out[:,E+W-50:E+W]
    ext=out[:,:E] if side=='L' else out[:,E+W:]
    g=(cv2.GaussianBlur(ref.mean(1).reshape(-1,1,3),(1,0),sigmaX=0,sigmaY=14).reshape(-1,3)+6)/(cv2.GaussianBlur(ext.mean(1).reshape(-1,1,3),(1,0),sigmaX=0,sigmaY=14).reshape(-1,3)+6)
    ext*=np.clip(g,.45,1.5)[:,None,:]
# match the new strips to the painting where they meet it: a per-row colour gain, full strength at the join and fading out over 60px
for side in ('L','R'):
    if side=='L':ref=out[:,E:E+6].mean(1);new=out[:,E-6:E].mean(1)
    else:ref=out[:,E+W-6:E+W].mean(1);new=out[:,E+W:E+W+6].mean(1)
    g=cv2.GaussianBlur((ref+8)/(new+8),(1,0),sigmaX=0,sigmaY=9).reshape(-1,3)
    g=np.clip(g,.5,1.6)
    for d in range(E):
        w=max(0.0,1-d/60.0);w=w*w*(3-2*w)
        x=E-1-d if side=='L' else E+W+d
        out[:,x]*=1+(g-1)*w

# the far ends of the room fall a little further into shadow
xx=np.arange(out.shape[1]);u=np.clip(np.minimum(xx,out.shape[1]-1-xx)/E,0,1);u=u*u*(3-2*u);out*=(0.5+.5*u)[None,:,None]
cv2.imwrite('ext.png',np.clip(out,0,255).astype(np.uint8));print(out.shape)
