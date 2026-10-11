import React, { useContext, useEffect, useRef, useState } from 'react';
import { v4 as uuidv4 } from 'uuid';
import { FireRiskContext } from '../context/FireRiskContext';
import apiService from '../services/apiService';
import { ChatMessage } from '../types';

interface ChatPanelProps {
  isOpen: boolean;
  onClose: () => void;
}

const GREETING =
  'Ask me about fire danger, smoke and air quality for the place you have selected on the map, or about wildfire safety in general.';

const ChatPanel: React.FC<ChatPanelProps> = ({ isOpen, onClose }) => {
  const { focus } = useContext(FireRiskContext);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);
  const sessionId = useRef(`session-${Date.now()}`);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  useEffect(() => {
    if (isOpen && messages.length === 0) {
      setMessages([{ id: uuidv4(), role: 'assistant', content: GREETING, timestamp: new Date().toISOString() }]);
    }
  }, [isOpen, messages.length]);

  const send = async () => {
    const text = input.trim();
    if (!text || isLoading) return;
    setMessages(prev => [...prev, { id: uuidv4(), role: 'user', content: text, timestamp: new Date().toISOString() }]);
    setInput('');
    setIsLoading(true);
    try {
      const res = await apiService.sendChatMessage(text, sessionId.current, focus);
      setMessages(prev => [...prev, {
        id: uuidv4(), role: 'assistant', content: res.response, sources: res.sources, timestamp: new Date().toISOString(),
      }]);
    } catch (e: any) {
      setMessages(prev => [...prev, {
        id: uuidv4(), role: 'assistant', content: `${e.message} Try again in a moment.`, timestamp: new Date().toISOString(),
      }]);
    } finally {
      setIsLoading(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed right-0 top-0 z-50 flex h-full w-full flex-col bg-white shadow-2xl sm:w-96" role="dialog" aria-label="Wildfire assistant">
      <div className="flex items-start justify-between bg-gray-900 p-4 text-white">
        <div>
          <h2 className="text-lg font-semibold">Wildfire assistant</h2>
          {focus && <p className="text-xs text-white/70">Asking about: {focus.name}</p>}
        </div>
        <button onClick={onClose} aria-label="Close assistant" className="rounded p-1 hover:bg-white/20 focus:outline-none focus:ring-2 focus:ring-orange-400">
          ✕
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-4">
        {messages.map(m => (
          <div key={m.id} className={`mb-4 ${m.role === 'user' ? 'text-right' : 'text-left'}`}>
            <div className={`inline-block max-w-[85%] rounded-lg p-3 text-left ${m.role === 'user' ? 'bg-orange-600 text-white' : 'bg-gray-100 text-gray-800'}`}>
              <p className="whitespace-pre-wrap text-sm">{m.content}</p>
              {m.sources && m.sources.length > 0 && (
                <p className="mt-2 text-xs text-gray-500">Sources: {m.sources.join('; ')}</p>
              )}
            </div>
          </div>
        ))}
        {isLoading && <p className="text-sm text-gray-500">Checking current conditions…</p>}
        <div ref={endRef} />
      </div>

      <div className="border-t p-4">
        <div className="flex gap-2">
          <label htmlFor="chat-input" className="sr-only">Message</label>
          <input
            id="chat-input"
            type="text"
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter') send(); }}
            placeholder="Is it safe to be outside today?"
            className="flex-1 rounded-lg border border-gray-300 px-3 py-2 focus:outline-none focus:ring-2 focus:ring-orange-500"
            disabled={isLoading}
          />
          <button
            onClick={send}
            disabled={isLoading || !input.trim()}
            className="rounded-lg bg-orange-600 px-4 py-2 font-medium text-white hover:bg-orange-700 focus:outline-none focus:ring-2 focus:ring-orange-400 disabled:opacity-50"
          >
            Send
          </button>
        </div>
      </div>
    </div>
  );
};

export default ChatPanel;
