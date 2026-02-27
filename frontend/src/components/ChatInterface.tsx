import { useState, useRef, useEffect } from 'react';
import { Send, Bot, User } from 'lucide-react';
import { ChatMessage } from '../types';

interface ChatInterfaceProps {
  messages: ChatMessage[];
  onSendMessage: (message: string) => void;
}

export function ChatInterface({ messages, onSendMessage }: ChatInterfaceProps) {
  const [input, setInput] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (input.trim()) {
      onSendMessage(input);
      setInput('');
    }
  };

  return (
    <div className="flex flex-col h-full" style={{ backgroundColor: 'var(--white)' }}>
      {/* Chat Header */}
      <div className="p-6 border-b" style={{ borderColor: 'var(--neutral-border)' }}>
        <h3>Academic Advisor</h3>
        <p className="text-sm mt-1" style={{ color: 'var(--neutral-dark)' }}>
          Ask questions about your degree plan
        </p>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-6 space-y-6">
        {messages.map((message, index) => (
          <div
            key={index}
            className="flex gap-4"
            style={{
              flexDirection: message.role === 'user' ? 'row-reverse' : 'row'
            }}
          >
            <div
              className="flex-shrink-0 w-10 h-10 rounded-full flex items-center justify-center"
              style={{
                backgroundColor: message.role === 'assistant' ? 'var(--navy-blue)' : 'var(--academic-gold)'
              }}
            >
              {message.role === 'assistant' ? (
                <Bot className="w-5 h-5" style={{ color: 'var(--white)' }} />
              ) : (
                <User className="w-5 h-5" style={{ color: 'var(--white)' }} />
              )}
            </div>
            <div
              className="flex-1 max-w-2xl rounded-lg p-4"
              style={{
                backgroundColor: message.role === 'assistant' ? 'var(--neutral-gray)' : 'var(--navy-blue)',
                color: message.role === 'assistant' ? 'var(--neutral-dark)' : 'var(--white)'
              }}
            >
              <p style={{ margin: 0, whiteSpace: 'pre-wrap' }}>{message.content}</p>
            </div>
          </div>
        ))}
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="p-6 border-t" style={{ borderColor: 'var(--neutral-border)' }}>
        <form onSubmit={handleSubmit} className="flex gap-3">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask about your degree plan..."
            className="flex-1 px-4 py-3 rounded-lg border-2 transition-colors"
            style={{
              borderColor: 'var(--neutral-border)',
              backgroundColor: 'var(--white)',
              color: 'var(--neutral-dark)'
            }}
          />
          <button
            type="submit"
            disabled={!input.trim()}
            className="px-6 py-3 rounded-lg flex items-center gap-2 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
            style={{
              backgroundColor: 'var(--navy-blue)',
              color: 'var(--white)'
            }}
          >
            <Send className="w-5 h-5" />
          </button>
        </form>
        
        {/* Quick Questions */}
        <div className="mt-4 flex flex-wrap gap-2">
          <button
            onClick={() => onSendMessage("Why is this course recommended?")}
            className="px-3 py-2 rounded-md text-sm border transition-all hover:shadow-sm"
            style={{
              borderColor: 'var(--neutral-border)',
              backgroundColor: 'var(--white)',
              color: 'var(--neutral-dark)'
            }}
          >
            Why is this course recommended?
          </button>
          <button
            onClick={() => onSendMessage("Can I graduate early?")}
            className="px-3 py-2 rounded-md text-sm border transition-all hover:shadow-sm"
            style={{
              borderColor: 'var(--neutral-border)',
              backgroundColor: 'var(--white)',
              color: 'var(--neutral-dark)'
            }}
          >
            Can I graduate early?
          </button>
          <button
            onClick={() => onSendMessage("What happens if I add a minor in Economics?")}
            className="px-3 py-2 rounded-md text-sm border transition-all hover:shadow-sm"
            style={{
              borderColor: 'var(--neutral-border)',
              backgroundColor: 'var(--white)',
              color: 'var(--neutral-dark)'
            }}
          >
            What if I add a minor?
          </button>
        </div>
      </div>
    </div>
  );
}
