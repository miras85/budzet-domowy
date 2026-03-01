import { createApp } from 'https://unpkg.com/vue@3/dist/vue.esm-browser.js';
import * as Utils from './utils.js';
import * as API from './api.js?v=54';
import * as Charts from './charts.js';

// Import Komponentów
import LoginView from './components/LoginView.js';
import DashboardView from './components/DashboardView.js?v=53';
import AccountsView from './components/AccountsView.js';
import GoalsView from './components/GoalsView.js?v=2';
import PaymentsView from './components/PaymentsView.js?v=3';
import SettingsView from './components/SettingsView.js?v=52';
import AddTransactionView from './components/AddTransactionView.js?V=6';
import SearchView from './components/SearchView.js';
import ImportModal from './components/ImportModal.js';
import TheNavigation from './components/TheNavigation.js?v=2';
import LoanAlertsModal from './components/LoanAlertsModal.js?v=1';  // NOWY

const app = createApp({
    components: {
        LoginView, DashboardView, AccountsView, GoalsView, PaymentsView, SettingsView, AddTransactionView, SearchView, ImportModal, TheNavigation, LoanAlertsModal
    },
    data() {
        return {
            toasts: [],
            isLoggedIn: !!API.getToken(),
            currentTab: 'dashboard',
            viewMode: 'list',
            periodOffset: 0,
            transitionName: 'slide-next',
            budgetRankingExpanded: false,  // NOWY - domyślnie zwinięty
            editingRecurring: null,
            editingGoal: null,
            
            // Modale
            showAddLoan: false, showPaidLoans: false, showAddGoal: false, showAddRecurring: false, showSearch: false,
            editingTxId: null, editingLoan: null, fundingGoal: null, transferingGoal: null, selectedCategory: null, withdrawingGoal: null, categoryTrend: null, categoryModalTab: 'overview',
            
            // Formularze
            withdrawData: { target_account_id: null, amount: '' },
            fundData: { source_account_id: null, target_savings_id: null, amount: '' },
            transferData: { target_goal_id: null, amount: '' },
            searchCriteria: { q: '', date_from: '', date_to: '', category_id: null, account_id: null, type: 'all', min_amount: '', max_amount: '' },
            searchResults: null, searchSummary: { income: 0, expense: 0, balance: 0, count: 0 },
            importAccountId: null, importData: null, importTargetAccountId: null,
            
            // Filtry
            filterStatus: 'all', filterAccount: '', isPlanned: false, newCategoryName: '', categorySearch: '',
            
            // Wykresy
            chartColors: ['#ef4444', '#f97316', '#eab308', '#84cc16', '#10b981', '#06b6d4', '#3b82f6', '#6366f1', '#8b5cf6', '#d946ef'],
            selectedChartSegment: null,
            
            // Dane
            dashboard: { total_balance: 0, disposable_balance: 0, forecast_ror: 0, savings_realized: 0, savings_rate: 0, total_debt: 0, monthly_income_realized: 0, monthly_income_forecast: 0, monthly_expenses_realized: 0, monthly_expenses_forecast: 0, goals_monthly_need: 0, goals_total_saved: 0, recent_transactions: [], period_start: '', period_end: '' },
            accounts: [], categories: [],
            loansData: { loans: []},
            loanAlerts: {
                overdue: [],
                urgent: [],
                upcoming: [],
                total_overdue: 0,
                total_urgent: 0,
                total_upcoming: 0,
                has_alerts: false
            },
            showLoanAlerts: false,
            loanAlertsRecentlyDismissed: false,
            
            goals: [], overrides: [], recurringList: [], duePayments: [],
            security: { oldPassword: '', newPassword: '', newUsername: '', newUserPass: '' },
            
            // Nowe obiekty
            newTx: { description: '', amount: '', type: 'expense', account_id: null, target_account_id: null, category_name: '', loan_id: null, date: new Date().toISOString().split('T')[0] },
            newLoan: { name: '', total_amount: '', remaining_amount: '', monthly_payment: '', next_payment_date: new Date().toISOString().split('T')[0] },
            newGoal: { name: '', target_amount: '', deadline: new Date().toISOString().split('T')[0], account_id: null },
            newRecurring: { name: '', amount: '', day_of_month: '', category_name: '', account_id: null },
            newOverride: { year: new Date().getFullYear(), month: new Date().getMonth() + 1, day: 25 },
            
            touchStartX: 0, touchEndX: 0
        }
    },
    computed: {
        filteredLoans() { if (!this.loansData.loans) return []; return this.loansData.loans.filter(l => this.showPaidLoans || l.remaining > 0); },
        activeLoans() { if (!this.loansData.loans) return []; return this.loansData.loans.filter(l => l.remaining > 0); },
        savingsAccounts() { return this.accounts.filter(a => a.is_savings); },
        budgetRanking() {
                const ranking = {
                    ok: [],        // 0-80%
                    warning: [],   // 80-100%
                    exceeded: []   // >100%
                };
                
                this.groupedCategories.forEach(cat => {
                    if (cat.limit <= 0) return;  // Pomiń kategorie bez limitu
                    if (cat.total >= 0) return;  // Pomiń przychody
                    
                    const spent = Math.abs(cat.total);
                    const percent = (spent / cat.limit) * 100;
                    
                    const item = {
                        name: cat.name,
                        spent: spent,
                        limit: cat.limit,
                        percent: percent.toFixed(0),
                        remaining: cat.limit - spent
                    };
                    
                    if (percent > 100) {
                        ranking.exceeded.push(item);
                    } else if (percent >= 80) {
                        ranking.warning.push(item);
                    } else {
                        ranking.ok.push(item);
                    }
                });
                
                // Sortuj exceeded po największym przekroczeniu
                ranking.exceeded.sort((a, b) => b.percent - a.percent);
                
                return ranking;
            },
        
        
        filteredTransactions() {
            if (!this.dashboard.recent_transactions) return [];
            let txs = this.dashboard.recent_transactions;
            if (this.filterStatus !== 'all') txs = txs.filter(tx => tx.status === this.filterStatus);
            if (this.filterAccount && this.filterAccount !== '') {  // Zmień na !== ''
                const accountId = parseInt(this.filterAccount);
                if (!isNaN(accountId)) {  // Sprawdź czy to liczba
                    txs = txs.filter(tx => tx.account_id === accountId || tx.target_account_id === accountId);
                }
            }
            return txs;
        },
        loanAlertsCount() {
                if (!this.loanAlerts) return 0;
                return (this.loanAlerts.overdue?.length || 0) +
                       (this.loanAlerts.urgent?.length || 0);
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
    methods: {
        formatMoney: Utils.formatMoney,
        formatDateShort: Utils.formatDateShort,
        
        notify(type, message) {
            const id = Date.now();
            this.toasts.push({
                id,
                type,
                title: type==='success'?'Sukces':(type==='error'?'Błąd':'Info'),
                message
            });
            setTimeout(() => {
                this.toasts = this.toasts.filter(t => t.id !== id);
            }, 4000);
        },
        
        removeToast(id) {
            this.toasts = this.toasts.filter(t => t.id !== id);
        },
        
        async addLoanPaymentsToPlanned(payments) {
            console.log('➕ addLoanPaymentsToPlanned wywołane dla:', payments);
            console.log('📊 recent_transactions:', this.dashboard.recent_transactions);
            let added = 0;
            let skipped = 0;
            
            for (const pay of payments) {
                try {
                    // Sprawdź czy już nie ma w recent_transactions (dashboard)
                    const exists = this.dashboard.recent_transactions?.find(tx =>
                        tx.loan_id === pay.loan_id &&
                        tx.status === 'planowana'
                    );
                    
                    if (exists) {
                        console.log(`Pominięto: ${pay.name} - już istnieje`);
                        skipped++;
                        continue;
                    }
                    
                    const txData = {
                        description: `Rata: ${pay.name}`,
                        amount: pay.amount,
                        type: 'expense',
                        account_id: this.accounts[0]?.id || 1,
                        date: pay.date,
                        status: 'planowana',
                        loan_id: pay.loan_id,
                        category_name: pay.name.toLowerCase().includes('hipote') ? 'Kredyt hipoteczny' : 'Spłata zobowiązań'
                    };
                    
                    await API.transactions.create(txData);
                    added++;
                } catch (e) {
                    console.error('Błąd dodawania płatności:', e);
                }
            }
            // Ustaw flagę "recently dismissed"
            this.loanAlertsRecentlyDismissed = true;
            
            // KLUCZOWA ZMIANA: Zamknij modal PRZED refetch
            this.showLoanAlerts = false;
            
            // Wyczyść alerty lokalnie
               this.loanAlerts = {
                   overdue: [],
                   urgent: [],
                   upcoming: [],
                   total_overdue: 0,
                   total_urgent: 0,
                   total_upcoming: 0,
                   has_alerts: false
               };
               
               // Komunikat
               if (added > 0 && skipped === 0) {
                   this.notify('success', `Dodano ${added} płatności do planowanych`);
               } else if (added > 0 && skipped > 0) {
                   this.notify('success', `Dodano ${added}, pominięto ${skipped}`);
               } else if (skipped > 0) {
                   this.notify('info', `Płatności już są w planowanych`);
               }
               
               // Refetch (modal się nie pojawi bo flaga "recently dismissed")
               this.fetchData();
               this.fetchLoans();
               
               // Zresetuj flagę po 2 sekundach
               setTimeout(() => {
                   this.loanAlertsRecentlyDismissed = false;
               }, 2000);
           },

            
        dismissLoanAlertsUntilTomorrow() {
            const tomorrow = new Date();
            tomorrow.setDate(tomorrow.getDate() + 1);
            localStorage.setItem('loan_alerts_dismissed_until', tomorrow.toISOString().split('T')[0]);
            
            // Ustaw flagę
            this.loanAlertsRecentlyDismissed = true;
            
            this.showLoanAlerts = false;
            
            // Wyczyść alerty lokalnie
            this.loanAlerts = {
                overdue: [],
                urgent: [],
                upcoming: [],
                total_overdue: 0,
                total_urgent: 0,
                total_upcoming: 0,
                has_alerts: false
            };
            
            this.notify('info', 'Przypomnę jutro');
            
            // Zresetuj flagę po 2 sekundach
            setTimeout(() => {
                this.loanAlertsRecentlyDismissed = false;
            }, 2000);
        },
        
        
        async login(username, password) {
            try {
                const data = await API.auth.login(username, password);
                API.setToken(data.access_token);
                this.isLoggedIn = true;
                this.refreshAllData();
                this.notify('success', 'Zalogowano');
            } catch (e) {
                // Wyświetl szczegółowy komunikat błędu z serwera
                const errorMsg = e.message || "Błąd logowania";
                this.notify('error', errorMsg);
            }
        },
        
        logout() {
            API.logout();
            this.isLoggedIn = false;
            
            // Reset wrażliwych danych
            this.dashboard = {
                total_balance: 0,
                disposable_balance: 0,
                forecast_ror: 0,
                savings_realized: 0,
                savings_rate: 0,
                total_debt: 0,
                monthly_income_realized: 0,
                monthly_income_forecast: 0,
                monthly_expenses_realized: 0,
                monthly_expenses_forecast: 0,
                goals_monthly_need: 0,
                goals_total_saved: 0,
                recent_transactions: [],
                period_start: '',
                period_end: ''
            };
            this.accounts = [];
            this.categories = [];
            this.goals = [];
            this.loansData = { loans: [], upcoming: [] };
            this.recurringList = [];
            this.duePayments = [];
            this.searchResults = null;
            this.searchSummary = { income: 0, expense: 0, balance: 0, count: 0 };
            this.importData = null;
            
            this.notify('info', 'Wylogowano');
        },
        
        refreshAllData() { this.fetchData(); this.fetchAccounts(); this.fetchLoans(); this.fetchGoals(); this.fetchCategories(); this.fetchOverrides(); this.fetchRecurring(); this.checkDuePayments(); },
        async fetchData() { if (!this.isLoggedIn) return; try { this.dashboard = await API.finance.getDashboard(this.periodOffset); if (this.accounts.length > 0 && !this.newTx.account_id) this.newTx.account_id = this.accounts[0].id; if (this.viewMode === 'chart') this.renderChart(); } catch (e) { console.error(e); } },
        async fetchAccounts() { if(this.isLoggedIn) this.accounts = await API.accounts.getAll(); },
        async fetchLoans() {
            console.log('🔄 fetchLoans() wywołane');
            if (!this.isLoggedIn) return;
            
            const data = await API.loans.getAll();
            this.loansData = { loans: data.loans };
            
            // Zapisz alerty
            if (data.alerts) {
                this.loanAlerts = data.alerts;
                
                // Sprawdź localStorage - czy dismissed?
                const dismissedUntil = localStorage.getItem('loan_alerts_dismissed_until');
                const today = new Date().toISOString().split('T')[0];
                
                // NIE POKAZUJ jeśli:
                // 1. Właśnie zamknięto modal (recently dismissed)
                // 2. LUB localStorage mówi że dismissed do jutra
                if (this.loanAlertsRecentlyDismissed) {
                    console.log('Modal nie pojawi się - właśnie zamknięty');
                    return;
                }
                
                if (dismissedUntil && dismissedUntil >= today) {
                    console.log('Modal nie pojawi się - dismissed do jutra');
                    return;
                }
                
                // Pokaż tylko jeśli są PILNE (overdue lub urgent)
                if (data.alerts.has_alerts &&
                    (this.loanAlerts.overdue.length > 0 || this.loanAlerts.urgent.length > 0)) {
                    this.showLoanAlerts = true;
                }
            }
        },
        
        async fetchGoals() { if(this.isLoggedIn) this.goals = await API.goals.getAll(); },
        async fetchCategories() { if(this.isLoggedIn) this.categories = await API.categories.getAll(); },
        async fetchOverrides() { if(this.isLoggedIn) this.overrides = await API.settings.getOverrides(); },
        async fetchRecurring() { if(this.isLoggedIn) this.recurringList = await API.recurring.getAll(); },
        async checkDuePayments() { if(this.isLoggedIn) this.duePayments = await API.recurring.checkDue(); },

        async submitTransaction() {
            if(!this.newTx.account_id) return this.notify('error', "Wybierz konto!");
            if(this.newTx.type === 'transfer' && !this.newTx.target_account_id) return this.notify('error', "Wybierz konto docelowe!");
            if(!this.newTx.description) return this.notify('error', "Opis jest wymagany!");
            const payload = { ...this.newTx, status: this.isPlanned ? 'planowana' : 'zrealizowana' };
            try { if (this.editingTxId) await API.transactions.update(this.editingTxId, payload); else await API.transactions.create(payload); this.resetForm(); this.currentTab = 'dashboard'; this.fetchData(); this.fetchAccounts(); this.notify('success', this.editingTxId ? 'Zaktualizowano' : 'Dodano'); } catch(e) { this.notify('error', 'Błąd zapisu'); }
        },
        async realizeTx(tx) { const payload = { description: tx.desc, amount: tx.amount, type: tx.type, account_id: tx.account_id, target_account_id: tx.target_account_id, category_name: tx.category, loan_id: tx.loan_id, date: tx.date.split('T')[0], status: 'zrealizowana' }; await API.transactions.update(tx.id, payload); this.fetchData(); this.fetchAccounts(); this.notify('success', 'Zrealizowano'); },
        async deleteTx(id) { if(!confirm("Usunąć?")) return; await API.transactions.delete(id); this.fetchData(); this.fetchAccounts(); this.notify('info', 'Usunięto'); },
        
        async createTestAccount() { const name = prompt("Nazwa:"); if(name) { await API.accounts.create({ name: name, type: "bank", balance: 0, is_savings: false }); this.fetchAccounts(); this.notify('success', 'Utworzono'); } },
        async deleteAccount(id) { if(!confirm("Usunąć?")) return; await API.accounts.delete(id); this.fetchAccounts(); this.fetchData(); this.notify('info', 'Usunięto'); },
        async editAccount(acc) { const newName = prompt("Nazwa:", acc.name); if(!newName) return; const newBalance = prompt("Saldo:", acc.balance); const isSavings = confirm("Oszczędnościowe?"); await API.accounts.update(acc.id, { name: newName, type: acc.type, balance: parseFloat(newBalance), is_savings: isSavings }); this.fetchAccounts(); this.notify('success', 'Zaktualizowano'); },

        async submitLoan() { await API.loans.create(this.newLoan); this.showAddLoan = false; this.fetchLoans(); this.notify('success', 'Dodano'); },
        async updateLoan() { await API.loans.update(this.editingLoan.id, this.editingLoan); this.editingLoan = null; this.fetchLoans(); this.notify('success', 'Zaktualizowano'); },
        
        async submitGoal() { if (!this.newGoal.account_id) return this.notify('error', "Wybierz konto!"); await API.goals.create(this.newGoal); this.showAddGoal = false; this.fetchGoals(); this.newGoal = { name: '', target_amount: '', deadline: new Date().toISOString().split('T')[0], account_id: null }; this.notify('success', 'Utworzono'); },
        async deleteGoal(id) {
            if(!confirm("Czy na pewno chcesz usunąć ten cel? Środki zostaną odblokowane i będą widoczne jako dostępne na koncie.")) return;
            
            try {
                const response = await API.goals.delete(id);
                
                if (response.ok) {
                    this.notify('success', 'Cel usunięty, środki zostały odblokowane');
                    
                    // KLUCZOWE: Odświeżamy oba zestawy danych
                    await this.fetchGoals();    // Usuwa cel z widoku celów
                    await this.fetchAccounts(); // Aktualizuje "Dostępne środki" w widoku kont
                    await this.fetchData();     // Aktualizuje Dashboard
                } else {
                    const errorData = await response.json();
                    this.notify('error', 'Błąd: ' + (errorData.detail || 'Nie udało się usunąć celu'));
                }
            } catch (e) {
                this.notify('error', 'Błąd połączenia. Sprawdź czy serwer działa.');
                console.error("Błąd usuwania celu:", e);
            }
        },
        async submitFundGoal() { await API.goals.fund(this.fundingGoal.id, this.fundData); this.fundingGoal = null; this.fetchGoals(); this.fetchAccounts(); this.notify('success', 'Zasilono'); },
        async submitWithdrawGoal() { if (!this.withdrawData.amount || !this.withdrawData.target_account_id) return this.notify('error', "Wypełnij pola"); if (parseFloat(this.withdrawData.amount) > parseFloat(this.withdrawingGoal.current_amount)) return this.notify('error', "Brak środków!"); await API.goals.withdraw(this.withdrawingGoal.id, this.withdrawData); this.withdrawingGoal = null; this.fetchGoals(); this.fetchAccounts(); this.notify('success', 'Wypłacono'); },
        async submitTransferGoal() { await API.goals.transfer(this.transferingGoal.id, this.transferData); this.transferingGoal = null; this.fetchGoals(); this.notify('success', 'Przeniesiono'); },
        editRecurring(rec) {
            console.log('🔧 editRecurring wywołane:', rec);
            
            // Ustaw POLA reactive object (nie nadpisuj całego obiektu):
            this.newRecurring.name = rec.name;
            this.newRecurring.amount = rec.amount;
            this.newRecurring.day_of_month = rec.day_of_month;
            this.newRecurring.category_name = rec.category ? rec.category.name : '';
            this.newRecurring.account_id = rec.account_id;
            
            console.log('✅ newRecurring po ustawieniu:', this.newRecurring);
            
            // Zapisz ID (flaga że to edycja, nie nowe):
            this.editingRecurring = { id: rec.id };
            
            // Otwórz formularz:
            this.showAddRecurring = true;
        },

        editGoal(goal) {
            this.editingGoal = { ...goal }; // Kopiujemy dane celu do edycji
            // deadline musimy sformatować do YYYY-MM-DD dla inputa date
            if (this.editingGoal.deadline) {
                this.editingGoal.deadline = this.editingGoal.deadline.split('T')[0];
            }
        },

        async submitUpdateGoal() {
            try {
                const response = await API.goals.update(this.editingGoal.id, {
                    name: this.editingGoal.name,
                    target_amount: parseFloat(this.editingGoal.target_amount),
                    deadline: this.editingGoal.deadline,
                    account_id: this.editingGoal.account_id
                });
                
                if (response.ok) {
                    this.notify('success', 'Cel zaktualizowany');
                    this.editingGoal = null;
                    await this.fetchGoals();
                }
            } catch (e) {
                this.notify('error', 'Błąd aktualizacji celu');
            }
        },
        
        
        
        async submitRecurring() {
            if (this.editingRecurring && this.editingRecurring.id) {
                // UPDATE
                await API.recurring.update(this.editingRecurring.id, this.newRecurring);
                this.notify('success', 'Zaktualizowano');
            } else {
                // CREATE
                await API.recurring.create(this.newRecurring);
                this.notify('success', 'Dodano');
            }
            
            this.editingRecurring = null;
            this.showAddRecurring = false;
            this.fetchRecurring();
        },
        async deleteRecurring(id) { if(!confirm("Usunąć?")) return; await API.recurring.delete(id); this.fetchRecurring(); this.notify('info', 'Usunięto'); },
        async processRecurring(pay) {
            // Użyj daty z payment_date (obliczonej przez backend):
            const paymentDate = pay.payment_date || new Date().toISOString().split('T')[0];
            await API.recurring.process(pay.id, paymentDate); this.duePayments = this.duePayments.filter(p => p.id !== pay.id); this.fetchData(); this.fetchAccounts(); this.notify('success', 'Zaksięgowano'); },
        async skipRecurring(pay) { if(!confirm("Pominąć?")) return; await API.recurring.skip(pay.id); this.duePayments = this.duePayments.filter(p => p.id !== pay.id); this.notify('info', 'Pominięto'); },

        async addCategory(catData) {
            if(!catData.name) return;
            await API.categories.create(catData);
            this.fetchCategories();
            this.notify('success', 'Dodano kategorię');
        },
        async deleteCategory(id) { if(!confirm("Usunąć?")) return; await API.categories.delete(id); this.fetchCategories(); this.notify('info', 'Usunięto'); },
        async updateCategoryLimit(cat) {
            if (!cat.id) return;
            await API.categories.update(cat.id, {
                name: cat.name,
                monthly_limit: parseFloat(cat.limit || 0),
                icon: cat.icon_name || 'tag',  // DODANE
                color: cat.color || '#94a3b8'  // DODANE
            });
            this.fetchCategories();
            this.notify('success', "Zapisano");
        },
        async updateCategory(cat) {
            if (!cat.id) return;
            await API.categories.update(cat.id, {
                name: cat.name,
                monthly_limit: parseFloat(cat.limit || 0),
                icon: cat.icon_name,
                color: cat.color
            });
            this.fetchCategories();
            this.notify('success', "Zaktualizowano kategorię");
        },

        async addOverride() { await API.settings.addOverride(this.newOverride); this.fetchOverrides(); this.notify('success', 'Dodano'); },
        async deleteOverride(id) { if(!confirm("Usunąć?")) return; await API.settings.deleteOverride(id); this.fetchOverrides(); this.notify('info', 'Usunięto'); },
        async changePassword() { if(!this.security.oldPassword || !this.security.newPassword) return this.notify('error', "Wpisz hasła"); try { await API.auth.changePassword(this.security.oldPassword, this.security.newPassword); this.notify('success', "Zmieniono"); this.security.oldPassword = ''; this.security.newPassword = ''; } catch(e) { this.notify('error', "Błąd"); } },
        async registerUser() { if(!this.security.newUsername || !this.security.newUserPass) return this.notify('error', "Wpisz dane"); try { await API.auth.register(this.security.newUsername, this.security.newUserPass); this.notify('success', "Dodano"); this.security.newUsername = ''; this.security.newUserPass = ''; } catch(e) { this.notify('error', "Błąd"); } },

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
        performSearch() {
            const params = new URLSearchParams();
            if(this.searchCriteria.q) params.append('q', this.searchCriteria.q);
            if(this.searchCriteria.date_from) params.append('date_from', this.searchCriteria.date_from);
            if(this.searchCriteria.date_to) params.append('date_to', this.searchCriteria.date_to);
            if(this.searchCriteria.category_id) params.append('category_id', this.searchCriteria.category_id);
            if(this.searchCriteria.account_id) params.append('account_id', this.searchCriteria.account_id);
            if(this.searchCriteria.type && this.searchCriteria.type !== 'all') params.append('type', this.searchCriteria.type);
            if(this.searchCriteria.min_amount) params.append('min_amount', this.searchCriteria.min_amount);
            if(this.searchCriteria.max_amount) params.append('max_amount', this.searchCriteria.max_amount);

            API.transactions.search(params.toString()).then(data => {
                this.searchResults = data.transactions;
                this.searchSummary = data.summary;
            });
        },
        clearSearchFilters() {
            this.searchCriteria = { q: '', date_from: '', date_to: '', category_id: null, account_id: null, type: 'all', min_amount: '', max_amount: '' };
            this.searchResults = null;
        },

        triggerImport(accountId) { this.importTargetAccountId = accountId; const input = document.createElement('input'); input.type = 'file'; input.accept = '.csv'; input.onchange = e => { if (e.target.files.length > 0) this.processImportFile(e.target.files[0]); }; input.click(); },
        async processImportFile(file) { try { const res = await API.importCSV.preview(file); if (!res.ok) throw new Error("Błąd"); const data = await res.json(); if (data.length === 0) return this.notify('error', "Brak danych"); this.importData = data.map(tx => ({...tx, ignore: false})); } catch (e) { this.notify('error', "Błąd importu"); } },
        async submitImport() {
            if (!this.importData || !this.importTargetAccountId) return;
            const toImport = this.importData.filter(tx => !tx.ignore);
            if (toImport.length === 0) return this.notify('error', 'Zaznacz przynajmniej jedną transakcję');
            const missingCat = toImport.find(tx => !tx.category_id);
            if (missingCat) return this.notify('error', `Transakcja "${missingCat.description}" nie ma kategorii`);
            
            try {
                const response = await API.importCSV.confirm(this.importTargetAccountId, toImport);
               
                if (!response.ok) {
                            throw new Error('Błąd API');
                        }
                const data = await response.json();
             
                
                const imported = data.imported || 0;
                const skipped = data.skipped || 0;
                
                // Inteligentny komunikat
                let message = '';
                if (imported > 0 && skipped === 0) {
                    message = `✅ Zaimportowano ${imported} transakcji`;
                } else if (imported > 0 && skipped > 0) {
                    message = `✅ Zaimportowano ${imported}, pominięto ${skipped} duplikatów`;
                } else if (imported === 0 && skipped > 0) {
                    message = `ℹ️ Wszystkie transakcje już istnieją (pominięto ${skipped})`;
                } else {
                    message = 'Brak transakcji do zaimportowania';
                }
                
                this.notify('success', message);
                this.importData = null;
                this.importTargetAccountId = null;
                this.fetchData();
                this.fetchAccounts();
            } catch (e) {
              
                this.notify('error', "Błąd zapisu: " + (e.message || 'Nieznany błąd'));
            }
        },

        changePeriod(delta) { this.transitionName = delta > 0 ? 'slide-next' : 'slide-prev'; this.periodOffset += delta; this.fetchData(); },
        handleTouchStart(e) { this.touchStartX = e.changedTouches[0].screenX; },
        handleTouchEnd(e) { this.touchEndX = e.changedTouches[0].screenX; this.handleSwipe(); },
        handleSwipe() { if (this.currentTab !== 'dashboard') return; const diff = this.touchEndX - this.touchStartX; if (diff > 50) this.changePeriod(-1); if (diff < -50) this.changePeriod(1); },
        
        async openCategoryDetails(cat) {
            this.selectedCategory = cat;
            this.categoryModalTab = 'overview';  // Zawsze zaczynaj od overview
            
            // Pobierz trend dla tej kategorii
            try {
                this.categoryTrend = await API.categories.getTrend(cat.id);
            } catch (e) {
                console.error('Błąd pobierania trendu:', e);
                this.categoryTrend = null;
            }
        },
        editTxFromModal(tx) { this.selectedCategory = null; this.editTx(tx); },
        async realizeTxFromModal(tx) { await this.realizeTx(tx); this.selectedCategory = null; },
        copyTx(tx) { this.newTx = { description: tx.desc, amount: tx.amount, type: tx.type, account_id: tx.account_id, target_account_id: tx.target_account_id, category_name: tx.category, loan_id: tx.loan_id, date: new Date().toISOString().split('T')[0] }; this.isPlanned = false; this.editingTxId = null; this.currentTab = 'add'; this.selectedCategory = null; window.scrollTo(0,0); this.notify('info', 'Skopiowano'); },
        handleLoanChange() {
            if (this.newTx.loan_id) {
                const loan = this.activeLoans.find(l => l.id === this.newTx.loan_id);
                // Jeśli nazwa kredytu zawiera "hipote", ustaw kategorię Hipoteczny
                if (loan && loan.name.toLowerCase().includes('hipote')) {
                    this.newTx.category_name = 'Kredyt hipoteczny';
                } else {
                    this.newTx.category_name = 'Spłata zobowiązań';
                }
            } else {
                this.newTx.category_name = '';
            }
        },
        detectCategory() {
            if(this.editingTxId) return;
            
            const desc = this.newTx.description.toLowerCase();
            console.log('🔍 detectCategory:', desc);
            
            if (desc.length < 3) return;
            
            // Szukaj w CAŁEJ BAZIE (nie tylko recent):
            API.transactions.search(`q=${desc}&type=${this.newTx.type}`)
                .then(data => {
                    if (data.transactions && data.transactions.length > 0) {
                        // Pierwsza znaleziona z kategorią:
                        const match = data.transactions.find(tx =>
                            tx.category &&
                            tx.category !== '-' &&
                            tx.category !== 'Transfer'
                        );
                        
                        if (match) {
                            console.log('✅ AUTO-KATEGORIA:', match.category);
                            this.newTx.category_name = match.category;
                        } else {
                            console.log('❌ Brak kategorii w wynikach');
                        }
                    } else {
                        console.log('❌ Brak wyników dla:', desc);
                    }
                })
                .catch(e => console.error('Błąd search:', e));
        },
        editTx(tx) { this.editingTxId = tx.id; this.isPlanned = (tx.status === 'planowana'); this.newTx = { description: tx.desc, amount: tx.amount, type: tx.type, account_id: tx.account_id, category_name: tx.category_name, loan_id: tx.loan_id, date: tx.date.split('T')[0], target_account_id: tx.target_account_id }; this.currentTab = 'add'; },
        cancelEdit() { this.resetForm(); this.currentTab = 'dashboard'; },
        resetForm() { this.editingTxId = null; this.isPlanned = false; this.showCategorySelector = false; this.newTx = { description: '', amount: '', type: 'expense', account_id: this.accounts[0]?.id, target_account_id: null, category_name: '', loan_id: null, date: new Date().toISOString().split('T')[0] }; },
        editLoan(loan) { this.editingLoan = { ...loan, total_amount: loan.total, remaining_amount: loan.remaining, monthly_payment: loan.monthly, next_payment_date: loan.next_date }; },
        openFundGoal(goal) { this.fundingGoal = goal; const defaultSource = this.accounts[0]?.id; const defaultTarget = this.savingsAccounts[0]?.id; this.fundData = { source_account_id: defaultSource, target_savings_id: defaultTarget, amount: '' }; },
        openTransferGoal(goal) { this.transferingGoal = goal; this.transferData = { target_goal_id: null, amount: '' }; },
        openWithdrawGoal(goal) { this.withdrawingGoal = goal; const defaultTarget = this.accounts.find(a => !a.is_savings) || this.accounts[0]; this.withdrawData = { target_account_id: defaultTarget ? defaultTarget.id : null, amount: '' }; },

        async renderChart() {
            const ctxTrend = document.getElementById('trendChart');
            if (ctxTrend) { const trendData = await API.finance.getTrend(); Charts.renderTrendChart(ctxTrend, trendData); }
            const ctxDoughnut = document.getElementById('expenseDoughnut');
            if (ctxDoughnut) { Charts.renderDoughnutChart(ctxDoughnut, this.expenseCategories, this.chartColors, (segment) => { this.selectedChartSegment = segment; }); }
        }
    },
    mounted() { if (this.isLoggedIn) this.refreshAllData(); }
}).mount('#app');
