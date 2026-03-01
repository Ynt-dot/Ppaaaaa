// editor.js

let canvas = document.getElementById('draw-canvas');
let ctx = canvas.getContext('2d');
let drawing = false;
let currentColor = '#000000';
let brushSize = 2;

// Массив кадров (dataURL)
let frames = [];
let currentFrameIndex = -1;

// Элементы управления
let colorPicker = document.getElementById('color-picker');
let brushSizeInput = document.getElementById('brush-size');
let clearBtn = document.getElementById('clear-canvas');
let addFrameBtn = document.getElementById('add-frame');
let copyFrameBtn = document.getElementById('copy-frame');
let deleteFrameBtn = document.getElementById('delete-frame');
let framesListDiv = document.getElementById('frames-list');

// Инициализация
ctx.fillStyle = '#ffffff';
ctx.fillRect(0, 0, canvas.width, canvas.height);

// Настройка рисования
canvas.addEventListener('mousedown', startDrawing);
canvas.addEventListener('mousemove', draw);
canvas.addEventListener('mouseup', stopDrawing);
canvas.addEventListener('mouseout', stopDrawing);

function startDrawing(e) {
    drawing = true;
    ctx.beginPath();
    ctx.moveTo(e.offsetX, e.offsetY);
}

function draw(e) {
    if (!drawing) return;
    ctx.strokeStyle = currentColor;
    ctx.lineWidth = brushSize;
    ctx.lineCap = 'round';
    ctx.lineTo(e.offsetX, e.offsetY);
    ctx.stroke();
    ctx.beginPath();
    ctx.moveTo(e.offsetX, e.offsetY);
}

function stopDrawing() {
    drawing = false;
    ctx.beginPath(); // чтобы не соединялись линии при следующем клике
}

// Если на странице есть переменная framesData (передана из Django)
if (typeof framesData !== 'undefined' && framesData.length > 0) {
    frames = framesData;
    currentFrameIndex = 0;
    // Загружаем первый кадр на холст
    let img = new Image();
    img.src = frames[0];
    img.onload = () => {
        ctx.drawImage(img, 0, 0);
        updateFramesList();
    };
}

// Изменение цвета
if (colorPicker) {
    colorPicker.addEventListener('input', (e) => {
        currentColor = e.target.value;
    });
}

// Изменение толщины
if (brushSizeInput) {
    brushSizeInput.addEventListener('input', (e) => {
        brushSize = parseInt(e.target.value);
    });
}

// Очистка холста (заливка белым)
if (clearBtn) {
    clearBtn.addEventListener('click', () => {
        ctx.fillStyle = '#ffffff';
        ctx.fillRect(0, 0, canvas.width, canvas.height);
    });
}

// Добавление нового кадра
if (addFrameBtn) {
    addFrameBtn.addEventListener('click', () => {
        // Сохраняем текущий кадр, если есть
        if (currentFrameIndex >= 0) {
            frames[currentFrameIndex] = canvas.toDataURL();
        }
        // Очищаем холст
        ctx.fillStyle = '#ffffff';
        ctx.fillRect(0, 0, canvas.width, canvas.height);
        // Добавляем новый пустой кадр (пока просто dataURL белого холста)
        frames.push(canvas.toDataURL());
        currentFrameIndex = frames.length - 1;
        updateFramesList();
    });
}

// Копирование текущего кадра
if (copyFrameBtn) {
    copyFrameBtn.addEventListener('click', () => {
        if (currentFrameIndex >= 0) {
            // Сохраняем текущее состояние в массив
            frames[currentFrameIndex] = canvas.toDataURL();
            // Копируем в новый кадр
            frames.push(frames[currentFrameIndex]);
            currentFrameIndex = frames.length - 1;
            // Загружаем этот кадр на холст
            loadFrame(currentFrameIndex);
        }
    });
}

// Удаление кадра
if (deleteFrameBtn) {
    deleteFrameBtn.addEventListener('click', () => {
        if (frames.length > 1 && currentFrameIndex >= 0) {
            frames.splice(currentFrameIndex, 1);
            if (currentFrameIndex >= frames.length) {
                currentFrameIndex = frames.length - 1;
            }
            loadFrame(currentFrameIndex);
        } else {
            alert('Нельзя удалить единственный кадр');
        }
    });
}

// Обновление списка миниатюр
function updateFramesList() {
    framesListDiv.innerHTML = '';
    frames.forEach((frame, index) => {
        let img = document.createElement('img');
        img.src = frame;
        img.style.width = '60px';
        img.style.height = '45px';
        img.style.margin = '2px';
        img.style.border = index === currentFrameIndex ? '3px solid red' : '1px solid gray';
        img.style.cursor = 'pointer';
        img.addEventListener('click', () => {
            loadFrame(index);
        });
        framesListDiv.appendChild(img);
    });
}

// Загрузка кадра на холст
function loadFrame(index) {
    if (currentFrameIndex >= 0) {
        frames[currentFrameIndex] = canvas.toDataURL();
    }
    let img = new Image();
    img.src = frames[index];
    img.onload = () => {
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        ctx.drawImage(img, 0, 0);
        currentFrameIndex = index;
        updateFramesList();
    };
}

// Перед отправкой формы сохраняем все кадры в скрытое поле
let form = document.getElementById('editor-form');
let framesInput = document.getElementById('frames-input');

form.addEventListener('submit', (e) => {
    // Сохраняем текущий кадр в массив
    if (currentFrameIndex >= 0) {
        frames[currentFrameIndex] = canvas.toDataURL();
    }
    // Записываем JSON в скрытое поле
    framesInput.value = JSON.stringify(frames);
    // Разрешаем отправку формы
    return true;
});