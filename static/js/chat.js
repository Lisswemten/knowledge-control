(function () {
    const toggleBtn = document.getElementById('chatToggleBtn');
    const popup = document.getElementById('chatPopup');
    const closeBtn = document.getElementById('chatCloseBtn');
    const form = document.getElementById('chatForm');
    const input = document.getElementById('chatInput');
    const messagesDiv = document.getElementById('chatMessages');

    if (!toggleBtn || !popup) return;

    let intervalId = null;

    // ==== Показать/скрыть попап ====
    toggleBtn.addEventListener('click', function () {
        if (popup.style.display === 'none' || !popup.style.display) {
            popup.style.display = 'flex';
            loadMessages(true);
            startPolling();
            input.focus();
        } else {
            closeChat();
        }
    });

    closeBtn.addEventListener('click', closeChat);

    function closeChat() {
        popup.style.display = 'none';
        stopPolling();
    }

    // ==== Загрузка сообщений ====
    function loadMessages(scrollToBottom = false) {
        fetch('/chat/messages/')
            .then(r => r.json())
            .then(data => {
                const messages = data.messages || [];
                if (!messages.length) {
                    messagesDiv.innerHTML = '<div class="text-center text-muted small">Сообщений пока нет</div>';
                    return;
                }

                messagesDiv.innerHTML = messages.map(m => {
                    const bubbleClass = m.is_mine ? 'bg-primary text-white' : 'bg-white border';
                    const marginClass = m.is_mine ? 'ms-auto' : '';
                    return `
                        <div class="mb-2">
                            <div class="small text-muted">
                                <strong>${escapeHtml(m.sender)}</strong> · ${m.created_at}
                            </div>
                            <div class="p-2 rounded ${bubbleClass} ${marginClass}"
                                 style="display: inline-block; max-width: 85%;">
                                ${escapeHtml(m.text)}
                            </div>
                        </div>
                    `;
                }).join('');

                if (scrollToBottom) {
                    messagesDiv.scrollTop = messagesDiv.scrollHeight;
                }
            })
            .catch(err => console.error('Chat error:', err));
    }

    // ==== Отправка ====
    form.addEventListener('submit', function (e) {
        e.preventDefault();
        const text = input.value.trim();
        if (!text) return;

        const formData = new FormData();
        formData.append('text', text);

        fetch('/chat/send/', {
            method: 'POST',
            body: formData,
            headers: {
                'X-CSRFToken': getCookie('csrftoken'),
            },
        })
            .then(r => r.json())
            .then(data => {
                if (data.ok) {
                    input.value = '';
                    loadMessages(true);
                } else {
                    alert(data.error || 'Ошибка отправки');
                }
            })
            .catch(err => console.error('Send error:', err));
    });

    // ==== Опрос каждые 3 секунды ====
    function startPolling() {
        if (intervalId) return;
        intervalId = setInterval(() => loadMessages(true), 3000);
    }

    function stopPolling() {
        if (intervalId) {
            clearInterval(intervalId);
            intervalId = null;
        }
    }

    // ==== CSRF-токен ====
    function getCookie(name) {
        const value = `; ${document.cookie}`;
        const parts = value.split(`; ${name}=`);
        if (parts.length === 2) return parts.pop().split(';').shift();
    }

    // ==== Защита от XSS ====
    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
})();