// editor.js

let drawCanvas = document.getElementById('draw-canvas');
let drawCtx = drawCanvas.getContext('2d');
let bgCanvas = document.getElementById('background-canvas');
let bgCtx = bgCanvas.getContext('2d');

let drawing = false;

let frames = [];
let currentFrameIndex = -1;
let history = []; // история предыдущих кадров (макс. 3)

let currentTool = 'pencil';
let currentColor = '#000000';
let brushSize = 2;
let playing = false;
let playInterval = null;
const fps = 10;
const frameDelay = 1000 / fps;

// Элементы управления
const addFrameBtn = document.getElementById('add-frame');
const deleteFrameBtn = document.getElementById('delete-frame');
const previewBtn = document.getElementById('preview-btn');
const saveBtn = document.getElementById('save-btn');
const pencilTool = document.getElementById('pencil-tool');
const eraserTool = document.getElementById('eraser-tool');
const sizeBtns = document.querySelectorAll('.size-btn');
const colorBtns = document.querySelectorAll('.color-btn');
const framesStrip = document.getElementById('frames-strip');
const saveModal = new bootstrap.Modal(document.getElementById('saveModal'));
const confirmSave = document.getElementById('confirm-save');
const modalTitleInput = document.getElementById('modal-title');

// ========== Вспомогательные функции ==========

function loadImage(src) {
    return new Promise((resolve) => {
        const img = new Image();
        img.src = src;
        img.onload = () => resolve(img);
    });
}

// Сохранить текущее состояние drawCanvas в frames
function saveCurrentFrame() {
    if (currentFrameIndex >= 0 && currentFrameIndex < frames.length) {
        frames[currentFrameIndex] = drawCanvas.toDataURL();
    }
}

// Обновление миниатюры текущего кадра
function updateCurrentThumbnail() {
    const thumb = document.querySelector(`.frame-thumb[data-index="${currentFrameIndex}"]`);
    if (thumb) {
        thumb.src = frames[currentFrameIndex];
    }
}

// Полное обновление списка миниатюр
function updateFramesUI() {
    framesStrip.innerHTML = '';
    frames.forEach((frame, index) => {
        let img = document.createElement('img');
        img.src = frame;
        img.className = 'frame-thumb';
        img.dataset.index = index;
        if (index === currentFrameIndex) img.classList.add('current');
        img.addEventListener('click', async () => {
            if (currentFrameIndex !== index) {
                saveCurrentFrame();
                updateHistory(index);          // добавляем старый индекс в историю
                currentFrameIndex = index;
                await loadCurrentFrame();      // загрузить чистый кадр в drawCanvas
                await drawOnionSkin();         // перерисовать шелуху на bgCanvas
                updateFramesUI();
            }
        });
        framesStrip.appendChild(img);
    });
}

// ========== Работа с историей ==========

// Обновление истории при выборе нового кадра
function updateHistory(newIndex) {
    const oldIndex = currentFrameIndex;
    if (oldIndex === newIndex || oldIndex === -1) return;

    history.unshift(oldIndex);
    // Убираем дубликаты
    history = history.filter((value, idx, self) => self.indexOf(value) === idx);
    // Ограничиваем длину 3
    if (history.length > 3) history = history.slice(0, 3);
}

// Коррекция истории после вставки кадра (все индексы >= startIdx увеличиваются на 1)
function adjustHistoryAfterInsert(startIdx) {
    history = history.map(idx => idx >= startIdx ? idx + 1 : idx);
}

// Коррекция истории после удаления кадра (индексы > deleteIdx уменьшаются на 1, равные удаляются)
function adjustHistoryAfterDelete(deleteIdx) {
    history = history.map(idx => {
        if (idx > deleteIdx) return idx - 1;
        if (idx === deleteIdx) return -1;
        return idx;
    }).filter(idx => idx !== -1);
}

// ========== Работа с фоновыми слоями (луковая шелуха) ==========

async function drawOnionSkin() {
    bgCtx.clearRect(0, 0, bgCanvas.width, bgCanvas.height);
    bgCtx.fillStyle = '#ffffff';
    bgCtx.fillRect(0, 0, bgCanvas.width, bgCanvas.height);

    // Рисуем кадры из истории с нужной прозрачностью
    for (let i = 0; i < history.length; i++) {
        const idx = history[i];
        if (idx < 0 || idx >= frames.length) continue;
        const img = await loadImage(frames[idx]);
        if (i === 0) bgCtx.globalAlpha = 0.5;      // слой 0 (50%)
        else if (i === 1) bgCtx.globalAlpha = 0.25; // слой -1 (25%)
        else if (i === 2) bgCtx.globalAlpha = 0.125; // слой -2 (12.5%)
        bgCtx.drawImage(img, 0, 0, bgCanvas.width, bgCanvas.height);
    }
    bgCtx.globalAlpha = 1.0;
}

// ========== Загрузка текущего кадра в drawCanvas ==========

async function loadCurrentFrame() {
    if (currentFrameIndex < 0 || currentFrameIndex >= frames.length) return;
    const img = await loadImage(frames[currentFrameIndex]);
    drawCtx.clearRect(0, 0, drawCanvas.width, drawCanvas.height);
    drawCtx.drawImage(img, 0, 0, drawCanvas.width, drawCanvas.height);
}

// ========== Инициализация ==========

async function initFrames() {
    history = [];
    if (typeof framesData !== 'undefined' && framesData.length > 0) {
        frames = framesData;
        currentFrameIndex = 0;
        await loadCurrentFrame();
        await drawOnionSkin();
        updateFramesUI();
    } else {
        // Создаём первый пустой кадр (прозрачный)
        drawCtx.clearRect(0, 0, drawCanvas.width, drawCanvas.height);
        frames.push(drawCanvas.toDataURL());
        currentFrameIndex = 0;
        await drawOnionSkin();  // пока нет предыдущих, просто белый фон
        updateFramesUI();
    }
}

// ========== Рисование (только на drawCanvas) ==========

function getCanvasCoords(e) {
    const rect = drawCanvas.getBoundingClientRect();
    const scaleX = drawCanvas.width / rect.width;
    const scaleY = drawCanvas.height / rect.height;
    const mouseX = (e.clientX - rect.left) * scaleX;
    const mouseY = (e.clientY - rect.top) * scaleY;
    return { x: mouseX, y: mouseY };
}

function startDrawing(e) {
    drawing = true;
    const coords = getCanvasCoords(e);
    if (currentTool === 'eraser') {
        drawCtx.globalCompositeOperation = 'destination-out';
    } else {
        drawCtx.globalCompositeOperation = 'source-over';
        drawCtx.strokeStyle = currentColor;
    }
    drawCtx.lineWidth = brushSize;
    drawCtx.lineCap = 'round';
    drawCtx.beginPath();
    drawCtx.moveTo(coords.x, coords.y);
}

function draw(e) {
    if (!drawing) return;
    const coords = getCanvasCoords(e);
    drawCtx.lineTo(coords.x, coords.y);
    drawCtx.stroke();
    drawCtx.beginPath();
    drawCtx.moveTo(coords.x, coords.y);
}

function stopDrawing() {
    if (drawing) {
        drawing = false;
        drawCtx.closePath();
        drawCtx.globalCompositeOperation = 'source-over';
        saveCurrentFrame();
        updateCurrentThumbnail();
        // Шелуху не перерисовываем, т.к. она зависит только от истории и массива frames
    }
}

drawCanvas.addEventListener('mousedown', startDrawing);
drawCanvas.addEventListener('mousemove', draw);
drawCanvas.addEventListener('mouseup', stopDrawing);
drawCanvas.addEventListener('mouseout', stopDrawing);

// ========== Управление кадрами ==========

addFrameBtn.addEventListener('click', async (e) => {
    saveCurrentFrame();
    drawCtx.clearRect(0, 0, drawCanvas.width, drawCanvas.height);
    const emptyFrame = drawCanvas.toDataURL();
    const oldIdx = currentFrameIndex;

    if (e.ctrlKey) {
        // Вставить перед текущим кадром (Ctrl)
        frames.splice(oldIdx, 0, emptyFrame);
        adjustHistoryAfterInsert(oldIdx); // сдвигаем индексы в истории
        // Добавляем старый кадр (теперь он на позиции oldIdx+1) в историю
        history.unshift(oldIdx + 1);
        // Убираем дубликаты и ограничиваем 3
        history = [...new Set(history)];
        if (history.length > 3) history = history.slice(0, 3);
        currentFrameIndex = oldIdx; // новый кадр становится текущим
    } else {
        // Вставить после текущего кадра
        frames.splice(oldIdx + 1, 0, emptyFrame);
        adjustHistoryAfterInsert(oldIdx); // сдвигаем индексы в истории
        // Добавляем старый кадр (он остаётся на позиции oldIdx) в историю
        history.unshift(oldIdx);
        history = [...new Set(history)];
        if (history.length > 3) history = history.slice(0, 3);
        currentFrameIndex = oldIdx + 1; // переключаемся на новый кадр
    }

    await loadCurrentFrame();
    await drawOnionSkin();
    updateFramesUI();
});

deleteFrameBtn.addEventListener('click', async () => {
    if (frames.length <= 1) {
        alert('Нельзя удалить единственный кадр');
        return;
    }
    saveCurrentFrame();
    const oldIdx = currentFrameIndex;
    frames.splice(oldIdx, 1);
    if (currentFrameIndex >= frames.length) {
        currentFrameIndex = frames.length - 1;
    }
    adjustHistoryAfterDelete(oldIdx);
    await loadCurrentFrame();
    await drawOnionSkin();
    updateFramesUI();
});

// ========== Предпросмотр ==========

async function drawPreviewFrame(index) {
    const img = await loadImage(frames[index]);
    drawCtx.clearRect(0, 0, drawCanvas.width, drawCanvas.height);
    drawCtx.drawImage(img, 0, 0, drawCanvas.width, drawCanvas.height);
    // Скрываем шелуху, очистив bgCanvas и нарисовав белый фон
    bgCtx.clearRect(0, 0, bgCanvas.width, bgCanvas.height);
    bgCtx.fillStyle = '#ffffff';
    bgCtx.fillRect(0, 0, bgCanvas.width, bgCanvas.height);
}

previewBtn.addEventListener('click', () => {
    if (playing) {
        stopPreview();
    } else {
        startPreview();
    }
});

function startPreview() {
    if (frames.length < 1) return;
    playing = true;
    previewBtn.innerHTML = '<i class="bi bi-pause-fill"></i>';
    previewBtn.title = 'Пауза';
    playInterval = setInterval(async () => {
        let next = (currentFrameIndex + 1) % frames.length;
        currentFrameIndex = next;
        await drawPreviewFrame(next);
        updateFramesUI();
    }, frameDelay);
}

function stopPreview() {
    playing = false;
    previewBtn.innerHTML = '<i class="bi bi-play-fill"></i>';
    previewBtn.title = 'Предпросмотр';
    clearInterval(playInterval);
    playInterval = null;
    // Возвращаем обычный режим: загружаем текущий кадр и шелуху
    loadCurrentFrame();
    drawOnionSkin();
}

// ========== Инструменты и цвета ==========

pencilTool.addEventListener('click', () => {
    currentTool = 'pencil';
    updateToolUI();
});

eraserTool.addEventListener('click', () => {
    currentTool = 'eraser';
    updateToolUI();
});

function updateToolUI() {
    pencilTool.classList.toggle('pencil-blue', currentTool === 'pencil');
    eraserTool.classList.toggle('eraser-blue', currentTool === 'eraser');
}

sizeBtns.forEach(btn => {
    btn.addEventListener('click', () => {
        sizeBtns.forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        brushSize = parseInt(btn.dataset.size);
    });
});

colorBtns.forEach(btn => {
    btn.addEventListener('click', () => {
        colorBtns.forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        if (currentTool === 'pencil') {
            currentColor = btn.dataset.color;
        }
    });
});

// ========== Сохранение ==========

saveBtn.addEventListener('click', () => {
    saveCurrentFrame();
    modalTitleInput.value = '';
    saveModal.show();
});

confirmSave.addEventListener('click', () => {
    let title = modalTitleInput.value.trim();
    if (!title) {
        alert('Введите название');
        return;
    }
    document.getElementById('title-input').value = title;
    document.getElementById('frames-input').value = JSON.stringify(frames);
    document.getElementById('editor-form').submit();
});

// ========== Запуск ==========
initFrames();