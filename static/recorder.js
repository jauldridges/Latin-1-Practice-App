// The teacher's recorder, for word audio (/teacher/audio) and DI mode's
// sentences and model screens (/teacher/di/audio).
//
// <script src="recorder.js" data-save-url="..." data-rate="22050" data-max="8000">
// Each row is an <li> with a button.rec (data-key; optional data-max in ms and
// data-hint), a button.say to play it back, and optionally data-label.
(function () {
  // Recorded as plain 16-bit WAV, built here from the microphone's samples,
  // because every browser plays WAV -- the compressed formats a browser
  // records natively do not all play on every student's phone.
  var me = document.currentScript;
  var RATE = Number(me.getAttribute('data-rate') || 22050), MAX_MS = Number(me.getAttribute('data-max') || 8000);
  var saveUrl = me.getAttribute('data-save-url');
  var msg = document.getElementById('recmsg');
  var stream = null, ctx = null, proc = null, src = null, chunks = [], active = null, timer = null;

  function say(text, bad) { msg.textContent = text; msg.className = 'recmsg' + (bad ? ' bad' : ''); }

  function start(btn) {
    var go = stream ? Promise.resolve(stream) : navigator.mediaDevices.getUserMedia(
      {audio: {echoCancellation: false, noiseSuppression: true, autoGainControl: true}});
    go.then(function (s) {
      stream = s;
      ctx = ctx || new (window.AudioContext || window.webkitAudioContext)();
      return ctx.resume();
    }).then(function () {
      chunks = [];
      src = ctx.createMediaStreamSource(stream);
      proc = ctx.createScriptProcessor(4096, 1, 1);
      proc.onaudioprocess = function (e) { chunks.push(new Float32Array(e.inputBuffer.getChannelData(0))); };
      src.connect(proc); proc.connect(ctx.destination);
      active = btn;
      btn.textContent = '■ Stop'; btn.classList.add('on');
      say('Recording… ' + (btn.getAttribute('data-hint') || 'say the word') + ', then press Stop.');
      timer = setTimeout(function () { stop(); }, Number(btn.getAttribute('data-max') || MAX_MS));
    }).catch(function () {
      say('The browser blocked the microphone. Click the icon at the left of the address bar, allow the microphone, and reload this page.', true);
    });
  }

  function stop() {
    if (!active) return;
    clearTimeout(timer);
    var btn = active; active = null;
    src.disconnect(); proc.disconnect();
    btn.textContent = '● Record'; btn.classList.remove('on');
    var n = 0, i, j;
    for (i = 0; i < chunks.length; i++) n += chunks[i].length;
    var all = new Float32Array(n), off = 0;
    for (i = 0; i < chunks.length; i++) { all.set(chunks[i], off); off += chunks[i].length; }
    var wav = encode(trim(all, ctx.sampleRate), ctx.sampleRate);
    if (!wav) { say("I didn't hear anything. Check the microphone and try again.", true); btn.focus(); return; }
    say('Saving…');
    fetch(saveUrl + '?key=' + encodeURIComponent(btn.dataset.key),
          {method: 'POST', body: wav, headers: {'Content-Type': 'audio/wav'}, credentials: 'same-origin'})
      .then(function (r) { if (!r.ok) throw new Error(); return r.json(); })
      .then(function (d) { saved(btn, d.url); })
      .catch(function () { say('That one did not save. Try again.', true); btn.focus(); });
  }

  function trim(x, rate) {
    var peak = 0, i;
    for (i = 0; i < x.length; i++) peak = Math.max(peak, Math.abs(x[i]));
    if (peak < 0.01) return null;
    var th = Math.max(0.01, peak * 0.08), a = 0, b = x.length - 1, pad = Math.round(rate * 0.12);
    while (a < x.length && Math.abs(x[a]) < th) a++;
    while (b > a && Math.abs(x[b]) < th) b--;
    a = Math.max(0, a - pad); b = Math.min(x.length - 1, b + pad);
    var out = x.slice(a, b + 1), gain = 0.9 / peak;
    for (i = 0; i < out.length; i++) out[i] *= gain;
    return out;
  }

  function encode(x, rate) {
    if (!x) return null;
    var ratio = rate / RATE, len = Math.floor(x.length / ratio);
    var buf = new ArrayBuffer(44 + len * 2), v = new DataView(buf), i;
    function str(o, s) { for (var k = 0; k < s.length; k++) v.setUint8(o + k, s.charCodeAt(k)); }
    str(0, 'RIFF'); v.setUint32(4, 36 + len * 2, true); str(8, 'WAVE'); str(12, 'fmt ');
    v.setUint32(16, 16, true); v.setUint16(20, 1, true); v.setUint16(22, 1, true);
    v.setUint32(24, RATE, true); v.setUint32(28, RATE * 2, true); v.setUint16(32, 2, true);
    v.setUint16(34, 16, true); str(36, 'data'); v.setUint32(40, len * 2, true);
    for (i = 0; i < len; i++) {
      // Average the samples each output sample stands for: a cheap low-pass,
      // so shrinking 48 kHz to 22 kHz doesn't add hiss.
      var s0 = Math.floor(i * ratio), s1 = Math.max(s0 + 1, Math.floor((i + 1) * ratio)), sum = 0;
      for (var k = s0; k < s1; k++) sum += x[k];
      var s = Math.max(-1, Math.min(1, sum / (s1 - s0)));
      v.setInt16(44 + i * 2, s < 0 ? s * 0x8000 : s * 0x7fff, true);
    }
    return new Blob([buf], {type: 'audio/wav'});
  }

  function saved(btn, url) {
    var li = btn.closest('li');
    var play = li.querySelector('button.say');
    play.setAttribute('data-src', url); play._audio = null; play.hidden = false;
    if (!li.classList.contains('has')) {
      li.classList.add('has');
      var c = document.getElementById('nrec'); c.textContent = String(Number(c.textContent) + 1);
      var d0 = li.closest('details'), wk = d0 && d0.querySelector('summary .wkcount');
      if (wk) wk.textContent = wk.textContent.replace(/^\d+/, function (n) { return String(Number(n) + 1); });
    }
    new Audio(url).play();
    say('Saved ' + (li.getAttribute('data-label') || li.querySelector('.latin').textContent).replace(/[.!?…]+$/, '') + '.');
    var all = Array.prototype.slice.call(document.querySelectorAll('button.rec'));
    var next = all[all.indexOf(btn) + 1];
    if (next) {
      var d = next.closest('details'); if (d) d.open = true;
      next.focus();
    }
  }

  document.addEventListener('click', function (ev) {
    var btn = ev.target.closest && ev.target.closest('button.rec');
    if (!btn) return;
    if (active === btn) { stop(); return; }
    if (active) stop();
    start(btn);
  });
})();
