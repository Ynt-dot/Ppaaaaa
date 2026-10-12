// Пасхалка: набрать "boo" на клавиатуре - по экрану пролетает призрак.
// Клавиши сравниваются по e.code (физическая клавиша), поэтому работает и
// на русской раскладке. Анимация - .hw-boo в style.css.
(function () {
    const SEQUENCE = ['KeyB', 'KeyO', 'KeyO'];
    const GHOST_SVG =
        '<svg class="hw-ghost" viewBox="0 0 40 48" aria-hidden="true">' +
        '<path class="hw-ghost-body" d="M4 22A16 16 0 0 1 36 22V44L31 40L26 44L20 40L14 44L9 40L4 44Z"/>' +
        '<ellipse class="hw-ghost-face" cx="14.5" cy="21" rx="2.3" ry="3.2"/>' +
        '<ellipse class="hw-ghost-face" cx="25.5" cy="21" rx="2.3" ry="3.2"/>' +
        '<ellipse class="hw-ghost-face" cx="20" cy="30" rx="2.6" ry="3.4"/></svg>';
    let typed = [];
    let flying = false;

    function isTyping(target) {
        return target.isContentEditable ||
            ['INPUT', 'TEXTAREA', 'SELECT'].includes(target.tagName);
    }

    function releaseGhost() {
        if (flying) return;  // один призрак за раз
        flying = true;
        const layer = document.createElement('div');
        layer.className = 'hw-boo';
        layer.setAttribute('aria-hidden', 'true');
        layer.innerHTML = '<div class="hw-boo-ghost">' + GHOST_SVG +
            '<span class="hw-boo-text">Бу!</span></div>';
        layer.firstChild.addEventListener('animationend', function () {
            layer.remove();
            flying = false;
        });
        document.body.appendChild(layer);
    }

    document.addEventListener('keydown', function (e) {
        if (e.ctrlKey || e.metaKey || e.altKey || isTyping(e.target)) {
            typed = [];
            return;
        }
        typed.push(e.code);
        typed = typed.slice(-SEQUENCE.length);
        if (typed.join() === SEQUENCE.join()) {
            typed = [];
            releaseGhost();
        }
    });
})();
