import * as Utils from '../utils.js';

export default {
    props: ['alerts', 'accounts'],
    emits: ['close', 'add-to-planned', 'dismiss-until-tomorrow'],
    setup() {
        return { ...Utils };
    },
    computed: {
        totalAmount() {
            return this.alerts.total_overdue + this.alerts.total_urgent + this.alerts.total_upcoming;
        },
        hasOverdue() {
            return this.alerts.overdue && this.alerts.overdue.length > 0;
        },
        hasUrgent() {
            return this.alerts.urgent && this.alerts.urgent.length > 0;
        },
        hasUpcoming() {
            return this.alerts.upcoming && this.alerts.upcoming.length > 0;
        }
    },
    methods: {
        addAllToPlanned() {
            // Dodaj wszystkie pilne płatności jako planowane transakcje
            const payments = [...this.alerts.overdue, ...this.alerts.urgent];
            this.$emit('add-to-planned', payments);
        },
        dismissUntilTomorrow() {
            this.$emit('dismiss-until-tomorrow');
        }
    },
    template: `
    <div class="fixed inset-0 z-[70] bg-black/90 backdrop-blur-md flex items-center justify-center p-4">
        <div class="glass-panel w-full max-w-md rounded-2xl p-6 border border-yellow-500/50">
            
            <!-- Header -->
            <div class="flex items-center gap-3 mb-4">
                <div class="text-3xl">⚠️</div>
                <div>
                    <h3 class="text-xl font-bold text-white">Zbliżające się płatności</h3>
                    <p class="text-sm text-slate-400">Raty kredytów wymagają uwagi</p>
                </div>
            </div>
            
            <!-- Przeterminowane (czerwone) -->
            <div v-if="hasOverdue" class="bg-red-900/30 border border-red-500/50 rounded-xl p-4 mb-3">
                <div class="text-xs font-bold text-red-400 uppercase mb-2">🔴 Przeterminowane</div>
                <div class="space-y-2">
                    <div v-for="pay in alerts.overdue" :key="pay.loan_id" class="flex justify-between items-center">
                        <div>
                            <div class="font-bold text-white text-sm">{{ pay.name }}</div>
                            <div class="text-xs text-red-300">{{ formatDateShort(pay.date) }} ({{ Math.abs(pay.days_until) }} dni temu)</div>
                        </div>
                        <div class="font-bold text-red-400">{{ formatMoney(pay.amount) }}</div>
                    </div>
                </div>
                <div class="text-xs text-red-300 mt-2 border-t border-red-500/30 pt-2">
                    Suma: <span class="font-bold">{{ formatMoney(alerts.total_overdue) }}</span>
                </div>
            </div>
            
            <!-- Pilne (żółte) -->
            <div v-if="hasUrgent" class="bg-yellow-900/30 border border-yellow-500/50 rounded-xl p-4 mb-3">
                <div class="text-xs font-bold text-yellow-400 uppercase mb-2">🟡 Pilne (0-7 dni)</div>
                <div class="space-y-2">
                    <div v-for="pay in alerts.urgent" :key="pay.loan_id" class="flex justify-between items-center">
                        <div>
                            <div class="font-bold text-white text-sm">{{ pay.name }}</div>
                            <div class="text-xs text-yellow-300">{{ formatDateShort(pay.date) }} (za {{ pay.days_until }} dni)</div>
                        </div>
                        <div class="font-bold text-yellow-400">{{ formatMoney(pay.amount) }}</div>
                    </div>
                </div>
                <div class="text-xs text-yellow-300 mt-2 border-t border-yellow-500/30 pt-2">
                    Suma: <span class="font-bold">{{ formatMoney(alerts.total_urgent) }}</span>
                </div>
            </div>
            
            <!-- Zbliżające się (niebieskie) -->
            <div v-if="hasUpcoming" class="bg-blue-900/30 border border-blue-500/50 rounded-xl p-4 mb-3">
                <div class="text-xs font-bold text-blue-400 uppercase mb-2">ℹ️ Wkrótce (8-30 dni)</div>
                <div class="space-y-2">
                    <div v-for="pay in alerts.upcoming" :key="pay.loan_id" class="flex justify-between items-center">
                        <div>
                            <div class="font-bold text-white text-sm">{{ pay.name }}</div>
                            <div class="text-xs text-blue-300">{{ formatDateShort(pay.date) }} (za {{ pay.days_until }} dni)</div>
                        </div>
                        <div class="font-bold text-blue-400">{{ formatMoney(pay.amount) }}</div>
                    </div>
                </div>
                <div class="text-xs text-blue-300 mt-2 border-t border-blue-500/30 pt-2">
                    Suma: <span class="font-bold">{{ formatMoney(alerts.total_upcoming) }}</span>
                </div>
            </div>
            
            <!-- Łączna kwota -->
            <div class="bg-slate-800 rounded-xl p-3 mb-4 border border-slate-700">
                <div class="flex justify-between items-center">
                    <span class="text-sm text-slate-400">Łącznie do zapłaty:</span>
                    <span class="text-xl font-bold text-white">{{ formatMoney(totalAmount) }}</span>
                </div>
            </div>
            
            <!-- Przyciski akcji -->
            <div class="space-y-2">
                <button 
                    v-if="hasOverdue || hasUrgent"
                    @click="addAllToPlanned" 
                    class="w-full bg-green-600 hover:bg-green-500 text-white font-bold py-3 rounded-xl transition-colors">
                    Dodaj pilne do planowanych
                </button>
                
                <div class="flex gap-2">
                    <button 
                        @click="dismissUntilTomorrow" 
                        class="flex-1 bg-slate-700 hover:bg-slate-600 text-slate-300 font-bold py-3 rounded-xl text-sm transition-colors">
                        Przypomnij jutro
                    </button>
                    <button 
                        @click="$emit('close')" 
                        class="flex-1 bg-blue-600 hover:bg-blue-500 text-white font-bold py-3 rounded-xl text-sm transition-colors">
                        OK, rozumiem
                    </button>
                </div>
            </div>
            
        </div>
    </div>
    `
}
