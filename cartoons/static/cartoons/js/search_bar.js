// Поисковая строка в шапке: на странице поиска работает "живьём" -
// набор в поле сразу фильтрует выдачу без перезагрузки, клики по
// тегам-капсулам добавляют/убирают фильтры прямо в строку. На любой
// другой странице клик по строке сразу перекидывает на страницу
// поиска (как в Janitor AI).
(function () {
    const scriptEl = document.currentScript;
    const SEARCH_URL = scriptEl.dataset.searchUrl;
    const SET_MODE_URL = scriptEl.dataset.setModeUrl;
    const AUTHENTICATED = scriptEl.dataset.authenticated === '1';
    const IS_SEARCH_PAGE = window.location.pathname === SEARCH_URL;

    function getCsrf() {
        for (const c of document.cookie.split(';')) {
            const t = c.trim();
            if (t.startsWith('csrftoken=')) return decodeURIComponent(t.slice('csrftoken='.length));
        }
        return '';
    }

    const state = { q: '', tagsIn: [], tagsOut: [], mode: 'and', page: 1 };

    document.addEventListener('DOMContentLoaded', function () {
        const bar = document.getElementById('search-bar');
        const form = document.getElementById('search-form');
        const textInput = document.getElementById('search-text-input');
        const chipsContainer = document.getElementById('search-chips');
        const modeBtn = document.getElementById('search-mode-btn');
        if (!bar || !textInput || !chipsContainer || !modeBtn) return;

        state.mode = modeBtn.dataset.mode === 'or' ? 'or' : 'and';

        function updateModeBtn() {
            modeBtn.textContent = state.mode.toUpperCase();
            modeBtn.title = state.mode === 'and'
                ? 'И: показывать мульты, у которых есть ВСЕ выбранные теги. Нажмите, чтобы переключить на ИЛИ.'
                : 'ИЛИ: показывать мульты, у которых есть хотя бы один из выбранных тегов. Нажмите, чтобы переключить на И.';
        }

        // ── Редирект на страницу поиска с любой другой страницы ────────────
        if (!IS_SEARCH_PAGE) {
            textInput.addEventListener('focus', function () {
                window.location.href = SEARCH_URL;
            });
            bar.addEventListener('mousedown', function (e) {
                if (e.target === modeBtn) return;
                window.location.href = SEARCH_URL;
            });
            updateModeBtn();
            modeBtn.addEventListener('click', function () {
                state.mode = state.mode === 'and' ? 'or' : 'and';
                updateModeBtn();
                if (AUTHENTICATED) {
                    fetch(SET_MODE_URL, {
                        method: 'POST',
                        headers: {
                            'X-CSRFToken': getCsrf(),
                            'Content-Type': 'application/x-www-form-urlencoded',
                        },
                        body: 'mode=' + state.mode,
                    });
                }
            });
            return;
        }

        // ── Живой поиск на странице поиска ──────────────────────────────────
        function makeChip(tag, exclude) {
            const span = document.createElement('span');
            span.className = 'search-chip' + (exclude ? ' search-chip-exclude' : '');
            span.dataset.tag = tag;
            span.dataset.exclude = exclude ? '1' : '0';
            const label = document.createElement('span');
            label.className = 'search-chip-label';
            label.textContent = tag;
            const remove = document.createElement('button');
            remove.type = 'button';
            remove.className = 'search-chip-remove';
            remove.setAttribute('aria-label', 'Убрать фильтр «' + tag + '»');
            remove.textContent = '×';
            span.appendChild(label);
            span.appendChild(remove);
            return span;
        }

        function renderChips() {
            chipsContainer.querySelectorAll('.search-chip').forEach(el => el.remove());
            const frag = document.createDocumentFragment();
            state.tagsIn.forEach(t => frag.appendChild(makeChip(t, false)));
            state.tagsOut.forEach(t => frag.appendChild(makeChip(t, true)));
            chipsContainer.insertBefore(frag, textInput);
        }

        function buildParams(forAjax) {
            const p = new URLSearchParams();
            if (state.q) p.set('q', state.q);
            state.tagsIn.forEach(t => p.append('tag', t));
            state.tagsOut.forEach(t => p.append('extag', t));
            p.set('mode', state.mode);
            if (state.page > 1) p.set('page', String(state.page));
            if (forAjax) p.set('ajax', '1');
            return p;
        }

        let abortController = null;
        function runSearch() {
            history.replaceState(null, '', SEARCH_URL + '?' + buildParams(false).toString());
            if (abortController) abortController.abort();
            abortController = new AbortController();
            fetch(SEARCH_URL + '?' + buildParams(true).toString(), { signal: abortController.signal })
                .then(r => r.json())
                .then(data => {
                    document.getElementById('search-tag-cloud').innerHTML = data.tags_html;
                    document.getElementById('search-results-wrap').innerHTML = data.results_html;
                })
                .catch(err => { if (err.name !== 'AbortError') console.error(err); });
        }

        function addTagIn(tag) {
            state.tagsOut = state.tagsOut.filter(t => t !== tag);
            if (!state.tagsIn.includes(tag)) state.tagsIn.push(tag);
            state.page = 1;
            renderChips();
            runSearch();
        }
        function addTagOut(tag) {
            state.tagsIn = state.tagsIn.filter(t => t !== tag);
            if (!state.tagsOut.includes(tag)) state.tagsOut.push(tag);
            state.page = 1;
            renderChips();
            runSearch();
        }

        // Начальное состояние - из query-строки текущего URL (сюда могли
        // прийти со страницы мульта с уже готовым тегом в капсуле).
        const initParams = new URLSearchParams(window.location.search);
        state.q = initParams.get('q') || '';
        state.tagsIn = initParams.getAll('tag');
        state.tagsOut = initParams.getAll('extag');
        const initMode = initParams.get('mode');
        if (initMode === 'and' || initMode === 'or') state.mode = initMode;
        state.page = parseInt(initParams.get('page') || '1', 10) || 1;
        renderChips();
        updateModeBtn();

        let debounceTimer = null;
        textInput.addEventListener('input', function () {
            state.q = textInput.value;
            state.page = 1;
            clearTimeout(debounceTimer);
            debounceTimer = setTimeout(runSearch, 300);
        });
        textInput.addEventListener('keydown', function (e) {
            if (e.key === 'Enter') {
                e.preventDefault();
                clearTimeout(debounceTimer);
                runSearch();
            }
        });
        if (form) {
            form.addEventListener('submit', function (e) { e.preventDefault(); });
        }

        modeBtn.addEventListener('click', function () {
            state.mode = state.mode === 'and' ? 'or' : 'and';
            state.page = 1;
            updateModeBtn();
            if (AUTHENTICATED) {
                fetch(SET_MODE_URL, {
                    method: 'POST',
                    headers: {
                        'X-CSRFToken': getCsrf(),
                        'Content-Type': 'application/x-www-form-urlencoded',
                    },
                    body: 'mode=' + state.mode,
                });
            }
            runSearch();
        });

        chipsContainer.addEventListener('click', function (e) {
            const btn = e.target.closest('.search-chip-remove');
            if (!btn) return;
            const chip = btn.closest('.search-chip');
            const tag = chip.dataset.tag;
            if (chip.dataset.exclude === '1') {
                state.tagsOut = state.tagsOut.filter(t => t !== tag);
            } else {
                state.tagsIn = state.tagsIn.filter(t => t !== tag);
            }
            state.page = 1;
            renderChips();
            runSearch();
        });

        // Клики по капсулам тегов (облако над результатами) - добавляют
        // фильтр прямо в строку поиска, без перезагрузки страницы.
        document.addEventListener('click', function (e) {
            const label = e.target.closest('.tag-pill-label');
            const xBtn = e.target.closest('.tag-pill-x');
            if (!label && !xBtn) return;
            e.preventDefault();
            const el = label || xBtn;
            const tag = el.dataset.tag;
            if (label) addTagIn(tag); else addTagOut(tag);
        });

        // Клики по пагинации внутри результатов поиска - тоже без
        // перезагрузки, меняем только номер страницы.
        document.addEventListener('click', function (e) {
            const link = e.target.closest('#search-results-wrap .page-link');
            if (!link || !link.closest('#search-results-wrap') || link.closest('.disabled')) return;
            if (!link.getAttribute('href')) return;
            e.preventDefault();
            const url = new URL(link.href, window.location.origin);
            state.page = parseInt(url.searchParams.get('page') || '1', 10) || 1;
            runSearch();
            window.scrollTo({ top: 0, behavior: 'smooth' });
        });
    });
})();
