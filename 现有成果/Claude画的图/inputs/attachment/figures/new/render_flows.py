"""从节点边CSV绘制双列蛇形流程：宽15.5cm，高不超过12cm，仅PNG/SVG。"""
import sys
sys.dont_write_bytecode=True
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch,Polygon
from figstyle import setup,read,save

def render(stem):
    setup();rows=read(stem);nodes={r['id']:r for r in rows if r['record_type']=='node'}
    height_cm=11.5 if len(nodes)==8 else 12.0
    fig,ax=plt.subplots(figsize=(15.5/2.54,height_cm/2.54));fig.subplots_adjust(left=0,right=1,top=1,bottom=0)
    ax.set(xlim=(0,1),ylim=(0,1));ax.axis('off')
    fill={'terminal':'#E1EDF4','process':'#F4F7F9','decision':'#FBEEE3'}
    for r in nodes.values():
        x,y,w,h=[float(r[k]) for k in ['x','y','width','height']]
        if r['kind']=='decision':p=Polygon([(x-w/2,y),(x,y+h/2),(x+w/2,y),(x,y-h/2)],closed=True)
        else:p=FancyBboxPatch((x-w/2,y-h/2),w,h,boxstyle='round,pad=0.005,rounding_size=0.015' if r['kind']=='terminal' else 'square,pad=0.005')
        p.set(facecolor=fill[r['kind']],edgecolor='#40515D',linewidth=.8);ax.add_patch(p)
        ax.text(x,y,r['text'],ha='center',va='center',fontsize=10.5,linespacing=1.12)
    for r in rows:
        if r['record_type']!='edge':continue
        a,b=nodes[r['source']],nodes[r['target']]
        x0,y0,x1,y1=float(a['x']),float(a['y']),float(b['x']),float(b['y'])
        if r['route']=='left':
            start=(x0-float(a['width'])/2,y0);end=(x1-float(b['width'])/2,y1);side=.035
            ax.plot([start[0],side,side],[start[1],start[1],end[1]],color='#7C6555',lw=.85)
            ax.annotate('',xy=end,xytext=(side,end[1]),arrowprops=dict(arrowstyle='-|>',lw=.85,color='#7C6555'))
            ax.text(.014,(y0+y1)/2,r['label'],rotation=90,ha='center',va='center',fontsize=10,color='#7C6555')
        else:
            if abs(x1-x0)>.1:
                start=(x0+float(a['width'])/2+.006,y0);end=(x1-float(b['width'])/2-.006,y1)
            else:
                direction=1 if y1>y0 else -1
                start=(x0,y0+direction*(float(a['height'])/2+.008));end=(x1,y1-direction*(float(b['height'])/2+.008))
            ax.annotate('',xy=end,xytext=start,arrowprops=dict(arrowstyle='-|>',lw=.85,color='#40515D'))
            if r['label']:ax.text((start[0]+end[0])/2,(start[1]+end[1])/2+.027,r['label'],ha='center',va='bottom',fontsize=10)
    save(fig,stem)
