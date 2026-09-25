import sys
sys.dont_write_bytecode = True
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from fractions import Fraction as F
from itertools import combinations
from pathlib import Path
import json


def fraction(x):
    return x if isinstance(x,F) else F(str(x))


def cell_shadow(anchor,a0,a1,row,col,height):
    """返回闭区间(Fraction lo, Fraction hi)或None；端点触地视为遮挡。"""
    B=list(map(fraction,anchor)); A0=list(map(fraction,a0)); A1=list(map(fraction,a1))
    D=[x-y for x,y in zip(A0,B)]; V=[x-y for x,y in zip(A1,A0)]
    # a*u+b*v+c >= 0，基础域0<=v<=u<=1。
    constraints=[(F(1),F(0),F(0)),(F(0),F(1),F(0)),(F(1),F(-1),F(0)),(F(-1),F(0),F(1))]
    for axis,low,high in [(0,col,col+1),(1,row,row+1)]:
        constraints += [(D[axis],V[axis],B[axis]-fraction(low)),(-D[axis],-V[axis],fraction(high)-B[axis])]
    constraints += [(-D[2],-V[2],fraction(height)-B[2])]
    if all(c>=0 for a,b,c in constraints):
        return (F(0),F(1))  # u=v=0可行：锚点接触本像元，所有时刻视线均含B。
    vertices=set()
    for (a,b,c),(d,e,f) in combinations(constraints,2):
        det=a*e-b*d
        if not det:
            continue
        u=(b*f-c*e)/det; v=(c*d-a*f)/det
        if all(aa*u+bb*v+cc>=0 for aa,bb,cc in constraints):
            vertices.add((u,v))
    if not vertices:
        return None
    assert all(u>0 for u,v in vertices)
    times=[v/u for u,v in vertices]
    return (min(times),max(times))


def check_case(name,anchor,a0,a1,row,col,height,expected):
    actual=cell_shadow(anchor,a0,a1,row,col,height)
    assert actual==expected,(name,actual,expected)
    return {'name':name,'anchor':anchor,'A0':a0,'A1':a1,'cell':[row,col],'height':height,'interval_exact':None if actual is None else list(map(str,actual)),'interval_float':None if actual is None else list(map(float,actual))}





if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Reusable numerical module. See README_reproduction.md for stage commands.")
    parser.parse_args()
    print("Module import check passed.")
