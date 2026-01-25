document.addEventListener('DOMContentLoaded', () => {
    const refreshBtn = document.getElementById('refresh-btn');
    const lastUpdatedEl = document.getElementById('last-updated');
    
    // Initial load
    fetchStats();

    // Auto refresh every 5 seconds
    let autoRefresh = setInterval(fetchStats, 5000);

    // Manual refresh
    refreshBtn.addEventListener('click', () => {
        refreshBtn.classList.add('loading');
        fetchStats().finally(() => {
            setTimeout(() => {
                refreshBtn.classList.remove('loading');
            }, 500);
        });
        
        // Reset interval on manual refresh
        clearInterval(autoRefresh);
        autoRefresh = setInterval(fetchStats, 5000);
    });

    async function fetchStats() {
        try {
            const response = await fetch('/api/stats');
            if (!response.ok) throw new Error('Network response was not ok');
            const data = await response.json();
            
            updateUI(data);
            updateLastRefreshed();
        } catch (error) {
            console.error('Failed to fetch stats:', error);
        }
    }

    function updateUI(data) {
        // Calculate total calls
        const totalCalls = data.tool_stats.reduce((sum, [_, count]) => sum + count, 0);
        document.getElementById('total-count').textContent = totalCalls;
        document.getElementById('tools-count').textContent = data.tool_stats.length;

        // Update Tool Stats Grid
        const statsContainer = document.getElementById('stats-container');
        statsContainer.innerHTML = data.tool_stats.map(([tool, count]) => `
            <div class="tool-stat-item">
                <h4>${tool}</h4>
                <div class="count">${count}</div>
            </div>
        `).join('');

        // Update Logs Table
        const logsBody = document.querySelector('#logs-table tbody');
        logsBody.innerHTML = data.recent_logs.map(([tool, time]) => `
            <tr>
                <td><strong>${tool}</strong></td>
                <td>${formatDate(time)}</td>
                <td><span class="status-badge">Success</span></td>
            </tr>
        `).join('');
    }

    function updateLastRefreshed() {
        const now = new Date();
        lastUpdatedEl.textContent = `最后更新: ${now.toLocaleTimeString()}`;
    }

    function formatDate(isoString) {
        const date = new Date(isoString);
        return new Intl.DateTimeFormat('zh-CN', {
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit'
        }).format(date);
    }
});