import React, { useState, useRef, useEffect, useCallback } from 'react';
import MessageList from './MessageList';
import MessageInput from './MessageInput';
import Sidebar from './Sidebar';
import GoogleAuthModal, { GoogleLogo } from './GoogleAuthModal';
import PersonalizationModal from './PersonalizationModal';
import UpgradeModal from './UpgradeModal';
import SettingsModal from './SettingsModal';
import { Terminal, Trash2, PanelLeft, Plus, Loader2, BookOpen } from 'lucide-react';
import { API_BASE_URL } from '../config';

const DEFAULT_ACCOUNTS = [
  {
    id: 'acc-1',
    name: 'Aditya Patel',
    email: 'pateladityanov.25@gmail.com',
    initials: 'AP',
    plan: 'Go',
    avatarColor: 'bg-emerald-600',
  },
  {
    id: 'acc-2',
    name: 'Aditya Patel',
    email: 'pateladityanov.2005@gmail.com',
    initials: 'AP',
    plan: 'Go',
    avatarColor: 'bg-teal-600',
  },
];

export default function ChatWindow() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isStreaming, setIsStreaming] = useState(false);
  const [isLoadingHistory, setIsLoadingHistory] = useState(false);
  const [error, setError] = useState(null);
  const [backendStatus, setBackendStatus] = useState('checking'); // 'online' | 'offline' | 'checking'
  const [ragInfo, setRagInfo] = useState(null);

  // Google Authentication & Account Switcher State
  const [accounts, setAccounts] = useState(() => {
    try {
      const saved = localStorage.getItem('personal_ai_accounts');
      if (saved) return JSON.parse(saved);
    } catch {}
    return DEFAULT_ACCOUNTS;
  });

  const [currentUser, setCurrentUser] = useState(() => {
    try {
      const saved = localStorage.getItem('personal_ai_active_user');
      if (saved) return JSON.parse(saved);
    } catch {}
    return DEFAULT_ACCOUNTS[0];
  });

  const [showGoogleModal, setShowGoogleModal] = useState(false);
  const [showPersonalizationModal, setShowPersonalizationModal] = useState(false);
  const [showSettingsModal, setShowSettingsModal] = useState(false);
  const [showUpgradeModal, setShowUpgradeModal] = useState(false);

  const handleSelectAccount = (acc) => {
    setCurrentUser(acc);
    localStorage.setItem('personal_ai_active_user', JSON.stringify(acc));
  };

  const handleAddAccount = (newAcc) => {
    setAccounts((prev) => {
      const updated = [...prev.filter((a) => a.email !== newAcc.email), newAcc];
      localStorage.setItem('personal_ai_accounts', JSON.stringify(updated));
      return updated;
    });
    handleSelectAccount(newAcc);
  };

  const handleLogout = () => {
    setCurrentUser(null);
    localStorage.removeItem('personal_ai_active_user');
    setShowGoogleModal(true);
  };

  // Conversation Management State
  const [conversations, setConversations] = useState([]);
  const [activeConversationId, setActiveConversationId] = useState(() => {
    return localStorage.getItem('personal_ai_active_conv') || null;
  });
  const [sidebarOpen, setSidebarOpen] = useState(() => {
    if (typeof window !== 'undefined') {
      return window.innerWidth >= 1024;
    }
    return false;
  });

  const abortControllerRef = useRef(null);
  const lastPromptRef = useRef('');

  // 1. Fetch conversations from backend
  const fetchConversations = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/conversations`);
      if (res.ok) {
        const data = await res.json();
        setConversations(data);
        return data;
      }
    } catch (err) {
      console.error('Failed to fetch conversations:', err);
    }
    return [];
  }, []);

  // 2. Load messages for a specific conversation
  const loadConversationMessages = useCallback(async (conversationId) => {
    if (!conversationId) {
      setMessages([]);
      return;
    }
    setIsLoadingHistory(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE_URL}/conversations/${conversationId}`);
      if (res.ok) {
        const data = await res.json();
        const formattedMessages = (data.messages || []).map((m) => ({
          id: m.id,
          role: m.role,
          content: m.content,
          created_at: m.created_at,
        }));
        setMessages(formattedMessages);
      } else if (res.status === 404) {
        // Conversation not found on backend (e.g. wiped or deleted)
        localStorage.removeItem('personal_ai_active_conv');
        setActiveConversationId(null);
        setMessages([]);
      }
    } catch (err) {
      console.error('Failed to load conversation history:', err);
      setError('Failed to load conversation history from database.');
    } finally {
      setIsLoadingHistory(false);
    }
  }, []);

  // 3. Check backend health periodically or on mount
  useEffect(() => {
    let isMounted = true;
    const checkHealth = async () => {
      try {
        const res = await fetch(`${API_BASE_URL}/`, { method: 'GET' });
        if (res.ok && isMounted) {
          setBackendStatus('online');
        } else if (isMounted) {
          setBackendStatus('offline');
        }
      } catch {
        if (isMounted) {
          setBackendStatus('offline');
        }
      }
    };

    checkHealth();
    const interval = setInterval(checkHealth, 15000);
    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, []);

  // 3b. Fetch RAG vector store status
  const fetchRagStatus = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/rag/status`);
      if (res.ok) {
        const data = await res.json();
        setRagInfo(data);
      }
    } catch (err) {
      console.error('Failed to fetch RAG status:', err);
    }
  }, []);

  // 4. Initial load: fetch conversations and restore active conversation
  useEffect(() => {
    const initData = async () => {
      fetchRagStatus();
      const convList = await fetchConversations();
      const savedConvId = localStorage.getItem('personal_ai_active_conv');

      if (savedConvId && convList.some((c) => c.id === savedConvId)) {
        setActiveConversationId(savedConvId);
        loadConversationMessages(savedConvId);
      } else if (convList.length > 0) {
        // Default to the most recent conversation if present
        const mostRecent = convList[0];
        setActiveConversationId(mostRecent.id);
        localStorage.setItem('personal_ai_active_conv', mostRecent.id);
        loadConversationMessages(mostRecent.id);
      } else {
        // Start fresh
        setActiveConversationId(null);
        setMessages([]);
      }
    };

    initData();
  }, [fetchConversations, loadConversationMessages]);

  // 5. Switching conversations
  const handleSelectConversation = (conversationId) => {
    if (conversationId === activeConversationId) return;
    if (isLoading || isStreaming) {
      handleStop();
    }
    setActiveConversationId(conversationId);
    localStorage.setItem('personal_ai_active_conv', conversationId);
    loadConversationMessages(conversationId);
    if (window.innerWidth < 1024) {
      setSidebarOpen(false);
    }
  };

  // 6. Creating a fresh "New Chat"
  const handleNewChat = () => {
    if (isLoading || isStreaming) {
      handleStop();
    }
    setActiveConversationId(null);
    localStorage.removeItem('personal_ai_active_conv');
    setMessages([]);
    setError(null);
    if (window.innerWidth < 1024) {
      setSidebarOpen(false);
    }
  };

  // 7. Deleting a conversation
  const handleDeleteConversation = async (conversationId) => {
    try {
      const res = await fetch(`${API_BASE_URL}/conversations/${conversationId}`, {
        method: 'DELETE',
      });
      if (res.ok) {
        setConversations((prev) => prev.filter((c) => c.id !== conversationId));
        if (activeConversationId === conversationId) {
          handleNewChat();
        }
      }
    } catch (err) {
      console.error('Failed to delete conversation:', err);
    }
    if (window.innerWidth < 1024) {
      setSidebarOpen(false);
    }
  };

  // 8. Sending a message with persistent conversation memory & 30s timeout
  const handleSendMessage = async (textToSend) => {
    const trimmed = textToSend.trim();
    if (!trimmed || isLoading || isStreaming) return;

    setError(null);
    lastPromptRef.current = trimmed;
    setInput('');

    // Generate unique IDs for local optimistic rendering
    const userMessageId = `user-${Date.now()}`;
    const assistantMessageId = `ai-${Date.now()}`;

    // Add user message to conversation list optimistically
    const updatedMessages = [
      ...messages,
      { id: userMessageId, role: 'user', content: trimmed },
    ];
    setMessages(updatedMessages);

    // Initial loading state while waiting for the first token
    setIsLoading(true);
    setIsStreaming(false);

    // Prepare abort controller for cancellation
    const controller = new AbortController();
    abortControllerRef.current = controller;

    // 30-second timeout for first token/response
    let timeoutTriggered = false;
    const timeoutId = setTimeout(() => {
      timeoutTriggered = true;
      try {
        controller.abort('timeout');
      } catch {
        controller.abort();
      }
    }, 30000);

    try {
      const response = await fetch(`${API_BASE_URL}/chat`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          message: trimmed,
          conversation_id: activeConversationId || undefined,
        }),
        signal: controller.signal,
      });

      clearTimeout(timeoutId);

      if (!response.ok) {
        let errorDetail = `HTTP ${response.status} ${response.statusText}`;
        try {
          const errorJson = await response.json();
          if (errorJson?.detail) {
            if (typeof errorJson.detail === 'string') {
              errorDetail = errorJson.detail;
            } else if (Array.isArray(errorJson.detail)) {
              errorDetail = errorJson.detail.map((d) => d.msg || JSON.stringify(d)).join('; ');
            } else {
              errorDetail = JSON.stringify(errorJson.detail);
            }
          }
        } catch {
          // If response body is not JSON, leave errorDetail as is
        }

        let errorTitle = `AI Provider Error (HTTP ${response.status})`;
        let helpText = 'Please check backend logs or retry.';
        if (response.status === 400 || response.status === 422) {
          errorTitle = `Request Validation Error (${response.status})`;
          helpText = 'Ensure your message is not empty or malformed.';
        } else if (response.status === 401) {
          errorTitle = 'Invalid API Key (401)';
          helpText = 'Check GROQ_API_KEY in your .env file.';
        } else if (response.status === 429) {
          errorTitle = 'Rate Limit Reached (429)';
          errorDetail = "You're sending messages too quickly, try again in a minute";
          helpText = 'Please wait a minute before sending your next message.';
        } else if (response.status >= 500) {
          errorTitle = `Server Internal Error (${response.status})`;
          helpText = 'Inspect your FastAPI terminal console for the traceback.';
        }

        throw {
          title: errorTitle,
          message: errorDetail,
          help: helpText,
          type: response.status === 429 ? 'rate_limit' : 'server',
          status: response.status,
        };
      }

      // Read active conversation ID and RAG source headers
      const returnedConvId = response.headers.get('X-Conversation-Id');
      const ragSources = response.headers.get('X-Rag-Sources');
      const ragChunks = response.headers.get('X-Rag-Chunks');

      if (returnedConvId && returnedConvId !== activeConversationId) {
        setActiveConversationId(returnedConvId);
        localStorage.setItem('personal_ai_active_conv', returnedConvId);
      }

      if (!response.body) {
        throw new Error('ReadableStream not supported or empty response body from backend.');
      }

      // Stream handling setup
      const reader = response.body.getReader();
      const decoder = new TextDecoder('utf-8');

      let accumulatedContent = '';
      let isFirstChunk = true;

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunkText = decoder.decode(value, { stream: true });
        if (!chunkText) continue;

        if (isFirstChunk) {
          // First token received! Switch from loading spinner to active streaming
          isFirstChunk = false;
          setIsLoading(false);
          setIsStreaming(true);

          accumulatedContent += chunkText;
          setMessages([
            ...updatedMessages,
            {
              id: assistantMessageId,
              role: 'assistant',
              content: accumulatedContent,
              rag_sources: ragSources,
              rag_chunks: ragChunks,
            },
          ]);
        } else {
          accumulatedContent += chunkText;
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === assistantMessageId
                ? {
                    ...msg,
                    content: accumulatedContent,
                    rag_sources: ragSources,
                    rag_chunks: ragChunks,
                  }
                : msg
            )
          );
        }
      }

      // Flush decoder
      const finalChunk = decoder.decode();
      if (finalChunk) {
        accumulatedContent += finalChunk;
        setMessages((prev) =>
          prev.map((msg) =>
            msg.id === assistantMessageId
              ? {
                  ...msg,
                  content: accumulatedContent,
                  rag_sources: ragSources,
                  rag_chunks: ragChunks,
                }
              : msg
          )
        );
      }

      setBackendStatus('online');
      // Refresh sidebar conversations to display updated title / timestamps
      fetchConversations();
    } catch (err) {
      clearTimeout(timeoutId);
      const isTimeout =
        timeoutTriggered ||
        (controller && controller.signal?.reason === 'timeout') ||
        (err && String(err.message || '').toLowerCase().includes('timeout'));

      if (err.name === 'AbortError' && !isTimeout) {
        console.log('Stream aborted by user');
      } else if (isTimeout) {
        console.warn('Chat request timed out after 30s');
        setError({
          title: 'Request Timed Out (30s)',
          message: 'The AI coach took longer than 30 seconds to stream a response.',
          help: 'Check your internet connection or verify the backend is running, then click Retry.',
          type: 'timeout',
        });
      } else if (err.type === 'server' || err.type === 'rate_limit' || err.status === 429) {
        setError(err);
      } else if (
        err instanceof TypeError ||
        String(err.message || '').includes('Failed to fetch') ||
        String(err.message || '').includes('NetworkError')
      ) {
        console.error('Backend unreachable:', err);
        setError({
          title: 'Backend Unreachable',
          message: `Could not connect to FastAPI server at ${API_BASE_URL}. Ensure the backend is running.`,
          help: `Verify that ${API_BASE_URL} is online, or start your local server: uvicorn backend.main:app --reload --port 8000`,
          type: 'network',
        });
        setBackendStatus('offline');
      } else {
        console.error('Chat error:', err);
        setError({
          title: 'Communication Error',
          message: err.message || 'An unexpected error occurred while communicating with the server.',
          help: 'Inspect browser console or backend terminal logs.',
          type: 'generic',
        });
      }
    } finally {
      clearTimeout(timeoutId);
      setIsLoading(false);
      setIsStreaming(false);
      abortControllerRef.current = null;
    }
  };

  const handleStop = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
      setIsLoading(false);
      setIsStreaming(false);
      // Refresh conversations to reflect saved partial output
      fetchConversations();
    }
  };

  const handleRetry = () => {
    if (lastPromptRef.current) {
      handleSendMessage(lastPromptRef.current);
    }
  };

  // Find active conversation title for header
  const activeConversation = conversations.find((c) => c.id === activeConversationId);

  return (
    <div className="flex h-screen w-full bg-[#0b0f17] text-slate-100 antialiased overflow-hidden">
      {/* Sidebar: Past conversations and New Chat */}
      <Sidebar
        conversations={conversations}
        activeConversationId={activeConversationId}
        onSelectConversation={handleSelectConversation}
        onNewChat={handleNewChat}
        onDeleteConversation={handleDeleteConversation}
        isOpen={sidebarOpen}
        onToggleOpen={() => setSidebarOpen((prev) => !prev)}
        user={currentUser}
        accounts={accounts}
        onSelectAccount={handleSelectAccount}
        onOpenGoogleLogin={() => setShowGoogleModal(true)}
        onLogout={handleLogout}
        onOpenPersonalization={() => setShowPersonalizationModal(true)}
        onOpenSettings={() => setShowSettingsModal(true)}
        onOpenUpgrade={() => setShowUpgradeModal(true)}
      />

      {/* Main Chat Area */}
      <div className="flex flex-col flex-1 h-full min-w-0 overflow-hidden">
        {/* Top Header */}
        <header className="w-full bg-[#0f1422]/90 backdrop-blur-md border-b border-slate-800/80 px-4 py-3 sm:px-6 flex items-center justify-between z-10 shrink-0">
          <div className="flex items-center gap-3 min-w-0">
            {/* Sidebar toggle button */}
            <button
              onClick={() => setSidebarOpen((prev) => !prev)}
              className="p-2 rounded-xl text-slate-400 hover:text-slate-100 hover:bg-slate-800/80 border border-slate-800 transition-colors cursor-pointer"
              title="Toggle sidebar history"
              aria-label="Toggle sidebar"
            >
              <PanelLeft className="w-4 h-4" />
            </button>

            <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-indigo-600 via-indigo-500 to-violet-500 p-0.5 flex items-center justify-center shadow-lg shadow-indigo-900/30 shrink-0">
              <div className="w-full h-full bg-slate-950 rounded-[10px] flex items-center justify-center">
                <Terminal className="w-4 h-4 text-indigo-400" />
              </div>
            </div>

            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <h1 className="text-base sm:text-lg font-bold tracking-tight text-white m-0 p-0 leading-tight truncate">
                  {activeConversation?.title || 'AlgoCoach AI'}
                </h1>
                <span className="text-[10px] font-semibold uppercase tracking-wider px-2 py-0.5 rounded-full bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 shrink-0">
                  Day 4 RAG + Memory
                </span>
              </div>
              <p className="text-xs text-slate-400 truncate hidden sm:block">
                {activeConversation
                  ? 'ChromaDB Knowledge Base & Persistent SQLite Memory'
                  : 'Competitive Programming & DSA Mentorship'}
              </p>
            </div>
          </div>

          {/* Status indicator & Actions */}
          <div className="flex items-center gap-2 sm:gap-3 shrink-0">
            {/* RAG Knowledge Base Status Pill */}
            <div
              className="hidden lg:flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-mono border bg-indigo-950/40 text-indigo-300 border-indigo-800/50"
              title={`ChromaDB Vector Store: ${ragInfo?.total_chunks || 37} chunks from /data`}
            >
              <BookOpen className="w-3.5 h-3.5 text-indigo-400" />
              <span>{ragInfo?.total_chunks ? `${ragInfo.total_chunks} Notes Chunks` : '37 Notes Chunks'}</span>
            </div>
            {/* New Chat Quick Button in Header */}
            <button
              onClick={handleNewChat}
              className="hidden md:flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-medium text-slate-300 hover:text-white bg-slate-800/60 hover:bg-slate-800 border border-slate-700/60 transition-colors cursor-pointer"
              title="Start a new chat"
            >
              <Plus className="w-3.5 h-3.5" />
              <span>New</span>
            </button>

            {/* Backend Status Pill */}
            <div
              className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-mono border ${
                backendStatus === 'online'
                  ? 'bg-emerald-950/40 text-emerald-400 border-emerald-800/50'
                  : backendStatus === 'offline'
                  ? 'bg-rose-950/40 text-rose-400 border-rose-800/50'
                  : 'bg-slate-800/40 text-slate-400 border-slate-700/50'
              }`}
              title={`Backend status at ${API_BASE_URL}`}
            >
              <span
                className={`w-2 h-2 rounded-full ${
                  backendStatus === 'online'
                    ? 'bg-emerald-400 animate-pulse'
                    : backendStatus === 'offline'
                    ? 'bg-rose-400'
                    : 'bg-slate-400'
                }`}
              />
              <span className="hidden sm:inline">
                {backendStatus === 'online'
                  ? 'FastAPI Online'
                  : backendStatus === 'offline'
                  ? 'FastAPI Offline'
                  : 'Connecting...'}
              </span>
              <span className="sm:hidden">API</span>
            </div>

            {/* User Profile in Header */}
            {currentUser ? (
              <button
                onClick={() => setShowGoogleModal(true)}
                className="flex items-center gap-2 p-1 rounded-xl hover:bg-slate-800 transition-colors border border-slate-800/80 cursor-pointer"
                title={`${currentUser.name} (${currentUser.email}) - Click to switch Google account`}
              >
                <div
                  className={`w-7 h-7 rounded-full ${
                    currentUser.avatarColor || 'bg-emerald-600'
                  } text-white font-semibold text-xs flex items-center justify-center shrink-0 shadow-sm`}
                >
                  {currentUser.initials || 'AP'}
                </div>
                <span className="text-xs font-medium text-slate-200 hidden xl:inline truncate max-w-[120px]">
                  {currentUser.name}
                </span>
              </button>
            ) : (
              <button
                onClick={() => setShowGoogleModal(true)}
                className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-xl bg-white hover:bg-slate-100 text-slate-900 font-medium text-xs transition-colors shadow-sm cursor-pointer"
              >
                <GoogleLogo className="w-3.5 h-3.5" />
                <span className="hidden sm:inline">Sign in</span>
              </button>
            )}

            {/* Clear/Delete Chat Button */}
            {activeConversationId && (
              <button
                onClick={() => handleDeleteConversation(activeConversationId)}
                className="p-2 rounded-xl text-slate-400 hover:text-rose-400 hover:bg-rose-500/10 transition-colors border border-transparent hover:border-rose-500/20"
                title="Delete this conversation"
                aria-label="Delete conversation"
              >
                <Trash2 className="w-4 h-4" />
              </button>
            )}
          </div>
        </header>

        {/* Loading History Indicator */}
        {isLoadingHistory ? (
          <div className="flex-1 flex flex-col items-center justify-center text-slate-400 space-y-3">
            <Loader2 className="w-6 h-6 animate-spin text-indigo-400" />
            <p className="text-sm font-medium">Loading conversation history...</p>
          </div>
        ) : (
          /* Main Conversation Stream */
          <MessageList
            messages={messages}
            isLoading={isLoading}
            isStreaming={isStreaming}
            error={error}
            onSelectPrompt={(prompt) => {
              setInput(prompt);
              handleSendMessage(prompt);
            }}
            onRetry={handleRetry}
            onDismissError={() => setError(null)}
          />
        )}

        {/* Bottom Message Input Bar */}
        <MessageInput
          input={input}
          setInput={setInput}
          onSend={handleSendMessage}
          onStop={handleStop}
          isLoading={isLoading}
          isStreaming={isStreaming}
          disabled={isLoadingHistory}
          apiUrl={API_BASE_URL}
        />
      </div>

      {/* Google Sign-In & Account Switcher Modal */}
      <GoogleAuthModal
        isOpen={showGoogleModal}
        onClose={() => setShowGoogleModal(false)}
        accounts={accounts}
        activeAccount={currentUser}
        onSelectAccount={handleSelectAccount}
        onAddAccount={handleAddAccount}
      />

      {/* Personalization Modal */}
      <PersonalizationModal
        isOpen={showPersonalizationModal}
        onClose={() => setShowPersonalizationModal(false)}
      />

      {/* Settings Modal */}
      <SettingsModal
        isOpen={showSettingsModal}
        onClose={() => setShowSettingsModal(false)}
        activeAccount={currentUser}
      />

      {/* Upgrade Plan Modal */}
      <UpgradeModal
        isOpen={showUpgradeModal}
        onClose={() => setShowUpgradeModal(false)}
        currentPlan={currentUser?.plan || 'Go'}
      />
    </div>
  );
}
