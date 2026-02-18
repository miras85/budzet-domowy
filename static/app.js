import { createApp } from 'https://unpkg.com/vue@3/dist/vue.esm-browser.js';
import * as Utils from './js/utils.js';
import * as API from './js/api.js';
import * as Charts from './js/charts.js';

createApp({
    data() {
        return {
            // --- SYSTEM POWIADOMIEŃ ---
            toasts: [],
            
            // --- STAN ---
            isLoggedIn: !!API.getToken(),
            loginForm: { username: '', password: '' },
            loginError: '',
            
            security: { oldPassword: '', newPassword: '', newUsername: '', newUserPass: '' },
            
            currentTab: 'dashboard',
            viewMode: 'list',
            periodOffset: 0,
            transitionName: 'slide-next',
            
            // Modale i Formularze
            showAddLoan: false,
            showPaidLoans: false,
            showAddGoal: false,
            showAddRecurring: false,
            
            editingTxId: null,
            editingLoan: null,
            fundingGoal: null,
            transferingGoal: null,
            selectedCategory: null,
            withdrawingGoal: null,
            
            withdrawData: { target_account_id: null, amount: '' },
            fundData: { source_account_id: null, target_savings_id: null, amount: '' },
            transferData: { target_goal_id: null, amount: '' },

            // Wyszukiwanie
            showSearch: false,
            searchCriteria: { q: '', date_from: '', date_to: '', category_id: null, account_id: null, type: 'all', min_amount: '', max_amount: '' },
            searchResults: null,
            searchSummary: { income: 0, expense: 0, balance: 0, count: 0 },
            
            // Import
            importAccountId: null,
            importData: null,
            importTargetAccountId: null,

            // Filtry UI
            filterStatus: 'all',
            filterAccount: null,
            isPlanned: false,
            newCategoryName: '',
            categorySearch: '',
            showCategorySelector: false,
            
            // Gesty
            touchStartX: 0,
            touchEndX: 0,
            
            // Wykresy
            chartColors: ['#ef4444', '#f97316', '#eab308', '#84cc16', '#10b981', '#06b6d4', '#3b82f6', '#6366f1', '#8b5cf6', '#d946ef'],
            selectedChartSegment: null,
            
            // Dane
            dashboard: { total_balance: 0, disposable_balance: 0, forecast_ror: 0, savings_realized: 0, savings_rate: 0, total_debt: 0, monthly_income_realized: 0, monthly_income_forecast: 0, monthly_expenses_realized: 0, monthly_expenses_forecast: 0, goals_monthly_need: 0, goals_total_saved: 0, recent_transactions: [], period_start: '', period_end: '' },
            accounts: [],
            categories: [],
            loansData: { loans: [], upcoming: [] },
            goals: [],
            overrides: [],
            recurringList: [],
            duePayments: [],
            
            // Nowe obiekty
            newTx: { description: '', amount: '', type: 'expense', account_id: null, target_account_id: null, category_name: '', loan_id: null, date: new Date().toISOString().split('T')[0] },
            newLoan: { name: '', total_amount: '', remaining_amount: '', monthly_payment: '', next_payment_date: new Date().toISOString().split('T')[0] },
            newGoal: { name: '', target_amount: '', deadline: new Date().toISOString().split('T')[0], account_id: null },
            newRecurring: { name: '', amount: '', day_of_month: '', category_name: '', account_id: null },
            newOverride: { year: new Date().getFullYear(), month: new Date().getMonth() + 1, day: 25 },
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
        filteredCategories() {
            if (!this.categorySearch) return this.categories;
            const search = this.categorySearch.toLowerCase();
            return this.categories.filter(c => c.name.toLowerCase().includes(search));
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
        // --- UTILS (Eksport do template) ---
        formatMoney: Utils.formatMoney,
        formatDateShort: Utils.formatDateShort,
        getIcon: Utils.getIcon,
        getIconClass: Utils.getIconClass,
        getColorClass: Utils.getColorClass,
        calculateProgress: Utils.calculateProgress,

        notify(type, message) {
            const id = Date.now();
            const title = type === 'success' ? 'Sukces' : (type === 'error' ? 'Błąd' : 'Info');
            this.toasts.push({ id, type, title, message });
            setTimeout(() => { this.removeToast(id); }, 4000);
        },
        removeToast(id) { this.toasts = this.toasts.filter(t => t.id !== id); },

        // --- AUTH ---
        async login() {
            this.loginError = '';
            try {
                const data = await API.auth.login(this.loginForm.username, this.loginForm.password);
                API.setToken(data.access_token);
                this.isLoggedIn = true;
                this.refreshAllData();
                this.notify('success', 'Zalogowano pomyślnie');
            } catch (e) { this.loginError = "Nieprawidłowy login lub hasło"; }
        },
        logout() {
            API.logout();
            this.isLoggedIn = false;
            this.loginForm.username = '';
            this.loginForm.password = '';
            this.duePayments = [];
            this.notify('info', 'Wylogowano');
        },
        async changePassword() {
            if(!this.security.oldPassword || !this.security.newPassword) return this.notify('error', "Wpisz oba hasła");
            try {
                await API.auth.changePassword(this.security.oldPassword, this.security.newPassword);
                this.notify('success', "Hasło zmienione pomyślnie!");
                this.security.oldPassword = ''; this.security.newPassword = '';
            } catch(e) { this.notify('error', "Błąd: Sprawdź stare hasło"); }
        },
        async registerUser() {
            if(!this.security.newUsername || !this.security.newUserPass) return this.notify('error', "Wpisz login i hasło");
            try {
                await API.auth.register(this.security.newUsername, this.security.newUserPass);
                this.notify('success', `Użytkownik ${this.security.newUsername} dodany!`);
                this.security.newUsername = ''; this.security.newUserPass = '';
            } catch(e) { this.notify('error', "Błąd: Taki użytkownik może już istnieć"); }
        },

        // --- DATA FETCHING ---
        refreshAllData() { this.fetchData(); this.fetchAccounts(); this.fetchLoans(); this.fetchGoals(); this.fetchCategories(); this.fetchOverrides(); this.fetchRecurring(); this.checkDuePayments(); },
        
        async fetchData() {
            if (!this.isLoggedIn) return;
            try {
                this.dashboard = await API.finance.getDashboard(this.periodOffset);
                if (this.accounts.length > 0 && !this.newTx.account_id) this.newTx.account_id = this.accounts[0].id;
                if (this.viewMode === 'chart') this.renderChart();
            } catch (e) { console.error(e); }
        },
        async fetchAccounts() { if(this.isLoggedIn) this.accounts = await API.accounts.getAll(); },
        async fetchLoans() { if(this.isLoggedIn) this.loansData = await API.loans.getAll(); },
        async fetchGoals() { if(this.isLoggedIn) this.goals = await API.goals.getAll(); },
        async fetchCategories() { if(this.isLoggedIn) this.categories = await API.categories.getAll(); },
        async fetchOverrides() { if(this.isLoggedIn) this.overrides = await API.settings.getOverrides(); },
        async fetchRecurring() { if(this.isLoggedIn) this.recurringList = await API.recurring.getAll(); },
        async checkDuePayments() { if(this.isLoggedIn) this.duePayments = await API.recurring.checkDue(); },

        // --- TRANSACTIONS ---
        async submitTransaction() {
            if(!this.newTx.account_id) return this.notify('error', "Wybierz konto!");
            if(this.newTx.type === 'transfer' && !this.newTx.target_account_id) return this.notify('error', "Wybierz konto docelowe!");
            if(!this.newTx.description) return this.notify('error', "Opis jest wymagany!");

            const payload = { ...this.newTx, status: this.isPlanned ? 'planowana' : 'zrealizowana' };
            try {
                if (this.editingTxId) await API.transactions.update(this.editingTxId, payload);
                else await API.transactions.create(payload);
                
                this.resetForm(); this.currentTab = 'dashboard'; this.fetchData(); this.fetchAccounts();
                this.notify('success', this.editingTxId ? 'Zaktualizowano transakcję' : 'Dodano transakcję');
            } catch(e) { this.notify('error', 'Błąd zapisu transakcji'); }
        },
        async realizeTx(tx) {
            const payload = { description: tx.desc, amount: tx.amount, type: tx.type, account_id: tx.account_id, target_account_id: tx.target_account_id, category_name: tx.category, loan_id: tx.loan_id, date: tx.date.split('T')[0], status: 'zrealizowana' };
            await API.transactions.update(tx.id, payload);
            this.fetchData(); this.fetchAccounts(); this.notify('success', 'Transakcja zrealizowana');
        },
        async deleteTx(id) {
            if(!confirm("Usunąć transakcję?")) return;
            await API.transactions.delete(id);
            this.fetchData(); this.fetchAccounts(); this.notify('info', 'Usunięto transakcję');
        },
        
        // --- ACCOUNTS ---
        async createTestAccount() {
            const name = prompt("Nazwa konta:");
            if(name) {
                await API.accounts.create({ name: name, type: "bank", balance: 0, is_savings: false });
                this.fetchAccounts(); this.notify('success', 'Utworzono konto');
            }
        },
        async deleteAccount(id) {
            if(!confirm("Usunąć konto i jego historię?")) return;
            await API.accounts.delete(id);
            this.fetchAccounts(); this.fetchData(); this.notify('info', 'Usunięto konto');
        },
        async editAccount(acc) {
            const newName = prompt("Nazwa konta:", acc.name);
            if(!newName) return;
            const newBalance = prompt("Saldo:", acc.balance);
            const isSavings = confirm("Czy to konto oszczędnościowe (do celów)?");
            await API.accounts.update(acc.id, { name: newName, type: acc.type, balance: parseFloat(newBalance), is_savings: isSavings });
            this.fetchAccounts(); this.notify('success', 'Zaktualizowano konto');
        },

        // --- LOANS ---
        async submitLoan() {
            await API.loans.create(this.newLoan);
            this.showAddLoan = false; this.fetchLoans(); this.notify('success', 'Dodano kredyt');
        },
        async updateLoan() {
            await API.loans.update(this.editingLoan.id, this.editingLoan);
            this.editingLoan = null; this.fetchLoans(); this.notify('success', 'Zaktualizowano kredyt');
        },

        // --- GOALS ---
        async submitGoal() {
            if (!this.newGoal.account_id) return this.notify('error', "Wybierz konto oszczędnościowe dla tego celu!");
            await API.goals.create(this.newGoal);
            this.showAddGoal = false; this.fetchGoals();
            this.newGoal = { name: '', target_amount: '', deadline: new Date().toISOString().split('T')[0], account_id: null };
            this.notify('success', 'Utworzono cel');
        },
        async deleteGoal(id) {
            if(!confirm("Usunąć cel?")) return;
            await API.goals.delete(id);
            this.fetchGoals(); this.notify('info', 'Usunięto cel');
        },
        async submitFundGoal() {
            await API.goals.fund(this.fundingGoal.id, this.fundData);
            this.fundingGoal = null; this.fetchGoals(); this.fetchAccounts(); this.notify('success', 'Zasilono cel');
        },
        async submitWithdrawGoal() {
            if (!this.withdrawData.amount || !this.withdrawData.target_account_id) return this.notify('error', "Wypełnij wszystkie pola");
            if (parseFloat(this.withdrawData.amount) > parseFloat(this.withdrawingGoal.current_amount)) return this.notify('error', "Kwota przekracza środki na celu!");
            await API.goals.withdraw(this.withdrawingGoal.id, this.withdrawData);
            this.withdrawingGoal = null; this.fetchGoals(); this.fetchAccounts(); this.notify('success', 'Wypłacono środki');
        },
        async submitTransferGoal() {
            await API.goals.transfer(this.transferingGoal.id, this.transferData);
            this.transferingGoal = null; this.fetchGoals(); this.notify('success', 'Przeniesiono środki');
        },

        // --- RECURRING ---
        async submitRecurring() {
            await API.recurring.create(this.newRecurring);
            this.showAddRecurring = false; this.fetchRecurring(); this.notify('success', 'Dodano subskrypcję');
        },
        async deleteRecurring(id) {
            if(!confirm("Usunąć subskrypcję?")) return;
            await API.recurring.delete(id);
            this.fetchRecurring(); this.notify('info', 'Usunięto subskrypcję');
        },
        async processRecurring(pay) {
            await API.recurring.process(pay.id, new Date().toISOString().split('T')[0]);
            this.duePayments = this.duePayments.filter(p => p.id !== pay.id);
            this.fetchData(); this.fetchAccounts(); this.notify('success', 'Zaksięgowano płatność');
        },
        async skipRecurring(pay) {
            if(!confirm("Pominąć tę płatność w tym miesiącu?")) return;
            await API.recurring.skip(pay.id);
            this.duePayments = this.duePayments.filter(p => p.id !== pay.id);
            this.notify('info', 'Pominięto płatność');
        },

        // --- SETTINGS ---
        async addCategory() {
            if(!this.newCategoryName) return;
            await API.categories.create(this.newCategoryName);
            this.newCategoryName = ''; this.fetchCategories(); this.notify('success', 'Dodano kategorię');
        },
        async deleteCategory(id) {
            if(!confirm("Usunąć kategorię?")) return;
            await API.categories.delete(id);
            this.fetchCategories(); this.notify('info', 'Usunięto kategorię');
        },
        async updateCategoryLimit(cat) {
            if (!cat.id) return this.notify('error', "Nie można edytować tej kategorii (brak ID).");
            await API.categories.update(cat.id, { name: cat.name, monthly_limit: parseFloat(cat.limit) });
            this.fetchCategories(); this.notify('success', "Limit zapisany!");
        },
        async addOverride() {
            await API.settings.addOverride(this.newOverride);
            this.fetchOverrides(); this.notify('success', 'Dodano wyjątek');
        },
        async deleteOverride(id) {
            if(!confirm("Usunąć wyjątek?")) return;
            await API.settings.deleteOverride(id);
            this.fetchOverrides(); this.notify('info', 'Usunięto wyjątek');
        },

        // --- SEARCH ---
        openSearch() {
            this.showSearch = true;
            const now = new Date();
            const firstDay = new Date(now.getFullYear(), now.getMonth(), 1);
            this.searchCriteria.date_from = firstDay.toISOString().split('T')[0];
            this.searchCriteria.date_to = now.toISOString().split('T')[0];
            this.searchResults = null;
        },
        closeSearch() { this.showSearch = false; this.searchResults = null; },
        applyDatePreset(months) {
            const end = new Date();
            const start = new Date();
            start.setMonth(start.getMonth() - months);
            this.searchCriteria.date_to = end.toISOString().split('T')[0];
            this.searchCriteria.date_from = start.toISOString().split('T')[0];
            this.performSearch();
        },
        async performSearch() {
            const params = new URLSearchParams();
            if(this.searchCriteria.q) params.append('q', this.searchCriteria.q);
            if(this.searchCriteria.date_from) params.append('date_from', this.searchCriteria.date_from);
            if(this.searchCriteria.date_to) params.append('date_to', this.searchCriteria.date_to);
            if(this.searchCriteria.category_id) params.append('category_id', this.searchCriteria.category_id);
            if(this.searchCriteria.account_id) params.append('account_id', this.searchCriteria.account_id);
            if(this.searchCriteria.type && this.searchCriteria.type !== 'all') params.append('type', this.searchCriteria.type);
            if(this.searchCriteria.min_amount) params.append('min_amount', this.searchCriteria.min_amount);
            if(this.searchCriteria.max_amount) params.append('max_amount', this.searchCriteria.max_amount);

            const data = await API.transactions.search(params.toString());
            this.searchResults = data.transactions;
            this.searchSummary = data.summary;
        },
        clearSearchFilters() {
            this.searchCriteria = { q: '', date_from: '', date_to: '', category_id: null, account_id: null, type: 'all', min_amount: '', max_amount: '' };
            this.searchResults = null;
        },

        // --- IMPORT ---
        triggerImport(accountId) {
            this.importTargetAccountId = accountId;
            const input = document.createElement('input');
            input.type = 'file';
            input.accept = '.csv';
            input.onchange = e => { if (e.target.files.length > 0) this.processImportFile(e.target.files[0]); };
            input.click();
        },
        async processImportFile(file) {
            try {
                const res = await API.importCSV.preview(file);
                if (!res.ok) {
                    const errData = await res.json();
                    throw new Error(errData.detail || "Błąd parsowania pliku");
                }
                const data = await res.json();
                if (data.length === 0) return this.notify('error', "Nie znaleziono transakcji w pliku.");
                this.importData = data.map(tx => ({...tx, ignore: false}));
            } catch (e) { this.notify('error', "Błąd importu: " + e.message); }
        },
        async submitImport() {
            if (!this.importData || !this.importTargetAccountId) return;
            const toImport = this.importData.filter(tx => !tx.ignore);
            if (toImport.length === 0) return this.notify('error', "Brak transakcji do importu.");
            const missingCat = toImport.find(tx => !tx.category_id);
            if (missingCat) return this.notify('error', `Błąd: Transakcja "${missingCat.description}" nie ma kategorii.`);
            
            try {
                await API.importCSV.confirm(this.importTargetAccountId, toImport);
                this.notify('success', "Zaimportowano pomyślnie!");
                this.importData = null; this.importTargetAccountId = null;
                this.fetchData(); this.fetchAccounts();
            } catch (e) { this.notify('error', "Błąd zapisu: " + e.message); }
        },

        // --- UI HELPERS ---
        changePeriod(delta) { this.transitionName = delta > 0 ? 'slide-next' : 'slide-prev'; this.periodOffset += delta; this.fetchData(); },
        handleTouchStart(e) { this.touchStartX = e.changedTouches[0].screenX; },
        handleTouchEnd(e) { this.touchEndX = e.changedTouches[0].screenX; this.handleSwipe(); },
        handleSwipe() { if (this.currentTab !== 'dashboard') return; const diff = this.touchEndX - this.touchStartX; if (diff > 50) this.changePeriod(-1); if (diff < -50) this.changePeriod(1); },
        
        openCategoryDetails(cat) { this.selectedCategory = cat; },
        editTxFromModal(tx) { this.selectedCategory = null; this.editTx(tx); },
        async realizeTxFromModal(tx) { await this.realizeTx(tx); this.selectedCategory = null; },
        
        copyTx(tx) {
            this.newTx = { description: tx.desc, amount: tx.amount, type: tx.type, account_id: tx.account_id, target_account_id: tx.target_account_id, category_name: tx.category, loan_id: tx.loan_id, date: new Date().toISOString().split('T')[0] };
            this.isPlanned = false; this.editingTxId = null; this.currentTab = 'add'; this.selectedCategory = null; window.scrollTo(0,0); this.notify('info', 'Skopiowano do formularza');
        },
        handleLoanChange() { if (this.newTx.loan_id) this.newTx.category_name = 'Spłata zobowiązań'; else this.newTx.category_name = ''; },
        detectCategory() {
            if(this.editingTxId) return;
            const desc = this.newTx.description.toLowerCase();
            if (desc.length < 3) return;
            const match = this.dashboard.recent_transactions.find(tx => tx.desc.toLowerCase().includes(desc) && tx.category !== '-' && tx.category !== 'Transfer');
            if (match) this.newTx.category_name = match.category;
        },
        editTx(tx) { this.editingTxId = tx.id; this.isPlanned = (tx.status === 'planowana'); this.newTx = { description: tx.desc, amount: tx.amount, type: tx.type, account_id: tx.account_id, category_name: tx.category_name, loan_id: tx.loan_id, date: tx.date.split('T')[0], target_account_id: tx.target_account_id }; this.currentTab = 'add'; },
        cancelEdit() { this.resetForm(); this.currentTab = 'dashboard'; },
        resetForm() {
            this.editingTxId = null; this.isPlanned = false; this.showCategorySelector = false;
            this.newTx = { description: '', amount: '', type: 'expense', account_id: this.accounts[0]?.id, target_account_id: null, category_name: '', loan_id: null, date: new Date().toISOString().split('T')[0] };
        },
        editLoan(loan) { this.editingLoan = { ...loan, total_amount: loan.total, remaining_amount: loan.remaining, monthly_payment: loan.monthly, next_payment_date: loan.next_date }; },
        openFundGoal(goal) { this.fundingGoal = goal; const defaultSource = this.accounts[0]?.id; const defaultTarget = this.savingsAccounts[0]?.id; this.fundData = { source_account_id: defaultSource, target_savings_id: defaultTarget, amount: '' }; },
        openTransferGoal(goal) { this.transferingGoal = goal; this.transferData = { target_goal_id: null, amount: '' }; },
        openWithdrawGoal(goal) { this.withdrawingGoal = goal; const defaultTarget = this.accounts.find(a => !a.is_savings) || this.accounts[0]; this.withdrawData = { target_account_id: defaultTarget ? defaultTarget.id : null, amount: '' }; },

        async renderChart() {
            const ctxTrend = document.getElementById('trendChart');
            if (ctxTrend) {
                const trendData = await API.finance.getTrend();
                Charts.renderTrendChart(ctxTrend, trendData);
            }

            const ctxDoughnut = document.getElementById('expenseDoughnut');
            if (ctxDoughnut) {
                Charts.renderDoughnutChart(ctxDoughnut, this.expenseCategories, this.chartColors, (segment) => {
                    this.selectedChartSegment = segment;
                });
            }
        }
    },
    mounted() {
        if (this.isLoggedIn) {
            this.refreshAllData();
        }
    }
}).mount('#app');
