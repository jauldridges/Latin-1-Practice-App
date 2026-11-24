// DI mode screens: answer timing, and the audio.
//
// Timing: the time from the screen opening (or the Listen tap on an echo
// item) to the answer goes in latency_ms; di_run.py brings a right but slow
// one-tap answer back later in the lesson.
//
// Audio: the browser's own speech, no files. Latin is read in an Italian
// voice (the closest the devices have), everything else in English; a model
// screen's script marks its Latin *like this*. A device with no speech
// shows the written form instead.
(function () {
  var t0 = Date.now();
  var form = document.getElementById('di-form');
  if (form) {
    form.addEventListener('submit', function () {
      var f = document.getElementById('latency_ms');
      if (f) f.value = String(Date.now() - t0);
    });
  }
  var speech = 'speechSynthesis' in window;
  function voice(prefix) {
    if (!speech) return null;
    var vs = window.speechSynthesis.getVoices() || [];
    for (var i = 0; i < vs.length; i++) {
      if ((vs[i].lang || '').toLowerCase().indexOf(prefix) === 0) return vs[i];
    }
    return null;
  }
  function segments(text) {
    var out = [], re = /\*([^*]+)\*/g, last = 0, m;
    while ((m = re.exec(text))) {
      if (m.index > last) out.push([text.slice(last, m.index), 'en']);
      out.push([m[1], 'la']);
      last = re.lastIndex;
    }
    if (last < text.length) out.push([text.slice(last), 'en']);
    return out;
  }
  function say(text, allLatin) {
    if (!speech) return false;
    window.speechSynthesis.cancel();
    var segs = allLatin ? [[text, 'la']] : segments(text);
    segs.forEach(function (s) {
      var t = s[0].replace(/\*\*/g, '').replace(/___/g, ' blank ').replace(/(^|\s)-/g, '$1').trim();
      if (!t) return;
      var u = new SpeechSynthesisUtterance(t);
      var latin = s[1] === 'la';
      var v = latin ? (voice('it') || voice('es')) : voice('en');
      if (v) u.voice = v;
      u.lang = v ? v.lang : (latin ? 'it-IT' : 'en-US');
      u.rate = latin ? 0.8 : 1;
      window.speechSynthesis.speak(u);
    });
    return true;
  }
  document.addEventListener('click', function (ev) {
    var b = ev.target.closest && ev.target.closest('[data-say]');
    if (!b) return;
    ev.preventDefault();
    var ok = say(b.getAttribute('data-say'), b.hasAttribute('data-latin'));
    if (!ok) {
      var fb = document.getElementById('di-fallback');
      if (fb) fb.hidden = false;
    }
    if (b.hasAttribute('data-echo')) t0 = Date.now();
  });
  if (!speech) {
    var fb = document.getElementById('di-fallback');
    if (fb) fb.hidden = false;
  } else {
    window.speechSynthesis.getVoices();   // some browsers load voices lazily
  }
  var input = document.querySelector('.di-input');
  if (input) input.focus();

  // Celebrations: confetti on a passed check and on every fifth right answer
  // in a row. Nothing moves for a student who has asked for reduced motion.
  var still = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  function confetti(n, top) {
    var colors = ['#2f6f4f', '#e0a526', '#d9644a', '#4a7fd9', '#8a5ad9'];
    for (var i = 0; i < n; i++) {
      var c = document.createElement('span');
      c.className = 'di-confetti';
      var a = Math.random() * Math.PI * 2, d = 120 + Math.random() * 180;
      c.style.background = colors[i % colors.length];
      c.style.top = top;
      c.style.setProperty('--x', Math.round(Math.cos(a) * d) + 'px');
      c.style.setProperty('--y', Math.round(Math.sin(a) * d + 120) + 'px');
      c.style.setProperty('--r', Math.round(Math.random() * 720 - 360) + 'deg');
      c.style.animationDelay = Math.round(Math.random() * 120) + 'ms';
      document.body.appendChild(c);
      setTimeout(function (el) { return function () { el.remove(); }; }(c), 1700);
    }
  }
  if (!still) {
    if (document.querySelector('.di-cheer[data-burst]')) confetti(24, '42%');
    if (document.querySelector('[data-confetti]')) confetti(60, '22%');
  }
})();
