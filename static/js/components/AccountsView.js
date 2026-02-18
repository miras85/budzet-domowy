import * as Utils from '../utils.js';
export default {
    props: ['accounts'],
    emits: ['create-account', 'edit-account', 'delete-account', 'trigger-import'],
    setup() { return { ...Utils }; },
    template: `
    <div class="px-6">
        <div class="flex justify-between items-center mb-6 mt-4"><h2 class="text-xl font-bold text-white">Moje konta</h2><button @click="$emit('create-account')" class="text-blue-400 text-sm font-bold">+ Dodaj</button></div>
        <div class="grid gap-4"><div v-for="acc in accounts" :key="acc.id" class="glass-panel p-5 rounded-2xl border-l-4" :class="acc.is_savings ? 'border-purple-500' : 'border-blue-500'"><div class="flex justify-between items-center"><div><div class="text-xs text-slate-400 uppercase">{{ acc.type }} <span v-if="acc.is_savings" class="text-purple-400 font-bold">(Oszcz.)</span></div><div class="font-bold text-lg text-white">{{ acc.name }}</div><div class="text-xl font-bold text-blue-400 mt-1">{{ formatMoney(acc.balance) }}</div></div><div class="flex gap-2"><button @click="$emit('trigger-import', acc.id)" class="p-2 bg-slate-800 rounded-lg text-slate-400 hover:text-yellow-400 transition-colors" title="Importuj CSV">📥</button><button @click="$emit('edit-account', acc)" class="p-2 bg-slate-800 rounded-lg text-slate-400 hover:text-blue-400 transition-colors">✏️</button><button @click="$emit('delete-account', acc.id)" class="p-2 bg-slate-800 rounded-lg text-slate-400 hover:text-red-500 transition-colors">🗑️</button></div></div></div></div>
    </div>`
}
