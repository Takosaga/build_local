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

// --- Chat interface helpers ---
const messagesEl = document.getElementById('messages');
const spinner = document.getElementById('spinner');
const userInput = document.getElementById('user-input');
const sendButton = document.querySelector('#chat-form button[type="submit"]');

function appendMessage(role, text) {
  const div = document.createElement('div');
  div.className = `msg ${role}`;
  div.textContent = text;
  messagesEl.appendChild(div);
  messagesEl.scrollTop = messagesEl.scrollHeight;
  return div;
}

async function streamSSE(url, method, body, onDelta, onDone) {
  // Shared SSE streaming logic used by both greet and chat.
  // Returns true if a step_changed event was seen.
  let stepChanged = false;
  const opts = { method };
  if (body) {
    opts.headers = { 'Content-Type': 'application/json' };
    opts.body = JSON.stringify(body);
  }

  const resp = await fetch(url, opts);
  const reader = resp.body.getReader();
  const decoder = new TextDecoder();

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    const chunk = decoder.decode(value);
    const lines = chunk.split('\n');
    for (const line of lines) {
      if (!line.startsWith('data: ')) continue;
      const data = line.slice(6).trim();
      if (data === '[DONE]') break;
      try {
        const parsed = JSON.parse(data);
        if (parsed.delta) onDelta(parsed.delta);
        if (parsed.step_changed) stepChanged = true;
      } catch {}
    }
  }

  onDone();
  return stepChanged;
}

// --- Auto-greet on wizard chat pages ---
const wizardChat = document.getElementById('wizard-chat');
if (wizardChat) {
  (async () => {
    const assistantEl = appendMessage('assistant', '');
    let buffer = '';

    try {
      const stepChanged = await streamSSE(
        '/wizard/greet', 'GET', null,
        (delta) => {
          buffer += delta;
          assistantEl.textContent = buffer;
          messagesEl.scrollTop = messagesEl.scrollHeight;
        },
        () => {
          if (userInput) userInput.disabled = false;
          if (sendButton) sendButton.disabled = false;
        }
      );
      if (stepChanged) {
        const btn = document.createElement('button');
        btn.textContent = 'Next Step →';
        btn.className = 'next-step-btn';
        btn.onclick = () => location.reload();
        messagesEl.appendChild(btn);
        messagesEl.scrollTop = messagesEl.scrollHeight;
      }
    } catch {
      assistantEl.textContent = 'Could not connect to the assistant. Please refresh.';
      if (userInput) userInput.disabled = false;
      if (sendButton) sendButton.disabled = false;
    }
  })();
}

// --- Chat form submission ---
const chatForm = document.getElementById('chat-form');
if (chatForm) {
  chatForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const message = userInput.value.trim();
    if (!message) return;
    userInput.value = '';
    userInput.disabled = true;
    if (sendButton) sendButton.disabled = true;

    appendMessage('user', message);
    spinner.classList.remove('hidden');

    const assistantEl = appendMessage('assistant', '');
    let buffer = '';

    try {
      const stepChanged = await streamSSE(
        '/chat', 'POST', { message },
        (delta) => {
          buffer += delta;
          assistantEl.textContent = buffer;
          messagesEl.scrollTop = messagesEl.scrollHeight;
        },
        () => {
          spinner.classList.add('hidden');
          userInput.disabled = false;
          if (sendButton) sendButton.disabled = false;
        }
      );
      if (stepChanged) {
        const btn = document.createElement('button');
        btn.textContent = 'Next Step →';
        btn.className = 'next-step-btn';
        btn.onclick = () => location.reload();
        messagesEl.appendChild(btn);
        messagesEl.scrollTop = messagesEl.scrollHeight;
      }
    } catch {
      assistantEl.textContent = 'Something went wrong. Please try again.';
      spinner.classList.add('hidden');
      userInput.disabled = false;
      if (sendButton) sendButton.disabled = false;
    }
  });
}

// --- Wizard controls ---
async function finaliseSetup() {
  const resp = await fetch('/wizard/finalise', { method: 'POST' });
  if (resp.ok) {
    location.href = '/';
  } else {
    alert('Setup is not ready to finalise yet.');
  }
}

async function resetWizard() {
  if (!confirm('Restart the setup wizard? Your ERPNext data will be preserved.')) return;
  await fetch('/wizard/reset', { method: 'POST' });
  location.href = '/';
}
