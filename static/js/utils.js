export function formatMoney(value) {
    return (parseFloat(value) || 0).toLocaleString('pl-PL', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + ' zł';
}

export function formatDateShort(dateStr) {
    if(!dateStr) return '';
    const d = new Date(dateStr);
    return d.toLocaleDateString('pl-PL', { day: 'numeric', month: 'short' });
}

export function getIcon(type) {
    return type === 'income' ? '💰' : (type === 'transfer' ? '↔️' : '🛒');
}

export function getIconClass(type) {
    return type === 'income' ? 'bg-green-500/10 text-green-400' : (type === 'transfer' ? 'bg-blue-500/10 text-blue-400' : 'bg-red-500/10 text-red-400');
}

export function getColorClass(type) {
    return type === 'income' ? 'text-green-400' : (type === 'transfer' ? 'text-blue-400' : 'text-slate-200');
}

export function calculateProgress(loan) {
    if(loan.total <= 0) return 0;
    return ((loan.total - loan.remaining) / loan.total) * 100;
}
