"""Login page: self-contained (inline CSS, NO scripts, NO third-party fonts/CDNs). The access key is typed on this
page, so nothing from another origin may ever run here."""

LOGIN_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="referrer" content="no-referrer">
<meta name="theme-color" content="#000000">
<title>AI QUANT X - LOGIN</title>
<style>
*{box-sizing:border-box;-webkit-tap-highlight-color:transparent}
html,body{margin:0;background:#000;color:#f6f6f6;font-family:Inter,system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
body{min-height:100vh;display:flex;align-items:center;justify-content:center;padding:20px;
background:radial-gradient(120% 60% at 50% 0%,rgba(214,255,31,.10),transparent 60%),#000}
.card{width:100%;max-width:380px;padding:30px 24px;border-radius:30px;background:radial-gradient(130% 90% at 0% 0%,rgba(255,255,255,.08),transparent 46%),#131313;
border:1px solid rgba(255,255,255,.07);box-shadow:inset 0 1px 0 rgba(255,255,255,.09),0 20px 50px rgba(0,0,0,.6)}
h1{margin:0;text-align:center;font-size:26px;letter-spacing:.14em;font-weight:800}
h1 b{color:#d6ff1f}
.sub{margin:8px 0 26px;text-align:center;font-size:11px;letter-spacing:.2em;color:#8e8e8e;text-transform:uppercase}
label{display:block;margin-bottom:8px;font-size:11px;letter-spacing:.14em;color:#8e8e8e;text-transform:uppercase}
input{width:100%;min-height:52px;padding:0 18px;border-radius:99px;border:1px solid rgba(255,255,255,.08);background:#1b1b1b;color:#fff;font-size:16px;text-align:center;letter-spacing:.2em}
input:focus{outline:2px solid #d6ff1f;outline-offset:2px}
button{width:100%;min-height:52px;margin-top:20px;border:0;border-radius:99px;background:linear-gradient(180deg,rgba(255,255,255,.4),rgba(255,255,255,0) 60%),#d6ff1f;color:#000;font-weight:800;font-size:15px;letter-spacing:.12em;cursor:pointer;
box-shadow:inset 0 1px 0 rgba(255,255,255,.5),0 6px 20px rgba(214,255,31,.25)}
button:active{transform:scale(.98)}
.note{margin-top:24px;padding-top:16px;border-top:1px solid rgba(255,255,255,.07);text-align:center;font-size:10px;letter-spacing:.18em;color:#5e5e5e}
</style>
</head>
<body>
<form class="card" action="/api/login" method="POST">
<h1>AI QUANT <b>X</b></h1>
<p class="sub">System Authentication</p>
<label for="password">Access Key</label>
<input id="password" type="password" name="password" required autofocus autocomplete="current-password" placeholder="&bull;&bull;&bull;&bull;&bull;&bull;&bull;&bull;&bull;&bull;&bull;&bull;">
<button type="submit">INITIALIZE</button>
<p class="note">PAPER TRADING SIMULATION</p>
</form>
</body>
</html>
"""
