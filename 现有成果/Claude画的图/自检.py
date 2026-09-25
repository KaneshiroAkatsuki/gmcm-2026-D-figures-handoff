"""交付前自检：
1. 复现：把本文件夹复制到临时目录，在副本中运行“一键重绘全部.py”，逐字节比较全部 PNG、SVG、CSV 与 meta.json。
   字体环境：各图 meta.json 的 fonts 字段记录出图时的字体（正式字体或开源替代字体）。与当前运行环境字体相同的图
   必须逐字节一致；字体环境不同的图（例如在装有宋体与 Times New Roman 的电脑上出的图，在无这两种字体的环境中自检）
   无法逐字节比较，改为核对 CSV 数值（相对差不超过 1e-12）与 meta.json 的 key_values，并在结果中单列。
2. 匿名扫描：PNG 文本块、SVG 元数据与文本、脚本与说明文件中不得出现本机路径、用户名、AI 或工具署名。
结果写入 自检结果.json；临时副本用完即删。
"""
import sys
sys.dont_write_bytecode = True
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
import hashlib
import json
import re
import shutil
import subprocess
import tempfile
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT_EXT = {".png", ".svg", ".csv"}
FORBIDDEN = [r"\b[A-Za-z]:[\\/]", r"\\Users\\", r"/Users/", r"/home/", r"/root/", r"/tmp/", r"ZhuanZ", r"Kaneshiro",
             r"privaterelay", r"Desktop", r"Kimi", r"scratchpad",
             r"\bClaude\b", r"Anthropic", r"\bGPT\b", r"OpenAI", r"Codex", r"ChatGPT", r"\bAI\b", r"人工智能",
             r"Matplotlib", r"matplotlib\.org", r"桌面"]
# 说明性 Markdown 本身写给队伍与 GPT，允许出现 GPT 等字样；只检查图件、数据与脚本
SKIP_TEXT = {"图清单.md", "给GPT的插入说明.md", "交付记录.md", "F1_对账记录.md", "自检.py", "自检结果.json"}


def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def outputs(base):
    res = {}
    for d in sorted(p for p in base.iterdir() if p.is_dir() and p.name[:1] in "FG" and p.name[1:3].isdigit()):
        for f in sorted(d.iterdir()):
            if f.suffix in OUT_EXT or f.name == "meta.json":
                res[f.relative_to(base).as_posix()] = digest(f)
    return res


def png_text(p):
    data = p.read_bytes()
    i, texts = 8, []
    while i < len(data):
        n = int.from_bytes(data[i:i + 4], "big")
        typ = data[i + 4:i + 8]
        body = data[i + 8:i + 8 + n]
        if typ in (b"tEXt", b"iTXt"):
            texts.append(body.decode("latin-1", "replace"))
        elif typ == b"zTXt":
            k, _, rest = body.partition(b"\0")
            texts.append(k.decode("latin-1") + ":" + zlib.decompress(rest[1:]).decode("latin-1", "replace"))
        i += 12 + n
    return texts


def scan_anonymity(base):
    hits = []
    pats = [re.compile(x) for x in FORBIDDEN]
    for f in sorted(base.rglob("*")):
        if not f.is_file() or "inputs" in f.relative_to(base).parts or f.name in SKIP_TEXT:
            continue
        if f.suffix == ".png":
            txt = "\n".join(png_text(f))
        elif f.suffix in {".svg", ".py", ".csv", ".json", ".md", ".txt", ".log"}:
            txt = f.read_text(encoding="utf-8", errors="replace")
            if f.suffix == ".svg":
                txt = "\n".join(re.findall(r"<metadata>.*?</metadata>|<!--.*?-->|<title>.*?</title>", txt, re.S)) + \
                      "\n".join(re.findall(r"<text[^>]*>.*?</text>", txt, re.S))
        else:
            continue
        for pat in pats:
            for m in pat.finditer(txt):
                hits.append({"file": f.relative_to(base).as_posix(), "pattern": pat.pattern,
                             "context": txt[max(0, m.start() - 30):m.end() + 30].replace("\n", " ")})
    return hits


def font_env(meta):
    return "formal" if "SimSun" in meta.get("fonts", "") and "替代" not in meta.get("fonts", "") else "substitute"


def current_font_env():
    sys.path.insert(0, str(ROOT / "lib"))
    import figkit
    figkit.font_family()
    return figkit.FONT_MODE


def csv_close(a, b, tol=1e-12):
    """逐格比较两个 CSV：文本完全相同，数值相对差不超过 tol。返回最大相对差；结构不同返回 None。"""
    import csv as _csv
    ra = list(_csv.reader(a.read_text(encoding="utf-8-sig").splitlines()))
    rb = list(_csv.reader(b.read_text(encoding="utf-8-sig").splitlines()))
    if len(ra) != len(rb):
        return None
    worst = 0.0
    for x, y in zip(ra, rb):
        if len(x) != len(y):
            return None
        for u, v in zip(x, y):
            if u == v:
                continue
            try:
                fu, fv = float(u), float(v)
            except ValueError:
                return None
            worst = max(worst, abs(fu - fv) / max(1.0, abs(fu), abs(fv)))
    return worst if worst <= tol else -worst


def main():
    env = current_font_env()
    before = outputs(ROOT)
    envs = {}
    for d in sorted(p for p in ROOT.iterdir() if p.is_dir() and p.name[:1] in "FG" and p.name[1:3].isdigit()):
        m = d / "meta.json"
        if m.exists():
            envs[d.name] = font_env(json.loads(m.read_text(encoding="utf-8")))
    tmp = Path(tempfile.mkdtemp(prefix="figcheck_"))
    copy = tmp / "副本"
    shutil.copytree(ROOT, copy, ignore=shutil.ignore_patterns("__pycache__", "自检结果.json"))
    try:
        subprocess.run([sys.executable, "-B", "一键重绘全部.py"], cwd=copy, check=True,
                       stdout=subprocess.DEVNULL)
        after = outputs(copy)
        same = [k for k in before if envs.get(k.split("/")[0]) == env]
        cross = [k for k in before if envs.get(k.split("/")[0]) != env]
        png_mismatch = [k for k in same if k.endswith(".png") and after.get(k) != before[k]]
        other_mismatch = [k for k in same if not k.endswith(".png") and after.get(k) != before[k]]
        missing = sorted(set(before) ^ set(after))
        cross_report = {}
        for k in cross:
            if k.endswith(".csv"):
                r = csv_close(ROOT / k, copy / k)
                cross_report[k] = "逐字节相同" if after.get(k) == before[k] else (
                    "结构或文本不同" if r is None else (f"数值最大相对差 {abs(r):.1e}" + ("" if r >= 0 else "（超限）")))
            elif k.endswith("meta.json"):
                a = json.loads((ROOT / k).read_text(encoding="utf-8"))["key_values"]
                b = json.loads((copy / k).read_text(encoding="utf-8"))["key_values"]
                cross_report[k] = "key_values 相同" if a == b else "key_values 不同"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    hits = scan_anonymity(ROOT)
    res = {"font_environment": env,
           "figure_font_environment": envs,
           "files_compared_bytewise": len(same), "png_count_bytewise": sum(k.endswith(".png") for k in same),
           "png_byte_identical": not png_mismatch, "png_mismatch": png_mismatch,
           "other_mismatch": other_mismatch, "missing_or_extra": missing,
           "cross_font_environment_checks": cross_report,
           "anonymity_hits": hits}
    (ROOT / "自检结果.json").write_text(json.dumps(res, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"字体环境 {env}：逐字节比较 {len(same)} 个文件，其中 PNG {res['png_count_bytewise']} 个；"
          f"PNG 逐字节一致：{res['png_byte_identical']}；其他不一致 {len(other_mismatch)}；缺失或多出 {len(missing)}；"
          f"跨字体环境核对 {len(cross_report)} 项；匿名扫描命中 {len(hits)} 处。")


if __name__ == "__main__":
    main()
