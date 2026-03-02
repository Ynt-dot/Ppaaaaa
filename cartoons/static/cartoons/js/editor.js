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
        img.style.width = '80px';
        img.style.height = 'auto';
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
    deleteFrameBtn.addEventListener('click', function() {
        console.log('=== Нажата кнопка Удалить ===');
        console.log('Текущий индекс до удаления:', currentFrameIndex);
        console.log('Количество кадров до удаления:', frames.length);
        console.log('Массив кадров до удаления (индексы):', frames.map((_, i) => i).join(','));

        // Сохраняем текущее состояние холста в массив
        if (currentFrameIndex >= 0 && currentFrameIndex < frames.length) {
            frames[currentFrameIndex] = canvas.toDataURL();
            console.log('Сохранён текущий кадр с индексом', currentFrameIndex);
        } else {
            console.error('Ошибка: currentFrameIndex вне диапазона');
            return;
        }

        // Проверяем, можно ли удалить
        if (frames.length <= 1) {
            alert('Нельзя удалить единственный кадр');
            console.log('Удаление отменено: остался бы 0 кадров');
            return;
        }

        // Удаляем кадр с текущим индексом
        console.log('Удаляем кадр с индексом', currentFrameIndex);
        const deleted = frames.splice(currentFrameIndex, 1);
        console.log('Удалённый кадр:', deleted[0] ? 'dataURL' : 'пусто');
        console.log('Новая длина массива после удаления:', frames.length);
        console.log('Теперь кадры имеют индексы от 0 до', frames.length-1);

        // Определяем новый индекс для отображения
        let newIndex;
        if (frames.length === 0) {
            // Такого не должно быть из-за проверки выше, но на всякий случай
            console.error('Неожиданно пустой массив после удаления');
            return;
        } else if (currentFrameIndex >= frames.length) {
            // Если удалили последний кадр, показываем новый последний
            newIndex = frames.length - 1;
        } else {
            // Иначе показываем кадр, который стоял на том же месте (следующий после удалённого)
            newIndex = currentFrameIndex;
        }
        console.log('Выбранный для отображения индекс:', newIndex);

        // Загружаем новый кадр
        console.log('Попытка загрузить кадр с индексом', newIndex);
        let img = new Image();
        img.src = frames[newIndex];
        img.onload = function() {
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            ctx.drawImage(img, 0, 0);
            currentFrameIndex = newIndex;
            console.log('Кадр успешно загружен, currentFrameIndex теперь =', currentFrameIndex);
            updateFramesList();
        };
        img.onerror = function() {
            console.error('ОШИБКА: не удалось загрузить кадр с индексом', newIndex);
        };
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

// Предпросмотр анимации
const previewBtn = document.getElementById('preview-btn');
const previewModal = document.getElementById('previewModal');
const previewFrame = document.getElementById('preview-frame');
const previewSlider = document.getElementById('preview-slider');
const previewCounter = document.getElementById('preview-counter');
const previewPlayPause = document.getElementById('preview-playpause');

let previewPlaying = false;
let previewInterval = null;
let previewCurrentFrame = 0;
let previewFrames = [];
let previewFps = 12;

if (previewBtn && previewModal) {
    previewBtn.addEventListener('click', function() {
        // Сохраняем текущий кадр в массив
        if (currentFrameIndex >= 0) {
            frames[currentFrameIndex] = canvas.toDataURL();
        }
        // Берём копию кадров
        previewFrames = frames.slice();
        // Получаем FPS из поля ввода
        const fpsInput = document.querySelector('input[name="fps"]');
        previewFps = fpsInput ? parseInt(fpsInput.value) : 12;

        // Настраиваем слайдер
        previewSlider.max = previewFrames.length - 1;
        previewSlider.value = 0;
        previewCounter.textContent = `1 / ${previewFrames.length}`;
        // Показываем первый кадр
        previewFrame.src = previewFrames[0];
        previewCurrentFrame = 0;

        // Если ранее был запущен предпросмотр, останавливаем
        if (previewInterval) {
            clearInterval(previewInterval);
            previewInterval = null;
            previewPlaying = false;
            previewPlayPause.textContent = '▶️ Воспроизвести';
        }

        // Показываем модальное окно через Bootstrap
        const modal = new bootstrap.Modal(previewModal);
        modal.show();

        // Автоматически запускаем воспроизведение после открытия
        previewModal.addEventListener('shown.bs.modal', function onShown() {
            playPreview();
            previewModal.removeEventListener('shown.bs.modal', onShown);
        });
    });
}

function loadPreviewFrame(index) {
    if (index < 0 || index >= previewFrames.length) return;
    previewCurrentFrame = index;
    previewFrame.src = previewFrames[index];
    previewSlider.value = index;
    previewCounter.textContent = `${index+1} / ${previewFrames.length}`;
}

function playPreview() {
    if (previewPlaying) return;
    previewPlaying = true;
    previewPlayPause.textContent = '⏸️ Пауза';
    const delay = 1000 / previewFps;
    previewInterval = setInterval(() => {
        let nextFrame = (previewCurrentFrame + 1) % previewFrames.length;
        loadPreviewFrame(nextFrame);
    }, delay);
}

function pausePreview() {
    if (!previewPlaying) return;
    previewPlaying = false;
    previewPlayPause.textContent = '▶️ Воспроизвести';
    clearInterval(previewInterval);
    previewInterval = null;
}

if (previewPlayPause) {
    previewPlayPause.addEventListener('click', () => {
        if (previewPlaying) {
            pausePreview();
        } else {
            playPreview();
        }
    });
}

if (previewSlider) {
    previewSlider.addEventListener('input', function() {
        if (previewPlaying) pausePreview();
        loadPreviewFrame(parseInt(this.value));
    });
}

// Очистка при закрытии модального окна
previewModal.addEventListener('hidden.bs.modal', function() {
    if (previewInterval) {
        clearInterval(previewInterval);
        previewInterval = null;
        previewPlaying = false;
    }
});