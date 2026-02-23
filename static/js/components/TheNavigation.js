export default {
    props: ['currentTab', 'loanAlertsCount'],
    emits: ['update:currentTab', 'open-add'],
    template: `
    <div class="fixed bottom-0 left-0 right-0 glass-panel border-t border-slate-800 pb-safe safe-bottom z-50 h-16">
        <div class="nav-container">
            <div class="nav-group">
                <div @click="$emit('update:currentTab', 'dashboard')" :class="{active: currentTab === 'dashboard'}" class="nav-item"><svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-6 h-6 nav-icon"><path stroke-linecap="round" stroke-linejoin="round" d="M2.25 12l8.954-8.955c.44-.439 1.152-.439 1.591 0L21.75 12M4.5 9.75v10.125c0 .621.504 1.125 1.125 1.125H9.75v-4.875c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125V21h4.125c.621 0 1.125-.504 1.125-1.125V9.75M8.25 21h8.25" /></svg><span class="nav-label">Pulpit</span></div>
                <div @click="$emit('update:currentTab', 'accounts')" :class="{active: currentTab === 'accounts'}" class="nav-item"><svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-6 h-6 nav-icon"><path stroke-linecap="round" stroke-linejoin="round" d="M2.25 8.25h19.5M2.25 9h19.5m-16.5 5.25h6m-6 2.25h3m-3.75 3h15a2.25 2.25 0 002.25-2.25V6.75A2.25 2.25 0 0019.5 4.5H4.5a2.25 2.25 0 00-2.25 2.25v10.5a2.25 2.25 0 002.25 2.25z" /></svg><span class="nav-label">Konta</span></div>
            </div>
            <div class="fab-container"><button @click="$emit('open-add')" class="fab-btn group"><svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" class="w-8 h-8 group-active:rotate-90 transition-transform duration-200"><path stroke-linecap="round" stroke-linejoin="round" d="M12 4.5v15m7.5-7.5h-15" /></svg></button></div>
            <div class="nav-group">
                <div @click="$emit('update:currentTab', 'goals')" :class="{active: currentTab === 'goals'}" class="nav-item"><svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-6 h-6 nav-icon"><path stroke-linecap="round" stroke-linejoin="round" d="M3 3v1.5M3 21v-6m0 0l2.77-.693a9 9 0 016.208.682l.108.054a9 9 0 006.086.71l3.114-.732a48.524 48.524 0 01-.005-10.499l-3.11.732a9 9 0 01-6.085-.711l-.108-.054a9 9 0 00-6.208-.682L3 4.5M3 15V4.5" /></svg><span class="nav-label">Cele</span></div>
                <div @click="$emit('update:currentTab', 'payments')" :class="{active: currentTab === 'payments'}" class="nav-item relative">
                    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-6 h-6 nav-icon">
                        <path stroke-linecap="round" stroke-linejoin="round" d="M12 6v12m-3-2.818l.879.659c1.171.879 3.07.879 4.242 0 1.172-.879 1.172-2.303 0-3.182C13.536 12.219 12.768 12 12 12c-.725 0-1.45-.22-2.003-.659-1.106-.879-1.106-2.303 0-3.182s2.9-.879 4.006 0l.415.33M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    <span class="nav-label">Płatności</span>
                    
                    <!-- Badge (NOWY) -->
                    <span 
                        v-if="loanAlertsCount > 0" 
                        class="absolute -top-1 -right-1 bg-red-500 text-white text-[10px] font-bold rounded-full w-5 h-5 flex items-center justify-center shadow-lg shadow-red-500/50 animate-pulse">
                        {{ loanAlertsCount }}
                    </span>
                </div>
            </div>
        </div>
    </div>`
}
