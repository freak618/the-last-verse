"""Maps for the Kill Room's wet floor, from the painting itself:
killroom_wet.webp  - where the floor is wet (blood pools strongest), as alpha: the reflections of the tubes only land there
killroom_spec.webp - the floor's own bright highlights (the glints on the blood and water), in their own colour: brightened live so they shine"""
import numpy as np,cv2
from PIL import Image
im=np.asarray(Image.open('ext.png').convert('RGB')).astype(np.float32);H,W=im.shape[:2]
R,G,B=im[...,0],im[...,1],im[...,2];L=im.mean(2)
y0,y1=390,516                              # the floor, from the wall's foot to the front lip
yy=np.arange(H)[:,None]*np.ones((1,W))
floor=np.clip((yy-y0)/10,0,1)*np.clip((y1-yy)/4,0,1)
# objects standing on the floor (table legs and crates, shelf, cart, door) are not floor: keep them out of the masks
obj=np.zeros((H,W),np.uint8)
for x0,a,x1,b in [(478,270,895,418),(225,140,382,416),(915,265,1018,394),(1045,110,1150,412),(170,90,232,428),(1150,90,1200,420)]:obj[a:b,x0:x1]=1
obj=cv2.dilate(obj,np.ones((5,5),np.uint8)).astype(np.float32)
floor*=1-obj
blood=np.clip((R-np.maximum(G,B)*1.35-12)/45,0,1)
wet=np.clip(blood*1.0+np.clip((L-60)/120,0,1)*.45,0,1)*floor
wet=cv2.GaussianBlur(wet,(0,0),1.2)
hp=L-cv2.GaussianBlur(L,(0,0),4)
spec=np.clip((hp-14)/34,0,1)*floor*np.clip(wet*1.6,0,1)
spec=cv2.GaussianBlur(spec,(0,0),.7)
col=np.clip(im*1.2+40,0,255);col[...,1]=col[...,1]*.85+col[...,0]*.15*0;col=np.where((blood>.3)[...,None],np.dstack([np.full((H,W),255.),col[...,1]*.55,col[...,2]*.5]),col)
def save(name,a,rgb):
    rgba=np.dstack([rgb,np.clip(a*255,0,255)]).astype(np.uint8);rgba[...,:3][rgba[...,3]==0]=0
    Image.fromarray(rgba[y0-4:y1+4],'RGBA').save(f'/home/claude/light/stages/{name}.webp','WEBP',lossless=True,quality=100,method=6)
save('killroom_wet',wet,np.full((H,W,3),255,np.float32))
save('killroom_spec',spec,col)
bl=cv2.GaussianBlur(np.clip(blood*1.3,0,1)*floor,(0,0),1.5)
save('killroom_blood',bl,np.dstack([np.full((H,W),120.),np.full((H,W),14.),np.full((H,W),20.)]))
print('rows',y0-4,y1+4,'wet mean',round(float(wet[y0:y1].mean()),3),'spec mean',round(float(spec[y0:y1].mean()),3))
v=Image.fromarray((np.dstack([wet,spec,blood*floor])[380:530]*255).astype(np.uint8));v.save('/tmp/floormaps.png')
