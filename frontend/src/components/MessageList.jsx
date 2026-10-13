import React, { useEffect, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {
  Bot,
  User,
  AlertCircle,
  Copy,
  Check,
  Terminal,
  Zap,
  BookOpen,
  Layers,
  RefreshCw,
  X,
  WifiOff,
  Clock,
  Sparkles,
  HelpCircle,
  Wrench,
} from 'lucide-react';

const SUGGESTED_PROMPTS = [
  {
    title: "Graph Traversal",
    prompt: "How do I choose between BFS and DFS for graph and tree problems?",
    icon: Layers,
    tag: "Graphs",
  },
  {
    title: "DP Space Optimization",
    prompt: "Explain 0/1 knapsack space optimization from 2D table to 1D array.",
    icon: Terminal,
    tag: "Dynamic Programming",
  },
  {
    title: "Binary Search on Answer",
    prompt: "What invariant should I maintain in binary search on answer (e.g. Koko Eating Bananas)?",
    icon: Zap,
    tag: "Binary Search",
  },
  {
    title: "Practice Recommendation",
    prompt: "Suggest a curated practice problem for dynamic programming with intuition and complexity.",
    icon: Wrench,
    tag: "Day 5 Tools",
  },
];

// Helper code block with copy button
function CodeBlock({ children, className }) {
  const [copied, setCopied] = React.useState(false);
  const codeText = Array.isArray(children)
    ? children.map((c) => (typeof c === 'string' ? c : '')).join('').replace(/\n$/, '')
    : String(children || '').replace(/\n$/, '');

  const handleCopy = () => {
    navigator.clipboard.writeText(codeText);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const language = className?.replace('language-', '') || 'code';

  return (
    <div className="relative group my-3 rounded-xl overflow-hidden border border-slate-700/60 bg-[#0d1117] shadow-md">
      <div className="flex items-center justify-between px-3.5 py-1.5 bg-slate-800/80 border-b border-slate-700/60 text-xs text-slate-400 font-mono">
        <span className="text-[11px] font-semibold text-slate-300 uppercase tracking-wider">
          {language}
        </span>
        <button
          onClick={handleCopy}
          className="flex items-center gap-1 text-[11px] text-slate-400 hover:text-slate-100 transition-colors px-2 py-0.5 rounded-md hover:bg-slate-700 cursor-pointer"
          title="Copy code"
        >
          {copied ? (
            <>
              <Check className="w-3.5 h-3.5 text-emerald-400" />
              <span className="text-emerald-400 font-medium">Copied</span>
            </>
          ) : (
            <>
              <Copy className="w-3.5 h-3.5" />
              <span>Copy</span>
            </>
          )}
        </button>
      </div>
      <pre className="p-3.5 overflow-x-auto text-xs sm:text-sm font-mono text-slate-200 leading-relaxed scrollbar-thin">
        <code>{codeText}</code>
      </pre>
    </div>
  );
}

export default function MessageList({
  messages,
  isLoading,
  isStreaming,
  error,
  onSelectPrompt,
  onRetry,
  onDismissError,
}) {
  const messagesEndRef = useRef(null);
  const containerRef = useRef(null);

  // Auto-scroll to bottom smoothly when messages update or streaming continues
  useEffect(() => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages, isLoading, isStreaming]);

  const isEmpty = messages.length === 0;

  // Format error display details
  const getErrorDetails = () => {
    if (!error) return null;
    if (typeof error === 'object') {
      return {
        title: error.title || 'Communication Error',
        message: error.message || 'An unexpected error occurred.',
        help: error.help || 'Please check backend logs or try again.',
        type: error.type || 'generic',
      };
    }
    const errStr = String(error);
    if (errStr.includes('429') || errStr.toLowerCase().includes('rate limit') || errStr.toLowerCase().includes('too quickly')) {
      return {
        title: 'Rate Limit Reached (429)',
        message: "You're sending messages too quickly, try again in a minute",
        help: 'Wait a minute for the quota window to reset, then try again.',
        type: 'rate_limit',
      };
    }
    if (errStr.includes('Backend Unreachable') || errStr.includes('Failed to fetch')) {
      return {
        title: 'Backend Unreachable',
        message: 'Could not connect to FastAPI server. Make sure your backend process is running.',
        help: 'Start server: uvicorn backend.main:app --reload --port 8000',
        type: 'network',
      };
    }
    if (errStr.toLowerCase().includes('timeout') || errStr.toLowerCase().includes('timed out')) {
      return {
        title: 'Request Timed Out',
        message: 'The AI service took more than 30 seconds to stream a response.',
        help: 'Check your internet connection or click Retry to resend.',
        type: 'timeout',
      };
    }
    if (errStr.includes('401') || errStr.toLowerCase().includes('api key')) {
      return {
        title: 'Authentication Error (401)',
        message: errStr,
        help: 'Configure GROQ_API_KEY in your .env file.',
        type: 'auth',
      };
    }
    if (errStr.includes('429') || errStr.toLowerCase().includes('rate limit')) {
      return {
        title: 'Rate Limit Reached (429)',
        message: errStr,
        help: 'Wait a few seconds for the quota window to reset.',
        type: 'rate_limit',
      };
    }
    return {
      title: 'Server Error',
      message: errStr,
      help: 'Inspect backend terminal for details or retry.',
      type: 'generic',
    };
  };

  const errorDetails = getErrorDetails();

  return (
    <main
      ref={containerRef}
      className="flex-1 overflow-y-auto px-3 py-4 sm:px-6 md:px-8 space-y-5"
    >
      <div className="max-w-4xl mx-auto space-y-5">
        {/* Empty State for New Conversation */}
        {isEmpty && !isLoading && !error && (
          <div className="py-6 sm:py-12 text-center animate-fadeIn">
            {/* Hero Icon */}
            <div className="inline-flex p-3 sm:p-3.5 rounded-2xl bg-gradient-to-tr from-indigo-600/20 via-indigo-500/10 to-violet-600/20 border border-indigo-500/30 text-indigo-400 mb-4 shadow-xl shadow-indigo-950/30">
              <Bot className="w-8 h-8 sm:w-10 sm:h-10 text-indigo-400" />
            </div>

            {/* Title & Subtitle */}
            <h2 className="text-xl sm:text-3xl font-bold tracking-tight text-white mb-2">
              Competitive Programming & DSA Coach
            </h2>
            <p className="text-slate-400 text-xs sm:text-base max-w-xl mx-auto mb-6 sm:mb-8 leading-relaxed px-2">
              Your algorithmic mentor powered by Groq Llama 3.3, ChromaDB vector RAG, and Day 5 action tools. Ask for step-by-step intuition, edge cases, or complexity breakdowns.
            </p>

            {/* Suggested Starter Prompts */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5 sm:gap-3 text-left max-w-2xl mx-auto">
              {SUGGESTED_PROMPTS.map((item, index) => {
                const IconComponent = item.icon;
                return (
                  <button
                    key={index}
                    onClick={() => onSelectPrompt(item.prompt)}
                    className="p-3 sm:p-3.5 rounded-xl bg-slate-900/70 hover:bg-slate-800/90 border border-slate-800 hover:border-indigo-500/50 text-left transition-all duration-200 group shadow-sm hover:shadow-indigo-500/10 cursor-pointer active:scale-[0.99]"
                  >
                    <div className="flex items-center justify-between mb-1">
                      <div className="flex items-center gap-2">
                        <IconComponent className="w-4 h-4 text-indigo-400 group-hover:text-indigo-300 transition-colors" />
                        <span className="text-xs font-semibold text-slate-200 group-hover:text-white">
                          {item.title}
                        </span>
                      </div>
                      <span className="text-[10px] font-medium px-2 py-0.5 rounded-full bg-slate-800 text-slate-400 group-hover:bg-indigo-950/70 group-hover:text-indigo-300 border border-slate-700/60">
                        {item.tag}
                      </span>
                    </div>
                    <p className="text-xs text-slate-400 group-hover:text-slate-300 line-clamp-2 leading-relaxed">
                      {item.prompt}
                    </p>
                  </button>
                );
              })}
            </div>

            {/* Capabilities Pill Bar */}
            <div className="mt-8 pt-6 border-t border-slate-800/60 flex flex-wrap items-center justify-center gap-2 text-[11px] text-slate-400">
              <span className="px-2.5 py-1 rounded-full bg-slate-900/80 border border-slate-800 flex items-center gap-1.5">
                <BookOpen className="w-3 h-3 text-indigo-400" />
                <span>ChromaDB Vector RAG</span>
              </span>
              <span className="px-2.5 py-1 rounded-full bg-slate-900/80 border border-slate-800 flex items-center gap-1.5">
                <Terminal className="w-3 h-3 text-indigo-400" />
                <span>SQLite Memory</span>
              </span>
              <span className="px-2.5 py-1 rounded-full bg-slate-900/80 border border-slate-800 flex items-center gap-1.5">
                <Zap className="w-3 h-3 text-indigo-400" />
                <span>Streaming Groq Llama 3.3</span>
              </span>
              <span className="px-2.5 py-1 rounded-full bg-slate-900/80 border border-slate-800 flex items-center gap-1.5">
                <Wrench className="w-3 h-3 text-indigo-400" />
                <span>Action Tools</span>
              </span>
            </div>
          </div>
        )}

        {/* Message Turns */}
        {messages.map((msg, index) => {
          const isUser = msg.role === 'user';
          const isLastAssistant =
            !isUser && index === messages.length - 1 && isStreaming;

          return (
            <div
              key={msg.id || index}
              className={`flex items-start gap-2.5 sm:gap-4 ${
                isUser ? 'flex-row-reverse' : 'flex-row'
              } animate-fadeIn`}
            >
              {/* Avatar */}
              <div
                className={`flex-shrink-0 w-8 h-8 sm:w-9 sm:h-9 rounded-xl flex items-center justify-center text-xs font-semibold shadow-md ${
                  isUser
                    ? 'bg-gradient-to-tr from-indigo-500 to-violet-600 text-white shadow-indigo-900/30'
                    : 'bg-slate-800/90 border border-slate-700/80 text-indigo-400 shadow-slate-950/40'
                }`}
              >
                {isUser ? <User className="w-4 h-4" /> : <Bot className="w-4 h-4" />}
              </div>

              {/* Message Bubble */}
              <div
                className={`rounded-2xl px-3.5 py-3 sm:px-4 sm:py-3.5 shadow-md ${
                  isUser
                    ? 'max-w-[88%] sm:max-w-[76%] bg-gradient-to-r from-indigo-600 to-indigo-700 text-white rounded-tr-xs shadow-indigo-950/30'
                    : 'w-full sm:max-w-[94%] md:max-w-[90%] lg:max-w-[88%] bg-slate-900/90 border border-slate-800/90 text-slate-100 rounded-tl-xs shadow-black/20 overflow-hidden'
                }`}
              >
                {/* Header label & RAG sources pill */}
                <div className="flex items-center justify-between gap-2 mb-1.5 flex-wrap">
                  <div
                    className={`text-[11px] font-semibold tracking-wider uppercase ${
                      isUser ? 'text-indigo-200' : 'text-indigo-400'
                    }`}
                  >
                    {isUser ? 'You' : 'Algo Coach'}
                  </div>
                  {!isUser && msg.rag_sources && (
                    <div
                      className="flex items-center gap-1 px-2 py-0.5 rounded-md bg-emerald-500/10 border border-emerald-500/25 text-[10px] text-emerald-300 font-mono"
                      title={`Grounded in notes: ${msg.rag_sources}`}
                    >
                      <BookOpen className="w-2.5 h-2.5 text-emerald-400 shrink-0" />
                      <span className="truncate max-w-[200px] sm:max-w-[320px]">
                        Grounded: {msg.rag_sources}
                      </span>
                      {msg.rag_chunks && (
                        <span className="text-emerald-400/80 shrink-0">
                          ({msg.rag_chunks} chunks)
                        </span>
                      )}
                    </div>
                  )}
                </div>

                {/* Content */}
                {isUser ? (
                  <div className="whitespace-pre-wrap text-sm sm:text-base leading-relaxed break-words font-normal">
                    {msg.content}
                  </div>
                ) : (
                  <div className="prose-dsa text-sm sm:text-base break-words">
                    <ReactMarkdown
                      remarkPlugins={[remarkGfm]}
                      components={{
                        pre({ node, children, ...props }) {
                          if (React.isValidElement(children)) {
                            const codeProps = children.props || {};
                            return (
                              <CodeBlock className={codeProps.className}>
                                {codeProps.children}
                              </CodeBlock>
                            );
                          }
                          return <pre {...props}>{children}</pre>;
                        },
                        code({ node, className, children, ...props }) {
                          return (
                            <code
                              className={`font-mono font-medium text-indigo-300 bg-slate-800/90 px-1.5 py-0.5 rounded-md border border-indigo-500/25 text-[0.875em] break-words ${
                                className || ''
                              }`}
                              {...props}
                            >
                              {children}
                            </code>
                          );
                        },
                        table({ node, children, ...props }) {
                          return (
                            <div className="overflow-x-auto my-3 sm:my-4 rounded-xl border border-slate-700/80 bg-slate-950/60 shadow-lg">
                              <table
                                className="w-full min-w-[520px] border-collapse text-left text-xs sm:text-sm"
                                {...props}
                              >
                                {children}
                              </table>
                            </div>
                          );
                        },
                        thead({ node, children, ...props }) {
                          return (
                            <thead
                              className="bg-slate-800/95 border-b border-slate-700/80 text-slate-100 font-semibold tracking-wide text-xs uppercase"
                              {...props}
                            >
                              {children}
                            </thead>
                          );
                        },
                        tbody({ node, children, ...props }) {
                          return (
                            <tbody
                              className="divide-y divide-slate-800/70"
                              {...props}
                            >
                              {children}
                            </tbody>
                          );
                        },
                        tr({ node, children, ...props }) {
                          return (
                            <tr
                              className="even:bg-slate-900/40 hover:bg-slate-800/35 transition-colors"
                              {...props}
                            >
                              {children}
                            </tr>
                          );
                        },
                        th({ node, children, ...props }) {
                          return (
                            <th
                              className="px-3.5 py-2.5 font-semibold text-slate-100 border-r border-slate-800/60 last:border-r-0 whitespace-nowrap"
                              {...props}
                            >
                              {children}
                            </th>
                          );
                        },
                        td({ node, children, ...props }) {
                          return (
                            <td
                              className="px-3.5 py-2.5 text-slate-300 align-top leading-relaxed border-r border-slate-800/60 last:border-r-0"
                              {...props}
                            >
                              {children}
                            </td>
                          );
                        },
                        hr({ node, ...props }) {
                          return <hr className="my-4 border-slate-800/80" {...props} />;
                        },
                      }}
                    >
                      {msg.content}
                    </ReactMarkdown>

                    {/* Blinking cursor while this message is actively streaming */}
                    {isLastAssistant && <span className="cursor-blink" />}
                  </div>
                )}
              </div>
            </div>
          );
        })}

        {/* Animated Loading / Typing Indicator (Waiting for first streamed token) */}
        {isLoading && (
          <div className="flex items-start gap-2.5 sm:gap-4 animate-fadeIn">
            {/* Avatar with subtle breathing pulse */}
            <div className="flex-shrink-0 w-8 h-8 sm:w-9 sm:h-9 rounded-xl bg-slate-800/90 border border-indigo-500/30 text-indigo-400 flex items-center justify-center shadow-lg shadow-indigo-950/20">
              <Bot className="w-4 h-4 text-indigo-400 animate-pulse" />
            </div>

            {/* Typing Indicator Box */}
            <div className="rounded-2xl rounded-tl-xs px-4 py-3 bg-slate-900/90 border border-slate-800/90 text-slate-300 shadow-md">
              <div className="flex items-center gap-2 mb-1.5">
                <span className="text-[11px] font-semibold text-indigo-400 uppercase tracking-wider">
                  Algo Coach
                </span>
                <span className="text-[10px] text-slate-400 font-mono">thinking</span>
              </div>

              <div className="flex items-center gap-3">
                {/* 3 Bouncing Dots */}
                <div className="flex items-center gap-1.5 py-0.5">
                  <span className="w-2 h-2 rounded-full bg-indigo-400 typing-dot-1" />
                  <span className="w-2 h-2 rounded-full bg-indigo-400 typing-dot-2" />
                  <span className="w-2 h-2 rounded-full bg-indigo-400 typing-dot-3" />
                </div>
                <span className="text-xs sm:text-sm text-slate-400">
                  Formulating algorithmic guidance & retrieving patterns...
                </span>
              </div>
            </div>
          </div>
        )}

        {/* Clear, Readable Error State Display */}
        {errorDetails && (
          <div className="p-4 rounded-xl bg-rose-950/40 border border-rose-800/60 text-rose-200 shadow-lg flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 animate-fadeIn">
            <div className="flex items-start gap-3 min-w-0">
              {errorDetails.type === 'network' ? (
                <WifiOff className="w-5 h-5 text-rose-400 shrink-0 mt-0.5" />
              ) : errorDetails.type === 'timeout' ? (
                <Clock className="w-5 h-5 text-amber-400 shrink-0 mt-0.5" />
              ) : (
                <AlertCircle className="w-5 h-5 text-rose-400 shrink-0 mt-0.5" />
              )}
              <div className="min-w-0">
                <div className="text-sm font-semibold text-rose-200 flex items-center gap-2">
                  <span>{errorDetails.title}</span>
                </div>
                <div className="text-xs text-rose-300/90 mt-1 leading-relaxed break-words">
                  {errorDetails.message}
                </div>
                {errorDetails.help && (
                  <div className="text-[11px] text-rose-400/80 mt-1.5 font-mono bg-rose-950/60 px-2 py-1 rounded-md border border-rose-900/60 inline-block break-all">
                    {errorDetails.help}
                  </div>
                )}
              </div>
            </div>

            {/* Error Actions: Retry & Dismiss */}
            <div className="flex items-center gap-2 self-end sm:self-center shrink-0">
              {onRetry && (
                <button
                  onClick={onRetry}
                  className="px-3 py-1.5 rounded-lg bg-rose-500/20 hover:bg-rose-500/30 text-rose-200 text-xs font-medium border border-rose-500/30 transition-colors flex items-center gap-1.5 cursor-pointer active:scale-95"
                  title="Retry prompt"
                >
                  <RefreshCw className="w-3.5 h-3.5" />
                  <span>Retry</span>
                </button>
              )}
              {onDismissError && (
                <button
                  onClick={onDismissError}
                  className="p-1.5 rounded-lg text-rose-400 hover:text-rose-200 hover:bg-rose-900/40 transition-colors cursor-pointer"
                  title="Dismiss error"
                  aria-label="Dismiss error"
                >
                  <X className="w-4 h-4" />
                </button>
              )}
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>
    </main>
  );
}

