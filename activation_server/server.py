"""
激活码验证服务器 + Web 管理面板
访问 http://localhost:9000/admin 管理激活码
"""
import json
import os
import uuid
from datetime import datetime, date, timezone
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel

app = FastAPI(title="Activation Server")

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

CODES_FILE = os.path.join(os.path.dirname(__file__), "codes.json")


def load_codes() -> dict:
    if not os.path.exists(CODES_FILE):
        return {"codes": {}}
    with open(CODES_FILE, "r") as f:
        return json.load(f)


def save_codes(data: dict):
    with open(CODES_FILE, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# ── Client validation ──

class ValidateRequest(BaseModel):
    code: str
    machine_id: str


@app.post("/validate")
def validate(req: ValidateRequest):
    data = load_codes()
    codes = data.get("codes", {})

    entry = codes.get(req.code.upper())
    if not entry:
        raise HTTPException(status_code=400, detail="无效的激活码")

    if entry.get("expires") and datetime.fromisoformat(entry["expires"]).replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="激活码已过期")

    bindings = entry.get("bindings", [])
    max_bindings = entry.get("max_bindings", 10)

    if req.machine_id in bindings:
        return {"ok": True, "message": "已激活"}

    if len(bindings) >= max_bindings:
        raise HTTPException(status_code=400, detail="激活码已达使用上限")

    bindings.append(req.machine_id)
    entry["bindings"] = bindings
    data["codes"] = codes
    save_codes(data)

    return {"ok": True, "message": "激活成功", "binding_index": len(bindings), "max_bindings": max_bindings}


# ── Admin panel ──

@app.get("/admin", response_class=HTMLResponse)
def admin_panel():
    return ADMIN_HTML


@app.get("/admin/api/codes")
def admin_list_codes():
    data = load_codes()
    result = []
    for code, entry in data.get("codes", {}).items():
        result.append({
            "code": code,
            "created": entry.get("created", ""),
            "expires": entry.get("expires", ""),
            "max_bindings": entry.get("max_bindings", 1),
            "used": len(entry.get("bindings", [])),
            "bindings": entry.get("bindings", []),
            "note": entry.get("note", ""),
        })
    result.sort(key=lambda x: x["created"], reverse=True)
    return {"codes": result, "total": len(result)}


class GenerateRequest(BaseModel):
    count: int = 10
    prefix: str = "RUN"
    max_bindings: int = 1
    expires: str = ""
    note: str = ""


@app.post("/admin/api/generate")
def admin_generate(req: GenerateRequest):
    data = load_codes()

    expires = req.expires or date.today().replace(year=date.today().year + 1).isoformat()
    created = date.today().isoformat()
    generated = []

    for i in range(req.count):
        while True:
            seq = uuid.uuid4().hex[:4].upper()
            suffix = uuid.uuid4().hex[:4].upper()
            code = f"{req.prefix}-{datetime.now().year}-{datetime.now().month:02d}{seq}-{suffix}"
            if code not in data["codes"]:
                break

        data["codes"][code] = {
            "created": created,
            "expires": expires,
            "max_bindings": req.max_bindings,
            "bindings": [],
            "note": req.note or f"批次 {datetime.now().strftime('%y%m%d')}-{i + 1}",
        }
        generated.append(code)

    save_codes(data)
    return {"ok": True, "generated": len(generated), "codes": generated}


@app.delete("/admin/api/codes/{code}")
def admin_delete_code(code: str):
    data = load_codes()
    if code not in data.get("codes", {}):
        raise HTTPException(status_code=404, detail="激活码不存在")
    del data["codes"][code]
    save_codes(data)
    return {"ok": True}


@app.get("/health")
def health():
    return {"status": "ok"}


# ── Admin HTML (single page, Tailwind CDN) ──

ADMIN_HTML = """<!doctype html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>激活码管理</title>
<script src="https://cdn.tailwindcss.com"></script>
<script src="https://unpkg.com/react@18/umd/react.production.min.js" crossorigin></script>
<script src="https://unpkg.com/react-dom@18/umd/react-dom.production.min.js" crossorigin></script>
<script>
tailwind.config = {
  theme: {
    extend: {
      colors: {
        bg: '#0A0C12',
        card: '#12141C',
        border: 'rgba(255,255,255,0.06)',
        accent: '#DC2626',
        muted: '#6B7280',
      }
    }
  }
}
</script>
</head>
<body class="bg-bg text-[#D1D5DB] min-h-screen font-sans">
<div id="app"></div>
<script>
const API = '/admin/api';

function App() {
  const [tab, setTab] = React.useState('list');
  const [codes, setCodes] = React.useState([]);
  const [msg, setMsg] = React.useState('');
  const [loading, setLoading] = React.useState(false);

  // Generate form
  const [gCount, setGCount] = React.useState(10);
  const [gPrefix, setGPrefix] = React.useState('RUN');
  const [gBindings, setGBindings] = React.useState(1);
  const [gExpires, setGExpires] = React.useState('');
  const [gNote, setGNote] = React.useState('');

  const fetchCodes = async () => {
    try {
      const r = await fetch(API + '/codes');
      const d = await r.json();
      setCodes(d.codes || []);
    } catch(e) {}
  };

  React.useEffect(() => { fetchCodes() }, []);

  const showMsg = (text) => { setMsg(text); setTimeout(() => setMsg(''), 4000) };

  const handleGenerate = async () => {
    setLoading(true);
    try {
      const r = await fetch(API + '/generate', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ count: gCount, prefix: gPrefix, max_bindings: gBindings, expires: gExpires, note: gNote }),
      });
      const d = await r.json();
      if (d.ok) {
        showMsg('已生成 ' + d.generated + ' 个激活码');
        await fetchCodes();
        setTab('list');
      }
    } catch(e) { showMsg('生成失败') }
    setLoading(false);
  };

  const handleDelete = async (code) => {
    if (!confirm('删除 ' + code + ' ?')) return;
    try {
      await fetch(API + '/codes/' + code, { method: 'DELETE' });
      showMsg('已删除');
      await fetchCodes();
    } catch(e) { showMsg('删除失败') }
  };

  const handleCopyAll = () => {
    const unused = codes.filter(c => c.used === 0);
    navigator.clipboard.writeText(unused.map(c => c.code).join('\\n'));
    showMsg('已复制 ' + unused.length + ' 个未使用激活码');
  };

  const statusColor = (c) => {
    if (c.used >= c.max_bindings) return 'bg-red-900/30 text-red-400 border-red-800/30';
    if (c.expires && new Date(c.expires) < new Date()) return 'bg-amber-900/20 text-amber-400 border-amber-800/20';
    return 'bg-emerald-900/20 text-emerald-400 border-emerald-800/20';
  };

  const statusLabel = (c) => {
    if (c.used >= c.max_bindings) return '已用完';
    if (c.expires && new Date(c.expires) < new Date()) return '已过期';
    return c.used > 0 ? '已激活' : '未使用';
  };

  const btn = 'px-4 py-2.5 rounded-lg text-sm font-medium transition-colors';
  const btnPrimary = btn + ' bg-accent text-white hover:bg-red-700 disabled:opacity-40';
  const btnSecondary = btn + ' border border-border text-muted hover:text-[#D1D5DB] hover:bg-white/[0.03]';
  const input = 'w-full px-3 py-2.5 bg-white/[0.03] border border-border rounded-lg text-sm text-[#F1F1F3] placeholder-muted focus:outline-none focus:ring-2 focus:ring-accent/30';
  const label = 'block text-xs text-muted mb-1.5 ml-1';

  return React.createElement('div', { className: 'max-w-5xl mx-auto p-6 space-y-6' },
    // Header
    React.createElement('div', { className: 'flex items-center justify-between' },
      React.createElement('div', null,
        React.createElement('h1', { className: 'text-2xl font-bold text-[#F1F1F3]' }, '激活码管理'),
        React.createElement('p', { className: 'text-sm text-muted mt-1' }, codes.length + ' 个激活码')
      ),
      React.createElement('div', { className: 'flex gap-2' },
        React.createElement('button', { onClick: () => setTab('list'), className: tab === 'list' ? btnPrimary : btnSecondary }, '列表'),
        React.createElement('button', { onClick: () => setTab('generate'), className: tab === 'generate' ? btnPrimary : btnSecondary }, '生成'),
      )
    ),

    // Toast
    msg && React.createElement('div', { className: 'fixed top-4 right-4 z-50 px-4 py-3 bg-card border border-border rounded-lg shadow-lg text-sm text-emerald-400 flex items-center gap-2' },
      React.createElement('span', null, msg)
    ),

    // List tab
    tab === 'list' && React.createElement('div', { className: 'space-y-3' },
      React.createElement('div', { className: 'flex items-center gap-3' },
        React.createElement('button', { onClick: handleCopyAll, className: btnSecondary }, '复制全部未使用'),
        React.createElement('span', { className: 'text-xs text-muted' }, '点击激活码可复制单个')
      ),
      React.createElement('div', { className: 'bg-card border border-border rounded-xl overflow-hidden' },
        React.createElement('div', { className: 'grid grid-cols-[1fr_80px_100px_80px_auto_40px] gap-3 px-5 py-3 bg-white/[0.02] border-b border-border text-xs text-muted font-medium' },
          React.createElement('span', null, '激活码'),
          React.createElement('span', null, '绑定数'),
          React.createElement('span', null, '过期'),
          React.createElement('span', null, '状态'),
          React.createElement('span', null, '备注'),
          React.createElement('span', null),
        ),
        React.createElement('div', { className: 'divide-y divide-border/50' },
          codes.map(c =>
            React.createElement('div', {
              key: c.code,
              className: 'grid grid-cols-[1fr_80px_100px_80px_auto_40px] gap-3 px-5 py-3 items-center hover:bg-white/[0.01] transition-colors'
            },
              React.createElement('button', {
                onClick: () => { navigator.clipboard.writeText(c.code); showMsg('已复制 ' + c.code) },
                className: 'text-sm text-[#F1F1F3] font-mono text-left hover:text-accent transition-colors truncate'
              }, c.code),
              React.createElement('span', { className: 'text-xs text-muted' }, c.used + '/' + c.max_bindings),
              React.createElement('span', { className: 'text-xs text-muted' }, c.expires || '--'),
              React.createElement('span', {
                className: 'text-xs px-2 py-0.5 rounded-full border inline-block text-center ' + statusColor(c)
              }, statusLabel(c)),
              React.createElement('span', { className: 'text-xs text-muted truncate' }, c.note || '--'),
              React.createElement('button', {
                onClick: () => handleDelete(c.code),
                className: 'text-muted hover:text-red-400 text-xs transition-colors text-center'
              }, '✕'),
            )
          )
        )
      )
    ),

    // Generate tab
    tab === 'generate' && React.createElement('div', { className: 'bg-card border border-border rounded-xl p-6 max-w-lg space-y-4' },
      React.createElement('div', { className: 'grid grid-cols-2 gap-4' },
        React.createElement('div', null,
          React.createElement('label', { className: label }, '数量'),
          React.createElement('input', { type: 'number', value: gCount, onChange: e => setGCount(parseInt(e.target.value) || 1), min: 1, max: 500, className: input }),
        ),
        React.createElement('div', null,
          React.createElement('label', { className: label }, '前缀'),
          React.createElement('input', { value: gPrefix, onChange: e => setGPrefix(e.target.value), className: input }),
        ),
        React.createElement('div', null,
          React.createElement('label', { className: label }, '每码绑定上限'),
          React.createElement('input', { type: 'number', value: gBindings, onChange: e => setGBindings(parseInt(e.target.value) || 1), min: 1, max: 100, className: input }),
        ),
        React.createElement('div', null,
          React.createElement('label', { className: label }, '过期日期（留空默认一年）'),
          React.createElement('input', { type: 'date', value: gExpires, onChange: e => setGExpires(e.target.value), className: input }),
        ),
      ),
      React.createElement('div', null,
        React.createElement('label', { className: label }, '备注'),
        React.createElement('input', { value: gNote, onChange: e => setGNote(e.target.value), placeholder: '如：闲鱼1月批次', className: input }),
      ),
      React.createElement('button', { onClick: handleGenerate, disabled: loading, className: btnPrimary + ' w-full' },
        loading ? '生成中...' : '生成 ' + gCount + ' 个激活码'
      )
    ),
  );
}

// Boot
const root = ReactDOM.createRoot(document.getElementById('app'));
root.render(React.createElement(App));
</script>
</body>
</html>"""


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=9000)
