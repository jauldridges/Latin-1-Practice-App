// The Reader: tap a word and its gloss pops up right beside it -- below the
// word, or above it near the bottom of the screen -- with a little arrow
// pointing at the word. Tapping anywhere else, Escape, or ✕ closes it.
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

  // "Look again at sentence 6": scroll there and flash it.
  document.addEventListener('click', function (ev) {
    var a = ev.target.closest('a.looklink');
    if (!a) return;
    var s = document.getElementById('s' + a.dataset.s);
    if (!s) return;
    ev.preventDefault();
    s.scrollIntoView({behavior: 'smooth', block: 'center'});
    s.classList.remove('flash'); void s.offsetWidth; s.classList.add('flash');
  });

  // Wide screens: every question group goes into the side column, in order,
  // with the Check button under them. Narrow screens: back after its paragraph.
  var side = document.getElementById('rqside');
  var submit = document.getElementById('rqsubmit');
  var form = reader.closest('form');
  var groups = Array.prototype.slice.call(document.querySelectorAll('.rp-qs'));
  var homes = groups.map(function (g) { return g.parentNode; });
  var wide = window.matchMedia('(min-width: 900px)');
  function arrange() {
    if (!side) return;
    if (wide.matches && groups.length) {
      groups.forEach(function (g) { side.appendChild(g); });
      if (submit) side.appendChild(submit);
      form.classList.add('side-qs');
    } else {
      groups.forEach(function (g, i) { homes[i].appendChild(g); });
      if (submit) form.appendChild(submit);
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
