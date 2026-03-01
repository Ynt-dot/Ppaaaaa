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

// Функция очистки холста (заливка белым)
function clearCanvas() {
    ctx.fillStyle = '#ffffff';
    ctx.fillRect(0, 0, canvas.width, canvas.height);
}

// Инициализация: если есть переданные кадры, загружаем, иначе создаём первый пустой кадр
function initFrames() {
    console.log('initFrames started');
    console.log('framesData exists?', typeof framesData !== 'undefined');
    if (typeof framesData !== 'undefined' && framesData.length > 0) {
        console.log('Loading existing frames, count:', framesData.length);
        frames = framesData;
        currentFrameIndex = 0;
        let img = new Image();
        img.src = frames[0];
        img.onload = () => {
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            ctx.drawImage(img, 0, 0);
            updateFramesList();
        };
    } else {
        console.log('Creating first empty frame');
        clearCanvas();
        let dataURL = canvas.toDataURL();
        frames = [dataURL];
        currentFrameIndex = 0;
        console.log('Frames array length:', frames.length);
        updateFramesList();
    }
}

// Обновление списка миниатюр
function updateFramesList() {
    console.log('updateFramesList called, frames length:', frames.length);
    if (!framesListDiv) {
        console.error('frames-list element not found!');
        return;
    }
    framesListDiv.innerHTML = '';
    frames.forEach((frame, index) => {
        console.log('Adding thumbnail for index', index);
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

// Настройка рисования
canvas.addEventListener('mousedown', (e) => {
    drawing = true;
    ctx.beginPath();
    ctx.moveTo(e.offsetX, e.offsetY);
});

canvas.addEventListener('mousemove', (e) => {
    if (!drawing) return;
    ctx.strokeStyle = currentColor;
    ctx.lineWidth = brushSize;
    ctx.lineCap = 'round';
    ctx.lineTo(e.offsetX, e.offsetY);
    ctx.stroke();
    ctx.beginPath();
    ctx.moveTo(e.offsetX, e.offsetY);
});

canvas.addEventListener('mouseup', () => {
    drawing = false;
    ctx.beginPath();
});

canvas.addEventListener('mouseout', () => {
    drawing = false;
    ctx.beginPath();
});

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
        clearCanvas();
    });
}

// Добавление нового кадра
if (addFrameBtn) {
    addFrameBtn.addEventListener('click', () => {
        // Сохраняем текущий кадр
        if (currentFrameIndex >= 0) {
            frames[currentFrameIndex] = canvas.toDataURL();
        }
        // Очищаем холст
        clearCanvas();
        // Добавляем новый кадр
        frames.push(canvas.toDataURL());
        currentFrameIndex = frames.length - 1;
        updateFramesList();
    });
}

// Копирование текущего кадра
if (copyFrameBtn) {
    copyFrameBtn.addEventListener('click', () => {
        if (currentFrameIndex >= 0) {
            frames[currentFrameIndex] = canvas.toDataURL();
            frames.push(frames[currentFrameIndex]);
            currentFrameIndex = frames.length - 1;
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

// Перед отправкой формы сохраняем все кадры в скрытое поле
let form = document.getElementById('editor-form');
let framesInput = document.getElementById('frames-input');

if (form) {
    form.addEventListener('submit', (e) => {
        // Сохраняем текущий кадр
        if (currentFrameIndex >= 0) {
            frames[currentFrameIndex] = canvas.toDataURL();
        }
        framesInput.value = JSON.stringify(frames);
        // Разрешаем отправку
        return true;
    });
}

// Запускаем инициализацию после загрузки DOM
document.addEventListener('DOMContentLoaded', initFrames);