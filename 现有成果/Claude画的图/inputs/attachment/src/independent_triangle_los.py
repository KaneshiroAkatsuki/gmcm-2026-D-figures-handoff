import sys
sys.dont_write_bytecode = True
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from math import ceil, floor
import json
from pathlib import Path
import numpy as np
import tifffile


def clip_plane(poly, axis, value, sense):
    if not poly:
        return []
    result=[]
    prev=poly[-1]
    dp=sense*(prev[axis]-value)
    for cur in poly:
        dc=sense*(cur[axis]-value)
        pin, cin=dp>=-1e-12, dc>=-1e-12
        if pin != cin:
            t=dp/(dp-dc)
            cross=[prev[k]+t*(cur[k]-prev[k]) for k in range(3)]
            cross[axis]=value
            result.append(cross)
        if cin:
            result.append(list(cur))
        prev, dp=cur, dc
    return result


def certify_los(terrain, anchor, a0, a1, nodata=-32767, vertical_clearance=1e-8):
    """True仅在整个时间区间每条视线都明确高于DEM时返回。

    False仅表示未取得此LOS证书，不等价全区间都遮挡，更不等价链路不可用。
    对临界接触采用更严格的正净空，避免相等边界的未定义解释造成误通过。
    """
    triangle=[list(anchor),list(a0),list(a1)]
    cols=np.arange(ceil(min(p[0] for p in triangle))-1, floor(max(p[0] for p in triangle))+1)
    rows=np.arange(ceil(min(p[1] for p in triangle))-1, floor(max(p[1] for p in triangle))+1)
    xx,yy=np.meshgrid(cols,rows)
    candidate=np.ones(xx.shape,dtype=bool)
    # 凸三角形和矩形的分离轴筛选：x/y已由bbox处理，另检查三条边法向。
    # 容差仅向外放宽候选集合；证书最后仍按精细裁剪高度的正净空判定。
    for p,q in zip(triangle,triangle[1:]+triangle[:1]):
        nx,ny=-(q[1]-p[1]),q[0]-p[0]
        projected=[nx*v[0]+ny*v[1] for v in triangle]
        rect_min=nx*xx+ny*yy+min(nx,0)+min(ny,0)
        rect_max=nx*xx+ny*yy+max(nx,0)+max(ny,0)
        tol=1e-8*(1+abs(nx)+abs(ny))
        candidate &= (rect_max>=min(projected)-tol) & (rect_min<=max(projected)+tol)
    minimum=float('inf'); worst=None; count=0
    nr,nc=terrain.shape
    for row,col in zip(yy[candidate],xx[candidate]):
            row,col=int(row),int(col)
            poly=triangle
            for axis,value,sense in [(0,col,1),(0,col+1,-1),(1,row,1),(1,row+1,-1)]:
                poly=clip_plane(poly,axis,value,sense)
                if not poly:
                    break
            if not poly:
                continue
            count+=1
            if not (0<=row<nr and 0<=col<nc) or not np.isfinite(terrain[row,col]) or terrain[row,col]==nodata:
                return {'certified':False,'reason':'outside_or_nodata','cell':[row,col],'tested_intersections':count}
            zmin=min(p[2] for p in poly)
            clearance=zmin-float(terrain[row,col])
            if clearance < minimum:
                minimum=clearance; worst=[row,col]
    return {'certified':minimum>vertical_clearance,'reason':'all_time_triangle_clear' if minimum>vertical_clearance else 'los_not_certified','min_clearance_m':minimum,'critical_cell':worst,'tested_intersections':count}


class TifLOS:
    """只读一次原始GeoTIFF；随后用(lon, lat, z)三元组查询。

    example: checker = TifLOS(path)
             checker(anchor_lonlatz, path_start_lonlatz, path_end_lonlatz)

    参数按WGS84经纬度转换到仿射像元坐标；轨迹定义必须同样按经纬度仿射，
    或已明确局部等距坐标与它的仿射对应。此适配不代替测地曲线模型。
    """
    def __init__(self, tif_path):
        with tifffile.TiffFile(tif_path) as tf:
            page=tf.pages[0]
            self.terrain=page.asarray()
            self.sx,self.sy,_=page.tags['ModelPixelScaleTag'].value
            tie=page.tags['ModelTiepointTag'].value
            # 支持给定原件的单Tiepoint+PixelScale型变换；不猜其他变换。
            if tuple(tie[:3])!=(0.,0.,0.):
                raise ValueError('reference implementation expects raster tie (0,0,0)')
            self.lon0,self.lat0=tie[3:5]
            raw=page.tags['GeoKeyDirectoryTag'].value
            keys={raw[i]:raw[i+3] for i in range(4,len(raw),4)}
            if keys.get(2048)!=4326 or keys.get(1025) not in [1,2]:
                raise ValueError('expected WGS84 and declared raster pixel convention')
            self.offset=.5 if keys[1025]==2 else 0.

    def pixel(self, lonlatz):
        lon,lat,z=lonlatz
        return ((lon-self.lon0)/self.sx+self.offset,(self.lat0-lat)/self.sy+self.offset,z)

    def __call__(self, anchor, a0, a1, vertical_clearance=1e-8):
        return certify_los(self.terrain,self.pixel(anchor),self.pixel(a0),self.pixel(a1),vertical_clearance=vertical_clearance)





if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Reusable numerical module. See README_reproduction.md for stage commands.")
    parser.parse_args()
    print("Module import check passed.")
