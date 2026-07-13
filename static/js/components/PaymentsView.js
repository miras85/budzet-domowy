import * as Utils from '../utils.js';
export default {
    props: ['filteredLoans', 'showPaidLoans', 'showAddLoan', 'newLoan', 'showAddRecurring', 'newRecurring', 'recurringList', 'accounts', 'filteredCategories', 'categorySearch', 'loansData', 'userRole'],
    emits: ['update:showPaidLoans', 'update:showAddLoan', 'update:showAddRecurring', 'update:categorySearch', 'submit-loan', 'edit-loan', 'submit-recurring', 'delete-recurring', 'edit-recurring'],
    data() { return { showCategorySelector: false } },
    setup() { return { ...Utils }; },
    template: `
    <div class="px-6">
        <h2 class="text-xl font-bold text-white mb-6 mt-4">Zobowiązania</h2>

        <div v-if="loansData.total_monthly_payments > 0"
             class="glass-panel p-4 rounded-2xl mb-6 border-l-4 border-red-500">
            <div class="flex justify-between items-center">
                <div>
                    <div class="text-xs text-slate-400 uppercase font-bold mb-1">Raty kredytów w tym cyklu</div>
                    <div class="text-xs text-slate-500">{{ formatDateShort(loansData.period_start) }} - {{ formatDateShort(loansData.period_end) }}</div>
                </div>
                <div class="text-xl font-bold text-red-400">{{ formatMoney(loansData.total_monthly_payments) }}</div>
            </div>
        </div>

        <!-- KREDYTY -->
        <div class="mb-8">
            <div class="flex justify-between items-center mb-4">
                <h3 class="text-sm font-bold text-slate-400 uppercase">Kredyty i Raty</h3>
                <button v-if="userRole === 'admin'" @click="$emit('update:showAddLoan', !showAddLoan)" class="text-blue-400 text-xs font-bold">{{ showAddLoan ? 'Anuluj' : '+ Dodaj' }}</button>
            </div>
            <div class="flex justify-end mb-2">
                <label class="flex items-center gap-2 text-xs text-slate-400">
                    <input type="checkbox" :checked="showPaidLoans" @change="$emit('update:showPaidLoans', $event.target.checked)"> Pokaż spłacone
                </label>
            </div>
            <div v-if="showAddLoan && userRole === 'admin'" class="glass-panel p-4 rounded-2xl mb-4">
                <div class="space-y-3">
                    <input v-model="newLoan.name" placeholder="Nazwa" class="input-dark w-full p-3 rounded-xl text-sm">
                    <input v-model="newLoan.total_amount" type="number" placeholder="Kwota całk." class="input-dark w-full p-3 rounded-xl text-sm">
                    <input v-model="newLoan.remaining_amount" type="number" placeholder="Pozostało" class="input-dark w-full p-3 rounded-xl text-sm">
                    <input v-model="newLoan.monthly_payment" type="number" placeholder="Rata" class="input-dark w-full p-3 rounded-xl text-sm">
                    <input v-model="newLoan.next_payment_date" type="date" class="input-dark w-full p-3 rounded-xl text-sm">
                    <button @click="$emit('submit-loan')" class="w-full bg-blue-600 py-3 rounded-xl font-bold text-sm">Dodaj</button>
                </div>
            </div>
            <div class="space-y-4">
                <div v-for="loan in filteredLoans" :key="loan.id" class="glass-panel p-5 rounded-2xl border-l-4" :class="loan.remaining <= 0 ? 'border-green-500 opacity-60' : 'border-red-500'">
                    <div class="flex justify-between items-start mb-2">
                        <div>
                            <div class="font-bold text-lg text-white">{{ loan.name }}</div>
                            <div :class="loan.remaining <= 0 ? 'text-green-400' : 'text-red-400'" class="font-bold">{{ formatMoney(loan.remaining) }}</div>
                        </div>
                        <button v-if="userRole === 'admin'" @click="$emit('edit-loan', loan)" class="text-slate-500 hover:text-blue-400 p-1">✎</button>
                    </div>
                    <div class="w-full bg-slate-700 h-2 rounded-full mb-3 overflow-hidden">
                        <div class="bg-green-500 h-full" :style="{ width: calculateProgress(loan) + '%' }"></div>
                    </div>
                    <div class="flex justify-between text-xs text-slate-400">
                        <div>Rata: <span class="text-slate-200">{{ formatMoney(loan.monthly) }}</span></div>
                        <div>Termin: <span class="text-slate-200">{{ loan.next_date }}</span></div>
                    </div>
                </div>
            </div>
        </div>

        <!-- SUBSKRYPCJE -->
        <div>
            <div class="flex justify-between items-center mb-4">
                <h3 class="text-sm font-bold text-slate-400 uppercase">Stałe Opłaty (Subskrypcje)</h3>
                <button v-if="userRole === 'admin'" @click="$emit('update:showAddRecurring', !showAddRecurring)" class="text-blue-400 text-xs font-bold">{{ showAddRecurring ? 'Anuluj' : '+ Dodaj' }}</button>
            </div>
            <div v-if="showAddRecurring && userRole === 'admin'" class="glass-panel p-4 rounded-2xl mb-4 space-y-3">
                <input v-model="newRecurring.name" placeholder="Nazwa (np. Netflix)" class="input-dark w-full p-3 rounded-xl text-sm">
                <input v-model="newRecurring.amount" type="number" placeholder="Kwota" class="input-dark w-full p-3 rounded-xl text-sm">
                <div class="flex gap-2">
                    <input v-model="newRecurring.day_of_month" type="number" placeholder="Dzień" class="input-dark w-20 p-3 rounded-xl text-sm text-center">
                    <div class="flex-1 relative">
                        <div @click="showCategorySelector = !showCategorySelector" class="bg-slate-900 p-3 rounded-xl border border-slate-700 flex justify-between items-center cursor-pointer h-full">
                            <span :class="newRecurring.category_name ? 'text-white font-bold' : 'text-slate-500'">{{ newRecurring.category_name || 'Kategoria...' }}</span>
                            <span class="text-slate-400 text-xs">▼</span>
                        </div>
                        <div v-if="showCategorySelector" class="absolute top-full left-0 right-0 mt-2 bg-slate-800 p-3 rounded-xl border border-slate-700 z-50 shadow-xl">
                            <input :value="categorySearch" @input="$emit('update:categorySearch', $event.target.value)" placeholder="Szukaj..." class="w-full bg-slate-900 p-2 rounded-lg text-sm text-white mb-3 border border-slate-700 outline-none">
                            <div class="grid grid-cols-2 gap-2 max-h-40 overflow-y-auto">
                                <button v-for="cat in filteredCategories" :key="cat.id" @click="newRecurring.category_name = cat.name; showCategorySelector = false" class="cat-chip" :class="newRecurring.category_name === cat.name ? 'selected' : ''">{{ cat.name }}</button>
                            </div>
                        </div>
                    </div>
                </div>
                <select v-model="newRecurring.account_id" class="input-dark w-full p-3 rounded-xl text-sm">
                    <option v-for="acc in accounts" :value="acc.id">{{ acc.name }}</option>
                </select>
                <button @click="$emit('submit-recurring')" class="w-full bg-blue-600 py-3 rounded-xl font-bold text-sm">Zapisz</button>
            </div>
            <div class="space-y-3">
                <div v-for="rec in recurringList" :key="rec.id" class="glass-panel p-4 rounded-2xl flex justify-between items-center">
                    <div>
                        <div class="font-bold text-white">{{ rec.name }}</div>
                        <div class="text-xs text-slate-400">{{ rec.day_of_month }}-go dnia miesiąca • {{ rec.category ? rec.category.name : '-' }}</div>
                    </div>
                    <div class="text-right">
                        <div class="font-bold text-white">{{ formatMoney(rec.amount) }}</div>
                        <div v-if="userRole === 'admin'" class="flex gap-2 mt-1">
                            <button @click="$emit('edit-recurring', rec)" class="text-blue-400 text-xs font-bold">EDYTUJ</button>
                            <button @click="$emit('delete-recurring', rec.id)" class="text-red-400 text-xs font-bold">USUŃ</button>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <div v-if="userRole === 'viewer'" class="mt-4 p-3 bg-slate-800/50 rounded-xl text-center">
            <p class="text-xs text-slate-500">👁️ Tryb podglądu — tylko odczyt</p>
        </div>
    </div>`
}
