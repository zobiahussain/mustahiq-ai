import { useEffect, useRef, useState } from "react";
import { getMatchMessages, sendMatchMessage, connectMatch, getMatchContact } from "./api.js";
import Header from "./Header.jsx";

// Added 5 Sep 2026 -- direct request: "there should be a chat within
// the marketplace... as soon as you feel like you already established
// something, then they can call." Simple REST polling (every 4s), not
// websockets -- matches this project's "no paid infra, free tier only"
// constraint (CLAUDE.md), and a match conversation is low-volume enough
// that polling is genuinely fine, not a corner cut.
//
// Phone numbers are NEVER shown until BOTH the match exists AND someone
// has explicitly tapped "We're connected" -- see messaging.py's
// get_contact_info() docstring for why that's a deliberate person's
// decision, not an automatic threshold.

const POLL_MS = 4000;

export default function Chat({ token, matchId, otherBusinessName, onBack }) {
  const [messages, setMessages] = useState(null);
  const [body, setBody] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState(null);
  const [contact, setContact] = useState(null);
  const [connecting, setConnecting] = useState(false);
  const bottomRef = useRef(null);

  async function loadMessages() {
    try {
      const res = await getMatchMessages(token, matchId);
      setMessages(res.messages);
    } catch (err) {
      setError(err.message);
    }
  }

  async function loadContact() {
    try {
      const c = await getMatchContact(token, matchId);
      setContact(c);
    } catch {
      // 404 just means "not connected yet" -- not an error state worth
      // showing, the "We're connected" button below covers it.
      setContact(null);
    }
  }

  useEffect(() => {
    loadMessages();
    loadContact();
    const interval = setInterval(loadMessages, POLL_MS);
    return () => clearInterval(interval);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [matchId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function handleSend(e) {
    e.preventDefault();
    if (!body.trim()) return;
    setSending(true);
    setError(null);
    try {
      await sendMatchMessage(token, matchId, body.trim());
      setBody("");
      await loadMessages();
    } catch (err) {
      setError(err.message);
    } finally {
      setSending(false);
    }
  }

  async function handleConnect() {
    setConnecting(true);
    setError(null);
    try {
      await connectMatch(token, matchId);
      await loadContact();
    } catch (err) {
      setError(err.message);
    } finally {
      setConnecting(false);
    }
  }

  return (
    <div className="page">
      <Header subtitle={otherBusinessName || "Chat"} subtitleUr="بات چیت" />

      {contact ? (
        <div className="card" style={{ padding: 14, marginBottom: 16 }}>
          <div style={{ fontSize: 13, color: "var(--color-ink-soft)" }}>You're connected --</div>
          <div style={{ fontWeight: 600 }}>{contact.full_name}</div>
          <a href={`tel:${contact.phone}`} className="btn btn-accent" style={{ marginTop: 8, display: "inline-block" }}>
            📞 {contact.phone}
          </a>
        </div>
      ) : (
        <div className="card" style={{ padding: 14, marginBottom: 16 }}>
          <p className="card-subtext" style={{ margin: "0 0 8px" }}>
            Talk here first -- once you feel like you've actually got something going, share
            contact to move to a call.
            <span className="ur" style={{ display: "block", marginTop: 2 }}>
              پہلے یہاں بات کریں -- جب لگے کہ بات بن گئی ہے تو رابطہ شیئر کریں۔
            </span>
          </p>
          <button className="btn btn-secondary" disabled={connecting} onClick={handleConnect}>
            {connecting ? "..." : "We're connected -- share contact"}{" "}
            <span style={{ fontFamily: "var(--font-ur)" }}>رابطہ شیئر کریں</span>
          </button>
        </div>
      )}

      {error && <div className="error-banner">{error}</div>}

      <div className="chat-thread">
        {messages === null && <div className="skeleton" />}
        {messages && messages.length === 0 && (
          <p style={{ color: "var(--color-ink-soft)", fontSize: 14 }}>
            No messages yet -- say hello.
          </p>
        )}
        {messages && messages.map((m) => (
          <div key={m.id} className={`chat-bubble ${m.is_mine ? "chat-bubble-mine" : ""}`}>
            {m.body}
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      <form onSubmit={handleSend} className="chat-input-row">
        <input
          className="input"
          value={body}
          onChange={(e) => setBody(e.target.value)}
          placeholder="Type a message..."
          dir="auto"
        />
        <button className="btn btn-primary" type="submit" disabled={sending || !body.trim()}>
          Send <span style={{ fontFamily: "var(--font-ur)" }}>بھیجیں</span>
        </button>
      </form>

      <button className="btn btn-secondary" style={{ marginTop: 12 }} onClick={onBack}>
        Back <span style={{ fontFamily: "var(--font-ur)" }}>پیچھے</span>
      </button>
    </div>
  );
}
