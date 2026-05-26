import re

with open('static/js/main.js', 'r') as f:
    content = f.read()

replacements = {
    'ℹ️': '<i data-lucide="info" style="width:16px;height:16px;display:inline-block;vertical-align:middle;"></i>',
    '✅': '<i data-lucide="check-circle" style="width:16px;height:16px;display:inline-block;vertical-align:middle;"></i>',
    '⚠️': '<i data-lucide="alert-triangle" style="width:16px;height:16px;display:inline-block;vertical-align:middle;"></i>',
    '❌': '<i data-lucide="x-circle" style="width:16px;height:16px;display:inline-block;vertical-align:middle;"></i>',
    '🔍 Checking...': '<i data-lucide="search" style="width:16px;height:16px;display:inline-block;vertical-align:middle;"></i> Checking...',
    'Intermediate 🟡': 'Intermediate',
    'Beginner friendly 🟢': 'Beginner friendly',
    'Advanced / Expert 🔴': 'Advanced / Expert',
    '⭐': '<i data-lucide="star" style="width:14px;height:14px;display:inline-block;vertical-align:middle;"></i>',
    '⚪': '<i data-lucide="circle" style="width:16px;height:16px;display:inline-block;vertical-align:middle;"></i>',
    '☀️': '<i data-lucide="sun" style="width:20px;height:20px;display:inline-block;vertical-align:middle;"></i>',
    '🌙': '<i data-lucide="moon" style="width:20px;height:20px;display:inline-block;vertical-align:middle;"></i>',
    '🧠': '<i data-lucide="brain" style="width:24px;height:24px;display:inline-block;vertical-align:middle;"></i>',
    '🎰': '<i data-lucide="dices" style="width:16px;height:16px;display:inline-block;vertical-align:middle;"></i>',
    '✨': '<i data-lucide="sparkles" style="width:16px;height:16px;display:inline-block;vertical-align:middle;"></i>',
    '🎉': '<i data-lucide="party-popper" style="width:24px;height:24px;display:inline-block;vertical-align:middle;"></i>',
    '🔄': '<i data-lucide="refresh-cw" style="width:16px;height:16px;display:inline-block;vertical-align:middle;"></i>'
}

for emoji, html in replacements.items():
    content = content.replace(emoji, html)

# Add lucide.createIcons() after common innerHTML updates
content = re.sub(r'(toast\.innerHTML = `.*?`;)', r'\1\n    if(window.lucide) lucide.createIcons();', content)
content = re.sub(r'(btn\.innerHTML = .*?;)', r'\1\n        if(window.lucide) lucide.createIcons();', content)
content = re.sub(r'(inner\.innerHTML = .*?;)', r'\1\n        if(window.lucide) lucide.createIcons();', content)
content = re.sub(r'(spinBtn\.innerText = .*?;)', r'\1\n    if(window.lucide) lucide.createIcons();', content)
content = re.sub(r'(spinBtn\.innerHTML = .*?;)', r'\1\n    if(window.lucide) lucide.createIcons();', content)

# spinBtn.innerText to spinBtn.innerHTML since we are using HTML now
content = content.replace("spinBtn.innerText =", "spinBtn.innerHTML =")
content = content.replace("document.getElementById('roulette-res-stars').innerText =", "document.getElementById('roulette-res-stars').innerHTML =")
content = content.replace("document.getElementById('stat-avg-rating').innerText =", "document.getElementById('stat-avg-rating').innerHTML =")

with open('static/js/main.js', 'w') as f:
    f.write(content)
