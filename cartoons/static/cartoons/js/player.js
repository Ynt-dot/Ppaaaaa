// player.js
document.addEventListener('DOMContentLoaded', function() {
    const framesData = window.framesData;
    if (!framesData || framesData.length === 0) {
        console.log('Нет данных кадров');
        return;
    }

    const fps = window.fps || 12;
    const frameDelay = 1000 / fps;

    let currentFrame = 0;
    let playing = false;
    let intervalId = null;

    const frameImg = document.getElementById('frame-display');
    const frameSlider = document.getElementById('frame-slider');
    const playPauseBtn = document.getElementById('play-pause-btn');
    const frameCounter = document.getElementById('frame-counter');
    const totalFrames = framesData.length;

    // Настройка слайдера
    if (frameSlider) {
        frameSlider.max = totalFrames - 1;
        frameSlider.value = 0;
    }
    if (frameCounter) {
        frameCounter.textContent = `1 / ${totalFrames}`;
    }

    // Загрузка кадра по индексу
    function loadFrame(index) {
        if (index < 0 || index >= totalFrames) return;
        currentFrame = index;
        frameImg.src = framesData[index];
        if (frameSlider) frameSlider.value = index;
        if (frameCounter) frameCounter.textContent = `${index+1} / ${totalFrames}`;
    }

    // Загружаем первый кадр
    loadFrame(0);
    // Автоматически запускаем воспроизведение
    play();

    // Воспроизведение
    function play() {
        if (playing) return;
        playing = true;
        if (playPauseBtn) playPauseBtn.textContent = '⏸️ Пауза';
        intervalId = setInterval(() => {
            let nextFrame = (currentFrame + 1) % totalFrames;
            loadFrame(nextFrame);
        }, frameDelay);
    }

    // Пауза
    function pause() {
        if (!playing) return;
        playing = false;
        if (playPauseBtn) playPauseBtn.textContent = '▶️ Воспроизвести';
        clearInterval(intervalId);
        intervalId = null;
    }

    // Кнопка play/pause
    if (playPauseBtn) {
        playPauseBtn.addEventListener('click', () => {
            if (playing) {
                pause();
            } else {
                play();
            }
        });
    }

    // Ползунок
    if (frameSlider) {
        frameSlider.addEventListener('input', function() {
            if (playing) pause(); // при ручной перемотке ставим на паузу
            loadFrame(parseInt(this.value));
        });
    }

    // Очистка интервала при уходе со страницы
    window.addEventListener('beforeunload', function() {
        if (intervalId) clearInterval(intervalId);
    });
});