// Floating Toast System
function showToast(message, type = 'info') {
    let container = document.getElementById('toast-container');
    if (!container) {
        container = document.createElement('div');
        container.id = 'toast-container';
        container.className = 'toast-container';
        document.body.appendChild(container);
    }
    
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    
    let icon = 'ℹ️';
    if (type === 'success') icon = '✅';
    else if (type === 'warning') icon = '⚠️';
    else if (type === 'error') icon = '❌';
    
    toast.innerHTML = `<span>${icon}</span><span>${message}</span>`;
    container.appendChild(toast);
    
    // Slide in
    setTimeout(() => toast.classList.add('active'), 50);
    
    // Slide out and remove
    setTimeout(() => {
        toast.classList.remove('active');
        setTimeout(() => toast.remove(), 400);
    }, 4000);
}

// 🔗 Smart Link Validator Interceptor
document.addEventListener('DOMContentLoaded', () => {
    document.addEventListener('click', (e) => {
        const btn = e.target.closest('.view-course-btn');
        if (!btn) return;
        
        e.preventDefault();
        const card = btn.closest('.course-card');
        if (!card) {
            window.open(btn.href, '_blank');
            return;
        }
        
        const url = card.getAttribute('data-url');
        const title = card.getAttribute('data-title');
        const provider = card.getAttribute('data-provider');
        
        const originalText = btn.innerHTML;
        btn.style.pointerEvents = 'none';
        btn.innerHTML = '🔍 Checking...';
        
        showToast("Verifying course URL...", "info");
        
        fetch(`/validate_link?url=${encodeURIComponent(url)}&title=${encodeURIComponent(title)}&provider=${encodeURIComponent(provider)}`)
            .then(res => res.json())
            .then(data => {
                btn.style.pointerEvents = 'auto';
                btn.innerHTML = originalText;
                
                if (data.valid) {
                    window.open(url, '_blank');
                } else {
                    showToast("Original course link archived by provider! Loading fallback search...", "warning");
                    setTimeout(() => {
                        window.open(data.fallback_url, '_blank');
                    }, 800);
                }
            })
            .catch(() => {
                btn.style.pointerEvents = 'auto';
                btn.innerHTML = originalText;
                // Fallback in case of server error
                let fallback = `https://www.coursera.org/search?query=${encodeURIComponent(title)}`;
                if (provider.toLowerCase() === 'udemy') {
                    fallback = `https://www.udemy.com/courses/search/?q=${encodeURIComponent(title)}`;
                } else if (provider.toLowerCase() === 'edx') {
                    fallback = `https://www.edx.org/search?q=${encodeURIComponent(title)}`;
                }
                window.open(fallback, '_blank');
            });
    });
});

// ⚖️ Course Comparison Engine
let comparedCourses = [];

function handleCompareChange(checkbox) {
    const card = checkbox.closest('.course-card');
    if (!card) return;
    
    const title = card.getAttribute('data-title') || '';
    const provider = card.getAttribute('data-provider') || '';
    const stars = card.getAttribute('data-stars') || '0.0';
    const ratingsCount = card.getAttribute('data-ratings-count') || '0';
    const url = card.getAttribute('data-url') || '';
    const desc = card.getAttribute('data-desc') || '';
    
    if (checkbox.checked) {
        if (comparedCourses.length >= 3) {
            checkbox.checked = false;
            showToast("You can compare a maximum of 3 courses at once.", "warning");
            return;
        }
        comparedCourses.push({ title, provider, stars, ratingsCount, url, desc });
        showToast(`Added "${title.substring(0, 25)}..." to compare queue`, "success");
    } else {
        comparedCourses = comparedCourses.filter(c => c.title !== title);
        showToast(`Removed "${title.substring(0, 25)}..." from compare queue`, "info");
    }
    
    updateCompareBar();
}

function updateCompareBar() {
    const bar = document.getElementById('compare-bar');
    const countSpan = document.getElementById('compare-count');
    
    if (countSpan) countSpan.textContent = comparedCourses.length;
    if (bar) {
        if (comparedCourses.length > 0) {
            bar.classList.add('active');
        } else {
            bar.classList.remove('active');
        }
    }
}

function clearCompareSelection() {
    comparedCourses = [];
    document.querySelectorAll('.compare-check').forEach(chk => chk.checked = false);
    updateCompareBar();
    showToast("Comparison queue cleared.", "info");
}

function launchCompareModal() {
    if (comparedCourses.length === 0) return;
    
    const grid = document.getElementById('compare-grid');
    grid.innerHTML = '';
    
    comparedCourses.forEach(course => {
        const tText = course.title.toLowerCase();
        const dText = course.desc.toLowerCase();
        const fullText = `${tText} ${dText}`;
        
        let difficulty = "Intermediate 🟡";
        if (fullText.includes("beginner") || 
            fullText.includes("introduction") || 
            fullText.includes("intro") || 
            fullText.includes("basic") || 
            fullText.includes("fundamental") || 
            fullText.includes("foundation") || 
            fullText.includes("101")) {
            difficulty = "Beginner friendly 🟢";
        } else if (fullText.includes("advanced") || 
                   fullText.includes("expert") || 
                   fullText.includes("deep dive") || 
                   fullText.includes("senior") || 
                   fullText.includes("mastery")) {
            difficulty = "Advanced / Expert 🔴";
        }

        const col = document.createElement('div');
        col.className = 'compare-column';
        
        const starsNum = parseFloat(course.stars);
        const starsInt = Math.min(Math.max(Math.round(starsNum), 1), 5);
        let starsStr = '';
        for (let i = 0; i < starsInt; i++) starsStr += '⭐';
        
        const reviewsStr = parseInt(course.ratingsCount) > 0 
            ? `(${parseInt(course.ratingsCount).toLocaleString()} reviews)`
            : '(No reviews)';
        
        col.innerHTML = `
            <div>
                <span class="compare-feature-label">Platform</span>
                <div style="font-weight:800; font-size:1.2rem; color:var(--secondary); margin-top:0.25rem;">${course.provider}</div>
            </div>
            <div>
                <span class="compare-feature-label">Course Title</span>
                <div style="font-weight:700; font-size:1.15rem; margin-top:0.25rem; color:var(--text-main); line-height:1.4;">${course.title}</div>
            </div>
            <div>
                <span class="compare-feature-label">Estimated Difficulty</span>
                <div style="font-weight:600; font-size:0.95rem; margin-top:0.25rem;">${difficulty}</div>
            </div>
            <div>
                <span class="compare-feature-label">AI Quality Rating</span>
                <div style="color:#FBBF24; display:flex; align-items:center; gap:0.25rem; font-weight:700; margin-top:0.25rem;">
                    ${starsStr} <span style="color:var(--primary); font-size:0.95rem; margin-left:0.15rem;">${starsNum.toFixed(1)}</span>
                </div>
                <div style="color:var(--text-muted); font-size:0.8rem; margin-top:0.15rem;">${reviewsStr}</div>
            </div>
            <div style="flex-grow:1;">
                <span class="compare-feature-label">Syllabus Snapshot</span>
                <p style="font-size:0.85rem; color:var(--text-muted); margin-top:0.25rem; line-height:1.5;">${course.desc}...</p>
            </div>
            <div style="margin-top:1.5rem;" class="compare-card-btn-container" 
                 data-url="${course.url}" data-title="${course.title}" data-provider="${course.provider}">
                <button class="btn btn-primary" onclick="validateCompareLink(this)" style="width:100%; text-decoration:none;">View Course ↗</button>
            </div>
        `;
        grid.appendChild(col);
    });
    
    const modal = document.getElementById('compare-modal');
    modal.style.display = 'flex';
    setTimeout(() => modal.classList.add('active'), 50);
}

function validateCompareLink(btn) {
    const container = btn.closest('.compare-card-btn-container');
    const url = container.getAttribute('data-url');
    const title = container.getAttribute('data-title');
    const provider = container.getAttribute('data-provider');
    
    const originalText = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = '🔍 Checking...';
    
    showToast("Validating course URL...", "info");
    
    fetch(`/validate_link?url=${encodeURIComponent(url)}&title=${encodeURIComponent(title)}&provider=${encodeURIComponent(provider)}`)
        .then(res => res.json())
        .then(data => {
            btn.disabled = false;
            btn.innerHTML = originalText;
            
            if (data.valid) {
                window.open(url, '_blank');
            } else {
                showToast("Original course link archived! Loading search fallback...", "warning");
                setTimeout(() => window.open(data.fallback_url, '_blank'), 800);
            }
        })
        .catch(() => {
            btn.disabled = false;
            btn.innerHTML = originalText;
            let fallback = `https://www.coursera.org/search?query=${encodeURIComponent(title)}`;
            if (provider.toLowerCase() === 'udemy') {
                fallback = `https://www.udemy.com/courses/search/?q=${encodeURIComponent(title)}`;
            } else if (provider.toLowerCase() === 'edx') {
                fallback = `https://www.edx.org/search?q=${encodeURIComponent(title)}`;
            }
            window.open(fallback, '_blank');
        });
}

function closeCompareModal() {
    const modal = document.getElementById('compare-modal');
    modal.classList.remove('active');
    setTimeout(() => modal.style.display = 'none', 400);
}

// 📊 D3.js Force-Directed Skill Map
let isGraphInitialized = false;

function initSkillMapGraph() {
    if (isGraphInitialized) return;
    
    const svg = d3.select("#map-svg");
    const container = document.querySelector(".map-container");
    if (!container) return;
    
    const width = container.clientWidth || 960;
    const height = 650;
    
    // Create floating tooltip element in body if missing
    let tooltip = d3.select(".graph-tooltip");
    if (tooltip.empty()) {
        tooltip = d3.select("body").append("div")
            .attr("class", "graph-tooltip")
            .style("opacity", 0);
    }
        
    const sidebarDetails = document.getElementById('sidebar-details');
    const sidebarInstruction = document.getElementById('sidebar-instruction');
    const sidebarTitle = document.getElementById('sidebar-title');
    const sidebarProvider = document.getElementById('sidebar-provider');
    const sidebarRating = document.getElementById('sidebar-rating');
    const sidebarLink = document.getElementById('sidebar-link');
    
    showToast("Mapping skill connections...", "info");
    
    fetch('/graph_data')
        .then(res => res.json())
        .then(data => {
            if (!data.nodes || data.nodes.length === 0) {
                showToast("Failed to load skill map data.", "error");
                return;
            }
            
            isGraphInitialized = true;
            
            // Cluster color scheme
            const currentTheme = document.documentElement.getAttribute('data-theme') || 'dark';
            const colorScale = d3.scaleOrdinal()
                .domain(["AI & Data Science", "Web Development", "Cybersecurity", "Software Engineering", "General CS"])
                .range(currentTheme === 'dark' 
                    ? ["#3282B8", "#BBE1FA", "#94A3B8", "#0F4C75", "#5F85A2"]
                    : ["#0F4C75", "#3282B8", "#5F85A2", "#1B262C", "#94A3B8"]
                );
                
            svg.selectAll("*").remove();
            
            const g = svg.append("g");
            
            // Zoom Support
            const zoomBehavior = d3.zoom()
                .scaleExtent([0.3, 3])
                .on("zoom", (event) => {
                    g.attr("transform", event.transform);
                });
            svg.call(zoomBehavior);
            
            // Setup simulation
            const simulation = d3.forceSimulation(data.nodes)
                .force("link", d3.forceLink(data.links).id(d => d.id).distance(110))
                .force("charge", d3.forceManyBody().strength(-150))
                .force("center", d3.forceCenter(width / 2, height / 2))
                .force("collision", d3.forceCollide().radius(35));
                
            // Draw links
            const link = g.append("g")
                .selectAll("line")
                .data(data.links)
                .join("line")
                .attr("stroke", currentTheme === 'dark' ? "rgba(255,255,255,0.06)" : "rgba(15,76,117,0.1)")
                .attr("stroke-width", d => Math.max(d.value * 3.5, 1.2));
                
            // Draw nodes
            const node = g.append("g")
                .selectAll("circle")
                .data(data.nodes)
                .join("circle")
                .attr("r", 10)
                .attr("fill", d => colorScale(d.group))
                .attr("stroke", currentTheme === 'dark' ? "rgba(255,255,255,0.2)" : "rgba(15,76,117,0.15)")
                .attr("stroke-width", 1.5)
                .style("cursor", "pointer")
                .call(d3.drag()
                    .on("start", dragstarted)
                    .on("drag", dragged)
                    .on("end", dragended)
                );
                
            // Node Interactions
            node.on("mouseover", (event, d) => {
                d3.select(event.currentTarget)
                    .transition().duration(200)
                    .attr("r", 14)
                    .attr("stroke", currentTheme === 'dark' ? "#FFF" : "var(--primary)");
                    
                tooltip.transition().duration(200).style("opacity", 0.95);
                tooltip.html(`
                    <strong style="color:var(--secondary); font-size:0.9rem;">${d.title}</strong><br/>
                    <span style="font-size:0.8rem; color:var(--text-muted);">Group: ${d.group}</span><br/>
                    <span style="font-size:0.8rem; color:#FBBF24;">⭐ ${d.stars.toFixed(1)} AI Score</span>
                `)
                .style("left", (event.pageX + 15) + "px")
                .style("top", (event.pageY - 28) + "px");
            })
            .on("mouseout", (event, d) => {
                d3.select(event.currentTarget)
                    .transition().duration(200)
                    .attr("r", 10)
                    .attr("stroke", currentTheme === 'dark' ? "rgba(255,255,255,0.2)" : "rgba(15,76,117,0.15)");
                    
                tooltip.transition().duration(200).style("opacity", 0);
            })
            .on("click", (event, d) => {
                // Focus camera on node
                event.stopPropagation();
                
                const neighbors = new Set();
                neighbors.add(d.id);
                
                data.links.forEach(l => {
                    if (l.source.id === d.id) neighbors.add(l.target.id);
                    if (l.target.id === d.id) neighbors.add(l.source.id);
                });
                
                node.transition().duration(300)
                    .attr("opacity", n => neighbors.has(n.id) ? 1.0 : 0.15)
                    .attr("r", n => n.id === d.id ? 15 : 10);
                    
                link.transition().duration(300)
                    .attr("stroke", l => (l.source.id === d.id || l.target.id === d.id) ? "var(--primary)" : (currentTheme === 'dark' ? "rgba(255,255,255,0.03)" : "rgba(15,76,117,0.03)"))
                    .attr("stroke-width", l => (l.source.id === d.id || l.target.id === d.id) ? 3.5 : 1.2);
                    
                // Update map sidebar Details
                if (sidebarInstruction) sidebarInstruction.style.display = 'none';
                if (sidebarDetails) sidebarDetails.style.display = 'block';
                if (sidebarTitle) sidebarTitle.textContent = d.title;
                if (sidebarProvider) sidebarProvider.textContent = d.provider;
                if (sidebarRating) sidebarRating.textContent = `⭐ ${d.stars.toFixed(1)} / 5.0`;
                if (sidebarLink) {
                    sidebarLink.href = d.url;
                    sidebarLink.onclick = (e) => {
                        e.preventDefault();
                        showToast("Validating course URL...", "info");
                        fetch(`/validate_link?url=${encodeURIComponent(d.url)}&title=${encodeURIComponent(d.title)}&provider=${encodeURIComponent(d.provider)}`)
                            .then(r => r.json())
                            .then(val => {
                                if (val.valid) {
                                    window.open(d.url, '_blank');
                                } else {
                                    showToast("Original course link archived! Opening fallback...", "warning");
                                    setTimeout(() => window.open(val.fallback_url, '_blank'), 800);
                                }
                            });
                    };
                }
            });
            
            // Double-click SVG background to reset filters
            svg.on("click", () => {
                node.transition().duration(300).attr("opacity", 1.0).attr("r", 10);
                link.transition().duration(300)
                    .attr("stroke", currentTheme === 'dark' ? "rgba(255,255,255,0.06)" : "rgba(15,76,117,0.1)")
                    .attr("stroke-width", l => Math.max(l.value * 3.5, 1.2));
                if (sidebarInstruction) sidebarInstruction.style.display = 'block';
                if (sidebarDetails) sidebarDetails.style.display = 'none';
            });
            
            simulation.on("tick", () => {
                link
                    .attr("x1", d => d.source.x)
                    .attr("y1", d => d.source.y)
                    .attr("x2", d => d.target.x)
                    .attr("y2", d => d.target.y);
                    
                node
                    .attr("cx", d => d.x)
                    .attr("cy", d => d.y);
            });
            
            function dragstarted(event, d) {
                if (!event.active) simulation.alphaTarget(0.3).restart();
                d.fx = d.x;
                d.fy = d.y;
            }
            
            function dragged(event, d) {
                d.fx = event.x;
                d.fy = event.y;
            }
            
            function dragended(event, d) {
                if (!event.active) simulation.alphaTarget(0);
                d.fx = null;
                d.fy = null;
            }
        });
}

// Scraper background trigger
function startScraper() {
    const btn = document.getElementById('scraper-btn');
    const container = document.getElementById('progress-container');
    const progressBar = document.getElementById('progress-bar');
    const progressText = document.getElementById('progress-text');
    const progressPercent = document.getElementById('progress-percent');
    
    if (btn) btn.disabled = true;
    if (btn) btn.textContent = 'Scraping in background...';
    if (container) container.style.display = 'block';
    
    fetch('/scrape', { method: 'POST' })
        .then(response => response.json())
        .then(data => {
            if(data.success || data.message === "Scraper is already running") {
                pollProgress();
            } else {
                alert(data.message);
                if (btn) btn.disabled = false;
                if (btn) btn.textContent = '🚀 Live Scraper';
            }
        })
        .catch(err => {
            alert('Error starting scraper.');
            if (btn) btn.disabled = false;
            if (btn) btn.textContent = '🚀 Live Scraper';
        });
        
    function pollProgress() {
        const interval = setInterval(() => {
            fetch('/scrape_status')
                .then(response => response.json())
                .then(status => {
                    if (status.total > 0) {
                        const percent = Math.round((status.progress / status.total) * 100);
                        if (progressBar) progressBar.style.width = percent + '%';
                        if (progressPercent) progressPercent.textContent = percent + '%';
                    }
                    if (progressText) progressText.textContent = status.message;
                    
                    if (!status.is_running && status.total > 0 && status.progress === status.total) {
                        clearInterval(interval);
                        if (progressBar) progressBar.style.width = '100%';
                        if (progressPercent) progressPercent.textContent = '100%';
                        setTimeout(() => {
                            window.location.reload();
                        }, 3000);
                    }
                });
        }, 1000);
    }
}

// AI Study Path Generator
function generateAIPath() {
    const input = document.getElementById('ai-goal-input');
    const btn = document.getElementById('ai-generate-btn');
    const loader = document.getElementById('ai-loader');
    const outputContainer = document.getElementById('ai-path-output');
    const pathContent = document.getElementById('ai-path-content');

    const goal = input ? input.value.trim() : "";
    if (!goal) {
        alert("Please enter a learning goal or career target (e.g., 'Learn Python' or 'Become a Data Scientist').");
        return;
    }

    if (btn) btn.disabled = true;
    if (btn) btn.textContent = "Designing...";
    if (loader) loader.style.display = "flex";
    if (outputContainer) outputContainer.style.display = "none";

    fetch('/generate_path', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ goal: goal })
    })
    .then(response => response.json())
    .then(data => {
        if (btn) btn.disabled = false;
        if (btn) btn.textContent = "Generate Plan";
        if (loader) loader.style.display = "none";

        if (data.success) {
            if (pathContent) pathContent.innerHTML = data.path_html;
            if (outputContainer) outputContainer.style.display = "block";

            // Make custom curriculum checks interactive
            const headers = pathContent.querySelectorAll('h3');
            headers.forEach((header) => {
                header.style.display = 'flex';
                header.style.alignItems = 'center';
                header.style.gap = '0.75rem';
                header.style.cursor = 'pointer';
                
                const checkbox = document.createElement('span');
                checkbox.className = 'path-checkbox';
                checkbox.innerHTML = '⚪';
                checkbox.style.transition = 'all 0.2s';
                header.prepend(checkbox);

                header.addEventListener('click', () => {
                    if (checkbox.innerHTML === '⚪') {
                        checkbox.innerHTML = '✅';
                        header.style.textDecoration = 'line-through';
                        header.style.opacity = '0.5';
                    } else {
                        checkbox.innerHTML = '⚪';
                        header.style.textDecoration = 'none';
                        header.style.opacity = '1';
                    }
                });
            });

            if (outputContainer) outputContainer.scrollIntoView({ behavior: 'smooth', block: 'start' });
        } else {
            alert(data.error || "An error occurred while generating your learning path.");
        }
    })
    .catch(err => {
        if (btn) btn.disabled = false;
        if (btn) btn.textContent = "Generate Plan";
        if (loader) loader.style.display = "none";
        alert("Failed to reach server or make API call. Make sure you set your GEMINI_API_KEY in the .env file.");
    });
}

// Tab switcher
function switchTab(tabId) {
    document.querySelectorAll('.tab-pane').forEach(pane => {
        pane.classList.remove('active');
    });
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.remove('active');
    });

    const activePane = document.getElementById(`tab-pane-${tabId}`);
    const activeBtn = document.getElementById(`tab-btn-${tabId}`);
    
    if (activePane) activePane.classList.add('active');
    if (activeBtn) activeBtn.classList.add('active');

    localStorage.setItem('activeDashboardTab', tabId);
    
    if (tabId === 'skill-map') {
        setTimeout(initSkillMapGraph, 100);
    }
}

// 🌓 Nordic Light/Dark Theme Switcher
function initTheme() {
    const savedTheme = localStorage.getItem('nordicTheme') || 'dark';
    document.documentElement.setAttribute('data-theme', savedTheme);
    updateThemeToggleButton(savedTheme);
}

function toggleTheme() {
    const currentTheme = document.documentElement.getAttribute('data-theme') || 'dark';
    const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
    
    document.documentElement.setAttribute('data-theme', newTheme);
    localStorage.setItem('nordicTheme', newTheme);
    updateThemeToggleButton(newTheme);
    
    showToast(`Switched to Nordic ${newTheme === 'dark' ? 'Dark' : 'Light'} Mode`, "success");
    
    // Redraw graph if currently active
    const activeTab = localStorage.getItem('activeDashboardTab') || 'catalog';
    if (activeTab === 'skill-map' && isGraphInitialized) {
        isGraphInitialized = false;
        initSkillMapGraph();
    }
}

function updateThemeToggleButton(theme) {
    const btn = document.getElementById('theme-toggle-btn');
    if (btn) {
        btn.innerHTML = theme === 'dark' ? '☀️' : '🌙';
        btn.setAttribute('title', `Switch to Nordic ${theme === 'dark' ? 'Light' : 'Dark'} Mode`);
    }
}

// Restore Tab state and Theme state
document.addEventListener('DOMContentLoaded', () => {
    initTheme();
    const activeTab = localStorage.getItem('activeDashboardTab') || 'catalog';
    switchTab(activeTab);
});
