// Динамика формы вопроса: смена типа, добавление/удаление вариантов
(function () {
    const answersBlock = document.getElementById('answersBlock');
    const textWarning = document.getElementById('textWarning');
    const container = document.getElementById('answersContainer');
    const addBtn = document.getElementById('addAnswerBtn');
    const form = document.getElementById('questionForm');

    if (!form) return;

    // ==== Показ/скрытие блока вариантов в зависимости от типа ====
    function updateVisibility() {
        const type = form.querySelector('input[name="question_type"]:checked').value;
        if (type === 'text') {
            answersBlock.classList.add('d-none');
            textWarning.classList.remove('d-none');
        } else {
            answersBlock.classList.remove('d-none');
            textWarning.classList.add('d-none');
        }
    }

    form.querySelectorAll('input[name="question_type"]').forEach(function (radio) {
        radio.addEventListener('change', updateVisibility);
    });

    updateVisibility();

    // ==== Пересчёт индексов чекбоксов после удаления ====
    function reindex() {
        const rows = container.querySelectorAll('.answer-row');
        rows.forEach(function (row, idx) {
            const checkbox = row.querySelector('input[type="checkbox"]');
            checkbox.name = 'answer_correct_' + idx;
        });
    }

    // ==== Добавление нового варианта ====
    if (addBtn) {
        addBtn.addEventListener('click', function () {
            const rows = container.querySelectorAll('.answer-row');
            const idx = rows.length;
            const div = document.createElement('div');
            div.className = 'input-group mb-2 answer-row';
            div.innerHTML = `
                <div class="input-group-text">
                    <input type="checkbox" name="answer_correct_${idx}"
                           class="form-check-input mt-0">
                </div>
                <input type="text" name="answer_text[]" class="form-control"
                       placeholder="Текст варианта ответа">
                <button type="button" class="btn btn-outline-danger remove-answer">
                    <i class="bi bi-x"></i>
                </button>
            `;
            container.appendChild(div);
            div.querySelector('input[type="text"]').focus();
        });
    }

    // ==== Удаление варианта (делегирование) ====
    container.addEventListener('click', function (e) {
        const btn = e.target.closest('.remove-answer');
        if (!btn) return;
        const rows = container.querySelectorAll('.answer-row');
        if (rows.length <= 2) {
            alert('Нужно минимум 2 варианта ответа.');
            return;
        }
        btn.closest('.answer-row').remove();
        reindex();
    });

    // ==== Ограничение: для типа «Один ответ» — только одна галочка ====
    container.addEventListener('change', function (e) {
        if (!e.target.matches('input[type="checkbox"]')) return;
        const type = form.querySelector('input[name="question_type"]:checked').value;
        if (type === 'single' && e.target.checked) {
            container.querySelectorAll('input[type="checkbox"]').forEach(function (cb) {
                if (cb !== e.target) cb.checked = false;
            });
        }
    });
})();