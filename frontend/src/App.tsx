/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useState, useRef, useEffect } from 'react';
import { Send, Bot, User, Loader2 } from 'lucide-react';
import { motion, AnimatePresence } from 'motion/react';
import ReactMarkdown from 'react-markdown';
import { sendMessageStream, ChatMessage as ApiChatMessage } from './services/gemini';
import { cn } from './lib/utils';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
}

const EXAMPLES = [
  'Python 백엔드 개발자 채용 공고 알려줘',
  'AI 엔지니어에게 요구하는 기술 스택은?',
  'FastAPI 경험을 요구하는 회사는?',
  '경력 1~3년차가 지원할 수 있는 공고는?',
];

export default function App() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  const handleSend = async (text?: string) => {
    const msg = text || input.trim();
    if (!msg || isLoading) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: msg,
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput('');
    setIsLoading(true);

    const assistantId = (Date.now() + 1).toString();
    setMessages((prev) => [...prev, { id: assistantId, role: 'assistant', content: '' }]);

    const history: ApiChatMessage[] = messages.map((m) => ({
      role: m.role,
      content: m.content,
    }));

    try {
      await sendMessageStream(msg, history, (token) => {
        setIsLoading(false);
        setMessages((prev) =>
          prev.map((m) => (m.id === assistantId ? { ...m, content: m.content + token } : m))
        );
      });
    } catch {
      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantId
            ? { ...m, content: '서버와 통신 중 오류가 발생했습니다. FastAPI 서버가 실행 중인지 확인해주세요.' }
            : m
        )
      );
    } finally {
      setIsLoading(false);
    }
  };

  const hasMessages = messages.length > 0;

  return (
    <div className="relative h-screen w-full bg-black overflow-hidden font-sans">
      {/* Background: Full-screen 3D Spline Viewer */}
      <div className="absolute inset-0 z-0">
        <iframe
          src="https://my.spline.design/r4xbot-CWSKBb2QUFGmYraRgMAVk2lK/"
          frameBorder="0"
          width="100%"
          height="100%"
          title="3D Robot Model"
        />
      </div>

      {/* Top Left: Logo & Branding */}
      <div className="absolute top-8 left-8 z-20 pointer-events-none">
        <motion.div
          initial={{ opacity: 0, x: -20 }}
          animate={{ opacity: 1, x: 0 }}
          className="space-y-1"
        >
          <h1 className="text-3xl font-display font-black tracking-tighter text-white drop-shadow-lg">
            JOB<span className="text-blue-500">BOT</span>
          </h1>
          <div className="flex items-center gap-2 bg-black/20 backdrop-blur-sm px-3 py-1 rounded-full border border-white/10 w-fit">
            <div className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
            <p className="text-[10px] font-bold uppercase tracking-widest text-white/70">
              System Active
            </p>
          </div>
        </motion.div>
      </div>

      {/* Right Side: Chat Panel */}
      <motion.div
        initial={{ opacity: 0, x: 40 }}
        animate={{ opacity: 1, x: 0 }}
        transition={{ delay: 0.3 }}
        className="absolute top-6 right-6 bottom-6 z-20 w-[420px] flex flex-col rounded-2xl overflow-hidden border border-white/10 bg-black/40 backdrop-blur-2xl shadow-2xl"
      >
        {/* Chat Header */}
        <div className="flex items-center gap-3 px-5 py-4 border-b border-white/10">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-blue-500 to-cyan-500 flex items-center justify-center">
            <Bot className="w-5 h-5 text-white" />
          </div>
          <div>
            <h3 className="text-sm font-bold text-white">JobBot</h3>
            <div className="flex items-center gap-1.5">
              <div className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
              <span className="text-[10px] text-emerald-400 font-semibold">온라인</span>
            </div>
          </div>
        </div>

        {/* Chat Messages */}
        <div ref={scrollRef} className="flex-1 overflow-y-auto p-4 space-y-4 chat-scroll-area">
          {!hasMessages && (
            <div className="flex flex-col items-center justify-center h-full gap-5">
              <div className="text-center space-y-2">
                <p className="text-white/40 text-xs font-semibold uppercase tracking-widest">
                  무엇이 궁금하신가요?
                </p>
              </div>
              <div className="w-full space-y-2">
                {EXAMPLES.map((ex, i) => (
                  <button
                    key={i}
                    onClick={() => handleSend(ex)}
                    className="w-full text-left px-4 py-3 rounded-xl bg-white/5 border border-white/10 text-white/70 text-sm hover:bg-white/10 hover:border-blue-500/30 hover:text-white transition-all duration-200"
                  >
                    💬 {ex}
                  </button>
                ))}
              </div>
            </div>
          )}

          <AnimatePresence>
            {messages.map((msg) => (
              <motion.div
                key={msg.id}
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ type: 'spring', stiffness: 300, damping: 24 }}
                className={cn(
                  'flex gap-2.5',
                  msg.role === 'user' ? 'flex-row-reverse' : 'flex-row'
                )}
              >
                <div
                  className={cn(
                    'w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0 mt-1',
                    msg.role === 'assistant'
                      ? 'bg-gradient-to-br from-blue-500 to-cyan-500'
                      : 'bg-white/10'
                  )}
                >
                  {msg.role === 'assistant' ? (
                    <Bot className="w-4 h-4 text-white" />
                  ) : (
                    <User className="w-4 h-4 text-white/70" />
                  )}
                </div>
                <div
                  className={cn(
                    'max-w-[85%] px-4 py-3 rounded-2xl text-sm leading-relaxed',
                    msg.role === 'user'
                      ? 'bg-blue-600 text-white rounded-br-md'
                      : 'bg-white/10 text-white/90 rounded-bl-md'
                  )}
                >
                  <div className="prose prose-sm prose-invert max-w-none [&>p]:m-0 [&>ul]:mt-1 [&>ul]:mb-0 [&>hr]:my-2 [&>hr]:border-white/10">
                    <ReactMarkdown>{msg.content}</ReactMarkdown>
                  </div>
                </div>
              </motion.div>
            ))}
          </AnimatePresence>

          {isLoading && messages[messages.length - 1]?.content === '' && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="flex gap-2.5"
            >
              <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-blue-500 to-cyan-500 flex items-center justify-center flex-shrink-0">
                <Bot className="w-4 h-4 text-white" />
              </div>
              <div className="bg-white/10 px-4 py-3 rounded-2xl rounded-bl-md flex items-center gap-2">
                <Loader2 className="w-4 h-4 text-blue-400 animate-spin" />
                <span className="text-xs text-white/40">답변 생성 중...</span>
              </div>
            </motion.div>
          )}
        </div>

        {/* Chat Input */}
        <div className="p-4 border-t border-white/10">
          <div className="flex items-center gap-2 bg-white/5 border border-white/10 rounded-xl p-1.5 focus-within:border-blue-500/40 transition-colors">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSend()}
              placeholder="채용 공고에 대해 질문하세요..."
              className="flex-1 bg-transparent border-none px-3 py-2.5 text-white placeholder:text-white/30 outline-none text-sm"
            />
            <button
              onClick={() => handleSend()}
              disabled={!input.trim() || isLoading}
              className={cn(
                'p-2.5 rounded-lg transition-all duration-200',
                input.trim() && !isLoading
                  ? 'bg-blue-600 text-white shadow-lg shadow-blue-500/30 hover:bg-blue-500'
                  : 'bg-white/5 text-white/20 cursor-not-allowed'
              )}
            >
              <Send className="w-4 h-4" />
            </button>
          </div>
        </div>
      </motion.div>

      {/* Bottom Left: Branding */}
      <div className="absolute bottom-8 left-8 z-20 hidden lg:block pointer-events-none">
        <div className="flex flex-col gap-2">
          <div className="h-px w-12 bg-white/20" />
          <p className="text-[10px] font-mono text-white/30 tracking-widest">JOBBOT</p>
        </div>
      </div>
    </div>
  );
}
