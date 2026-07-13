// Pobierz token z URL
const params = new URLSearchParams(window.location.search);
const token = params.get('token');

// Sprawdź czy token istnieje
if (!token) {
    document.getElementById('loading').classList.add('hidden');
    document.getElementById('error').classList.remove('hidden');
} else {
    document.getElementById('loading').classList.add('hidden');
    document.getElementById('form').classList.remove('hidden');
}

async function register() {
    const username = document.getElementById('username').value.trim();
    const password = document.getElementById('password').value;
    const password2 = document.getElementById('password2').value;
    const errorMsg = document.getElementById('error-msg');
    const btn = document.getElementById('submit-btn');

    if (!username || !password) {
        errorMsg.textContent = 'Wypełnij wszystkie pola';
        errorMsg.classList.remove('hidden');
        return;
    }
    if (password.length < 8) {
        errorMsg.textContent = 'Hasło musi mieć minimum 8 znaków';
        errorMsg.classList.remove('hidden');
        return;
    }
    if (password !== password2) {
        errorMsg.textContent = 'Hasła nie są identyczne';
        errorMsg.classList.remove('hidden');
        return;
    }

    btn.textContent = 'Tworzenie konta...';
    btn.disabled = true;
    errorMsg.classList.add('hidden');

    try {
        const res = await fetch(`/api/register?token=${token}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password })
        });

        if (res.ok) {
            document.getElementById('form').classList.add('hidden');
            document.getElementById('success').classList.remove('hidden');
        } else {
            const data = await res.json();
            errorMsg.textContent = data.detail || 'Błąd rejestracji';
            errorMsg.classList.remove('hidden');
            btn.textContent = 'Utwórz konto';
            btn.disabled = false;
        }
    } catch(e) {
        errorMsg.textContent = 'Błąd połączenia';
        errorMsg.classList.remove('hidden');
        btn.textContent = 'Utwórz konto';
        btn.disabled = false;
    }
}

// Enter key support
document.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') register();
});

document.getElementById('submit-btn').addEventListener('click', register);
