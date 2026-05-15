"""
激活码批量生成工具
用法: python generate.py 10 --prefix RUN --note "闲鱼1月批次"
"""
import argparse
import json
import os
import uuid
from datetime import datetime, date

CODES_FILE = os.path.join(os.path.dirname(__file__), "codes.json")

ALLOWED_CHARS = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # 去除易混淆字符 0/O/1/I


def random_suffix(length: int = 4) -> str:
    return "".join(uuid.uuid4().hex[:length].upper())


def generate_code(prefix: str = "RUN") -> str:
    now = datetime.now()
    seq = uuid.uuid4().hex[:4].upper()
    suffix = random_suffix(4)
    return f"{prefix}-{now.year}-{now.month:02d}{seq}-{suffix}"


def main():
    parser = argparse.ArgumentParser(description="生成激活码")
    parser.add_argument("count", type=int, default=10, help="生成数量")
    parser.add_argument("--prefix", default="RUN", help="前缀 (默认: RUN)")
    parser.add_argument("--max-bindings", type=int, default=1, help="每码绑定上限 (默认: 1)")
    parser.add_argument("--expires", default="", help="过期日期 YYYY-MM-DD (默认: 一年后)")
    parser.add_argument("--note", default="", help="备注")
    args = parser.parse_args()

    # Load existing
    if os.path.exists(CODES_FILE):
        with open(CODES_FILE, "r") as f:
            data = json.load(f)
    else:
        data = {"codes": {}}

    expires = args.expires or date.today().replace(year=date.today().year + 1).isoformat()
    created = date.today().isoformat()
    generated = []

    for i in range(args.count):
        code = generate_code(args.prefix)
        # Avoid collision
        while code in data["codes"]:
            code = generate_code(args.prefix)

        data["codes"][code] = {
            "created": created,
            "expires": expires,
            "max_bindings": args.max_bindings,
            "bindings": [],
            "note": args.note or f"批次 {datetime.now().strftime('%y%m%d')}-{i + 1}",
        }
        generated.append(code)

    with open(CODES_FILE, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"已生成 {len(generated)} 个激活码（max_bindings={args.max_bindings}，过期 {expires}）：\n")
    for code in generated:
        print(f"  {code}")
    print(f"\n已写入 {CODES_FILE}")


if __name__ == "__main__":
    main()
