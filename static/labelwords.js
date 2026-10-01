// Tap-to-place labelling: tap a label then a box (or a box then a label), or
// drag a label onto a box. Tapping works on phones and Chromebooks alike;
// dragging is there for a mouse. Every control is a button, so the keyboard
// works too. A filled box tapped again is emptied and ready for a new label.
(function () {
  function fill(slot, label) {
    var input = slot.parentNode.querySelector('input[name=pick]');
    input.value = label || '';
    slot.textContent = '';
    if (label) {
      var parts = label.split(' · ');
      var main = document.createElement('span');
      main.className = 'lw-main'; main.textContent = parts[0];
      slot.appendChild(main);
      if (parts.length > 1) {
        var sub = document.createElement('span');
        sub.className = 'lw-sub'; sub.textContent = parts.slice(1).join(' · ');
        slot.appendChild(sub);
      }
    }
    slot.classList.toggle('filled', !!label);
  }

  Array.prototype.forEach.call(document.querySelectorAll('[data-lw]'), function (root) {
    var chosen = null, active = null;
    function choose(chip) {
      if (chosen) chosen.classList.remove('selected');
      chosen = chip;
      if (chip) chip.classList.add('selected');
      root.classList.toggle('choosing', !!chip);
    }
    function activate(slot) {
      if (active) active.classList.remove('active');
      active = slot;
      if (slot) slot.classList.add('active');
    }
    root.addEventListener('click', function (ev) {
      var chip = ev.target.closest('.lw-chip'), slot = ev.target.closest('.lw-slot');
      if (chip) {
        if (active) { fill(active, chip.dataset.label); activate(null); return; }
        choose(chosen === chip ? null : chip);
      } else if (slot) {
        if (chosen) { fill(slot, chosen.dataset.label); choose(null); return; }
        if (slot.classList.contains('filled')) fill(slot, '');
        activate(active === slot ? null : slot);
      }
    });
    root.addEventListener('dragstart', function (ev) {
      var chip = ev.target.closest('.lw-chip');
      if (chip) ev.dataTransfer.setData('text/plain', chip.dataset.label);
    });
    root.addEventListener('dragover', function (ev) {
      if (ev.target.closest('.lw-slot')) ev.preventDefault();
    });
    root.addEventListener('drop', function (ev) {
      var slot = ev.target.closest('.lw-slot');
      if (!slot) return;
      ev.preventDefault();
      fill(slot, ev.dataTransfer.getData('text/plain'));
      choose(null); activate(null);
    });

    if (root.hasAttribute('data-lw-guard')) {
      var form = root.closest('form'), warned = false;
      form.addEventListener('submit', function (ev) {
        var empty = Array.prototype.some.call(root.querySelectorAll('input[name=pick]'),
                                              function (i) { return !i.value; });
        if (empty && !warned) {
          ev.preventDefault();
          warned = true;
          root.querySelector('.lw-warn').hidden = false;
        }
      });
    }
  });
})();
