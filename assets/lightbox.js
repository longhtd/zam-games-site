/* Screenshot preview: click any gallery screenshot to see it large. Esc / arrows / swipe / click outside. No libraries. */
(function () {
  'use strict';
  var imgs = Array.prototype.slice.call(document.querySelectorAll('.shots img'));
  if (!imgs.length) return;

  var css = '.zlb{position:fixed;inset:0;z-index:9999;display:none;align-items:center;justify-content:center;background:rgba(10,8,14,.92);-webkit-backdrop-filter:blur(6px);backdrop-filter:blur(6px);touch-action:pan-y}' +
    '.zlb.on{display:flex}' +
    '.zlb figure{margin:0;display:flex;flex-direction:column;align-items:center;max-width:100vw;max-height:100vh;padding:56px 56px 16px}' +
    '.zlb img{max-width:min(92vw,560px);max-height:calc(100vh - 150px);width:auto;height:auto;border-radius:18px;box-shadow:0 12px 48px rgba(0,0,0,.6);background:#111;user-select:none;-webkit-user-drag:none}' +
    '.zlb figcaption{color:#f3eee6;font:500 15px/1.4 system-ui,sans-serif;margin-top:12px;text-align:center;max-width:520px}' +
    '.zlb .zc{color:#bdb5a8;font-size:13px;margin-top:4px}' +
    '.zlb button{position:absolute;border:0;border-radius:50%;width:48px;height:48px;background:rgba(255,255,255,.14);color:#fff;font:600 24px/1 system-ui,sans-serif;cursor:pointer;display:flex;align-items:center;justify-content:center}' +
    '.zlb button:hover,.zlb button:focus-visible{background:rgba(255,255,255,.3);outline:2px solid #fff}' +
    '.zlb .zx{top:12px;right:12px}.zlb .zp{left:10px;top:50%;margin-top:-24px}.zlb .zn{right:10px;top:50%;margin-top:-24px}' +
    '.shots img{cursor:zoom-in}' +
    '@media (max-width:520px){.zlb figure{padding:56px 8px 12px}.zlb .zp,.zlb .zn{top:auto;bottom:14px;margin:0}.zlb .zp{left:14px}.zlb .zn{right:14px}}';
  var st = document.createElement('style'); st.textContent = css; document.head.appendChild(st);

  var box = document.createElement('div');
  box.className = 'zlb'; box.setAttribute('role', 'dialog'); box.setAttribute('aria-modal', 'true'); box.setAttribute('aria-label', 'Screenshot preview');
  box.innerHTML = '<button class="zx" type="button" aria-label="Close">\u00d7</button>' +
    '<button class="zp" type="button" aria-label="Previous screenshot">\u2039</button>' +
    '<figure><img alt=""><figcaption></figcaption><div class="zc"></div></figure>' +
    '<button class="zn" type="button" aria-label="Next screenshot">\u203a</button>';
  document.body.appendChild(box);
  var big = box.querySelector('img'), cap = box.querySelector('figcaption'), cnt = box.querySelector('.zc');
  var idx = 0, opener = null, x0 = null;

  function show(i) {
    idx = (i + imgs.length) % imgs.length;
    var el = imgs[idx], fig = el.closest('figure'), t = fig && fig.querySelector('figcaption');
    big.src = el.currentSrc || el.src; big.alt = el.alt || '';
    cap.textContent = t ? t.textContent : (el.alt || '');
    cnt.textContent = (idx + 1) + ' / ' + imgs.length;
    var nx = imgs[(idx + 1) % imgs.length]; if (nx) { var pre = new Image(); pre.src = nx.currentSrc || nx.src; }
  }
  function open(i, from) { opener = from || null; show(i); box.classList.add('on'); document.documentElement.style.overflow = 'hidden'; box.querySelector('.zx').focus(); }
  function close() { box.classList.remove('on'); document.documentElement.style.overflow = ''; big.removeAttribute('src'); if (opener && opener.focus) opener.focus(); }

  imgs.forEach(function (el, i) {
    el.setAttribute('tabindex', '0'); el.setAttribute('role', 'button');
    el.setAttribute('aria-label', 'View larger: ' + (el.alt || 'screenshot'));
    el.addEventListener('click', function () { open(i, el); });
    el.addEventListener('keydown', function (e) { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); open(i, el); } });
  });
  box.querySelector('.zx').addEventListener('click', close);
  box.querySelector('.zp').addEventListener('click', function () { show(idx - 1); });
  box.querySelector('.zn').addEventListener('click', function () { show(idx + 1); });
  box.addEventListener('click', function (e) { if (e.target === box || e.target.tagName === 'FIGURE') close(); });
  document.addEventListener('keydown', function (e) {
    if (!box.classList.contains('on')) return;
    if (e.key === 'Escape') close();
    else if (e.key === 'ArrowLeft') show(idx - 1);
    else if (e.key === 'ArrowRight') show(idx + 1);
    else if (e.key === 'Tab') { var f = box.querySelectorAll('button'); var a = document.activeElement; if (e.shiftKey && a === f[0]) { e.preventDefault(); f[f.length - 1].focus(); } else if (!e.shiftKey && a === f[f.length - 1]) { e.preventDefault(); f[0].focus(); } }
  });
  box.addEventListener('touchstart', function (e) { x0 = e.changedTouches[0].clientX; }, { passive: true });
  box.addEventListener('touchend', function (e) { if (x0 === null) return; var dx = e.changedTouches[0].clientX - x0; x0 = null; if (Math.abs(dx) > 50) show(idx + (dx < 0 ? 1 : -1)); }, { passive: true });
})();
