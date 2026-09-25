"""交付前自检：
1. 复现：把本文件夹复制到临时目录，在副本中运行“一键重绘全部.py”，逐字节比较全部 PNG、SVG、CSV 与 meta.json。
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
FORBIDDEN = [r"[A-Za-z]:[\\/]", r"\\Users\\", r"/Users/", r"ZhuanZ", r"Kaneshiro", r"privaterelay", r"Desktop",
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
        elif f.suffix in {".svg", ".py", ".csv", ".json", ".md", ".txt"}:
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


def main():
    before = outputs(ROOT)
    tmp = Path(tempfile.mkdtemp(prefix="figcheck_"))
    copy = tmp / "副本"
    shutil.copytree(ROOT, copy, ignore=shutil.ignore_patterns("__pycache__", "自检结果.json"))
    try:
        subprocess.run([sys.executable, "-B", "一键重绘全部.py"], cwd=copy, check=True,
                       stdout=subprocess.DEVNULL)
        after = outputs(copy)
        png_mismatch = [k for k in before if k.endswith(".png") and after.get(k) != before[k]]
        other_mismatch = [k for k in before if not k.endswith(".png") and after.get(k) != before[k]]
        missing = sorted(set(before) ^ set(after))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    hits = scan_anonymity(ROOT)
    res = {"files_compared": len(before), "png_count": sum(k.endswith(".png") for k in before),
           "png_byte_identical": not png_mismatch, "png_mismatch": png_mismatch,
           "other_mismatch": other_mismatch, "missing_or_extra": missing,
           "anonymity_hits": hits}
    (ROOT / "自检结果.json").write_text(json.dumps(res, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"比较 {len(before)} 个文件，其中 PNG {res['png_count']} 个；PNG 逐字节一致：{res['png_byte_identical']}；"
          f"其他不一致 {len(other_mismatch)}；匿名扫描命中 {len(hits)} 处。")


if __name__ == "__main__":
    main()
