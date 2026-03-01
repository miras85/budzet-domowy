const state = {
    token: localStorage.getItem('token') || null
};

async function authFetch(url, options = {}) {
    if (!options.headers) options.headers = {};
    if (state.token) {
        options.headers['Authorization'] = `Bearer ${state.token}`;
    }
    
    const res = await fetch(url, options);
    if (res.status === 401) {
        logout();
        throw new Error("Unauthorized");
    }
    return res;
}

export function setToken(newToken) {
    state.token = newToken;
    if(newToken) localStorage.setItem('token', newToken);
    else localStorage.removeItem('token');
}

export function getToken() { return state.token; }

export function logout() {
    setToken(null);
}

export const auth = {
    async login(username, password) {
        const formData = new FormData();
        formData.append('username', username);
        formData.append('password', password);
        const res = await fetch('/token', { method: 'POST', body: formData });
        
        if (!res.ok) {
            // Spróbuj wyciągnąć szczegółowy komunikat z serwera
            const errorData = await res.json().catch(() => ({}));
            const errorMsg = errorData.detail || `Błąd: ${res.status}`;
            throw new Error(errorMsg);
        }
        
        return await res.json();
    },
    // ... reszta bez zmian
    async changePassword(oldPwd, newPwd) {
        return authFetch('/api/users/change-password', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ old_password: oldPwd, new_password: newPwd })
        });
    },
    async register(username, password) {
        return authFetch('/api/users', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ username, password })
        });
    }
};

export const finance = {
    async getDashboard(offset) { return (await authFetch(`/api/dashboard?offset=${offset}`)).json(); },
    async getTrend() { return (await authFetch('/api/stats/trend')).json(); }
};

export const transactions = {
    async create(txData) { return authFetch('/api/transactions', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(txData) }); },
    async update(id, txData) { return authFetch(`/api/transactions/${id}`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(txData) }); },
    async delete(id) { return authFetch(`/api/transactions/${id}`, { method: 'DELETE' }); },
    async search(params) { return (await authFetch(`/api/transactions/search?${params}`)).json(); }
};

export const accounts = {
    async getAll() { return (await authFetch('/api/accounts')).json(); },
    async create(data) { return authFetch('/api/accounts', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) }); },
    async update(id, data) { return authFetch(`/api/accounts/${id}`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) }); },
    async delete(id) { return authFetch(`/api/accounts/${id}`, { method: 'DELETE' }); }
};

export const goals = {
    async getAll() { return (await authFetch('/api/goals')).json(); },
    async create(data) { return authFetch('/api/goals', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) }); },
    async delete(id) { return authFetch(`/api/goals/${id}`, { method: 'DELETE' }); },
    async fund(id, data) { return authFetch(`/api/goals/${id}/fund`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) }); },
    async withdraw(id, data) { return authFetch(`/api/goals/${id}/withdraw`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) }); },
    async transfer(id, data) { return authFetch(`/api/goals/${id}/transfer`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) }); },
    async update(id, data) {
            return authFetch(`/api/goals/${id}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });
        }
};

export const loans = {
    async getAll() { return (await authFetch('/api/loans')).json(); },
    async create(data) { return authFetch('/api/loans', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) }); },
    async update(id, data) { return authFetch(`/api/loans/${id}`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) }); }
};

export const recurring = {
    async getAll() { return (await authFetch('/api/recurring')).json(); },
    async checkDue() { return (await authFetch('/api/recurring/check')).json(); },
    async create(data) { return authFetch('/api/recurring', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) }); },
    async delete(id) { return authFetch(`/api/recurring/${id}`, { method: 'DELETE' }); },
    async process(id, dateStr) { return authFetch(`/api/recurring/${id}/process`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ date: dateStr }) }); },
    async skip(id) { return authFetch(`/api/recurring/${id}/skip`, { method: 'POST' }); },
    async update(id, data) {
            return authFetch(`/api/recurring/${id}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });
        }

};

export const categories = {
    async getAll() { return (await authFetch('/api/categories')).json(); },
    // ZMIANA TUTAJ: przyjmujemy obiekt 'data' zamiast 'name'
        async create(data) {
            return authFetch('/api/categories', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data) // data to { name, icon, color }
            });
        },
    async getTrend(id) {
            return (await authFetch(`/api/categories/${id}/trend`)).json();
        },
    async update(id, data) { return authFetch(`/api/categories/${id}`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) }); },
    async delete(id) { return authFetch(`/api/categories/${id}`, { method: 'DELETE' }); }
};

export const settings = {
    async getOverrides() { return (await authFetch('/api/settings/payday-overrides')).json(); },
    async addOverride(data) { return authFetch('/api/settings/payday-overrides', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) }); },
    async deleteOverride(id) { return authFetch(`/api/settings/payday-overrides/${id}`, { method: 'DELETE' }); }
};

export const importCSV = {
    async preview(file) {
        const formData = new FormData();
        formData.append('file', file);
        return authFetch('/api/import/preview', { method: 'POST', body: formData });
    },
    async confirm(accountId, transactions) {
        return authFetch('/api/import/confirm', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ account_id: accountId, transactions }) });
    }
};
