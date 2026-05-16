function startScraper() {
    const btn = document.getElementById('scraper-btn');
    const container = document.getElementById('progress-container');
    const progressBar = document.getElementById('progress-bar');
    const progressText = document.getElementById('progress-text');
    const progressPercent = document.getElementById('progress-percent');
    
    btn.disabled = true;
    btn.textContent = 'Scraping in background...';
    container.style.display = 'block';
    
    fetch('/scrape', { method: 'POST' })
        .then(response => response.json())
        .then(data => {
            if(data.success || data.message === "Scraper is already running") {
                pollProgress();
            } else {
                alert(data.message);
                btn.disabled = false;
                btn.textContent = '🚀 Run Live Scraper';
            }
        })
        .catch(err => {
            alert('Error starting scraper.');
            btn.disabled = false;
            btn.textContent = '🚀 Run Live Scraper';
        });
        
    function pollProgress() {
        const interval = setInterval(() => {
            fetch('/scrape_status')
                .then(response => response.json())
                .then(status => {
                    if (status.total > 0) {
                        const percent = Math.round((status.progress / status.total) * 100);
                        progressBar.style.width = percent + '%';
                        progressPercent.textContent = percent + '%';
                    }
                    progressText.textContent = status.message;
                    
                    if (!status.is_running && status.total > 0 && status.progress === status.total) {
                        clearInterval(interval);
                        progressBar.style.width = '100%';
                        progressPercent.textContent = '100%';
                        setTimeout(() => {
                            window.location.reload();
                        }, 3000);
                    }
                });
        }, 1000);
    }
}
