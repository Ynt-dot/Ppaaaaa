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
let brushSize = 4; // начальный размер кисти
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
        // Создаём контейнер для миниатюры и номера
        let container = document.createElement('div');
        container.style.position = 'relative';
        container.style.display = 'inline-block';
        container.style.margin = '2px';

        // Миниатюра
        let img = document.createElement('img');
        img.src = frame;
        img.className = 'frame-thumb';
        img.dataset.index = index;
        if (index === currentFrameIndex) img.classList.add('current');

        // Номер кадра
        let number = document.createElement('span');
        number.textContent = index; // нумерация с 0
        number.style.position = 'absolute';
        number.style.top = '0';
        number.style.right = '0';
        number.style.backgroundColor = '#ff0000'; // красный
        number.style.color = 'white';
        number.style.fontSize = '10px';
        number.style.padding = '2px 4px';
        number.style.borderRadius = '2px';
        number.style.fontWeight = 'bold';
        number.style.zIndex = '1';
        number.style.lineHeight = '1';
        number.style.minWidth = '16px';
        number.style.textAlign = 'center';

        container.appendChild(img);
        container.appendChild(number);

        // Обработчик клика на контейнер
        container.addEventListener('click', async () => {
            if (currentFrameIndex !== index) {
                saveCurrentFrame();
                updateHistory(index);
                currentFrameIndex = index;
                await loadCurrentFrame();
                await drawOnionSkin();
                updateFramesUI();
            }
        });

        framesStrip.appendChild(container);
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
    undoStack = [];
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
    pushState();
    updateSizeButtons();
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
    pushState()
    cursorCtx.clearRect(0, 0, cursorCanvas.width, cursorCanvas.height);
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
        if (lastMouseCoords) {
            drawCursor(lastMouseCoords.x, lastMouseCoords.y);
        }
    }
}

drawCanvas.addEventListener('mousedown', startDrawing);
drawCanvas.addEventListener('mousemove', (e) => {
    const coords = getCanvasCoords(e);
    lastMouseCoords = coords;
    if (drawing) {
        draw(e);
        // Во время рисования курсор не отображаем
        cursorCtx.clearRect(0, 0, cursorCanvas.width, cursorCanvas.height);
    } else {
        drawCursor(coords.x, coords.y);
    }
});
drawCanvas.addEventListener('mouseup', stopDrawing);
drawCanvas.addEventListener('mouseout', () => {
    cursorCtx.clearRect(0, 0, cursorCanvas.width, cursorCanvas.height);
    lastMouseCoords = null;
});

// ========== Управление кадрами ==========

addFrameBtn.addEventListener('click', async (e) => {
    pushState()
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
    pushState()
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
    modalTitleInput.value = typeof currentCartoonTitle !== 'undefined' ? currentCartoonTitle : '';
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

// ========== Undo ==========

let undoStack = [];
const MAX_UNDO = 20; // ограничим глубину

function pushState() {
    // Сохраняем копию frames (глубокое копирование)
    const state = frames.map(frame => frame); // копия массива строк
    undoStack.push(state);
    if (undoStack.length > MAX_UNDO) {
        undoStack.shift();
    }
}

document.addEventListener('keydown', (e) => {
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;

    // Клавиша Z (отмена)
    if (e.code === 'KeyZ' && !e.ctrlKey && !e.metaKey) {
        e.preventDefault();
        undo();
    }

    // Клавиша C (копировать)
    if (e.code === 'KeyC' && !e.ctrlKey && !e.metaKey) {
        e.preventDefault();
        copyFrame();
    }

    // Клавиша V (вставить)
    if (e.code === 'KeyV' && !e.ctrlKey && !e.metaKey) {
        e.preventDefault();
        pasteFrame();
    }

    // Клавиша = (увеличить размер)
    if (e.code === 'Equal' && !e.ctrlKey && !e.metaKey) {
        e.preventDefault();
        changeBrushSize(1);
    }

    // Клавиша - (уменьшить размер)
    if (e.code === 'Minus' && !e.ctrlKey && !e.metaKey) {
        e.preventDefault();
        changeBrushSize(-1);
    }
});

function undo() {
    if (undoStack.length === 0) return;
    frames = undoStack.pop().map(frame => frame); // восстанавливаем предыдущее состояние
    loadCurrentFrame().then(() => {
        drawOnionSkin();
        updateCurrentThumbnail();
        updateFramesUI(); // обновляем миниатюры и подсветку текущего кадра
    });
}

// ========== Добавление горячих клавиш C (копировать) и V (вставить) ==========

// Переменная для скопированного кадра
let copiedFrame = null;

function copyFrame() {
    if (currentFrameIndex < 0 || currentFrameIndex >= frames.length) return;
    copiedFrame = frames[currentFrameIndex];
    // Можно добавить визуальный фидбек (например, всплывающее сообщение или изменение цвета кнопки)
    console.log('Кадр скопирован');
}

function pasteFrame() {
    if (copiedFrame === null) {
        alert('Сначала скопируйте кадр (клавиша C)');
        return;
    }
    if (currentFrameIndex < 0 || currentFrameIndex >= frames.length) return;

    // Сохраняем состояние для отмены
    pushState();

    // Заменяем текущий кадр скопированным
    frames[currentFrameIndex] = copiedFrame;

    // Перезагружаем интерфейс
    loadCurrentFrame().then(() => {
        drawOnionSkin();
        updateCurrentThumbnail();
    });
}

// ========== Добавление горячих клавиш + и - для изменения размера кисти ==========

// Функция обновления активности кнопок размера
function updateSizeButtons() {
    sizeBtns.forEach(btn => {
        const size = parseInt(btn.dataset.size);
        btn.classList.toggle('active', size === brushSize);
    });
}

// Функция изменения размера кисти
function changeBrushSize(direction) {
    let newSize;
    if (direction > 0) {
        newSize = Math.ceil(brushSize * 1.2);
    } else {
        newSize = Math.floor(brushSize * 0.8);
    }
    // Ограничения
    newSize = Math.min(500, Math.max(1, newSize));
    if (newSize === brushSize) return;
    brushSize = newSize;
    if (lastMouseCoords) {
        drawCursor(lastMouseCoords.x, lastMouseCoords.y);
    }
    updateSizeButtons();
}

// ========== Добавление предпросмотра размера кисти в виде круга под курсором ==========

let cursorCanvas = document.getElementById('cursor-canvas');
let cursorCtx = cursorCanvas.getContext('2d');
let lastMouseCoords = null; // последние координаты мыши для восстановления курсора

function drawCursor(x, y) {
    cursorCtx.clearRect(0, 0, cursorCanvas.width, cursorCanvas.height);
    if (x === undefined || y === undefined) return;

    const radius = brushSize / 2;
    
    cursorCtx.beginPath();
    cursorCtx.arc(x, y, radius, 0, 2 * Math.PI);
    
    if (brushSize <= 5) {
        // Маленький размер — полностью залитый круг
        cursorCtx.fillStyle = '#e0e0e0';  // ещё чуть темнее
        cursorCtx.fill();
    } else {
        // Большой размер — только контур
        cursorCtx.strokeStyle = '#e0e0e0'; // тот же цвет
        cursorCtx.lineWidth = 1.5;         // потоньше
        cursorCtx.stroke();
    }
}

// ========== Запуск ==========
initFrames();