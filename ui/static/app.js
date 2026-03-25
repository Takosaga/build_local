// --- Wizard Step 0: form submission ---
const startForm = document.getElementById('start-form');
if (startForm) {
  startForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const data = new FormData(startForm);
    await fetch('/wizard/start', { method: 'POST', body: data });
    location.reload();
  });
}

// --- Chat interface ---
const chatForm = document.getElementById('chat-form');
const messagesEl = document.getElementById('messages');
const spinner = document.getElementById('spinner');
const userInput = document.getElementById('user-input');

function appendMessage(role, text) {
  const div = document.createElement('div');
  div.className = `msg ${role}`;
  div.textContent = text;
  messagesEl.appendChild(div);
  messagesEl.scrollTop = messagesEl.scrollHeight;
  return div;
}

if (chatForm) {
  chatForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const message = userInput.value.trim();
    if (!message) return;
    userInput.value = '';

    appendMessage('user', message);
    spinner.classList.remove('hidden');

    const assistantEl = appendMessage('assistant', '');
    let buffer = '';

    try {
      const resp = await fetch('/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message }),
      });

      const reader = resp.body.getReader();
      const decoder = new TextDecoder();

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        const chunk = decoder.decode(value);
        const lines = chunk.split('\n');
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data = line.slice(6).trim();
            if (data === '[DONE]') break;
            try {
              const parsed = JSON.parse(data);
              if (parsed.delta) {
                buffer += parsed.delta;
                assistantEl.textContent = buffer;
                messagesEl.scrollTop = messagesEl.scrollHeight;
              }
            } catch {}
          }
        }
      }
    } catch (err) {
      assistantEl.textContent = 'Something went wrong. Please try again.';
    } finally {
      spinner.classList.add('hidden');
    }
  });
}

// --- Wizard controls ---
async function finaliseSetup() {
  await fetch('/wizard/finalise', { method: 'POST' });
  location.href = '/';
}

async function resetWizard() {
  if (!confirm('Restart the setup wizard? Your ERPNext data will be preserved.')) return;
  await fetch('/wizard/reset', { method: 'POST' });
  location.href = '/';
}
