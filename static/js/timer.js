// Таймер обратного отсчёта для теста
(function () {
    const timerEl = document.getElementById('timer');
    if (!timerEl) return;

    const form = document.getElementById('testForm');

    function updateTimer() {
        const now = Date.now();
        const elapsed = Math.floor((now - startedAt) / 1000);
        const remaining = timeLimitSeconds - elapsed;

        if (remaining <= 0) {
            timerEl.textContent = '00:00';
            timerEl.classList.remove('text-primary');
            timerEl.classList.add('text-danger');
            // Автоотправка формы
            if (form && !form.dataset.submitted) {
                form.dataset.submitted = '1';
                alert('Время вышло! Тест будет отправлен автоматически.');
                form.submit();
            }
            return;
        }

        const minutes = Math.floor(remaining / 60);
        const seconds = remaining % 60;
        timerEl.textContent =
            String(minutes).padStart(2, '0') + ':' +
            String(seconds).padStart(2, '0');

        // Подсветка при малом времени
        if (remaining <= 60) {
            timerEl.classList.remove('text-primary');
            timerEl.classList.add('text-danger');
        }
    }

    updateTimer();
    setInterval(updateTimer, 1000);
})();