"""新增插图的公共样式与输出工具：字体、配色、尺寸、CSV、PNG/SVG 与 meta.json。

所有路径均相对于本文件夹根目录计算；输出文件不含本机绝对路径。
"""
import sys
sys.dont_write_bytecode = True
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
import csv
import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.text import Text

ROOT = Path(__file__).resolve().parents[1]
INPUTS = ROOT / "inputs"
RESULTS = INPUTS / "results"
ATTACH = INPUTS / "attachment"
RAW = INPUTS / "raw"
SRC = ATTACH / "src"

CM = 1 / 2.54
FULL_W = 15.5 * CM          # 通栏宽
HALF_W = 7.5 * CM           # 半栏宽
MIN_PT = 10.0               # 印刷尺寸下的最小字号

# 与现有 figures/fusion 一致的机型配色（Okabe-Ito），B、C 另加纹理，黑白打印可辨
C = {
    "A": "#0072B2", "B": "#D55E00", "C": "#009E73",
    "relay": "#8660A8",        # 中继无人机、能源组件、中继悬停点（与图18一致）
    "direct": "#3D697A",       # 通信状态：直连（与图21一致）
    "relaycomm": "#CB8E3C",    # 通信状态：中继（与图21一致）
    "ink": "#222222", "muted": "#67737D", "grid": "#DDE2E5", "light": "#EEF1F3",
    "inventory": "#B84438",    # 库存线、约束线
}
HATCH = {"A": "", "B": "////", "C": "xx"}
TYPE_NAME = {"A": "A 型", "B": "B 型", "C": "C 型"}


FONT_NOTE = {
    "formal": "中文宋体（SimSun），英文与数字 Times New Roman，记号 STIX",
    "substitute": "替代字体：中文 Noto Serif CJK SC（宋体类），英文与数字 Liberation Serif（与 Times New Roman 等宽），记号 STIX；"
                  "在装有宋体与 Times New Roman 的环境中运行同一程序即得正式字体版本",
}
FONT_MODE = None


def _noto_serif_sc():
    """从系统 Noto Serif CJK 字体集中取出简体中文字面，注册给 matplotlib（字体集默认只暴露日文字面）。"""
    import tempfile
    from matplotlib import font_manager as fm
    ttc = [f.fname for f in fm.fontManager.ttflist if Path(f.fname).name == "NotoSerifCJK-Regular.ttc"]
    if not ttc:
        return None
    out = Path(tempfile.gettempdir()) / "figkit_fonts" / "NotoSerifCJKsc-Regular.otf"
    if not out.exists():
        from fontTools.ttLib import TTCollection
        out.parent.mkdir(parents=True, exist_ok=True)
        coll = TTCollection(ttc[0])
        face = next(f for f in coll.fonts if f["name"].getDebugName(1) == "Noto Serif CJK SC")
        tmp = out.with_suffix(".part")
        face.save(tmp)
        tmp.replace(out)
    fm.fontManager.addfont(str(out))
    return "Noto Serif CJK SC"


def font_family():
    """正式字体（宋体、Times New Roman）齐全时使用正式字体，否则使用开源替代字体。"""
    global FONT_MODE
    from matplotlib import font_manager as fm
    names = {f.name for f in fm.fontManager.ttflist}
    if {"Times New Roman", "SimSun"} <= names:
        FONT_MODE = "formal"
        return ["Times New Roman", "SimSun", "STIXGeneral"]
    cjk = _noto_serif_sc()
    assert cjk and "Liberation Serif" in names, "缺少宋体/Times New Roman，也缺少替代字体 Noto Serif CJK 与 Liberation Serif"
    FONT_MODE = "substitute"
    return ["Liberation Serif", cjk, "STIXGeneral"]


def setup():
    plt.rcParams.update({
        "font.family": font_family(),
        "font.size": 10.5, "axes.titlesize": 10.5, "axes.labelsize": 10.5,
        "xtick.labelsize": 10, "ytick.labelsize": 10, "legend.fontsize": 10,
        "axes.unicode_minus": False, "axes.spines.top": False, "axes.spines.right": False,
        "axes.edgecolor": "#657078", "axes.linewidth": 0.7,
        "xtick.major.width": 0.6, "ytick.major.width": 0.6,
        "xtick.major.size": 3, "ytick.major.size": 3,
        "grid.color": C["grid"], "grid.linewidth": 0.5,
        "legend.frameon": False, "legend.handlelength": 1.6, "legend.borderaxespad": 0.3,
        "mathtext.fontset": "stix", "hatch.linewidth": 0.55,
        "svg.fonttype": "path", "svg.hashsalt": "figkit",
        "savefig.facecolor": "white", "figure.facecolor": "white",
        "pdf.fonttype": 42, "ps.fonttype": 42,
    })


def labels():
    """读取 labels.json，并把 {r}、{soc} 等占位符替换为 sym 中的记号。"""
    raw = json.loads((ROOT / "lib" / "labels.json").read_text(encoding="utf-8"))
    sym = raw["sym"]

    def fill(v):
        if isinstance(v, str):
            for k, s in sym.items():
                v = v.replace("{" + k + "}", s)
            return v
        if isinstance(v, dict):
            return {k: fill(x) for k, x in v.items()}
        if isinstance(v, list):
            return [fill(x) for x in v]
        return v
    return {k: (fill(v) if k != "sym" else v) for k, v in raw.items()}


LABELS_FILE = ROOT / "lib" / "labels.json"
NODE_XLSX = RAW / "无人机应急物资运输基础数据" / "调度中心与服务区.xlsx"
BOX_XLSX = RAW / "无人机应急物资运输基础数据" / "物资需求与配送时限.xlsx"
TYPE_XLSX = RAW / "无人机应急物资运输基础数据" / "运输无人机数据.xlsx"
RELAY_XLSX = RAW / "无人机应急物资运输基础数据" / "中继无人机数据.xlsx"
COMM_XLSX = RAW / "无人机应急物资运输基础数据" / "通信链路参数.xlsx"
DEM_TIF = RAW / "镇龙乡地理空间数据" / "镇龙乡及周边地理数据" / "数字高程模型数据（DEM）" / "镇龙乡及周边30米DEM.tif"


def _sheet(path, title="数据"):
    import openpyxl
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    rows = list(wb[title].values)
    wb.close()
    return rows


def nodes():
    """原题节点表：O01 与 15 个服务区（编号、名称、经度、纬度、海拔）。"""
    s = _sheet(NODE_XLSX)
    out = {}
    for r in [s[2]] + s[6:21]:
        out[r[0]] = {"id": r[0], "name": r[1], "lon": float(r[2]), "lat": float(r[3]), "z": float(r[4])}
    return out


def boxes():
    s = _sheet(BOX_XLSX, "逐箱货箱清单")
    keys = ["id", "site", "category", "mass", "volume", "first", "first_due", "expected", "priority"]
    return {r[0]: dict(zip(keys, r)) for r in s[1:81]}


def charge_full():
    """原题：三型电池与中继能源组件的等效完全充电时间（s）。"""
    s = _sheet(TYPE_XLSX)
    out = {r[0]: float(r[2]) for r in s[19:22]}
    out["R"] = float(_sheet(RELAY_XLSX)[11][2])
    return out


def relay_turnaround():
    return float(_sheet(RELAY_XLSX)[2][11])


def charge_time(soc, full):
    """论文式(15)：两阶段等效充电，从荷电状态 soc 充满所需时间。"""
    soc = min(1.0, max(0.0, soc))
    return full * (0.65 * (0.9 - soc) / 0.9 + 0.35) if soc < 0.9 else full * 0.35 * (1 - soc) / 0.1


class DEM:
    """原题 30 m DEM（GeoTIFF，PixelIsPoint）。与附件 dcore.Terrain 的像元边界口径一致。"""

    def __init__(self):
        import tifffile
        with tifffile.TiffFile(DEM_TIF) as t:
            self.a = t.asarray().astype(float)
            m = t.geotiff_metadata
        self.dx, self.dy = m["ModelPixelScale"][:2]
        x0, y0 = m["ModelTiepoint"][3:5]
        assert int(m["GTRasterTypeGeoKey"]) == 2
        self.left, self.top = x0 - self.dx / 2, y0 + self.dy / 2
        self.nrow, self.ncol = self.a.shape

    def window(self, lon0, lon1, lat0, lat1):
        c0 = max(0, int((lon0 - self.left) / self.dx))
        c1 = min(self.ncol, int((lon1 - self.left) / self.dx) + 1)
        r0 = max(0, int((self.top - lat1) / self.dy))
        r1 = min(self.nrow, int((self.top - lat0) / self.dy) + 1)
        sub = self.a[r0:r1, c0:c1]
        extent = (self.left + c0 * self.dx, self.left + c1 * self.dx,
                  self.top - r1 * self.dy, self.top - r0 * self.dy)
        return sub, extent, (r0, c0)

    def hillshade(self, sub, lat):
        from matplotlib.colors import LightSource
        import math
        kx, ky = local_scale(lat)
        ls = LightSource(azdeg=315, altdeg=45)
        return ls.hillshade(sub, vert_exag=1.0, dx=self.dx * kx, dy=self.dy * ky)


def local_scale(lat):
    """WGS84 椭球在纬度 lat 处每度经度、纬度对应的米数（与附件局部平面口径相同）。"""
    import math
    a, e2 = 6378137.0, 6.6943799901413165e-3
    phi = math.radians(lat)
    kx = math.pi / 180 * a / math.sqrt(1 - e2 * math.sin(phi) ** 2) * math.cos(phi)
    ky = math.pi / 180 * a * (1 - e2) / (1 - e2 * math.sin(phi) ** 2) ** 1.5
    return kx, ky


def map_axes(ax, lat_mid):
    import math
    from matplotlib.ticker import FormatStrFormatter, MultipleLocator
    ax.set_aspect(1 / math.cos(math.radians(lat_mid)))
    ax.xaxis.set_major_locator(MultipleLocator(0.02))
    ax.yaxis.set_major_locator(MultipleLocator(0.02))
    ax.xaxis.set_major_formatter(FormatStrFormatter("%.2f"))
    ax.yaxis.set_major_formatter(FormatStrFormatter("%.2f"))
    for s in ["top", "right"]:
        ax.spines[s].set_visible(True)


def north_arrow(ax, x=0.955, y=0.86, size=0.08):
    ax.annotate("", xy=(x, y + size), xytext=(x, y), xycoords="axes fraction",
                arrowprops=dict(arrowstyle="-|>", lw=0.9, color=C["ink"], mutation_scale=9))
    ax.text(x, y + size + 0.01, "N", transform=ax.transAxes, ha="center", va="bottom", fontsize=10)


def scale_bar(ax, lat, km=2.0, x0=0.04, y0=0.05):
    """在经纬度坐标轴上画比例尺（沿纬线方向）。"""
    kx, _ = local_scale(lat)
    lon_len = km * 1000 / kx
    xl, xh = ax.get_xlim()
    yl, yh = ax.get_ylim()
    x = xl + x0 * (xh - xl)
    y = yl + y0 * (yh - yl)
    ax.plot([x, x + lon_len], [y, y], color=C["ink"], lw=1.6, solid_capstyle="butt", zorder=6)
    ax.plot([x, x], [y, y + 0.008 * (yh - yl) * 1.5], color=C["ink"], lw=0.8, zorder=6)
    ax.plot([x + lon_len, x + lon_len], [y, y + 0.008 * (yh - yl) * 1.5], color=C["ink"], lw=0.8, zorder=6)
    ax.text(x + lon_len / 2, y + 0.012 * (yh - yl), f"{km:g} km", ha="center", va="bottom", fontsize=10, zorder=6)


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source_digest(path):
    """源文件指纹。冻结记录与审查包按原始 CRLF 换行计算 SHA-256；本仓库中的文本副本换行被规范为 LF，
    因此对不含回车的文本文件按 CRLF 还原后计算 sha256（与冻结记录一致），同时给出仓库副本本身的 sha256_repo。"""
    b = Path(path).read_bytes()
    out = {"path": rel(path), "sha256": hashlib.sha256(b).hexdigest()}
    if b"\0" not in b and b"\r" not in b and b"\n" in b:
        try:
            b.decode("utf-8")
        except UnicodeDecodeError:
            return out
        out = {"path": out["path"], "sha256": hashlib.sha256(b.replace(b"\n", b"\r\n")).hexdigest(),
               "sha256_repo": out["sha256"], "line_ending": "按 CRLF 计算"}
    return out


def rel(path):
    return Path(path).resolve().relative_to(ROOT).as_posix()


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_csv(path, rows, fields=None):
    """写出图中所用全部数值；浮点数按最短可回读形式写出。"""
    rows = list(rows)
    fields = fields or list(rows[0].keys())
    with Path(path).open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fields})
    return Path(path)


def grid(ax, axis="both"):
    ax.grid(axis=axis, zorder=0)
    ax.set_axisbelow(True)


def panel_label(ax, s, x=-0.02, y=1.02, **kw):
    ax.text(x, y, s, transform=ax.transAxes, ha="right", va="bottom", fontsize=10.5, **kw)


def _text_checks(fig):
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    sizes, outside = [], []
    hidden = set()
    for ax in fig.axes:
        for axis, lim in [(ax.xaxis, ax.get_xlim()), (ax.yaxis, ax.get_ylim())]:
            lo, hi = sorted(lim)
            for tk in axis.get_major_ticks() + axis.get_minor_ticks():
                if not lo - 1e-9 <= tk.get_loc() <= hi + 1e-9:
                    hidden.update([id(tk.label1), id(tk.label2)])
    for t in fig.findobj(Text):
        if not (t.get_visible() and t.get_text().strip()) or id(t) in hidden:
            continue
        sizes.append(t.get_fontsize())
        b = t.get_window_extent(renderer)
        if b.x0 < -2 or b.y0 < -2 or b.x1 > fig.bbox.width + 2 or b.y1 > fig.bbox.height + 2:
            outside.append(t.get_text())
    return (min(sizes) if sizes else None), outside


def save(fig, here, stem, *, figure_id, caption, sources, key_values, notes="", section=""):
    """输出 PNG(300 dpi)、SVG 与 meta.json；检查最小字号与越界文字。"""
    here = Path(here)
    min_pt, outside = _text_checks(fig)
    assert min_pt is None or min_pt >= MIN_PT - 1e-9, f"{stem}: 最小字号 {min_pt} pt 小于 {MIN_PT} pt"
    assert not outside, f"{stem}: 文字越出图幅 {outside}"
    png, svg = here / f"{stem}.png", here / f"{stem}.svg"
    fig.savefig(png, dpi=300, metadata={"Software": None})
    fig.savefig(svg, metadata={"Creator": None, "Date": None, "Format": None, "Type": None})
    w_in, h_in = fig.get_size_inches()
    from PIL import Image
    with Image.open(png) as im:
        px = list(im.size)
    plt.close(fig)
    script = here / f"{stem}.py"
    meta = {
        "figure_id": figure_id,
        "stem": stem,
        "suggested_caption": caption,
        "section": section,
        "files": {"script": script.name, "csv": f"{stem}.csv", "png": png.name, "svg": svg.name},
        "size_cm": [round(w_in * 2.54, 2), round(h_in * 2.54, 2)],
        "dpi": 300,
        "pixel_size": px,
        "min_font_pt": min_pt,
        "fonts": FONT_NOTE[FONT_MODE or "formal"],
        "sources": [source_digest(p) for p in sources],
        "key_values": key_values,
        "notes": notes,
    }
    (here / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{figure_id} {stem}: {px[0]}x{px[1]} px, 最小字号 {min_pt} pt")
    return meta


ORIG_FIG = ATTACH / "figures"


def copy_source_csv(src, here, stem):
    """改进版沿用原图源的同名 CSV：原样复制到本图文件夹，作为图中数值的记录。"""
    import shutil
    dst = Path(here) / f"{stem}.csv"
    shutil.copyfile(src, dst)
    return dst


def read_source_csv(src):
    with Path(src).open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))
