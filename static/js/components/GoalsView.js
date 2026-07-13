import * as Utils from '../utils.js';
export default {
    props: ['goals', 'savingsAccounts', 'showAddGoal', 'newGoal', 'showArchivedGoals', 'archivedGoals', 'userRole'],
    emits: [
        'update:showAddGoal',
        'submit-goal',
        'delete-goal',
        'open-fund',
        'open-withdraw',
        'open-transfer',
        'edit-goal',
        'archive-goal',
        'toggle-archive'
    ],
    setup() { return { ...Utils }; },
    template: `
    <div class="px-6">
        <div class="flex justify-between items-center mb-6 mt-4">
            <h2 class="text-xl font-bold text-white">Cele Oszczędnościowe</h2>
            <button v-if="userRole === 'admin'" @click="$emit('update:showAddGoal', !showAddGoal)" class="text-blue-400 text-sm font-bold">{{ showAddGoal ? 'Anuluj' : '+ Dodaj' }}</button>
        </div>

        <div v-if="showAddGoal && userRole === 'admin'" class="glass-panel p-4 rounded-2xl mb-6">
            <div class="space-y-3">
                <input v-model="newGoal.name" placeholder="Nazwa celu" class="input-dark w-full p-3 rounded-xl">
                <select v-model="newGoal.account_id" class="input-dark w-full p-3 rounded-xl">
                    <option :value="null" disabled>-- Wybierz konto --</option>
                    <option v-for="acc in savingsAccounts" :value="acc.id">{{ acc.name }} ({{ formatMoney(acc.balance) }})</option>
                </select>
                <input v-model="newGoal.target_amount" type="number" placeholder="Kwota docelowa" class="input-dark w-full p-3 rounded-xl">
                <input v-model="newGoal.deadline" type="date" class="input-dark w-full p-3 rounded-xl">
                <button @click="$emit('submit-goal')" class="w-full bg-blue-600 py-3 rounded-xl font-bold text-sm mt-2">Utwórz Cel</button>
            </div>
        </div>

        <div class="space-y-4">
            <div v-for="goal in goals" :key="goal.id" class="glass-panel p-5 rounded-2xl border-l-4 border-green-500 relative overflow-hidden">
                <div class="flex justify-between items-start mb-2 relative z-10">
                    <div>
                        <div class="font-bold text-lg text-white">{{ goal.name }}</div>
                        <div class="text-xs text-slate-400">Termin: {{ formatDateShort(goal.deadline) }}</div>
                    </div>
                    <div class="text-right">
                        <div class="font-bold text-green-400">{{ formatMoney(goal.current_amount) }}</div>
                        <div class="text-[10px] text-slate-500">z {{ formatMoney(goal.target_amount) }}</div>
                    </div>
                </div>
                <div class="w-full bg-slate-700 h-2 rounded-full mb-2 overflow-hidden relative z-10">
                    <div class="bg-green-500 h-full" :style="{ width: Math.min(100, (goal.current_amount / goal.target_amount) * 100) + '%' }"></div>
                </div>
                <div v-if="goal.current_amount >= goal.target_amount" class="mb-3 text-xs text-green-400 font-bold text-right relative z-10">Cel osiągnięty! 🎉</div>
                <div v-else-if="goal.monthly_need > 0" class="flex justify-between items-center mb-3 relative z-10">
                    <div class="text-[10px] text-slate-400 uppercase font-bold">Wymagane w tym cyklu:</div>
                    <div class="text-xs font-bold text-yellow-400 bg-yellow-400/10 px-2 py-1 rounded">{{ formatMoney(goal.monthly_need) }}</div>
                </div>
                <div v-else class="mb-3 text-xs text-blue-400 font-bold text-right relative z-10">Plan na ten miesiąc wykonany 👍</div>

                <div class="flex gap-2 mt-1 relative z-10">
                    <button v-if="userRole === 'admin'" @click="$emit('open-fund', goal)" class="flex-1 bg-slate-800 py-2 rounded-lg text-xs font-bold text-white border border-slate-700">Zasil</button>
                    <button v-if="userRole === 'admin'" @click="$emit('open-withdraw', goal)" class="flex-1 bg-slate-800 py-2 rounded-lg text-xs font-bold text-white border border-slate-700">Wypłać</button>
                    <button v-if="userRole === 'admin'" @click="$emit('open-transfer', goal)" class="flex-1 bg-slate-800 py-2 rounded-lg text-xs font-bold text-white border border-slate-700">Przenieś</button>
                    <button v-if="userRole === 'admin'" @click="$emit('archive-goal', goal.id)" class="px-3 bg-slate-800 py-2 rounded-lg text-xs font-bold text-yellow-400 border border-slate-700">📦</button>
                    <button v-if="userRole === 'admin'" @click="$emit('edit-goal', goal)" class="px-3 bg-slate-800 rounded-lg text-blue-400 font-bold border border-slate-700">✎</button>
                    <button v-if="userRole === 'admin'" @click="$emit('delete-goal', goal.id)" class="px-3 bg-slate-800 rounded-lg text-red-400 font-bold border border-slate-700">×</button>
                </div>
            </div>
        </div>

        <!-- Sekcja Archiwum -->
        <div class="mt-8">
            <button @click="$emit('toggle-archive')"
                    class="w-full flex justify-between items-center bg-slate-800/50 p-3 rounded-xl border border-slate-700 text-slate-400 text-xs font-bold uppercase">
                <span>📦 Archiwum celów</span>
                <span>{{ showArchivedGoals ? '▲' : '▼' }}</span>
            </button>
            <div v-if="showArchivedGoals" class="mt-4 space-y-3">
                <div v-if="archivedGoals.length === 0" class="text-center text-slate-500 text-sm py-4">
                    Brak zarchiwizowanych celów
                </div>
                <div v-for="goal in archivedGoals" :key="goal.id"
                     class="glass-panel p-4 rounded-2xl border-l-4 border-slate-600 opacity-70">
                    <div class="flex justify-between items-start">
                        <div>
                            <div class="font-bold text-slate-400">{{ goal.name }}</div>
                            <div class="text-xs text-slate-500">Termin: {{ formatDateShort(goal.deadline) }}</div>
                        </div>
                        <div class="text-right">
                            <div class="text-sm font-bold text-slate-400">{{ formatMoney(goal.current_amount) }}</div>
                            <div class="text-[10px] text-slate-600">z {{ formatMoney(goal.target_amount) }}</div>
                        </div>
                    </div>
                    <div class="w-full bg-slate-700 h-1.5 rounded-full mt-2 overflow-hidden">
                        <div class="bg-slate-500 h-full"
                             :style="{ width: Math.min(100, (goal.current_amount / goal.target_amount) * 100) + '%' }">
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
