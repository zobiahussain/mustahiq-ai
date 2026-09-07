import { useRef, useState } from 'react';
import { BookOpen, ChevronDown, MessageCircle, Send, X } from 'lucide-react';
import { streamApi } from './api';

const starters = [
  'Which programs are available?',
  'What documents are required?',
  'How does verification work?',
];

export function SupportChatbot() {
  const [open, setOpen] = useState(false);
  const [question, setQuestion] = useState('');
  const [messages, setMessages] = useState([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const bottom = useRef(null);

  async function ask(value) {
    const text = value.trim();
    if (!text || busy) return;
    const replyId = crypto.randomUUID();
    setBusy(true);
    setError('');
    setMessages(items => [...items, { role: 'user', text }, { role: 'assistant', id: replyId, text: '', sources: [] }]);
    setQuestion('');
    try {
      await streamApi('/support/chat/stream', {
        body: { question: text },
        onEvent: event => {
          if (event.type === 'meta') {
            setMessages(items => items.map(item => item.id === replyId ? { ...item, sources: event.sources || [] } : item));
          }
          if (event.type === 'token') {
            setMessages(items => items.map(item => item.id === replyId ? { ...item, text: item.text + event.text } : item));
            setTimeout(() => bottom.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' }), 20);
          }
        },
      });
    } catch (err) {
      setMessages(items => items.filter(item => item.id !== replyId));
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return <aside className={`support-chat ${open ? 'open' : ''}`} aria-label="Alkhidmat support chatbot">
    {!open && <button className="support-launcher" onClick={() => setOpen(true)} aria-label="Open Alkhidmat support chatbot"><MessageCircle size={21}/><span>Program help</span></button>}
    {open && <div className="support-window">
      <header><div><span><BookOpen size={17}/> Alkhidmat support</span><small>Ask about programs, documents, and verification.</small></div><button className="icon-button" onClick={() => setOpen(false)} aria-label="Close support chatbot"><ChevronDown size={18}/></button></header>
      <div className="support-thread" aria-live="polite">
        {!messages.length && <div className="support-empty"><MessageCircle size={30}/><strong>How can I help?</strong><p>I can answer from the available program information in this project.</p><div>{starters.map(text => <button key={text} onClick={() => ask(text)} disabled={busy}>{text}</button>)}</div></div>}
        {messages.map((message, index) => message.role === 'user'
          ? <p key={index} className="support-bubble user">{message.text}</p>
          : <div key={message.id || index} className="support-bubble answer"><p>{message.text || 'Starting reply...'}</p>{message.sources?.slice(0, 2).map((source, i) => <details key={source.id || i}><summary>{source.program_name || 'Source'} [{i + 1}]</summary><p>{source.text}</p></details>)}</div>)}
        {busy && <p className="support-thinking">Replying...</p>}
        <div ref={bottom}/>
      </div>
      {error && <div className="support-error"><span>{error}</span><button aria-label="Dismiss support error" onClick={() => setError('')}><X size={14}/></button></div>}
      <form className="support-compose" onSubmit={event => { event.preventDefault(); ask(question); }}>
        <label className="sr-only" htmlFor="support-question">Ask about Alkhidmat programs</label>
        <input id="support-question" value={question} onChange={event => setQuestion(event.target.value)} placeholder="Ask about programs..." maxLength={1000}/>
        <button aria-label="Send support question" disabled={busy || question.trim().length < 3}><Send size={17}/></button>
      </form>
    </div>}
  </aside>;
}
