import * as Utils from '../utils.js';
export default {
    props: ['importData', 'categories'],
    emits: ['close', 'submit'],
    setup() { return { ...Utils }; },
    template: `
    <div class="fixed inset-0 z-[80] bg-black/90 backdrop-blur-sm flex flex-col p-4 animate-fade-in">
        <div class="flex justify-between items-center mb-4 shrink-0"><h2 class="text-xl font-bold text-white">Weryfikacja Importu</h2><div class="flex gap-2"><button @click="$emit('close')" class="px-4 py-2 rounded-xl bg-slate-800 text-slate-400 font-bold text-sm">Anuluj</button><button @click="$emit('submit')" class="px-4 py-2 rounded-xl bg-green-600 text-white font-bold text-sm shadow-lg shadow-green-900/20">Zatwierdź ({{ importData.filter(t => !t.ignore).length }})</button></div></div>
        <div class="flex-1 overflow-y-auto bg-slate-900/50 rounded-2xl border border-slate-800">
            <table class="w-full text-left border-collapse">
                <thead class="bg-slate-800 text-xs text-slate-400 uppercase sticky top-0 z-10"><tr><th class="p-3 w-10 text-center">Import?</th><th class="p-3">Data</th><th class="p-3">Opis</th><th class="p-3 text-right">Kwota</th><th class="p-3">Kategoria</th></tr></thead>
                <tbody class="text-sm"><tr v-for="(tx, idx) in importData" :key="idx" class="border-b border-slate-800 hover:bg-white/5 transition-colors" :class="{'opacity-40': tx.ignore}"><td class="p-3 text-center"><input type="checkbox" v-model="tx.ignore" :true-value="false" :false-value="true" class="w-4 h-4 rounded bg-slate-700 border-slate-600"></td><td class="p-3 text-slate-300 whitespace-nowrap">{{ formatDateShort(tx.date) }}</td><td class="p-3"><input v-model="tx.description" type="text" class="bg-slate-800 text-white text-xs p-2 rounded-lg border border-slate-700 outline-none w-full min-w-[200px]"></td><td class="p-3 text-right font-bold whitespace-nowrap" :class="tx.type === 'income' ? 'text-green-400' : 'text-red-400'">{{ tx.type === 'income' ? '+' : '-' }}{{ formatMoney(tx.amount) }}</td><td class="p-3"><select v-model="tx.category_id" class="bg-slate-800 text-white text-xs p-2 rounded-lg border border-slate-700 outline-none w-full max-w-[150px]"><option :value="null" class="text-slate-500">-- Bez kategorii --</option><option v-for="cat in categories" :value="cat.id">{{ cat.name }}</option></select></td></tr></tbody>
            </table>
        </div>
    </div>`
}
