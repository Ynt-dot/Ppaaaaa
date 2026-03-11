// editor.js

let canvas = document.getElementById('draw-canvas');
let ctx = canvas.getContext('2d');
let drawing = false;

// Состояние редактора
let frames = [];
let currentFrameIndex = -1;
let currentTool = 'pencil'; // 'pencil' или 'eraser'
let currentColor = '#000000';
let brushSize = 2; // от 1 до 5
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
// const frameSlider = document.getElementById('frame-slider');
const framesStrip = document.getElementById('frames-strip');
const saveModal = new bootstrap.Modal(document.getElementById('saveModal'));
const confirmSave = document.getElementById('confirm-save');
console.log('confirmSave элемент:', confirmSave);
if (!confirmSave) {
    console.error('❌ Кнопка confirm-save не найдена в DOM! Проверьте id.');
} else {
    console.log('✅ Кнопка найдена, добавляем обработчик...');
}
const modalTitleInput = document.getElementById('modal-title');

function updateCurrentThumbnail() {
    const thumb = document.querySelector(`.frame-thumb[data-index="${currentFrameIndex}"]`);
    if (thumb) {
        thumb.src = frames[currentFrameIndex];
    }
}

function getCanvasCoords(e) {
    const rect = canvas.getBoundingClientRect();
    const scaleX = canvas.width / rect.width;   // отношение физической ширины к видимой
    const scaleY = canvas.height / rect.height;
    const mouseX = (e.clientX - rect.left) * scaleX;
    const mouseY = (e.clientY - rect.top) * scaleY;
    return { x: mouseX, y: mouseY };
}

// Инициализация: если есть переданные кадры, загружаем, иначе создаём первый пустой кадр
function initFrames() {
    console.log('initFrames called');
    console.log('framesData defined?', typeof framesData !== 'undefined');
    if (typeof framesData !== 'undefined' && framesData.length > 0) {
        frames = framesData;
        currentFrameIndex = 0;
        loadFrame(currentFrameIndex);
    } else {
        console.log('Creating first empty frame');
        clearCanvas();
        frames.push(canvas.toDataURL());
        console.log('Frames length after push:', frames.length);
        currentFrameIndex = 0;
        updateFramesUI();
    }
}

// Очистка холста (заливка белым)
function clearCanvas() {
    ctx.fillStyle = '#ffffff';
    ctx.fillRect(0, 0, canvas.width, canvas.height);
}

// Загрузка кадра на холст
function loadFrame(index) {
    if (index < 0 || index >= frames.length) return;
    let img = new Image();
    img.src = frames[index];
    img.onload = () => {
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        ctx.drawImage(img, 0, 0);
        currentFrameIndex = index;
        updateFramesUI();
    };
}

// Сохранить текущий кадр в массив
function saveCurrentFrame() {
    if (currentFrameIndex >= 0 && currentFrameIndex < frames.length) {
        frames[currentFrameIndex] = canvas.toDataURL();
    }
}

// Обновление UI: миниатюры и слайдер
function updateFramesUI() {
    // Обновляем слайдер
    // frameSlider.max = frames.length - 1;
    // frameSlider.value = currentFrameIndex;

    // Обновляем миниатюры
    framesStrip.innerHTML = '';
    frames.forEach((frame, index) => {
        let img = document.createElement('img');
        img.src = frame;
        img.className = 'frame-thumb';
        img.dataset.index = index;  // сохраняем индекс
        if (index === currentFrameIndex) img.classList.add('current');
        img.addEventListener('click', () => {
            saveCurrentFrame();
            loadFrame(index);
        });
        framesStrip.appendChild(img);
    });
}

// Рисование
function startDrawing(e) {
    drawing = true;
    const coords = getCanvasCoords(e);
    ctx.beginPath();
    ctx.moveTo(coords.x, coords.y);
}

function draw(e) {
    if (!drawing) return;
    const coords = getCanvasCoords(e);
    ctx.strokeStyle = currentColor;
    ctx.lineWidth = brushSize;
    ctx.lineCap = 'round';
    ctx.lineTo(coords.x, coords.y);
    ctx.stroke();
    ctx.beginPath();
    ctx.moveTo(coords.x, coords.y);
}

function stopDrawing() {
    drawing = false;
    ctx.beginPath();
    saveCurrentFrame(); // сохраняем текущий кадр после завершения рисования
    updateCurrentThumbnail();  // обновляем только текущую миниатюру
}

canvas.addEventListener('mousedown', startDrawing);
canvas.addEventListener('mousemove', draw);
canvas.addEventListener('mouseup', stopDrawing);
canvas.addEventListener('mouseout', stopDrawing);

// Добавление кадра
addFrameBtn.addEventListener('click', (e) => {
    saveCurrentFrame();
    clearCanvas();
    if (e.ctrlKey) {
        // Вставить перед текущим
        frames.splice(currentFrameIndex, 0, canvas.toDataURL());
        // currentFrameIndex остаётся тем же (новый кадр встал на его место)
    } else {
        // Добавить после текущего
        frames.splice(currentFrameIndex + 1, 0, canvas.toDataURL());
        currentFrameIndex++;
    }
    loadFrame(currentFrameIndex);
});

// Удаление кадра
deleteFrameBtn.addEventListener('click', () => {
    if (frames.length <= 1) {
        alert('Нельзя удалить единственный кадр');
        return;
    }
    saveCurrentFrame();
    frames.splice(currentFrameIndex, 1);
    if (currentFrameIndex >= frames.length) {
        currentFrameIndex = frames.length - 1;
    }
    loadFrame(currentFrameIndex);
});

// Предпросмотр
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
    previewBtn.title = 'Пауза (Space)';
    playInterval = setInterval(() => {
        let next = (currentFrameIndex + 1) % frames.length;
        loadFrame(next);
    }, frameDelay);
}

function stopPreview() {
    playing = false;
    previewBtn.innerHTML = '<i class="bi bi-play-fill"></i>';
    previewBtn.title = 'Предпросмотр (Space)';
    clearInterval(playInterval);
    playInterval = null;
}

// Сохранение
saveBtn.addEventListener('click', () => {
    saveCurrentFrame();
    // Если мульт уже имеет название (при редактировании), можно подставить
    let existingTitle = document.querySelector('input[name="title"]')?.value;
    if (existingTitle) {
        modalTitleInput.value = existingTitle;
    } else {
        modalTitleInput.value = '';
    }
    saveModal.show();
});

confirmSave.addEventListener('click', () => {
    console.log('🖱️ Кнопка сохранения нажата (обработчик сработал)');
    let title = modalTitleInput.value.trim();
    if (!title) {
        alert('Введите название');
        return;
    }
    document.getElementById('title-input').value = title;
    document.getElementById('frames-input').value = JSON.stringify(frames);
    document.getElementById('editor-form').submit();
});

// Инструменты
pencilTool.addEventListener('click', () => {
    currentTool = 'pencil';
    updateToolUI();
});
eraserTool.addEventListener('click', () => {
    currentTool = 'eraser';
    updateToolUI();
});

function updateToolUI() {
    // Сбрасываем классы иконок
    pencilTool.classList.remove('pencil-blue', 'pencil-black', 'eraser-blue', 'eraser-black');
    eraserTool.classList.remove('pencil-blue', 'pencil-black', 'eraser-blue', 'eraser-black');

    if (currentTool === 'pencil') {
        pencilTool.classList.add('pencil-blue');
        eraserTool.classList.add('eraser-black');
        currentColor = document.querySelector('.color-btn.active').dataset.color;
    } else {
        pencilTool.classList.add('pencil-black');
        eraserTool.classList.add('eraser-blue');
        currentColor = '#ffffff'; // белый для ластика
    }
}

// Размер кисти
sizeBtns.forEach(btn => {
    btn.addEventListener('click', () => {
        sizeBtns.forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        brushSize = parseInt(btn.dataset.size);
    });
});

// Цвет
colorBtns.forEach(btn => {
    btn.addEventListener('click', () => {
        colorBtns.forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        if (currentTool === 'pencil') {
            currentColor = btn.dataset.color;
        }
    });
});

// Ползунок кадров
// // frameSlider.addEventListener('input', () => {
//     if (playing) stopPreview();
//     saveCurrentFrame();
//     loadFrame(parseInt(frameSlider.value));
// });

// Горячие клавиши
document.addEventListener('keydown', (e) => {
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;

    switch (e.key) {
        case 'Insert':
            addFrameBtn.click();
            e.preventDefault();
            break;
        case 'Delete':
            deleteFrameBtn.click();
            e.preventDefault();
            break;
        case ' ':
            e.preventDefault();
            previewBtn.click();
            break;
        case 's':
            if (e.ctrlKey) {
                e.preventDefault();
                saveBtn.click();
            }
            break;
        case 'p':
            pencilTool.click();
            e.preventDefault();
            break;
        case 'e':
            eraserTool.click();
            e.preventDefault();
            break;
        case '1':
        case '2':
        case '3':
        case '4':
        case '5':
            let size = parseInt(e.key);
            sizeBtns[size-1]?.click();
            e.preventDefault();
            break;
        case 'b':
            document.querySelector('.color-btn[data-color="#000000"]')?.click();
            e.preventDefault();
            break;
        case 'r':
            document.querySelector('.color-btn[data-color="#dc3545"]')?.click();
            e.preventDefault();
            break;
    }
});

// Инициализация
initFrames();