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
    
    let icon = '<i data-lucide="info" style="width:16px;height:16px;display:inline-block;vertical-align:middle;"></i>';
    if (type === 'success') icon = '<i data-lucide="check-circle" style="width:16px;height:16px;display:inline-block;vertical-align:middle;"></i>';
    else if (type === 'warning') icon = '<i data-lucide="alert-triangle" style="width:16px;height:16px;display:inline-block;vertical-align:middle;"></i>';
    else if (type === 'error') icon = '<i data-lucide="x-circle" style="width:16px;height:16px;display:inline-block;vertical-align:middle;"></i>';
    
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

// Smart Link Validator Interceptor
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
        btn.innerHTML = '<i data-lucide="search" style="width:16px;height:16px;display:inline-block;vertical-align:middle;"></i> Checking...';
        
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

// Course Comparison Engine
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

function addToCompare(course) {
    const exists = comparedCourses.some(c => c.title === course.title);
    if (exists) {
        showToast("This course is already in your comparison queue.", "info");
        return;
    }
    if (comparedCourses.length >= 3) {
        showToast("You can compare a maximum of 3 courses at once.", "warning");
        return;
    }
    comparedCourses.push({
        title: course.title,
        provider: course.provider,
        stars: String(course.stars),
        ratingsCount: String(course.ratings_count),
        url: course.url,
        desc: course.desc || ''
    });
    
    // Auto-check any matching checkboxes on the catalog page for visual sync
    document.querySelectorAll('.course-card').forEach(card => {
        if (card.getAttribute('data-title') === course.title) {
            const chk = card.querySelector('.compare-check');
            if (chk) chk.checked = true;
        }
    });
    
    updateCompareBar();
}

function launchCompareModal() {
    if (comparedCourses.length === 0) return;
    
    const grid = document.getElementById('compare-grid');
    grid.innerHTML = '';
    
    comparedCourses.forEach(course => {
        const tText = course.title.toLowerCase();
        const dText = course.desc.toLowerCase();
        const fullText = `${tText} ${dText}`;
        
        let difficulty = "Intermediate";
        if (fullText.includes("beginner") || 
            fullText.includes("introduction") || 
            fullText.includes("intro") || 
            fullText.includes("basic") || 
            fullText.includes("fundamental") || 
            fullText.includes("foundation") || 
            fullText.includes("101")) {
            difficulty = "Beginner friendly";
        } else if (fullText.includes("advanced") || 
                   fullText.includes("expert") || 
                   fullText.includes("deep dive") || 
                   fullText.includes("senior") || 
                   fullText.includes("mastery")) {
            difficulty = "Advanced / Expert";
        }

        const col = document.createElement('div');
        col.className = 'compare-column';
        
        const starsNum = parseFloat(course.stars);
        const starsInt = Math.min(Math.max(Math.round(starsNum), 1), 5);
        let starsStr = '';
        for (let i = 0; i < starsInt; i++) starsStr += '<i data-lucide="star" style="width:14px;height:14px;display:inline-block;vertical-align:middle;"></i>';
        
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
                <button class="btn btn-primary" onclick="validateCompareLink(this)" style="width:100%; text-decoration:none;">View Course <i data-lucide="arrow-up-right" style="width: 14px; height: 14px; display: inline-block;"></i></button>
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
    btn.innerHTML = '<i data-lucide="search" style="width:16px;height:16px;display:inline-block;vertical-align:middle;"></i> Checking...';
    
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

// D3.js Force-Directed Skill Map
let isGraphInitialized = false;

function initSkillMapGraph() {
    if (isGraphInitialized) return;
    
    const svg = d3.select("#map-svg");
    const container = document.querySelector(".map-container");
    if (!container) return;
    
    const width = container.clientWidth || 960;
    const height = window.innerWidth <= 768 ? 400 : 650;
    
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
                .selectAll("g")
                .data(data.nodes)
                .join("g")
                .style("cursor", "pointer")
                .call(d3.drag()
                    .on("start", dragstarted)
                    .on("drag", dragged)
                    .on("end", dragended)
                );
                
            node.append("circle")
                .attr("r", 10)
                .attr("fill", d => colorScale(d.group))
                .attr("stroke", currentTheme === 'dark' ? "rgba(255,255,255,0.2)" : "rgba(15,76,117,0.15)")
                .attr("stroke-width", 1.5);
                
            node.append("text")
                .text(d => d.title.length > 20 ? d.title.substring(0, 20) + "..." : d.title)
                .attr("x", 14)
                .attr("y", 4)
                .style("font-size", "10px")
                .style("font-weight", "600")
                .style("fill", currentTheme === 'dark' ? "rgba(255,255,255,0.9)" : "rgba(15,23,42,0.9)")
                .style("pointer-events", "none")
                .style("text-shadow", currentTheme === 'dark' ? "0px 1px 3px rgba(0,0,0,0.8)" : "0px 1px 3px rgba(255,255,255,0.8)");
                
            // Node Interactions
            node.on("mouseover", (event, d) => {
                const current = d3.select(event.currentTarget);
                current.select("circle")
                    .transition().duration(200)
                    .attr("r", 14)
                    .attr("stroke", currentTheme === 'dark' ? "#FFF" : "var(--primary)");
                    
                current.select("text")
                    .transition().duration(200)
                    .style("font-size", "12px");
                    
                tooltip.transition().duration(200).style("opacity", 0.95);
                tooltip.html(`
                    <strong style="color:var(--secondary); font-size:0.9rem;">${d.title}</strong><br/>
                    <span style="font-size:0.8rem; color:var(--text-muted);">Group: ${d.group}</span><br/>
                    <span style="font-size:0.8rem; color:#FBBF24;"><i data-lucide="star" style="width:14px;height:14px;display:inline-block;vertical-align:middle;"></i> ${d.stars.toFixed(1)} AI Score</span>
                `)
                .style("left", (event.pageX + 15) + "px")
                .style("top", (event.pageY - 28) + "px");
            })
            .on("mouseout", (event, d) => {
                const current = d3.select(event.currentTarget);
                current.select("circle")
                    .transition().duration(200)
                    .attr("r", 10)
                    .attr("stroke", currentTheme === 'dark' ? "rgba(255,255,255,0.2)" : "rgba(15,76,117,0.15)");
                    
                current.select("text")
                    .transition().duration(200)
                    .style("font-size", "10px");
                    
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
                    .attr("opacity", n => neighbors.has(n.id) ? 1.0 : 0.15);
                
                node.selectAll("circle").transition().duration(300)
                    .attr("r", n => n.id === d.id ? 15 : 10);
                    
                link.transition().duration(300)
                    .attr("stroke", l => (l.source.id === d.id || l.target.id === d.id) ? "var(--primary)" : (currentTheme === 'dark' ? "rgba(255,255,255,0.03)" : "rgba(15,76,117,0.03)"))
                    .attr("stroke-width", l => (l.source.id === d.id || l.target.id === d.id) ? 3.5 : 1.2);
                    
                // Update map sidebar Details
                if (sidebarInstruction) sidebarInstruction.style.display = 'none';
                if (sidebarDetails) sidebarDetails.style.display = 'block';
                if (sidebarTitle) sidebarTitle.textContent = d.title;
                if (sidebarProvider) sidebarProvider.textContent = d.provider;
                if (sidebarRating) sidebarRating.textContent = `${d.stars.toFixed(1)} / 5.0`;
                
                if (window.innerWidth <= 768) {
                    const sidebarElem = document.querySelector('.map-sidebar');
                    if (sidebarElem) {
                        sidebarElem.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
                    }
                }

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
                node.transition().duration(300).attr("opacity", 1.0);
                node.selectAll("circle").transition().duration(300).attr("r", 10);
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
                    
                node.attr("transform", d => `translate(${d.x},${d.y})`);
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
            
            // Search Functionality
            const searchInput = document.getElementById('skill-map-search-input');
            if (searchInput) {
                searchInput.addEventListener('input', (e) => {
                    const query = e.target.value.toLowerCase();
                    if (!query) {
                        node.transition().duration(200).attr("opacity", 1);
                        link.transition().duration(200).attr("stroke-opacity", 1);
                        return;
                    }
                    
                    node.transition().duration(200).attr("opacity", d => d.title.toLowerCase().includes(query) ? 1 : 0.1);
                    link.transition().duration(200).attr("stroke-opacity", 0.1); // Dim links to focus on matching nodes
                });
            }
        });
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
                checkbox.innerHTML = '<i data-lucide="circle" style="width:16px;height:16px;display:inline-block;vertical-align:middle;"></i>';
                checkbox.style.transition = 'all 0.2s';
                header.prepend(checkbox);

                header.addEventListener('click', () => {
                    if (checkbox.innerHTML === '<i data-lucide="circle" style="width:16px;height:16px;display:inline-block;vertical-align:middle;"></i>') {
                        checkbox.innerHTML = '<i data-lucide="check-circle" style="width:16px;height:16px;display:inline-block;vertical-align:middle;"></i>';
                        header.style.textDecoration = 'line-through';
                        header.style.opacity = '0.5';
                    } else {
                        checkbox.innerHTML = '<i data-lucide="circle" style="width:16px;height:16px;display:inline-block;vertical-align:middle;"></i>';
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

function submitCourse(event) {
    event.preventDefault();
    const btn = document.getElementById('submit-course-btn');
    const status = document.getElementById('submit-course-status');
    const form = document.getElementById('submit-course-form');
    
    if (btn) {
        btn.disabled = true;
        btn.textContent = "Submitting...";
    }
    
    const formData = new FormData(form);
    
    fetch('/submit_course', {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        if (btn) {
            btn.disabled = false;
            btn.textContent = "Submit for Verification";
        }
        if (data.success) {
            status.style.color = "var(--success)";
            status.innerHTML = '<i data-lucide="check-circle" style="width: 16px; height: 16px; display: inline-block; vertical-align: middle;"></i> ' + data.message;
            lucide.createIcons();
            form.reset();
            setTimeout(() => { status.textContent = ""; }, 5000);
        } else {
            status.style.color = "var(--danger)";
            status.innerHTML = '<i data-lucide="x-circle" style="width: 16px; height: 16px; display: inline-block; vertical-align: middle;"></i> Error: ' + data.error;
            lucide.createIcons();
            if (data.error === "Not logged in") {
                window.location.href = "/login";
            }
        }
    })
    .catch(err => {
        if (btn) {
            btn.disabled = false;
            btn.textContent = "Submit for Verification";
        }
        status.style.color = "var(--danger)";
        status.innerHTML = '<i data-lucide="x-circle" style="width: 16px; height: 16px; display: inline-block; vertical-align: middle;"></i> Failed to reach server.';
        lucide.createIcons();
    });
}

function openSubmitCourseModal() {
    const modal = document.getElementById('submit-course-modal');
    if (modal) {
        modal.style.display = 'flex';
        // Force reflow
        void modal.offsetWidth;
        modal.classList.add('active');
    }
}

function closeSubmitCourseModal() {
    const modal = document.getElementById('submit-course-modal');
    if (modal) {
        modal.classList.remove('active');
        setTimeout(() => {
            modal.style.display = 'none';
        }, 300); // match transition duration
    }
}

// Close modal when clicking outside of it
document.addEventListener('click', function(e) {
    const modal = document.getElementById('submit-course-modal');
    if (modal && modal.style.display === 'flex' && e.target === modal) {
        closeSubmitCourseModal();
    }
    
    const rModal = document.getElementById('roulette-modal');
    if (rModal && rModal.classList.contains('active') && e.target === rModal) {
        closeRouletteModal();
    }
});

// Tab switcher
function switchTab(tabId) {
    if (tabId === 'dashboard' && !document.getElementById('tab-pane-dashboard')) {
        tabId = 'catalog';
        window.history.pushState(null, '', '/');
    }
    document.querySelectorAll('.tab-pane').forEach(pane => {
        pane.classList.remove('active');
    });
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.remove('active');
    });
    document.querySelectorAll('.app-sidebar-link').forEach(link => {
        if (link.id && link.id.startsWith('side-link-')) {
            link.classList.remove('active');
        }
    });

    const activePane = document.getElementById(`tab-pane-${tabId}`);
    const activeBtn = document.getElementById(`tab-btn-${tabId}`);
    const activeSideLink = document.getElementById(`side-link-${tabId}`);
    
    if (activePane) activePane.classList.add('active');
    if (activeBtn) activeBtn.classList.add('active');
    if (activeSideLink) activeSideLink.classList.add('active');

    // Auto-close mobile sidebar if open
    const sidebar = document.getElementById('app-sidebar');
    const backdrop = document.getElementById('sidebar-backdrop');
    if (sidebar && sidebar.classList.contains('mobile-open')) {
        sidebar.classList.remove('mobile-open');
        if (backdrop) {
            backdrop.classList.remove('active');
        }
    }

    localStorage.setItem('activeDashboardTab', tabId);
    
    if (tabId === 'skill-map') {
        setTimeout(initSkillMapGraph, 100);
    } else if (tabId === 'dashboard') {
        setTimeout(initDashboardCharts, 100);
    }
}

// Nordic Light/Dark Theme Switcher
function initTheme() {
    const savedTheme = localStorage.getItem('nordicTheme') || 'light';
    document.documentElement.setAttribute('data-theme', savedTheme);
    updateThemeToggleButton(savedTheme);
}

function toggleTheme() {
    const currentTheme = document.documentElement.getAttribute('data-theme') || 'light';
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
        btn.innerHTML = theme === 'dark' ? '<i data-lucide="sun" style="width:20px;height:20px;display:inline-block;vertical-align:middle;"></i>' : '<i data-lucide="moon" style="width:20px;height:20px;display:inline-block;vertical-align:middle;"></i>';
        if(window.lucide) lucide.createIcons();
        btn.setAttribute('title', `Switch to Nordic ${theme === 'dark' ? 'Light' : 'Dark'} Mode`);
    }
}

function exportPlanToPDF() {
    const goalInput = document.getElementById('ai-goal-input');
    const goalText = goalInput ? goalInput.value.trim() : "Custom Learning Path";
    const pathContent = document.getElementById('ai-path-content');
    
    if (!pathContent || pathContent.innerHTML.trim() === "") {
        showToast("No generated plan found! Please generate a plan first.", "warning");
        return;
    }
    
    showToast("Preparing your premium PDF download...", "info");
    
    // 1. Inject temporary high-priority print styles to override dark theme colors
    const pdfStyles = document.createElement('style');
    pdfStyles.id = 'temp-pdf-styles';
    pdfStyles.innerHTML = `
        #ai-path-content {
            color: #0F172A !important;
            background: #FFFFFF !important;
            padding: 20px !important;
            border-radius: 0 !important;
        }
        #ai-path-content .path-step {
            background: #F8FAFC !important;
            border: 1px solid #E2E8F0 !important;
            color: #0F172A !important;
            padding: 24px !important;
            margin-bottom: 24px !important;
            page-break-inside: avoid !important;
            break-inside: avoid !important;
            border-radius: 12px !important;
            box-shadow: none !important;
            text-align: left !important;
        }
        #ai-path-content h3 {
            color: #0F4C75 !important;
            font-size: 18px !important;
            border-bottom: 2px solid #3282B8 !important;
            padding-bottom: 6px !important;
            margin-top: 0 !important;
            margin-bottom: 12px !important;
            font-weight: 800 !important;
        }
        #ai-path-content .path-checkbox {
            display: none !important;
        }
        #ai-path-content h4 {
            color: #3282B8 !important;
            font-size: 13px !important;
            margin-top: 15px !important;
            font-weight: 700 !important;
        }
        #ai-path-content p, #ai-path-content li {
            color: #334155 !important;
            font-size: 13.5px !important;
        }
        #ai-path-content strong {
            color: #0F172A !important;
            font-weight: 700 !important;
        }
        #ai-path-content a {
            color: #0F4C75 !important;
            text-decoration: underline !important;
            font-weight: 600 !important;
        }
    `;
    document.head.appendChild(pdfStyles);
    
    // 2. Create and prepend a beautiful document header
    const pdfHeader = document.createElement('div');
    pdfHeader.id = 'temp-pdf-header';
    pdfHeader.style.paddingBottom = '15px';
    pdfHeader.style.borderBottom = '2px solid #0F4C75';
    pdfHeader.style.marginBottom = '25px';
    pdfHeader.style.textAlign = 'left';
    pdfHeader.innerHTML = `
        <div style="display: flex; justify-content: space-between; align-items: flex-end;">
            <div>
                <h1 style="margin: 0; color: #0F4C75; font-size: 24px; font-weight: 800; letter-spacing: -0.02em;"><i data-lucide="brain" style="width:24px;height:24px;display:inline-block;vertical-align:middle;"></i> AI STUDY PATH</h1>
                <p style="margin: 5px 0 0 0; color: #5F85A2; font-size: 14px; font-weight: 600;">Personalized CS Learning Curriculum</p>
            </div>
            <div style="text-align: right; font-size: 11px; color: #64748B;">
                <strong>Date:</strong> ${new Date().toLocaleDateString()}<br/>
                <strong>Platform:</strong> AI CS Recommender
            </div>
        </div>
        <div style="background: #F8FAFC; border-left: 4px solid #3282B8; padding: 12px 18px; border-radius: 6px; margin-top: 20px; text-align: left;">
            <span style="font-size: 10px; text-transform: uppercase; letter-spacing: 0.05em; color: #64748B; font-weight: 700;">Target Goal / Career Focus</span>
            <h2 style="margin: 3px 0 0 0; color: #0F172A; font-size: 18px; font-weight: 700; text-transform: capitalize;">${goalText}</h2>
        </div>
    `;
    pathContent.prepend(pdfHeader);
    
    // 3. Create and append a beautiful document footer
    const pdfFooter = document.createElement('div');
    pdfFooter.id = 'temp-pdf-footer';
    pdfFooter.style.borderTop = '1px solid #E2E8F0';
    pdfFooter.style.marginTop = '40px';
    pdfFooter.style.paddingTop = '15px';
    pdfFooter.style.textAlign = 'center';
    pdfFooter.style.fontSize = '11px';
    pdfFooter.style.color = '#94A3B8';
    pdfFooter.innerHTML = `AI-Powered CS Course Recommender Intelligence Dashboard &bull; Curated and Structured with Gemini 2.5-Flash`;
    pathContent.appendChild(pdfFooter);
    
    // 4. PDF Generation Options
    const opt = {
        margin:       12,
        filename:     `AI_Study_Plan_${goalText.replace(/[^a-z0-9]/gi, '_').toLowerCase()}.pdf`,
        image:        { type: 'jpeg', quality: 0.98 },
        html2canvas:  { 
            scale: 2, 
            useCORS: true, 
            letterRendering: true,
            scrollY: 0,
            scrollX: 0
        },
        jsPDF:        { unit: 'mm', format: 'a4', orientation: 'portrait' }
    };
    
    // 5. Run html2pdf directly on the fully painted DOM container
    html2pdf().set(opt).from(pathContent).save().then(() => {
        // Clean up immediately!
        pdfHeader.remove();
        pdfFooter.remove();
        pdfStyles.remove();
        showToast("PDF Export Complete!", "success");
    }).catch(err => {
        console.error("PDF Export Error: ", err);
        pdfHeader.remove();
        pdfFooter.remove();
        pdfStyles.remove();
        showToast("Failed to generate PDF.", "error");
    });
}

let dashboardCharts = {};

function initDashboardCharts() {
    if (!document.getElementById('stat-total-courses')) return;
    
    // If charts already exist, destroy them to support clean re-rendering
    Object.keys(dashboardCharts).forEach(key => {
        if (dashboardCharts[key]) {
            dashboardCharts[key].destroy();
        }
    });
    
    fetch('/api/stats')
        .then(response => response.json())
        .then(data => {
            if (!data.success) {
                console.error("Failed to load statistics:", data.error);
                return;
            }
            
            // 1. Update Metrics Cards
            document.getElementById('stat-total-courses').innerText = data.metrics.total_courses.toLocaleString();
            document.getElementById('stat-avg-rating').innerHTML = data.metrics.avg_rating.toFixed(2) + ' <i data-lucide="star" style="width:14px;height:14px;display:inline-block;vertical-align:middle;"></i>';
            document.getElementById('stat-total-reviews').innerText = data.metrics.total_reviews.toLocaleString();
            
            // Check active theme to customize text/axes colors dynamically!
            const currentTheme = document.documentElement.getAttribute('data-theme') || 'dark';
            const labelColor = currentTheme === 'dark' ? '#BBE1FA' : '#334155';
            const gridColor = currentTheme === 'dark' ? 'rgba(187, 225, 250, 0.1)' : 'rgba(15, 23, 42, 0.08)';
            
            // 2. Chart 1: Course Provider Distribution (Doughnut)
            const providerCtx = document.getElementById('chart-provider').getContext('2d');
            const providers = Object.keys(data.provider_distribution);
            const providerValues = Object.values(data.provider_distribution);
            
            dashboardCharts.provider = new Chart(providerCtx, {
                type: 'doughnut',
                data: {
                    labels: providers,
                    datasets: [{
                        data: providerValues,
                        backgroundColor: [
                            '#3282B8',
                            '#0F4C75',
                            '#BBE1FA',
                            '#10B981',
                            '#FBBF24'
                        ].slice(0, providers.length),
                        borderWidth: 0,
                        hoverOffset: 10
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            position: 'bottom',
                            labels: { color: labelColor, font: { family: 'Inter', weight: '600' } }
                        }
                    }
                }
            });
            
            // 3. Chart 2: Keyword Frequency statistics (Bar Chart)
            const keywordCtx = document.getElementById('chart-keywords').getContext('2d');
            // Sort keywords descending
            const sortedKeywords = Object.entries(data.keyword_frequencies)
                .sort((a, b) => b[1] - a[1])
                .slice(0, 8);
                
            dashboardCharts.keywords = new Chart(keywordCtx, {
                type: 'bar',
                data: {
                    labels: sortedKeywords.map(x => x[0].toUpperCase()),
                    datasets: [{
                        label: 'Term Counts',
                        data: sortedKeywords.map(x => x[1]),
                        backgroundColor: 'rgba(50, 130, 184, 0.85)',
                        borderColor: '#3282B8',
                        borderWidth: 1.5,
                        borderRadius: 6
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        x: {
                            ticks: { color: labelColor, font: { family: 'Inter', weight: '600', size: 10 } },
                            grid: { display: false }
                        },
                        y: {
                            ticks: { color: labelColor },
                            grid: { color: gridColor }
                        }
                    },
                    plugins: {
                        legend: { display: false }
                    }
                }
            });
            
            // 4. Chart 3: Difficulty ratio (Pie)
            const difficultyCtx = document.getElementById('chart-difficulty').getContext('2d');
            const diffLabels = Object.keys(data.difficulty_distribution);
            const diffValues = Object.values(data.difficulty_distribution);
            
            // Re-order to green-yellow-red sequence: Beginner, Intermediate, Advanced
            const order = ["Beginner", "Intermediate", "Advanced"];
            const orderedLabels = [];
            const orderedValues = [];
            
            order.forEach(level => {
                const idx = diffLabels.indexOf(level);
                if (idx !== -1) {
                    orderedLabels.push(level);
                    orderedValues.push(diffValues[idx]);
                }
            });
            
            dashboardCharts.difficulty = new Chart(difficultyCtx, {
                type: 'pie',
                data: {
                    labels: orderedLabels,
                    datasets: [{
                        data: orderedValues,
                        backgroundColor: [
                            '#10B981', // green
                            '#FBBF24', // yellow/gold
                            '#EF4444'  // red
                        ],
                        borderWidth: 0
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            position: 'bottom',
                            labels: { color: labelColor, font: { family: 'Inter', weight: '600' } }
                        }
                    }
                }
            });
            
            // 5. Chart 4: Ratings Distribution Histogram (Bar)
            const ratingCtx = document.getElementById('chart-ratings').getContext('2d');
            const ratingsBins = Object.keys(data.ratings_distribution);
            const ratingsValues = Object.values(data.ratings_distribution);
            
            dashboardCharts.ratings = new Chart(ratingCtx, {
                type: 'bar',
                data: {
                    labels: ratingsBins,
                    datasets: [{
                        label: 'Course Counts',
                        data: ratingsValues,
                        backgroundColor: 'rgba(15, 76, 117, 0.85)',
                        borderColor: '#0F4C75',
                        borderWidth: 1.5,
                        borderRadius: 6
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        x: {
                            ticks: { color: labelColor, font: { family: 'Inter', weight: '600' } },
                            grid: { display: false }
                        },
                        y: {
                            ticks: { color: labelColor },
                            grid: { color: gridColor }
                        }
                    },
                    plugins: {
                        legend: { display: false }
                    }
                }
            });
        })
        .catch(err => {
            console.error("Error loading dashboard data:", err);
        });
}

// <i data-lucide="dices" style="width:16px;height:16px;display:inline-block;vertical-align:middle;"></i> Course Discovery Roulette Implementation
function openRouletteModal() {
    const modal = document.getElementById('roulette-modal');
    modal.classList.add('active');
    
    // Reset modal state
    document.getElementById('roulette-result-card').style.display = 'none';
    const inner = document.getElementById('roulette-spinner-inner');
    inner.innerHTML = '<span class="roulette-spinner-placeholder">Ready to Spin!</span>';
    
    const spinBtn = document.getElementById('roulette-spin-btn');
    spinBtn.disabled = false;
    spinBtn.innerHTML = '<i data-lucide="sparkles" style="width:16px;height:16px;display:inline-block;vertical-align:middle;"></i> Spin the Wheel!';
}

function closeRouletteModal() {
    document.getElementById('roulette-modal').classList.remove('active');
}

function startRouletteSpin() {
    const spinBtn = document.getElementById('roulette-spin-btn');
    const container = document.querySelector('.roulette-spinner-container');
    const inner = document.getElementById('roulette-spinner-inner');
    const resultCard = document.getElementById('roulette-result-card');
    
    // Disable inputs and reset state
    spinBtn.disabled = true;
    spinBtn.innerHTML = '<i data-lucide="dices" style="width:16px;height:16px;display:inline-block;vertical-align:middle;"></i> Spinning...';
    resultCard.style.display = 'none';
    container.classList.add('spinning');
    
    // Rapidly cycle intermediate CS terms to simulate slot machine reel!
    const placeholderTerms = [
        "Advanced Neural Networks",
        "Python Data Science 101",
        "Cybersecurity Pentesting",
        "Algorithmic Data Structures",
        "Full-Stack Web Dev Bootcamp",
        "Database Architecture & SQL",
        "Introduction to AI Models",
        "Cloud DevOps with Docker",
        "Framer Motion Animations",
        "Pairwise Cosine Similarity",
        "TF-IDF Term Weighting",
        "Graph Search Traversals",
        "MongoDB Ingestion Pipeline"
    ];
    
    let cycleIdx = 0;
    const spinInterval = setInterval(() => {
        inner.innerHTML = `<span>${placeholderTerms[cycleIdx]}</span>`;
        cycleIdx = (cycleIdx + 1) % placeholderTerms.length;
    }, 75);
    
    // Fetch random course in the background
    fetch('/api/random_course')
        .then(response => response.json())
        .then(data => {
            setTimeout(() => {
                // Stop spinning
                clearInterval(spinInterval);
                container.classList.remove('spinning');
                
                if (!data.success) {
                    inner.innerHTML = '<span class="roulette-spinner-placeholder">Spin Failed! Try Again.</span>';
                    spinBtn.disabled = false;
                    spinBtn.innerHTML = '<i data-lucide="sparkles" style="width:16px;height:16px;display:inline-block;vertical-align:middle;"></i> Spin the Wheel!';
                    return;
                }
                
                const course = data.course;
                
                // Set snapped visual title
                inner.innerHTML = `<span style="color: var(--accent-emerald); font-size: 1.45rem;"><i data-lucide="party-popper" style="width:24px;height:24px;display:inline-block;vertical-align:middle;"></i> MATCH FOUND! <i data-lucide="party-popper" style="width:24px;height:24px;display:inline-block;vertical-align:middle;"></i></span>`;
                
                // Populate Result Card
                document.getElementById('roulette-res-provider').innerText = course.provider;
                document.getElementById('roulette-res-title').innerText = course.title;
                
                // Formulate stars
                const starCount = Math.min(Math.max(Math.round(course.stars), 1), 5);
                document.getElementById('roulette-res-stars').innerHTML = '<i data-lucide="star" style="width:14px;height:14px;display:inline-block;vertical-align:middle;"></i>'.repeat(starCount);
                document.getElementById('roulette-res-reviews').innerText = `(${course.ratings_count.toLocaleString()} student reviews)`;
                
                // Formulate description
                let desc = course.content_text || "No description provided.";
                if (desc.length > 200) {
                    desc = desc.substring(0, 197) + '...';
                }
                document.getElementById('roulette-res-desc').innerText = desc;
                
                // Formulate links & actions
                const linkBtn = document.getElementById('roulette-res-link');
                linkBtn.href = course.url && course.url !== '#' ? `/verify_link?url=${encodeURIComponent(course.url)}&title=${encodeURIComponent(course.title)}&provider=${encodeURIComponent(course.provider)}` : '#';
                
                // Compare binding
                const compareBtn = document.getElementById('roulette-add-compare-btn');
                compareBtn.onclick = () => {
                    addToCompare({
                        title: course.title,
                        provider: course.provider,
                        stars: course.stars,
                        ratings_count: course.ratings_count,
                        url: course.url,
                        desc: course.content_text
                    });
                    showToast(`Added ${course.title.substring(0, 25)}... to Comparison!`, "success");
                };
                
                // Render Result Card
                resultCard.style.display = 'block';
                
                // Enable button for spin again
                spinBtn.disabled = false;
                spinBtn.innerHTML = '<i data-lucide="refresh-cw" style="width:16px;height:16px;display:inline-block;vertical-align:middle;"></i> Spin Again!';
                
                // TRIPLE NEON CONFETTI BURST!
                triggerConfettiExplosion();
            }, 1800); // Perfect duration to build slot-machine suspense!
        })
        .catch(err => {
            console.error("Roulette search failure: ", err);
            clearInterval(spinInterval);
            container.classList.remove('spinning');
            inner.innerHTML = '<span class="roulette-spinner-placeholder">Error! Try Again.</span>';
            spinBtn.disabled = false;
            spinBtn.innerHTML = '<i data-lucide="sparkles" style="width:16px;height:16px;display:inline-block;vertical-align:middle;"></i> Spin the Wheel!';
        });
}

function triggerConfettiExplosion() {
    if (typeof confetti === 'function') {
        const duration = 2.5 * 1000;
        const animationEnd = Date.now() + duration;
        const defaults = { startVelocity: 30, spread: 360, ticks: 60, zIndex: 1100 };

        function randomInRange(min, max) {
            return Math.random() * (max - min) + min;
        }

        const interval = setInterval(function() {
            const timeLeft = animationEnd - Date.now();

            if (timeLeft <= 0) {
                return clearInterval(interval);
            }

            const particleCount = 50 * (timeLeft / duration);
            // double bottom-corner bursts!
            confetti(Object.assign({}, defaults, { particleCount, origin: { x: randomInRange(0.1, 0.3), y: Math.random() - 0.2 } }));
            confetti(Object.assign({}, defaults, { particleCount, origin: { x: randomInRange(0.7, 0.9), y: Math.random() - 0.2 } }));
        }, 250);
        
        // Single heavy center burst
        confetti({
            particleCount: 150,
            spread: 80,
            origin: { y: 0.6 },
            zIndex: 1100
        });
    }
}

// Restore Tab state and Theme state
document.addEventListener('DOMContentLoaded', () => {
    initTheme();
    const activeTab = localStorage.getItem('activeDashboardTab') || 'catalog';
    switchTab(activeTab);
});
