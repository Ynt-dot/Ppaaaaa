// Хэллоуинские искры за курсором мыши. Подключается из base.html блоком
// hw_sparks (в редакторе блок пустой - там своя кисть). Каждая искра -
// <span> с CSS-анимацией (.hw-spark в style.css), удаляется по её окончании.
(function () {
    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
    const COLORS = ['#FF7518', '#FFB347', '#7FFF00', '#B57EDC'];
    const MIN_DIST = 14;    // px между искрами - не сыпать на каждый пиксель
    const MAX_SPARKS = 40;  // потолок одновременно живых искр

    const layer = document.createElement('div');
    layer.className = 'hw-sparks';
    layer.setAttribute('aria-hidden', 'true');
    document.body.appendChild(layer);

    let lastX = -1000, lastY = -1000;

    document.addEventListener('pointermove', function (e) {
        // только мышь: на тач-экранах "курсора" нет
        if (e.pointerType !== 'mouse' || reducedMotion.matches) return;
        if (Math.hypot(e.clientX - lastX, e.clientY - lastY) < MIN_DIST) return;
        if (layer.childElementCount >= MAX_SPARKS) return;
        lastX = e.clientX;
        lastY = e.clientY;

        const spark = document.createElement('span');
        spark.className = 'hw-spark';
        spark.style.left = e.clientX + 'px';
        spark.style.top = e.clientY + 'px';
        spark.style.setProperty('--hw-spark-color', COLORS[Math.floor(Math.random() * COLORS.length)]);
        spark.style.setProperty('--hw-spark-dx', (Math.random() * 30 - 15).toFixed(1) + 'px');
        spark.style.setProperty('--hw-spark-dy', (Math.random() * 20 + 10).toFixed(1) + 'px');
        spark.addEventListener('animationend', function () { spark.remove(); });
        layer.appendChild(spark);
    }, { passive: true });
})();
