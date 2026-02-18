import { ICON_PATHS, COLORS } from '../icons.js?v=20';

export default {
    props: ['categories', 'overrides', 'newCategoryName', 'newOverride', 'security'],
    emits: ['update:newCategoryName', 'add-category', 'update-category', 'delete-category', 'add-override', 'delete-override', 'change-password', 'register-user'],
    data() {
        return {
            iconPaths: ICON_PATHS,
            colors: COLORS,
            formCat: { id: null, name: '', icon: 'tag', color: '#94a3b8' },
            showIconPicker: false
        }
    },
    methods: {
        handleSubmit() {
            if(!this.formCat.name) return;
            if (this.formCat.id) {
                this.$emit('update-category', {
                    id: this.formCat.id,
                    name: this.formCat.name,
                    icon_name: this.formCat.icon,
                    color: this.formCat.color,
                    limit: 0
                });
            } else {
                this.$emit('add-category', {
                    name: this.formCat.name,
                    icon: this.formCat.icon,
                    color: this.formCat.color
                });
            }
            this.resetForm();
        },
        editCategory(cat) {
            this.formCat = {
                id: cat.id,
                name: cat.name,
                icon: cat.icon_name || 'tag',
                color: cat.color || '#94a3b8'
            };
            this.showIconPicker = true;
            window.scrollTo({ top: 0, behavior: 'smooth' });
        },
        resetForm() {
            this.formCat = { id: null, name: '', icon: 'tag', color: '#94a3b8' };
            this.showIconPicker = false;
        }
    },
    template: `
    <div class="px-6">
        <h2 class="text-xl font-bold text-white mb-6 mt-4">Ustawienia</h2>
        
        <div class="glass-panel p-5 rounded-2xl mb-6">
            <h3 class="font-bold text-slate-200 mb-4">Kategorie</h3>
            <p class="text-xs text-slate-400 mb-2">Kliknij kategorię poniżej, aby ją edytować.</p>
            
            <div class="bg-slate-800/50 p-3 rounded-xl border border-slate-700 mb-4 transition-all" :class="formCat.id ? 'border-blue-500 ring-1 ring-blue-500/50' : ''">
                <div class="flex gap-2 mb-3">
                    <button @click="showIconPicker = !showIconPicker" class="w-12 h-12 rounded-xl flex items-center justify-center border border-slate-600 transition-all" :style="{ backgroundColor: formCat.color + '20', borderColor: formCat.color }">
                        <svg viewBox="0 0 256 256" fill="none" stroke="currentColor" stroke-width="16" class="w-6 h-6" :style="{ color: formCat.color }">
                            <path :d="iconPaths[formCat.icon]" stroke-linecap="round" stroke-linejoin="round"/>
                        </svg>
                    </button>
                    <input v-model="formCat.name" type="text" :placeholder="formCat.id ? 'Edytuj nazwę' : 'Nowa kategoria'" class="input-dark flex-1 p-2 rounded-xl text-sm">
                    <button @click="handleSubmit" class="w-12 rounded-xl font-bold text-xl shadow-lg transition-colors flex items-center justify-center" :class="formCat.id ? 'bg-green-600 text-white' : 'bg-blue-600 text-white'">{{ formCat.id ? '✓' : '+' }}</button>
                    <button v-if="formCat.id" @click="resetForm" class="w-12 rounded-xl font-bold text-xl bg-slate-700 text-slate-400">✕</button>
                </div>

                <div v-if="showIconPicker" class="animate-fade-in border-t border-slate-700 pt-3">
                    <div class="text-[10px] text-slate-400 uppercase font-bold mb-2">Wybierz kolor</div>
                    <div class="flex flex-wrap gap-2 mb-4">
                        <div v-for="c in colors" :key="c" @click="formCat.color = c" class="w-6 h-6 rounded-full cursor-pointer border-2 transition-transform active:scale-90" :class="formCat.color === c ? 'border-white' : 'border-transparent'" :style="{ backgroundColor: c }"></div>
                    </div>
                    <div class="text-[10px] text-slate-400 uppercase font-bold mb-2">Wybierz ikonę</div>
                    <div class="grid grid-cols-6 gap-2 max-h-60 overflow-y-auto pr-1">
                        <div v-for="(path, name) in iconPaths" :key="name" @click="formCat.icon = name" class="aspect-square rounded-lg flex items-center justify-center cursor-pointer hover:bg-white/5 transition-colors" :class="formCat.icon === name ? 'bg-white/10 ring-1 ring-white/30' : ''">
                            <svg viewBox="0 0 256 256" fill="none" stroke="currentColor" stroke-width="16" class="w-5 h-5 text-slate-300">
                                <path :d="path" stroke-linecap="round" stroke-linejoin="round"/>
                            </svg>
                        </div>
                    </div>
                </div>
            </div>

            <div class="flex flex-wrap gap-2">
                <div v-for="cat in categories" :key="cat.id" @click="editCategory(cat)" class="pl-2 pr-2 py-1.5 rounded-xl text-xs font-bold flex items-center gap-2 border transition-all cursor-pointer active:scale-95 hover:brightness-110" :class="formCat.id === cat.id ? 'ring-2 ring-white' : ''" :style="{ backgroundColor: (cat.color || '#64748b') + '15', borderColor: (cat.color || '#64748b') + '30', color: (cat.color || '#64748b') }">
                    <svg viewBox="0 0 256 256" fill="none" stroke="currentColor" stroke-width="16" class="w-4 h-4">
                        <path :d="iconPaths[cat.icon_name || 'tag'] || iconPaths['tag']" stroke-linecap="round" stroke-linejoin="round"/>
                    </svg>
                    {{ cat.name }}
                    <button @click.stop="$emit('delete-category', cat.id)" class="hover:text-white ml-1 p-1 rounded-full hover:bg-black/20">×</button>
                </div>
            </div>
        </div>

        <div class="glass-panel p-5 rounded-2xl mb-6"><h3 class="font-bold text-slate-200 mb-4">Wyjątki Dnia Wypłaty</h3><div class="flex gap-2 mb-4"><input v-model="newOverride.year" type="number" placeholder="Rok" class="input-dark w-20 p-2 rounded-lg text-center"><select v-model="newOverride.month" class="input-dark flex-1 p-2 rounded-lg"><option v-for="m in 12" :value="m">{{ m }}</option></select><input v-model="newOverride.day" type="number" placeholder="Dzień" class="input-dark w-16 p-2 rounded-lg text-center"><button @click="$emit('add-override')" class="bg-blue-600 text-white px-4 rounded-lg font-bold">+</button></div><div class="space-y-2"><div v-for="ov in overrides" :key="ov.id" class="flex justify-between items-center bg-slate-800 p-3 rounded-lg"><div class="text-sm text-slate-200"><span class="font-bold">{{ ov.year }}-{{ String(ov.month).padStart(2, '0') }}</span>: Wypłata {{ ov.day }}-go</div><button @click="$emit('delete-override', ov.id)" class="text-red-400 text-xs font-bold">USUŃ</button></div></div></div>
        <div class="glass-panel p-5 rounded-2xl mb-6 border-l-4 border-blue-500"><h3 class="font-bold text-slate-200 mb-4">Bezpieczeństwo</h3><div class="mb-6"><h4 class="text-xs text-slate-400 uppercase font-bold mb-2">Zmień swoje hasło</h4><div class="space-y-2"><input v-model="security.oldPassword" type="password" placeholder="Stare hasło" class="input-dark w-full p-2 rounded-lg text-sm"><input v-model="security.newPassword" type="password" placeholder="Nowe hasło" class="input-dark w-full p-2 rounded-lg text-sm"><button @click="$emit('change-password')" class="w-full bg-slate-700 hover:bg-blue-600 text-white py-2 rounded-lg text-xs font-bold transition-colors">Zatwierdź zmianę</button></div></div><div><h4 class="text-xs text-slate-400 uppercase font-bold mb-2">Dodaj domownika</h4><div class="flex gap-2 mb-2"><input v-model="security.newUsername" type="text" placeholder="Login (np. zona)" class="input-dark flex-1 p-2 rounded-lg text-sm"><input v-model="security.newUserPass" type="password" placeholder="Hasło" class="input-dark flex-1 p-2 rounded-lg text-sm"></div><button @click="$emit('register-user')" class="w-full bg-slate-700 hover:bg-green-600 text-white py-2 rounded-lg text-xs font-bold transition-colors">+ Utwórz konto</button></div></div>
    </div>`
}
