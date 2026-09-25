"""流程图绘制工具：起止框（圆角）、处理框（矩形）、判断框（菱形）与带标注的箭头。坐标为 0—1 归一化。"""
import sys
sys.dont_write_bytecode = True
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Polygon
from figstyle import setup

EDGE = "#2F3E4C"
FILL = {"term": "#E3EDF5", "proc": "#F6F8FA", "dec": "#FBF1EA", "io": "#EEF5EC"}


class Flow:
    def __init__(self, w=6.5, h=8.0, size=10.2):
        setup()
        self.fig = plt.figure(figsize=(w, h))
        self.ax = self.fig.add_axes([0, 0, 1, 1])
        self.ax.set_xlim(0, 1); self.ax.set_ylim(0, 1); self.ax.axis("off")
        self.size = size
        self.boxes = {}

    def node(self, key, x, y, text, kind="proc", w=0.56, h=0.058):
        ax = self.ax
        if kind == "dec":
            pts = [(x, y + h / 2), (x + w / 2, y), (x, y - h / 2), (x - w / 2, y)]
            ax.add_patch(Polygon(pts, closed=True, facecolor=FILL["dec"], edgecolor=EDGE, linewidth=0.8))
        else:
            style = "round,pad=0.006,rounding_size=0.03" if kind == "term" else "square,pad=0.006"
            ax.add_patch(FancyBboxPatch((x - w / 2, y - h / 2), w, h, boxstyle=style,
                                        facecolor=FILL[kind], edgecolor=EDGE, linewidth=0.8))
        ax.text(x, y, text, ha="center", va="center", fontsize=self.size, linespacing=1.2)
        self.boxes[key] = (x, y, w, h, kind)

    def _port(self, key, side):
        x, y, w, h, _ = self.boxes[key]
        return {"top": (x, y + h / 2), "bottom": (x, y - h / 2), "left": (x - w / 2, y), "right": (x + w / 2, y)}[side]

    def arrow(self, a, b, sa="bottom", sb="top", label=None, via=None, lpos=0.5, loff=(0.012, 0)):
        p0 = self._port(a, sa); p1 = self._port(b, sb)
        pts = [p0] + (via or []) + [p1]
        for q0, q1 in zip(pts[:-2], pts[1:-1]):
            self.ax.plot([q0[0], q1[0]], [q0[1], q1[1]], color=EDGE, linewidth=0.8)
        self.ax.annotate("", xy=pts[-1], xytext=pts[-2],
                         arrowprops=dict(arrowstyle="-|>", color=EDGE, linewidth=0.8, shrinkA=0, shrinkB=0, mutation_scale=9))
        if label:
            q0, q1 = pts[0], pts[1]
            lx = q0[0] + (q1[0] - q0[0]) * lpos + loff[0]; ly = q0[1] + (q1[1] - q0[1]) * lpos + loff[1]
            self.ax.text(lx, ly, label, fontsize=self.size - 0.8, ha="left", va="center", color="#7A3A20")

    def chain(self, keys):
        for a, b in zip(keys[:-1], keys[1:]):
            self.arrow(a, b)
