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
let brushSize = 20; // начальный размер кисти
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
const frameBackgroundsInput = document.getElementById('frame-backgrounds-input');
const bgToggleBtn = document.getElementById('bg-toggle');
const inkBtn = document.querySelector('.color-btn.ink-color');

// Фон каждого кадра (#000000 / #ffffff), параллельно frames. Кадры
// прозрачные - фон только подкладывается под них (холст, миниатюры, а на
// сервере - сборка GIF). Начальные фоны - из json_script в editor.html,
// на сервер уходят через скрытое поле формы.
const BLACK = '#000000';
const WHITE = '#ffffff';
let frameBgs = [];

// ========== Вспомогательные функции ==========

// Цвет "чернил", который виден на данном фоне
function contrastColor(bg) {
    return bg === BLACK ? WHITE : BLACK;
}

function currentBg() {
    return frameBgs[currentFrameIndex] || WHITE;
}

function selectColor(color) {
    colorBtns.forEach(b => b.classList.toggle('active', b.dataset.color === color));
    currentColor = color;
}

// Фоны из json_script: ровно count штук, неизвестные и недостающие -
// fallback (белый для готовых мультов - так они рисовались до появления
// фонов; чёрный для нового мульта)
function readFrameBackgrounds(count, fallback) {
    let seed = [];
    try {
        seed = JSON.parse(document.getElementById('frame-backgrounds-data').textContent);
    } catch (e) { /* страница ошибки сохранения - фонов нет */ }
    if (!Array.isArray(seed)) seed = [];
    const result = [];
    for (let i = 0; i < count; i++) {
        result.push(seed[i] === BLACK || seed[i] === WHITE ? seed[i] : fallback);
    }
    return result;
}

// Показать фон текущего кадра: подложка холста (CSS-переменная в
// editor.css) и кнопка "чернил" в палитре - контрастный к фону цвет. Если
// кисть рисовала чернилами прошлого фона, она переходит на новые.
function applyBackground() {
    const bg = currentBg();
    const ink = contrastColor(bg);
    const oldInk = inkBtn.dataset.color;
    document.documentElement.style.setProperty('--canvas-bg', bg);
    inkBtn.dataset.color = ink;
    inkBtn.style.background = ink;
    inkBtn.title = ink === WHITE ? 'Белый' : 'Чёрный';
    selectColor(currentColor === oldInk || currentColor === bg ? ink : currentColor);
}

// Перекрасить чернила текущего кадра (from -> to, чёрное <-> белое) при
// смене его фона, чтобы рисунок остался виден. Цветные штрихи не трогаем;
// сглаженные края чернил - тот же RGB с меньшей альфой, их тоже красим.
function recolorInk(from, to) {
    const fromV = from === BLACK ? 0 : 255;
    const toV = to === BLACK ? 0 : 255;
    const image = drawCtx.getImageData(0, 0, drawCanvas.width, drawCanvas.height);
    const d = image.data;
    for (let i = 0; i < d.length; i += 4) {
        if (d[i + 3] !== 0 &&
            Math.abs(d[i] - fromV) <= 8 &&
            Math.abs(d[i + 1] - fromV) <= 8 &&
            Math.abs(d[i + 2] - fromV) <= 8) {
            d[i] = d[i + 1] = d[i + 2] = toV;
        }
    }
    drawCtx.putImageData(image, 0, 0);
}

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
        thumb.style.background = currentBg();
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
        img.style.background = frameBgs[index];
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
    // вызывается после любой смены текущего кадра - заодно показываем его фон
    applyBackground();
    bgCtx.clearRect(0, 0, bgCanvas.width, bgCanvas.height);
    bgCtx.fillStyle = currentBg();
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
    // кисть по умолчанию - чернила первого кадра (в шаблоне уже выбраны)
    currentColor = inkBtn.dataset.color;
    if (typeof framesData !== 'undefined' && framesData.length > 0) {
        frames = framesData;
        frameBgs = readFrameBackgrounds(frames.length, WHITE);
        currentFrameIndex = 0;
        await loadCurrentFrame();
        await drawOnionSkin();
        updateFramesUI();
    } else {
        // Создаём первый пустой кадр (прозрачный)
        drawCtx.clearRect(0, 0, drawCanvas.width, drawCanvas.height);
        frames.push(drawCanvas.toDataURL());
        frameBgs = readFrameBackgrounds(1, BLACK);
        currentFrameIndex = 0;
        await drawOnionSkin();  // пока нет предыдущих, просто фон
        updateFramesUI();
    }
    pushState();
    updateSizeButtons();
    updateToolUI()
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
    if (frames.length >= 5000) {
        alert('Достигнут лимит кадров (5000). Нельзя добавить новый кадр.');
        return;
    }
    pushState()
    saveCurrentFrame();
    drawCtx.clearRect(0, 0, drawCanvas.width, drawCanvas.height);
    const emptyFrame = drawCanvas.toDataURL();
    const oldIdx = currentFrameIndex;
    const newBg = currentBg();  // новый кадр - на фоне текущего

    if (e.ctrlKey) {
        // Вставить перед текущим кадром (Ctrl)
        frames.splice(oldIdx, 0, emptyFrame);
        frameBgs.splice(oldIdx, 0, newBg);
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
        frameBgs.splice(oldIdx + 1, 0, newBg);
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
    frameBgs.splice(oldIdx, 1);
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
    // Скрываем шелуху, очистив bgCanvas и залив его фоном этого кадра
    bgCtx.clearRect(0, 0, bgCanvas.width, bgCanvas.height);
    bgCtx.fillStyle = frameBgs[index];
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
    // Убираем active у обеих кнопок
    pencilTool.classList.remove('active');
    eraserTool.classList.remove('active');
    // Добавляем active к выбранному инструменту
    if (currentTool === 'pencil') {
        pencilTool.classList.add('active');
    } else {
        eraserTool.classList.add('active');
    }
}

sizeBtns.forEach(btn => {
    btn.addEventListener('click', () => {
        sizeBtns.forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        brushSize = parseInt(btn.dataset.size);
    });
});

colorBtns.forEach(btn => {
    btn.addEventListener('click', () => selectColor(btn.dataset.color));
});

// Переключение фона текущего кадра чёрный <-> белый. Остальные кадры не
// меняются; чернила кадра перекрашиваются вместе с фоном (чёрное на белом
// становится белым на чёрном).
bgToggleBtn.addEventListener('click', async () => {
    if (playing) return;
    pushState();
    const oldBg = currentBg();
    recolorInk(contrastColor(oldBg), oldBg);
    frameBgs[currentFrameIndex] = contrastColor(oldBg);
    saveCurrentFrame();
    updateCurrentThumbnail();
    await drawOnionSkin();
});

// ========== Сохранение ==========

saveBtn.addEventListener('click', () => {
    saveCurrentFrame();
    // Название
    modalTitleInput.value = typeof currentCartoonTitle !== 'undefined' ? currentCartoonTitle : '';
    // FPS
    const fpsInput = document.getElementById('modal-fps');
    if (fpsInput) fpsInput.value = typeof currentCartoonFps !== 'undefined' ? currentCartoonFps : 10;
    // Теги (преобразуем массив в строку через запятую)
    const tagsInput = document.getElementById('modal-tags');
    if (tagsInput) tagsInput.value = typeof currentCartoonTags !== 'undefined' ? currentCartoonTags.join(', ') : '';
    // Описание
    const descInput = document.getElementById('modal-description');
    if (descInput) descInput.value = typeof currentCartoonDescription !== 'undefined' ? currentCartoonDescription : '';
    saveModal.show();
});

confirmSave.addEventListener('click', () => {
    let title = document.getElementById('modal-title').value.trim();
    let fps = document.getElementById('modal-fps').value;
    let tags = document.getElementById('modal-tags').value.split(',').map(s => s.trim()).filter(s => s);
    let description = document.getElementById('modal-description').value.trim();
    let fpsNum = Number(fps);

    if (!title) {
        alert('Введите название');
        return;
    }

    // Проверка FPS
    if (!Number.isInteger(fpsNum) || fpsNum < 1 || fpsNum > 30) {
        alert('FPS должен быть целым числом от 1 до 30');
        return;
    }
    document.getElementById('title-input').value = title;
    document.getElementById('fps-input').value = fps;
    document.getElementById('tags-input').value = JSON.stringify(tags);
    document.getElementById('description-input').value = description;
    document.getElementById('frames-input').value = JSON.stringify(frames);
    frameBackgroundsInput.value = JSON.stringify(frameBgs);
    formChanged = false;
    exitFullscreen();
    document.getElementById('editor-form').submit();
});

// ========== Отмена действия ==========

let undoStack = [];
const MAX_UNDO = 20; // ограничим глубину

function pushState() {
    // Сохраняем копии frames и их фонов (массивы строк)
    const state = { frames: frames.slice(), bgs: frameBgs.slice() };
    undoStack.push(state);
    if (undoStack.length > MAX_UNDO) {
        undoStack.shift();
    }
}

// ========== Полноэкранный режим ==========

let isFullscreen = false;

function enterFullscreen() {
    isFullscreen = true;
    document.body.classList.add('editor-fullscreen');
    if (!document.fullscreenElement) {
        document.documentElement.requestFullscreen().catch(() => {});
    }
}

function exitFullscreen() {
    isFullscreen = false;
    document.body.classList.remove('editor-fullscreen');
    if (document.fullscreenElement) {
        document.exitFullscreen().catch(() => {});
    }
}

function toggleFullscreen() {
    if (isFullscreen) exitFullscreen(); else enterFullscreen();
}

document.addEventListener('fullscreenchange', () => {
    if (!document.fullscreenElement && isFullscreen) {
        isFullscreen = false;
        document.body.classList.remove('editor-fullscreen');
    }
});

document.addEventListener('keydown', (e) => {
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;

    // Клавиша F (полноэкранный режим)
    if (e.code === 'KeyF' && !e.ctrlKey && !e.metaKey) {
        e.preventDefault();
        toggleFullscreen();
    }

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

    // Клавиша B (карандаш)
    if (e.code === 'KeyB' && !e.ctrlKey && !e.metaKey) {
        e.preventDefault();
        if (currentTool !== 'pencil') {
            currentTool = 'pencil';
            updateToolUI();
        }
    }

    // Клавиша E (ластик)
    if (e.code === 'KeyE' && !e.ctrlKey && !e.metaKey) {
        e.preventDefault();
        if (currentTool !== 'eraser') {
            currentTool = 'eraser';
            updateToolUI();
        }
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
    const state = undoStack.pop(); // восстанавливаем предыдущее состояние
    frames = state.frames.slice();
    frameBgs = state.bgs.slice();
    if (currentFrameIndex >= frames.length) currentFrameIndex = frames.length - 1;
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
    copiedFrame = { image: frames[currentFrameIndex], bg: currentBg() };
    // Можно добавить визуальный фидбек (например, всплывающее сообщение или изменение цвета кнопки)
    console.log('Кадр скопирован');
}

function pasteFrame() {
    if (copiedFrame === null) {
        alert('Сначала скопируйте кадр (клавиша C)');
        return;
    }
    if (currentFrameIndex < 0 || currentFrameIndex >= frames.length) return;
    if (frames.length >= 5000) {
        alert('Достигнут лимит кадров (5000). Нельзя вставить кадр.');
        return;
    }

    // Сохраняем состояние для отмены
    pushState();

    // Заменяем текущий кадр скопированным (вместе с его фоном)
    frames[currentFrameIndex] = copiedFrame.image;
    frameBgs[currentFrameIndex] = copiedFrame.bg;

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

    if (brushSize <= 62) {
        cursorCtx.beginPath();
        cursorCtx.arc(x, y, radius, 0, 2 * Math.PI);
        cursorCtx.fillStyle = '#e0e0e0';
        cursorCtx.fill();
    } else {
        const strokeWidth = 4;
        cursorCtx.beginPath();
        cursorCtx.arc(x, y, radius - strokeWidth / 2, 0, 2 * Math.PI);
        cursorCtx.strokeStyle = '#e0e0e0';
        cursorCtx.lineWidth = strokeWidth;
        cursorCtx.stroke();
    }
}

// ========== Добавление предупреждения при уходе со страницы редактора ==========

// Предупреждение при уходе со страницы
let formChanged = false;

function markChanged() {
    formChanged = true;
}

// Отслеживаем изменения в редакторе
// Рисование (mousedown на canvas)
drawCanvas.addEventListener('mousedown', markChanged);

// Добавление/удаление кадров
addFrameBtn.addEventListener('click', markChanged);
deleteFrameBtn.addEventListener('click', markChanged);

// Предпросмотр
previewBtn.addEventListener('click', markChanged);

// При изменении инструментов, размера кисти, цвета – тоже помечаем (необязательно)
pencilTool.addEventListener('click', markChanged);
eraserTool.addEventListener('click', markChanged);
sizeBtns.forEach(btn => btn.addEventListener('click', markChanged));
colorBtns.forEach(btn => btn.addEventListener('click', markChanged));
bgToggleBtn.addEventListener('click', markChanged);

const originalSaveCurrentFrame = saveCurrentFrame;
saveCurrentFrame = function() {
    originalSaveCurrentFrame();
    markChanged();
};

// Однако осторожно: saveCurrentFrame вызывается и при сохранении мульта (перед отправкой), но там мы не хотим маркировать, потому что после сохранения предупреждение не нужно.
// Но это нормально, потому что при отправке формы мы сбросим флаг.

// Отключаем предупреждение при отправке формы
const editorForm = document.getElementById('editor-form');
editorForm.addEventListener('submit', () => {
    formChanged = false;
});

// Также при клике на кнопку сохранения (открытие модального окна) не сбрасываем, но при успешном сохранении форма отправится и сбросит.
// При отмене модального окна предупреждение останется, что правильно.

// Предупреждение перед уходом
window.addEventListener('beforeunload', (e) => {
    if (formChanged) {
        e.preventDefault();
        e.returnValue = 'Вы уверены, что хотите выйти? Весь текущий прогресс будет удалён.';
        return e.returnValue;
    }
});

// ========== Запуск ==========
initFrames();