import React, { useState } from 'react';

const newConversationId = () => {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) return crypto.randomUUID();
  return `coraleum-${Date.now()}-${Math.random().toString(36).slice(2)}`;
};

export default function CoralChat({ selectedDate }) {
  const [open, setOpen] = useState(false);
  const [message, setMessage] = useState('');
  const [sending, setSending] = useState(false);
  const [error, setError] = useState('');
  const [conversationId] = useState(newConversationId);
  const [messages, setMessages] = useState([
    { role: 'assistant', text: '¡Hola! Soy Coral, tu asistente de Coraleum. Puedo ayudarte a entender el estrés térmico y consultar los datos disponibles de las áreas coralinas.' },
  ]);

  async function sendMessage(event) {
    event.preventDefault();
    const question = message.trim();
    if (!question || sending) return;

    setMessages((current) => [...current, { role: 'user', text: question }]);
    setMessage('');
    setSending(true);
    setError('');

    try {
      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: question,
          conversation_id: conversationId,
          fecha: selectedDate,
        }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || 'No pude conectarme con Coral. Inténtalo de nuevo.');
      setMessages((current) => [...current, { role: 'assistant', text: data.reply }]);
    } catch (err) {
      setError(err.message || 'Ocurrió un error al enviar tu mensaje.');
    } finally {
      setSending(false);
    }
  }

  return (
    <div style={{ position: 'fixed', right: 22, bottom: 20, zIndex: 1000, fontFamily: 'inherit' }}>
      {open && (
        <section aria-label="Chat con Coral" style={{ width: 'min(360px, calc(100vw - 32px))', height: 460, maxHeight: 'calc(100dvh - 100px)', display: 'flex', flexDirection: 'column', overflow: 'hidden', borderRadius: 18, background: '#ffffff', border: '1px solid rgba(35,113,122,0.22)', boxShadow: '0 18px 55px rgba(22,66,72,0.22)', marginBottom: 12 }}>
          <header style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '14px 16px', color: '#ffffff', background: 'linear-gradient(120deg, #126e70, #0aa6a0)' }}>
            <div style={{ width: 36, height: 36, borderRadius: '50%', display: 'grid', placeItems: 'center', background: 'rgba(255,255,255,0.18)', fontSize: 20 }}>✦</div>
            <div style={{ flex: 1 }}>
              <div style={{ fontWeight: 700, fontSize: 15 }}>Coral</div>
              <div style={{ fontSize: 11, opacity: 0.86 }}>Asistente virtual de Coraleum</div>
            </div>
            <button type="button" onClick={() => setOpen(false)} aria-label="Cerrar chat" style={{ color: '#ffffff', border: 0, background: 'transparent', fontSize: 23, cursor: 'pointer' }}>×</button>
          </header>

          <div role="log" aria-live="polite" style={{ flex: 1, overflowY: 'auto', padding: 14, display: 'flex', flexDirection: 'column', gap: 10, background: '#f4faf9' }}>
            {messages.map((item, index) => (
              <div key={index} style={{ alignSelf: item.role === 'user' ? 'flex-end' : 'flex-start', maxWidth: '88%', padding: '10px 12px', borderRadius: 14, background: item.role === 'user' ? '#d9f4ef' : '#ffffff', color: '#234c52', border: '1px solid rgba(35,113,122,0.10)', fontSize: 13, lineHeight: 1.5, whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>
                {item.text}
              </div>
            ))}
            {sending && <div style={{ color: '#53777a', fontSize: 12 }}>Coral está preparando una respuesta…</div>}
          </div>

          {error && <div role="alert" style={{ padding: '8px 12px', fontSize: 11, color: '#9d3427', background: '#fff1ee' }}>{error}</div>}

          <form onSubmit={sendMessage} style={{ display: 'flex', gap: 8, padding: 12, borderTop: '1px solid #e1eeec', background: '#ffffff' }}>
            <input
              aria-label="Escribe tu pregunta"
              value={message}
              onChange={(event) => setMessage(event.target.value)}
              placeholder="Pregunta sobre el estrés térmico…"
              maxLength={1500}
              disabled={sending}
              style={{ minWidth: 0, flex: 1, border: '1px solid #c8dfdc', borderRadius: 12, padding: '10px 11px', outlineColor: '#0aa6a0', fontSize: 12 }}
            />
            <button type="submit" disabled={sending || !message.trim()} aria-label="Enviar mensaje" style={{ width: 42, border: 0, borderRadius: 12, background: sending || !message.trim() ? '#a8c8c5' : '#087f7b', color: '#ffffff', cursor: sending || !message.trim() ? 'default' : 'pointer', fontSize: 18 }}>➤</button>
          </form>
        </section>
      )}

      <button type="button" onClick={() => setOpen((value) => !value)} aria-label={open ? 'Ocultar chat de Coral' : 'Abrir chat de Coral'} style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 9, border: 'none', borderRadius: 999, padding: '13px 17px', color: '#ffffff', background: 'linear-gradient(120deg, #126e70, #0aa6a0)', boxShadow: '0 8px 25px rgba(18,110,112,0.32)', fontWeight: 700, fontSize: 13, cursor: 'pointer' }}>
        <span style={{ fontSize: 18 }}>{open ? '×' : '✦'}</span>
        {open ? 'Cerrar Coral' : 'Habla con Coral'}
      </button>
    </div>
  );
}
