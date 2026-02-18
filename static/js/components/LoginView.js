export default {
    data() { return { username: '', password: '', error: '' } },
    emits: ['login'],
    template: `
    <div class="h-screen flex flex-col items-center justify-center p-6 z-50 relative">
        <div class="w-full max-w-sm glass-panel p-8 rounded-3xl shadow-2xl border-t border-white/10">
            <div class="text-center mb-8"><div class="w-16 h-16 bg-blue-600 rounded-2xl mx-auto flex items-center justify-center text-3xl shadow-lg shadow-blue-500/30 mb-4">🔐</div><h1 class="text-2xl font-bold text-white">Witaj z powrotem</h1></div>
            <form @submit.prevent="$emit('login', username, password)" class="space-y-4">
                <input v-model="username" type="text" class="w-full input-dark p-3 rounded-xl" placeholder="Login">
                <input v-model="password" type="password" class="w-full input-dark p-3 rounded-xl" placeholder="Hasło">
                <button type="submit" class="w-full bg-blue-600 hover:bg-blue-500 text-white font-bold py-3.5 rounded-xl shadow-lg mt-4">Zaloguj się</button>
            </form>
        </div>
    </div>`
}
