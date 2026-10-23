/*
 * Zamverse Wall of Honor (public). Vanilla JS, no libraries.
 * Reads the public feed "zamverse.honors" v1 from the Honor Worker and renders it with
 * createElement/textContent ONLY. Supporter names are user input: never use innerHTML with feed data.
 *
 * Mounts:
 *   #honor-wall[data-honor-page]   full wall (all games, tier sections, filter chips) on /honor/
 *   [data-honor-app="<slug>"]      compact strip of the latest supporters of one game on its page
 */
(function (root) {
  'use strict';

  var FEED_URL = 'https://honor-worker.longhtd.workers.dev/honors.json';
  var TIMEOUT_MS = 5000;
  var MAX_BYTES = 1024 * 1024;
  var MAX_SUPPORTERS = 5000;
  var PAGE_SIZE = 60;
  var STRIP_COUNT = 6;
  var CACHE_KEY = 'zv_honor_feed_v1';
  var PLAY = 'https://play.google.com/store/apps/details?id=com.zamverse.';
  // Games whose Google Play listing is live. Others link to their page here until launch.
  var LIVE_SLUGS = {wordlodge: 1, arrowaway: 1, snugcats: 1, pixelpicnic: 1, styledrop: 1, glimmergrove: 1, burrowbuddy: 1};
  var PLAY_REF = '&referrer=utm_source%3Dgames_site%26utm_medium%3Dhonor_wall';

  // Games that have a Wall of Honor (Burrow Buddy, made for families, has none).
  var GAMES = [
    { slug: 'wordlodge', name: 'Word Lodge' },
    { slug: 'glimmergrove', name: 'Glimmer Grove' },
    { slug: 'snugcats', name: 'Snug Cats' },
    { slug: 'pixelpicnic', name: 'Pixel Picnic' },
    { slug: 'styledrop', name: 'Style Drop' },
    { slug: 'arrowaway', name: 'Arrow Away' }
  ];
  function gameBySlug(slug) {
    for (var i = 0; i < GAMES.length; i++) if (GAMES[i].slug === slug) return GAMES[i];
    return null;
  }

  // ------------------------------------------------------------------ feed location
  function isLocalHost() {
    var h = root.location && root.location.hostname;
    return h === 'localhost' || h === '127.0.0.1' || h === '[::1]' || h === '::1';
  }
  function feedUrl() {
    // Test override, honoured ONLY on localhost / 127.0.0.1 / [::1]; ignored on the real site.
    if (isLocalHost()) {
      try {
        var q = new URLSearchParams(root.location.search).get('feed');
        if (q && q.length < 600) return q;
      } catch (e) { /* ignore */ }
    }
    return FEED_URL;
  }

  // ------------------------------------------------------------------ normalise (defensive: the feed is data, not code)
  function cleanText(v, max) {
    if (typeof v !== 'string') return '';
    var s = v.replace(/[\u0000-\u001f\u007f-\u009f\u200b-\u200f\u2028-\u202e\u2060-\u206f\ufeff]/g, '')
      .replace(/\s+/g, ' ').trim();
    var chars = Array.from(s);
    if (chars.length > max) s = chars.slice(0, max).join('').trim();
    return s;
  }
  function num(v, lo, hi, dflt) {
    var n = Number(v);
    if (!isFinite(n)) return dflt;
    return Math.min(hi, Math.max(lo, n));
  }

  function normalize(raw) {
    if (!raw || typeof raw !== 'object' || Array.isArray(raw)) throw new Error('bad_feed');
    if (raw.schema !== 'zamverse.honors' || raw.schemaVersion !== 1) throw new Error('unsupported_feed');
    var out = {
      sequence: num(raw.sequence, 0, 9007199254740991, 0),
      updated: cleanText(raw.updated, 40),
      ttlMinutes: num(raw.ttlMinutes, 1, 1440, 15),
      killSwitch: raw.killSwitch === true,
      empty: raw.message && typeof raw.message === 'object' ? cleanText(raw.message.empty, 200) : '',
      tiers: {},
      supporters: []
    };
    if (out.killSwitch) return out; // every honor surface hides; do not even read the supporters

    var tiers = Array.isArray(raw.tiers) ? raw.tiers : [];
    for (var i = 0; i < tiers.length && i < 20; i++) {
      var t = tiers[i];
      if (!t || typeof t !== 'object') continue;
      var tid = cleanText(t.id, 16);
      if (!tid) continue;
      var m = /^t(\d+)$/.exec(tid);
      out.tiers[tid] = {
        id: tid,
        rank: num(t.rank, 0, 99, m ? Number(m[1]) : 0),
        label: cleanText(t.label, 24) || 'Supporter',
        podium: Array.isArray(t.grants) && t.grants.indexOf('gold_badge_podium') !== -1
      };
    }
    var list = Array.isArray(raw.supporters) ? raw.supporters : [];
    var seen = {};
    for (var j = 0; j < list.length && out.supporters.length < MAX_SUPPORTERS; j++) {
      var s = list[j];
      if (!s || typeof s !== 'object') continue;
      var id = cleanText(s.id, 40);
      if (id) { if (seen[id]) continue; seen[id] = true; }
      var app = typeof s.app === 'string' && /^[a-z0-9]{1,32}$/.test(s.app) ? s.app : '';
      var tierId = cleanText(s.tierId || s.tier, 16);
      var anonymous = s.anonymous === true;
      var name = anonymous ? '' : cleanText(s.displayName, 32);
      var at = cleanText(s.at, 40);
      var time = Date.parse(at);
      out.supporters.push({
        id: id, app: app, tierId: tierId, name: name, anonymous: !name,
        at: isNaN(time) ? '' : at, time: isNaN(time) ? 0 : time, order: j
      });
    }
    return out;
  }

  function tierInfo(data, tierId) {
    return data.tiers[tierId] || { id: tierId, rank: 0, label: 'Supporter', podium: false };
  }

  // ------------------------------------------------------------------ transport
  function fetchJson(url) {
    return new Promise(function (resolve, reject) {
      var done = false;
      var ctrl = typeof AbortController !== 'undefined' ? new AbortController() : null;
      var timer = setTimeout(function () {
        if (done) return;
        done = true;
        if (ctrl) { try { ctrl.abort(); } catch (e) { /* ignore */ } }
        reject(new Error('timeout'));
      }, TIMEOUT_MS);
      function finish(err, val) {
        if (done) return;
        done = true;
        clearTimeout(timer);
        if (err) reject(err); else resolve(val);
      }
      var opts = { cache: 'no-cache', credentials: 'omit', mode: 'cors' };
      if (ctrl) opts.signal = ctrl.signal;
      root.fetch(url, opts).then(function (r) {
        if (!r.ok) throw new Error('http_' + r.status);
        return r.text();
      }).then(function (text) {
        if (text.length > MAX_BYTES) throw new Error('too_large');
        finish(null, JSON.parse(text));
      }).catch(function (e) { finish(e instanceof Error ? e : new Error('network')); });
    });
  }

  // sessionStorage is only a fallback for failed refreshes and the "sequence never goes backwards" rule.
  function readCache(url) {
    try {
      var c = JSON.parse(root.sessionStorage.getItem(CACHE_KEY) || 'null');
      if (c && c.url === url && c.data && typeof c.data.sequence === 'number') return c.data;
    } catch (e) { /* storage blocked */ }
    return null;
  }
  function writeCache(url, data) {
    try { root.sessionStorage.setItem(CACHE_KEY, JSON.stringify({ url: url, data: data })); } catch (e) { /* ignore */ }
  }

  var inflight = null;
  // Resolves to { data, stale }. Rejects only when there is neither a fresh nor a cached feed.
  function load() {
    if (inflight) return inflight;
    var url = feedUrl();
    var cached = readCache(url);
    inflight = fetchJson(url).then(function (raw) {
      var d = normalize(raw);
      if (cached && cached.sequence > d.sequence) return { data: cached, stale: true }; // client rejects a lower sequence
      writeCache(url, d);
      return { data: d, stale: false };
    }).catch(function (err) {
      if (cached) return { data: cached, stale: true };
      throw err;
    });
    var clear = function () { inflight = null; };
    inflight.then(clear, clear);
    return inflight;
  }

  // ------------------------------------------------------------------ DOM helpers (textContent only)
  function el(tag, cls, text) {
    var n = root.document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  }
  function clear(node) { while (node.firstChild) node.removeChild(node.firstChild); }
  function plural(n, one, many) { return n + ' ' + (n === 1 ? one : many); }
  function fmtDate(time) {
    if (!time) return '';
    try {
      return new Date(time).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric', timeZone: 'UTC' });
    } catch (e) { return new Date(time).toISOString().slice(0, 10); }
  }
  function fmtStamp(iso) {
    var t = Date.parse(iso);
    if (isNaN(t)) return '';
    try {
      return new Date(t).toLocaleString('en-US', { year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', timeZone: 'UTC', timeZoneName: 'short' });
    } catch (e) { return iso; }
  }
  function playLink(game, cls) {
    if (!LIVE_SLUGS[game.slug]) {
      var s = el('a', cls || 'btn', game.name + ' (coming soon)');
      s.href = '/' + game.slug + '/';
      return s;
    }
    var a = el('a', cls || 'btn', 'Get ' + game.name + ' on Google Play');
    a.href = PLAY + game.slug + PLAY_REF;
    a.rel = 'noopener';
    return a;
  }

  function card(s, data, withGame) {
    var info = tierInfo(data, s.tierId);
    var li = el('li', 'hcard rank-' + Math.min(6, Math.max(0, info.rank)) + (info.podium ? ' podium' : ''));
    li.appendChild(el('p', 'hname' + (s.anonymous ? ' anon' : ''), s.anonymous ? 'Anonymous supporter' : s.name));
    var badge = el('p', 'hmeta');
    var b = el('span', 'hbadge', info.label);
    badge.appendChild(b);
    li.appendChild(badge);
    if (withGame) {
      var g = gameBySlug(s.app);
      var line = el('p', 'hmeta');
      line.appendChild(root.document.createTextNode('Supported '));
      if (g) {
        var a = el('a', null, g.name);
        a.href = '/' + g.slug + '/';
        line.appendChild(a);
      } else {
        line.appendChild(root.document.createTextNode('a Zamverse game'));
      }
      li.appendChild(line);
    }
    if (s.time) {
      var dl = el('p', 'hmeta');
      var tm = el('time', null, fmtDate(s.time));
      tm.setAttribute('datetime', new Date(s.time).toISOString());
      dl.appendChild(tm);
      li.appendChild(dl);
    }
    return li;
  }

  // ------------------------------------------------------------------ full wall (/honor/)
  function initPage(host) {
    var statusEl = root.document.getElementById('honor-status');
    var filtersEl = root.document.getElementById('honor-filters');
    var state = { data: null, filter: 'all', stale: false, timer: null, last: 0 };

    function setStatus(parts) {
      if (!statusEl) return;
      clear(statusEl);
      parts.forEach(function (p) { statusEl.appendChild(el('span', p.cls || '', p.text)); });
    }
    function busy(v) { host.setAttribute('aria-busy', v ? 'true' : 'false'); }

    function messageBox(title, text, extra) {
      clear(host);
      var box = el('div', 'hempty');
      box.appendChild(el('h2', null, title));
      if (text) box.appendChild(el('p', null, text));
      if (extra) box.appendChild(extra);
      host.appendChild(box);
    }

    function counts(data) {
      var c = { all: data.supporters.length };
      GAMES.forEach(function (g) { c[g.slug] = 0; });
      data.supporters.forEach(function (s) { if (s.app in c) c[s.app]++; });
      return c;
    }

    function renderChips(data) {
      if (!filtersEl) return;
      clear(filtersEl);
      if (!data.supporters.length) { filtersEl.hidden = true; return; }
      var c = counts(data);
      var items = [{ slug: 'all', name: 'All games' }].concat(GAMES);
      items.forEach(function (g) {
        var btn = el('button', 'hchip', g.name + ' (' + c[g.slug] + ')');
        btn.type = 'button';
        btn.setAttribute('data-filter', g.slug);
        btn.setAttribute('aria-pressed', state.filter === g.slug ? 'true' : 'false');
        btn.addEventListener('click', function () {
          state.filter = g.slug;
          var all = filtersEl.querySelectorAll('.hchip');
          for (var i = 0; i < all.length; i++) {
            all[i].setAttribute('aria-pressed', all[i].getAttribute('data-filter') === g.slug ? 'true' : 'false');
          }
          renderWall(state.data);
        });
        filtersEl.appendChild(btn);
      });
      filtersEl.hidden = false;
    }

    function emptyAll(data) {
      var wrap = el('div', 'hplay');
      GAMES.forEach(function (g) { wrap.appendChild(playLink(g, 'btn hbtn')); });
      messageBox('Be the first on the wall',
        (data.empty || 'No supporters yet. Your name could be the first on this wall.') +
        ' Supporters of any Zamverse game appear here and inside the apps.', wrap);
    }

    function renderWall(data) {
      busy(true);
      clear(host);
      var filter = state.filter;
      var all = data.supporters;
      var list = filter === 'all' ? all : all.filter(function (s) { return s.app === filter; });
      var c = counts(data);

      var parts = [{ cls: 'honor-count', text: filter === 'all' ? plural(all.length, 'supporter', 'supporters') : list.length + ' of ' + plural(all.length, 'supporter', 'supporters') }];
      var stamp = fmtStamp(data.updated);
      if (stamp) parts.push({ text: 'Last updated ' + stamp });
      if (state.stale) parts.push({ cls: 'honor-warn', text: 'Showing the last list we could load.' });
      setStatus(parts);

      if (!all.length) { emptyAll(data); busy(false); return; }
      if (!list.length) {
        var g = gameBySlug(filter);
        var extra = g ? playLink(g, 'btn primary') : null;
        messageBox('No supporters of ' + (g ? g.name : 'this game') + ' yet', 'Be the first to appear on the wall.', extra);
        busy(false);
        return;
      }

      // tier sections: highest rank first; inside a tier the earliest to reach it first (the spec does not rank by amount)
      var groups = {};
      list.forEach(function (s) { (groups[s.tierId] = groups[s.tierId] || []).push(s); });
      var ids = Object.keys(groups).sort(function (a, b) {
        var d = tierInfo(data, b).rank - tierInfo(data, a).rank;
        return d !== 0 ? d : (a < b ? -1 : 1);
      });
      ids.forEach(function (tid) {
        var info = tierInfo(data, tid);
        var items = groups[tid].slice().sort(function (a, b) { return a.time - b.time || a.order - b.order; });
        var sec = el('section', 'honor-tier' + (info.podium ? ' podium' : ''));
        var h = el('h2', null, info.label + ' ');
        h.appendChild(el('small', null, '(' + items.length + ')'));
        sec.appendChild(h);
        var ul = el('ul', 'hgrid');
        var shown = 0;
        var more = null;
        function showMore() {
          var end = Math.min(items.length, shown + PAGE_SIZE);
          for (; shown < end; shown++) ul.appendChild(card(items[shown], data, true));
          if (more) {
            if (shown >= items.length) { more.remove(); more = null; }
            else more.textContent = 'Show ' + Math.min(PAGE_SIZE, items.length - shown) + ' more';
          }
        }
        sec.appendChild(ul);
        if (items.length > PAGE_SIZE) {
          more = el('button', 'hchip hmore', '');
          more.type = 'button';
          more.addEventListener('click', showMore);
          sec.appendChild(more);
        }
        showMore();
        host.appendChild(sec);
      });
      busy(false);
    }

    function render(res) {
      state.data = res.data;
      state.stale = res.stale;
      state.last = Date.now();
      if (res.data.killSwitch) {
        if (filtersEl) filtersEl.hidden = true;
        setStatus([{ text: 'The wall is resting.' }]);
        messageBox('The wall is resting', 'The Wall of Honor is taking a short break. Please check back soon.');
        busy(false);
        return;
      }
      renderChips(res.data);
      renderWall(res.data);
    }

    function schedule() {
      if (state.timer) clearTimeout(state.timer);
      var minutes = state.data ? state.data.ttlMinutes : 15;
      state.timer = setTimeout(refresh, minutes * 60000);
    }
    function refresh() {
      if (root.document.hidden) { schedule(); return; }
      load().then(render, function () { /* keep what is on screen */ }).then(schedule, schedule);
    }

    function start() {
      busy(true);
      load().then(render, function () {
        if (filtersEl) filtersEl.hidden = true;
        setStatus([{ text: 'Could not load the wall.' }]);
        var retry = el('button', 'btn primary hbtn', 'Try again');
        retry.type = 'button';
        retry.addEventListener('click', function () { setStatus([{ text: 'Loading the Wall of Honor...' }]); start(); });
        messageBox('We could not load the Wall of Honor', 'Please check your connection and try again in a moment.', retry);
        busy(false);
      }).then(schedule, schedule);
    }
    root.document.addEventListener('visibilitychange', function () {
      if (!root.document.hidden && state.data && Date.now() - state.last > state.data.ttlMinutes * 60000) refresh();
    });
    start();
  }

  // ------------------------------------------------------------------ per-game strip
  function initStrip(section) {
    var slug = section.getAttribute('data-honor-app');
    var game = gameBySlug(slug);
    var body = section.querySelector('[data-honor-body]');
    if (!game || !body) return;
    function render(res) {
      var data = res.data;
      if (data.killSwitch) { section.hidden = true; return; } // resting: hide every honor surface
      var mine = data.supporters.filter(function (s) { return s.app === slug; })
        .sort(function (a, b) { return b.time - a.time || a.order - b.order; });
      clear(body);
      if (!mine.length) {
        var e = el('div', 'hstripempty');
        e.appendChild(el('p', null, 'The wall is waiting for its first ' + game.name + ' supporter. Supporters are thanked here, on the full wall and inside the game.'));
        body.appendChild(e);
      } else {
        var ul = el('ul', 'hgrid');
        mine.slice(0, STRIP_COUNT).forEach(function (s) { ul.appendChild(card(s, data, false)); });
        body.appendChild(ul);
      }
      var more = el('p', 'hstripmore');
      var a = el('a', 'btn ghost hbtn', mine.length ? 'See the full Wall of Honor (' + plural(mine.length, 'supporter', 'supporters') + ' for ' + game.name + ')' : 'See the Wall of Honor');
      a.href = '/honor/';
      more.appendChild(a);
      body.appendChild(more);
    }
    load().then(render, function () { /* keep the static fallback text and link */ });
  }

  // ------------------------------------------------------------------ boot
  function boot() {
    var page = root.document.querySelector('[data-honor-page]');
    if (page) initPage(page);
    var strips = root.document.querySelectorAll('[data-honor-app]');
    for (var i = 0; i < strips.length; i++) initStrip(strips[i]);
  }

  var api = { normalize: normalize, cleanText: cleanText, feedUrl: feedUrl, load: load, GAMES: GAMES, boot: boot };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  root.ZamHonorWall = api;
  if (root.document) {
    if (root.document.readyState === 'loading') root.document.addEventListener('DOMContentLoaded', boot);
    else boot();
  }
})(typeof window !== 'undefined' ? window : globalThis);
