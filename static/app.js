const { createApp } = Vue

createApp({
    data() {
        return {
            isLoggedIn: false,
            loginForm: { username: '', password: '' },
            loginError: '',
            token: localStorage.getItem('token') || null,
            security: { oldPassword: '', newPassword: '', newUsername: '', newUserPass: '' },
            
            currentTab: 'dashboard',
            viewMode: 'list',
            periodOffset: 0,
            transitionName: 'slide-next',
            showAddLoan: false,
            showPaidLoans: false,
            showAddGoal: false,
            showAddRecurring: false,
            
            editingTxId: null,
            editingLoan: null,
            fundingGoal: null,
            transferingGoal: null,
            selectedCategory: null,
            
            filterStatus: 'all',
            filterAccount: null,
            isPlanned: false,
            newCategoryName: '',
            
            touchStartX: 0,
            touchEndX: 0,
            trendChartInstance: null,
            trendData: [],
            
            dashboard: { total_balance: 0, total_debt: 0, monthly_income_realized: 0, monthly_income_forecast: 0, monthly_expenses_realized: 0, monthly_expenses_forecast: 0, goals_monthly_need: 0, goals_total_saved: 0, recent_transactions: [], period_start: '', period_end: '' },
            accounts: [],
            categories: [],
            loansData: { loans: [], upcoming: [] },
            goals: [],
            overrides: [],
            recurringList: [],
            duePayments: [],
            
            newTx: { description: '', amount: '', type: 'expense', account_id: null, target_account_id: null, category_name: '', loan_id: null, date: new Date().toISOString().split('T')[0] },
            newLoan: { name: '', total_amount: '', remaining_amount: '', monthly_payment: '', next_payment_date: new Date().toISOString().split('T')[0] },
            newGoal: { name: '', target_amount: '', deadline: new Date().toISOString().split('T')[0], account_id: null },
            newRecurring: { name: '', amount: '', day_of_month: '', category_name: '', account_id: null },
            newOverride: { year: new Date().getFullYear(), month: new Date().getMonth() + 1, day: 25 },
            fundData: { source_account_id: null, target_savings_id: null, amount: '' },
            transferData: { target_goal_id: null, amount: '' }
        }
    },
    computed: {
        filteredLoans() { if (!this.loansData.loans) return []; return this.loansData.loans.filter(l => this.showPaidLoans || l.remaining > 0); },
        activeLoans() { if (!this.loansData.loans) return []; return this.loansData.loans.filter(l => l.remaining > 0); },
        savingsAccounts() { return this.accounts.filter(a => a.is_savings); },
        filteredTransactions() {
            if (!this.dashboard.recent_transactions) return [];
            let txs = this.dashboard.recent_transactions;
            if (this.filterStatus !== 'all') txs = txs.filter(tx => tx.status === this.filterStatus);
            if (this.filterAccount) txs = txs.filter(tx => tx.account_id === this.filterAccount || tx.target_account_id === this.filterAccount);
            return txs;
        },
        groupedCategories() {
            if (!this.filteredTransactions) return [];
            const groups = {};
            this.filteredTransactions.forEach(tx => {
                if (tx.type === 'transfer') return;
                const catName = tx.category || 'Bez kategorii';
                if (!groups[catName]) {
                    const catObj = this.categories.find(c => c.name === catName);
                    groups[catName] = { name: catName, total: 0, count: 0, transactions: [], limit: catObj ? parseFloat(catObj.monthly_limit) : 0, id: catObj ? catObj.id : null };
                }
                const val = tx.type === 'expense' ? -tx.amount : tx.amount;
                groups[catName].total += val;
                groups[catName].count++;
                groups[catName].transactions.push(tx);
            });
            return Object.values(groups).sort((a, b) => Math.abs(b.total) - Math.abs(a.total));
        },
        maxCategoryAmount() { if (this.groupedCategories.length === 0) return 1; return Math.max(...this.groupedCategories.map(c => Math.abs(c.total))); },
        expenseCategories() {
            const totalExp = Math.abs(this.dashboard.monthly_expenses_realized) || 1;
            return this.groupedCategories.filter(c => c.total < 0).map(c => ({ ...c, percent: ((Math.abs(c.total) / totalExp) * 100).toFixed(1) }));
        },
        isSourceROR() {
            if (!this.fundData.source_account_id) return false;
            const acc = this.accounts.find(a => a.id === this.fundData.source_account_id);
            return acc && !acc.is_savings;
        }
    },
    watch: { viewMode(newVal) { if (newVal === 'chart') this.renderChart(); } },
    methods: {
        async login() {
            this.loginError = '';
            const formData = new FormData();
            formData.append('username', this.loginForm.username);
            formData.append('password', this.loginForm.password);
            try {
                const res = await fetch('/token', { method: 'POST', body: formData });
                if (!res.ok) throw new Error('Błędne dane');
                const data = await res.json();
                this.token = data.access_token;
                localStorage.setItem('token', this.token);
                this.isLoggedIn = true;
                this.refreshAllData();
            } catch (e) { this.loginError = "Nieprawidłowy login lub hasło"; }
        },
        logout() { this.token = null; localStorage.removeItem('token'); this.isLoggedIn = false; this.loginForm.username = ''; this.loginForm.password = ''; },
        async authFetch(url, options = {}) {
            if (!options.headers) options.headers = {};
            options.headers['Authorization'] = `Bearer ${this.token}`;
            const res = await fetch(url, options);
            if (res.status === 401) { this.logout(); throw new Error("Unauthorized"); }
            return res;
        },
        refreshAllData() { this.fetchData(); this.fetchAccounts(); this.fetchLoans(); this.fetchGoals(); this.fetchCategories(); this.fetchOverrides(); this.fetchRecurring(); this.checkDuePayments(); },
        
        async fetchRecurring() { if(this.isLoggedIn) this.recurringList = await (await this.authFetch('/api/recurring')).json(); },
        async checkDuePayments() { if(this.isLoggedIn) this.duePayments = await (await this.authFetch('/api/recurring/check')).json(); },
        async submitRecurring() { await this.authFetch('/api/recurring', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(this.newRecurring) }); this.showAddRecurring = false; this.fetchRecurring(); },
        async deleteRecurring(id) { if(!confirm("Usunąć subskrypcję?")) return; await this.authFetch(`/api/recurring/${id}`, { method: 'DELETE' }); this.fetchRecurring(); },
        async processRecurring(pay) { await this.authFetch(`/api/recurring/${pay.id}/process`, { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ date: new Date().toISOString().split('T')[0] }) }); this.duePayments = this.duePayments.filter(p => p.id !== pay.id); this.fetchData(); this.fetchAccounts(); },

        async changePassword() { if(!this.security.oldPassword || !this.security.newPassword) return alert("Wpisz oba hasła"); try { await this.authFetch('/api/users/change-password', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ old_password: this.security.oldPassword, new_password: this.security.newPassword }) }); alert("Hasło zmienione pomyślnie!"); this.security.oldPassword = ''; this.security.newPassword = ''; } catch(e) { alert("Błąd: Sprawdź stare hasło"); } },
        async registerUser() { if(!this.security.newUsername || !this.security.newUserPass) return alert("Wpisz login i hasło"); try { await this.authFetch('/api/users', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ username: this.security.newUsername, password: this.security.newUserPass }) }); alert(`Użytkownik ${this.security.newUsername} dodany!`); this.security.newUsername = ''; this.security.newUserPass = ''; } catch(e) { alert("Błąd: Taki użytkownik może już istnieć"); } },

        getAccountName(id) { const acc = this.accounts.find(a => a.id === id); return acc ? acc.name : ''; },
        formatMoney(value) { return parseFloat(value).toLocaleString('pl-PL', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + ' zł'; },
        formatDateShort(dateStr) { if(!dateStr) return ''; const d = new Date(dateStr); return d.toLocaleDateString('pl-PL', { day: 'numeric', month: 'short' }); },
        getIcon(type) { return type === 'income' ? '💰' : (type === 'transfer' ? '↔️' : '🛒'); },
        getIconClass(type) { return type === 'income' ? 'bg-green-500/10 text-green-400' : (type === 'transfer' ? 'bg-blue-500/10 text-blue-400' : 'bg-red-500/10 text-red-400'); },
        getColorClass(type) { return type === 'income' ? 'text-green-400' : (type === 'transfer' ? 'text-blue-400' : 'text-slate-200'); },
        calculateProgress(loan) { if(loan.total <= 0) return 0; return ((loan.total - loan.remaining) / loan.total) * 100; },
        
        handleTouchStart(e) { this.touchStartX = e.changedTouches[0].screenX; },
        handleTouchEnd(e) { this.touchEndX = e.changedTouches[0].screenX; this.handleSwipe(); },
        handleSwipe() { if (this.currentTab !== 'dashboard') return; const diff = this.touchEndX - this.touchStartX; if (diff > 50) this.changePeriod(-1); if (diff < -50) this.changePeriod(1); },

        openCategoryDetails(cat) { this.selectedCategory = cat; },
        
        editTxFromModal(tx) {
            this.selectedCategory = null;
            this.editTx(tx);
        },
        async realizeTxFromModal(tx) {
            await this.realizeTx(tx);
            this.selectedCategory = null;
        },

        copyTx(tx) {
            this.newTx = {
                description: tx.desc,
                amount: tx.amount,
                type: tx.type,
                account_id: tx.account_id,
                target_account_id: tx.target_account_id,
                category_name: tx.category,
                loan_id: tx.loan_id,
                date: new Date().toISOString().split('T')[0]
            };
            this.isPlanned = false;
            this.editingTxId = null;
            this.currentTab = 'add';
            this.selectedCategory = null;
            window.scrollTo(0,0);
        },

        // --- NOWA FUNKCJA: OBSŁUGA WYBORU KREDYTU ---
        handleLoanChange() {
            if (this.newTx.loan_id) {
                this.newTx.category_name = 'Spłata zobowiązań';
            } else {
                this.newTx.category_name = '';
            }
        },
        // --------------------------------------------

        async updateCategoryLimit(cat) {
            if (!cat.id) return alert("Nie można edytować tej kategorii (brak ID).");
            await this.authFetch(`/api/categories/${cat.id}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name: cat.name, monthly_limit: parseFloat(cat.limit) })
            });
            this.fetchCategories();
            alert("Limit zapisany!");
        },

        async fetchData() { if (!this.isLoggedIn) return; try { this.dashboard = await (await this.authFetch(`/api/dashboard?offset=${this.periodOffset}`)).json(); if (this.accounts.length > 0 && !this.newTx.account_id) this.newTx.account_id = this.accounts[0].id; if (this.viewMode === 'chart') this.renderChart(); } catch (e) { console.error(e); } },
        async fetchAccounts() { if(this.isLoggedIn) this.accounts = await (await this.authFetch('/api/accounts')).json(); },
        async fetchLoans() { if(this.isLoggedIn) this.loansData = await (await this.authFetch('/api/loans')).json(); },
        async fetchGoals() { if(this.isLoggedIn) this.goals = await (await this.authFetch('/api/goals')).json(); },
        async fetchCategories() { if(this.isLoggedIn) this.categories = await (await this.authFetch('/api/categories')).json(); },
        async fetchOverrides() { if(this.isLoggedIn) this.overrides = await (await this.authFetch('/api/settings/payday-overrides')).json(); },
        
        async renderChart() {
            const ctx = document.getElementById('trendChart');
            if (!ctx) return;
            const trendData = await (await this.authFetch('/api/stats/trend')).json();
            if (this.trendChartInstance) this.trendChartInstance.destroy();
            this.trendChartInstance = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: trendData.map(d => d.label),
                    datasets: [
                        { label: 'Przychody', data: trendData.map(d => d.income), borderColor: '#4ade80', backgroundColor: 'rgba(74, 222, 128, 0.1)', tension: 0.4, fill: true },
                        { label: 'Wydatki', data: trendData.map(d => d.expense), borderColor: '#f87171', backgroundColor: 'rgba(248, 113, 113, 0.1)', tension: 0.4, fill: true }
                    ]
                },
                options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { labels: { color: '#94a3b8' } } }, scales: { y: { grid: { color: '#334155' }, ticks: { color: '#94a3b8' } }, x: { grid: { display: false }, ticks: { color: '#94a3b8' } } } }
            });
        },
        changePeriod(delta) { this.transitionName = delta > 0 ? 'slide-next' : 'slide-prev'; this.periodOffset += delta; this.fetchData(); },
        detectCategory() { if(this.editingTxId) return; const desc = this.newTx.description.toLowerCase(); if (desc.length < 3) return; const match = this.dashboard.recent_transactions.find(tx => tx.desc.toLowerCase().includes(desc) && tx.category !== '-' && tx.category !== 'Transfer'); if (match) this.newTx.category_name = match.category; },
        editTx(tx) { this.editingTxId = tx.id; this.isPlanned = (tx.status === 'planowana'); this.newTx = { description: tx.desc, amount: tx.amount, type: tx.type, account_id: tx.account_id, category_name: tx.category_name, loan_id: tx.loan_id, date: tx.date.split('T')[0], target_account_id: tx.target_account_id }; this.currentTab = 'add'; },
        cancelEdit() { this.resetForm(); this.currentTab = 'dashboard'; },
        resetForm() { this.editingTxId = null; this.isPlanned = false; this.newTx = { description: '', amount: '', type: 'expense', account_id: this.accounts[0]?.id, target_account_id: null, category_name: '', loan_id: null, date: new Date().toISOString().split('T')[0] }; },
        
        async submitTransaction() {
            if(!this.newTx.account_id) return alert("Wybierz konto!");
            if(this.newTx.type === 'transfer' && !this.newTx.target_account_id) return alert("Wybierz konto docelowe!");
            if(!this.newTx.description) return alert("Opis jest wymagany!");

            const url = this.editingTxId ? `/api/transactions/${this.editingTxId}` : '/api/transactions';
            const method = this.editingTxId ? 'PUT' : 'POST';
            const payload = { ...this.newTx, status: this.isPlanned ? 'planowana' : 'zrealizowana' };
            await this.authFetch(url, { method: method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
            this.resetForm(); this.currentTab = 'dashboard'; this.fetchData(); this.fetchAccounts();
        },
        
        async realizeTx(tx) { const payload = { description: tx.desc, amount: tx.amount, type: tx.type, account_id: tx.account_id, target_account_id: tx.target_account_id, category_name: tx.category, loan_id: tx.loan_id, date: tx.date.split('T')[0], status: 'zrealizowana' }; await this.authFetch(`/api/transactions/${tx.id}`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) }); this.fetchData(); this.fetchAccounts(); },
        async deleteTx(id) { if(!confirm("Usunąć transakcję?")) return; await this.authFetch(`/api/transactions/${id}`, { method: 'DELETE' }); this.fetchData(); this.fetchAccounts(); },
        async deleteAccount(id) { if(!confirm("Usunąć konto i jego historię?")) return; await this.authFetch(`/api/accounts/${id}`, { method: 'DELETE' }); this.fetchAccounts(); this.fetchData(); },
        async editAccount(acc) {
            const newName = prompt("Nazwa konta:", acc.name);
            if(!newName) return;
            const newBalance = prompt("Saldo:", acc.balance);
            const isSavings = confirm("Czy to konto oszczędnościowe (do celów)?");
            await this.authFetch(`/api/accounts/${acc.id}`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name: newName, type: acc.type, balance: parseFloat(newBalance), is_savings: isSavings }) });
            this.fetchAccounts();
        },
        async submitLoan() { await this.authFetch('/api/loans', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(this.newLoan) }); this.showAddLoan = false; this.fetchLoans(); },
        editLoan(loan) { this.editingLoan = { ...loan, total_amount: loan.total, remaining_amount: loan.remaining, monthly_payment: loan.monthly, next_payment_date: loan.next_date }; },
        async updateLoan() { await this.authFetch(`/api/loans/${this.editingLoan.id}`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(this.editingLoan) }); this.editingLoan = null; this.fetchLoans(); },
        async createTestAccount() { const name = prompt("Nazwa konta:"); if(name) { await this.authFetch('/api/accounts', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name: name, type: "bank", balance: 0, is_savings: false }) }); this.fetchAccounts(); } },
        async addOverride() { await this.authFetch('/api/settings/payday-overrides', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(this.newOverride) }); this.fetchOverrides(); },
        async deleteOverride(id) { if(!confirm("Usunąć wyjątek?")) return; await this.authFetch(`/api/settings/payday-overrides/${id}`, { method: 'DELETE' }); this.fetchOverrides(); },
        async addCategory() { if(!this.newCategoryName) return; await this.authFetch('/api/categories', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name: this.newCategoryName }) }); this.newCategoryName = ''; this.fetchCategories(); },
        async deleteCategory(id) { if(!confirm("Usunąć kategorię?")) return; await this.authFetch(`/api/categories/${id}`, { method: 'DELETE' }); this.fetchCategories(); },
        
        async submitGoal() {
            if (!this.newGoal.account_id) return alert("Wybierz konto oszczędnościowe dla tego celu!");
            await this.authFetch('/api/goals', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(this.newGoal) });
            this.showAddGoal = false;
            this.fetchGoals();
            this.newGoal = { name: '', target_amount: '', deadline: new Date().toISOString().split('T')[0], account_id: null };
        },
        async deleteGoal(id) { if(!confirm("Usunąć cel?")) return; await this.authFetch(`/api/goals/${id}`, { method: 'DELETE' }); this.fetchGoals(); },
        openFundGoal(goal) {
            this.fundingGoal = goal;
            const defaultSource = this.accounts[0]?.id;
            const defaultTarget = this.savingsAccounts[0]?.id;
            this.fundData = { source_account_id: defaultSource, target_savings_id: defaultTarget, amount: '' };
        },
        async submitFundGoal() { await this.authFetch(`/api/goals/${this.fundingGoal.id}/fund`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(this.fundData) }); this.fundingGoal = null; this.fetchGoals(); this.fetchAccounts(); },
        openTransferGoal(goal) { this.transferingGoal = goal; this.transferData = { target_goal_id: null, amount: '' }; },
        async submitTransferGoal() { await this.authFetch(`/api/goals/${this.transferingGoal.id}/transfer`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(this.transferData) }); this.transferingGoal = null; this.fetchGoals(); }
    },
    mounted() {
        if (this.token) {
            this.isLoggedIn = true;
            this.refreshAllData();
        }
    }
}).mount('#app')
