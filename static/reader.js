// The Reader: tap a word, its gloss appears in the bar at the bottom. The bar
// never covers the line being read, and Escape or ✕ closes it. "AA" makes the
// text bigger for a projector and is remembered on this device only.
(function () {
  var bar = document.getElementById('glossbar');
  var reader = document.getElementById('reader');
  if (!bar || !reader) return;
  var current = null;

  function show(btn) {
    if (current) current.classList.remove('on');
    current = btn;
    btn.classList.add('on');
    bar.querySelector('.gb-word').textContent = btn.textContent;
    bar.querySelector('.gb-gloss').textContent = btn.dataset.gloss || '(no gloss)';
    var note = bar.querySelector('.gb-note');
    note.textContent = btn.dataset.note || '';
    note.hidden = !btn.dataset.note;
    bar.hidden = false;
  }
  function hide() {
    if (current) current.classList.remove('on');
    current = null;
    bar.hidden = true;
  }

  reader.addEventListener('click', function (ev) {
    var btn = ev.target.closest('button.rw');
    if (!btn) return;
    if (btn === current) hide(); else show(btn);
  });
  bar.querySelector('.gb-close').addEventListener('click', hide);
  document.addEventListener('keydown', function (ev) { if (ev.key === 'Escape') hide(); });

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

  var size = document.getElementById('readersize');
  function setBig(on) {
    document.body.classList.toggle('reader-big', on);
    size.setAttribute('aria-pressed', on ? 'true' : 'false');
  }
  try { setBig(window.localStorage.getItem('readerBig') === '1'); } catch (e) {}
  size.addEventListener('click', function () {
    var on = !document.body.classList.contains('reader-big');
    setBig(on);
    try { window.localStorage.setItem('readerBig', on ? '1' : '0'); } catch (e) {}
  });
})();
