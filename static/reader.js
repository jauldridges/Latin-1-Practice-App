// The Reader: tap a word and its gloss pops up right beside it -- below the
// word, or above it near the bottom of the screen -- with a little arrow
// pointing at the word. Tapping anywhere else, Escape, or ✕ closes it.
// Each question is checked on its own; a miss offers "See hint".
// "AA" makes the text bigger for a projector, remembered on this device only.
(function () {
  var pop = document.getElementById('glosspop');
  var reader = document.getElementById('reader');
  if (!pop || !reader) return;
  var current = null, GAP = 10, EDGE = 8;

  function place(btn) {
    var r = btn.getBoundingClientRect();
    var w = pop.offsetWidth, h = pop.offsetHeight;
    var vw = document.documentElement.clientWidth, vh = window.innerHeight;
    var centre = r.left + r.width / 2;
    var left = Math.max(EDGE, Math.min(centre - w / 2, vw - w - EDGE));
    var below = r.bottom + GAP + h <= vh || r.top - GAP - h < 0;
    var top = below ? r.bottom + GAP : r.top - GAP - h;
    pop.style.left = (left + window.scrollX) + 'px';
    pop.style.top = (top + window.scrollY) + 'px';
    pop.classList.toggle('above', !below);
    pop.querySelector('.gp-arrow').style.left = Math.max(12, Math.min(centre - left, w - 12)) + 'px';
  }

  function show(btn) {
    if (current) current.classList.remove('on');
    current = btn;
    btn.classList.add('on');
    pop.querySelector('.gp-word').textContent = btn.textContent;
    pop.querySelector('.gp-gloss').textContent = btn.dataset.gloss || '(no gloss)';
    var note = pop.querySelector('.gp-note');
    note.textContent = btn.dataset.note || '';
    note.hidden = !btn.dataset.note;
    pop.hidden = false;
    place(btn);
  }
  function hide() {
    if (current) current.classList.remove('on');
    current = null;
    pop.hidden = true;
  }

  document.addEventListener('click', function (ev) {
    var btn = ev.target.closest('button.rw');
    if (btn && reader.contains(btn)) {
      if (btn === current) hide(); else show(btn);
      return;
    }
    if (ev.target.closest('.gp-close') || !ev.target.closest('#glosspop')) hide();
  });
  document.addEventListener('keydown', function (ev) { if (ev.key === 'Escape') hide(); });
  window.addEventListener('resize', function () { if (current) place(current); });

  // Each question is checked on its own, in place, so a student answers as
  // they read. A miss shows "See hint", which lights up the Latin that
  // answers the question and scrolls it into view.
  var form = reader.closest('form');
  var checkUrl = form && form.dataset.check;
  var tally = document.getElementById('rqtally');
  var verdicts = {};
  Array.prototype.forEach.call(document.querySelectorAll('fieldset.rq.right'), function (f) {
    verdicts[f.dataset.qid] = 'right';
  });
  function showTally() {
    if (!tally) return;
    var n = 0;
    for (var k in verdicts) if (verdicts[k] === 'right') n++;
    tally.querySelector('strong').textContent = String(n);
  }
  function setVerdict(fs, res) {
    fs.classList.remove('right', 'wrong', 'blank');
    if (res) fs.classList.add(res);
    fs.querySelector('.rq-verdict').textContent =
      res === 'right' ? '✓ Right!' : res === 'wrong' ? 'Not quite.' :
      res === 'blank' ? 'Pick an answer first.' : '';
    fs.querySelector('.rq-hint').hidden = res !== 'wrong';
    verdicts[fs.dataset.qid] = res;
    showTally();
  }
  function clearHint() {
    Array.prototype.forEach.call(document.querySelectorAll('.rw.hint-on'), function (w) {
      w.classList.remove('hint-on');
    });
  }

  document.addEventListener('click', function (ev) {
    var check = ev.target.closest('button.rq-check');
    if (check && checkUrl && window.fetch) {
      ev.preventDefault();
      var fs = check.closest('fieldset.rq');
      var on = fs.querySelector('input[type=radio]:checked');
      var body = new FormData();
      body.append('qid', fs.dataset.qid);
      body.append('picked', on ? on.value : '');
      check.disabled = true;
      fetch(checkUrl, {method: 'POST', body: body, credentials: 'same-origin'})
        .then(function (r) { if (!r.ok) throw new Error(); return r.json(); })
        .then(function (d) { setVerdict(fs, d.result); })
        .catch(function () { form.requestSubmit ? form.requestSubmit(check) : form.submit(); })
        .then(function () { check.disabled = false; });
      return;
    }
    var hint = ev.target.closest('button.rq-hint');
    if (hint) {
      clearHint();
      var first = null;
      hint.dataset.hint.split(' ').forEach(function (id) {
        var w = document.getElementById(id);
        if (w) { w.classList.add('hint-on'); first = first || w; }
      });
      if (first) first.scrollIntoView({behavior: 'smooth', block: 'center'});
    }
  });

  // Choosing a different answer clears the old verdict, so "Right!" never
  // sits next to an answer that wasn't the one checked.
  document.addEventListener('change', function (ev) {
    var fs = ev.target.closest && ev.target.closest('fieldset.rq');
    if (fs && ev.target.type === 'radio') {
      fs.classList.remove('right', 'wrong', 'blank');
      fs.querySelector('.rq-verdict').textContent = '';
      fs.querySelector('.rq-hint').hidden = true;
      delete verdicts[fs.dataset.qid];
      showTally();
    }
  });

  // Wide screens: every question group goes into the side column, in order,
  // with the Check button under them. Narrow screens: back after its paragraph.
  var side = document.getElementById('rqside');
  var groups = Array.prototype.slice.call(document.querySelectorAll('.rp-qs'));
  var homes = groups.map(function (g) { return g.parentNode; });
  var wide = window.matchMedia('(min-width: 900px)');
  function arrange() {
    if (!side) return;
    if (wide.matches && groups.length) {
      if (tally) side.appendChild(tally);
      groups.forEach(function (g) { side.appendChild(g); });
      form.classList.add('side-qs');
    } else {
      if (tally) form.parentNode.insertBefore(tally, form);
      groups.forEach(function (g, i) { homes[i].appendChild(g); });
      form.classList.remove('side-qs');
    }
    if (current) place(current);
  }
  arrange();
  if (wide.addEventListener) wide.addEventListener('change', arrange);
  else if (wide.addListener) wide.addListener(arrange);

  var size = document.getElementById('readersize');
  function setBig(on) {
    document.body.classList.toggle('reader-big', on);
    size.setAttribute('aria-pressed', on ? 'true' : 'false');
    if (current) place(current);
  }
  try { setBig(window.localStorage.getItem('readerBig') === '1'); } catch (e) {}
  size.addEventListener('click', function () {
    var on = !document.body.classList.contains('reader-big');
    setBig(on);
    try { window.localStorage.setItem('readerBig', on ? '1' : '0'); } catch (e) {}
  });
})();
