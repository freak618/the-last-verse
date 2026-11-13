import sys;sys.path.insert(0,'/tmp/claude-0/b_mord3');import cut2z as C
from PIL import Image
s,f,a,m=C.cut({k:k+'_hd.png' for k in 'ABC'},'sheet.png','sheet.json','mordemir')
print('mordemir',s.size,{k:len(v) for k,v in a.items()},[(k,f['mordemir_'+k]['frame']['h']) for k in ['idle_0','walk_0','punch_0','kick_2','special_2','hit_3','victory_0']])
bg=Image.new('RGBA',s.size,(60,60,70,255));bg.alpha_composite(s);bg.thumbnail((700,2000));bg.convert('RGB').save('prev.png')
