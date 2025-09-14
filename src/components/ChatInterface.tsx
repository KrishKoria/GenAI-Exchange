"use client";

import { useRef, useState, useEffect } from "react";
import {
  Send,
  Paperclip,
  Bot,
  User,
  FileText,
  Trash2,
  RotateCcw,
  AlertCircle,
  CheckCircle,
  Clock,
  Loader2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import ReactMarkdown from "react-markdown";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { vscDarkPlus } from "react-syntax-highlighter/dist/esm/styles/prism";
import { useTranslations } from "next-intl";

// Custom markdown component for chat messages
const ChatMarkdown = ({ content }: { content: string }) => {
  return (
    <div className="prose prose-invert prose-sm max-w-none">
      <ReactMarkdown
        components={{
          // Custom code block rendering with syntax highlighting
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          code({ inline, className, children, ...props }: any) {
            const match = /language-(\w+)/.exec(className || "");
            return !inline && match ? (
              <SyntaxHighlighter
                style={vscDarkPlus as Record<string, React.CSSProperties>}
                language={match[1]}
                PreTag="div"
                className="rounded-md !bg-[#1e1e1e] !mb-4"
                {...props}
              >
                {String(children).replace(/\n$/, "")}
              </SyntaxHighlighter>
            ) : (
              <code
                className="bg-[#2a2a2a] text-purple-300 px-1.5 py-0.5 rounded text-xs font-mono"
                {...props}
              >
                {children}
              </code>
            );
          },
          // Custom styling for other elements
          p: ({ children }) => (
            <p className="mb-3 last:mb-0 leading-relaxed">{children}</p>
          ),
          h1: ({ children }) => (
            <h1 className="text-lg font-semibold mb-3 text-white">
              {children}
            </h1>
          ),
          h2: ({ children }) => (
            <h2 className="text-base font-semibold mb-2 text-white">
              {children}
            </h2>
          ),
          h3: ({ children }) => (
            <h3 className="text-sm font-semibold mb-2 text-white">
              {children}
            </h3>
          ),
          ul: ({ children }) => (
            <ul className="list-disc list-outside ml-4 mb-3 space-y-2 text-white/90 marker:text-white/90">
              {children}
            </ul>
          ),
          ol: ({ children }) => (
            <ol className="list-decimal list-outside ml-4 mb-3 space-y-2 text-white/90 marker:text-white/90">
              {children}
            </ol>
          ),
          li: ({ children }) => (
            <li className="text-white/90 leading-relaxed">{children}</li>
          ),
          blockquote: ({ children }) => (
            <blockquote className="border-l-4 border-purple-500/50 pl-4 italic text-white/80 mb-3">
              {children}
            </blockquote>
          ),
          strong: ({ children }) => (
            <strong className="font-semibold text-white">{children}</strong>
          ),
          em: ({ children }) => (
            <em className="italic text-white/90">{children}</em>
          ),
          a: ({ children, href, ...props }) => (
            <a
              href={href}
              className="text-purple-400 hover:text-purple-300 underline"
              target="_blank"
              rel="noopener noreferrer"
              {...props}
            >
              {children}
            </a>
          ),
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
};

export interface ChatMessage {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  timestamp?: Date;
  isLoading?: boolean;
  error?: boolean;
  optimistic?: boolean; // Add flag for optimistic messages
  sources?: Array<{
    clause_id?: string;
    clause_number?: number;
    category?: string;
    snippet: string;
    relevance_score: number;
  }>;
  feedback?: "positive" | "negative" | null;
}

export interface SelectedDocument {
  id: string;
  name: string;
  status?: string;
}

interface ChatInterfaceProps {
  messages: ChatMessage[];
  onSendMessage: (content: string) => void;
  onRetryMessage?: (messageId: string) => void;
  onFeedback?: (messageId: string, feedback: "positive" | "negative") => void;
  selectedDocuments: SelectedDocument[];
  onRemoveDocument: (docId: string) => void;
  onClearContext: () => void;
  onUploadClick: () => void;
  isProcessing?: boolean;
  placeholder?: string;
  disabled?: boolean;
}

export const ChatInterface = ({
  messages,
  onSendMessage,
  onRetryMessage,
  onFeedback,
  selectedDocuments,
  onRemoveDocument,
  onClearContext,
  onUploadClick,
  isProcessing = false,
  placeholder = "Ask about clauses, risks, or request a plain-English summary…",
  disabled = false,
}: ChatInterfaceProps) => {
  const t = useTranslations();
  const [input, setInput] = useState("");
  const [isComposing, setIsComposing] = useState(false);
  const [showTypingHint, setShowTypingHint] = useState(false);
  const [typingTimer, setTypingTimer] = useState<NodeJS.Timeout | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Auto-resize textarea
  useEffect(() => {
    const textarea = textareaRef.current;
    if (textarea) {
      textarea.style.height = "auto";
      textarea.style.height = `${Math.min(textarea.scrollHeight, 120)}px`;
    }
  }, [input]);

  // Cleanup timer on unmount
  useEffect(() => {
    return () => {
      if (typingTimer) {
        clearTimeout(typingTimer);
      }
    };
  }, [typingTimer]);

  const handleSend = () => {
    const content = input.trim();
    if (!content || disabled || isProcessing) return;

    // Clear input immediately for better UX
    setInput("");
    setIsComposing(false);

    // Send message to parent for processing
    onSendMessage(content);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const formatTimestamp = (timestamp?: Date) => {
    if (!timestamp) return "";
    return new Intl.DateTimeFormat("en-US", {
      hour: "2-digit",
      minute: "2-digit",
      hour12: true,
    }).format(timestamp);
  };

  const renderTypingIndicator = () => (
    <div className="flex items-center gap-2 text-white/60">
      <div className="flex gap-1">
        <div className="w-2 h-2 bg-purple-400 rounded-full animate-bounce" />
        <div className="w-2 h-2 bg-purple-400 rounded-full animate-bounce delay-100" />
        <div className="w-2 h-2 bg-purple-400 rounded-full animate-bounce delay-200" />
      </div>
      <span className="text-sm">{t("chat.assistantThinking")}</span>
    </div>
  );

  const renderMessageSkeleton = () => (
    <div className="mr-auto max-w-[85%]">
      <Card className="bg-[#121212] border-white/10">
        <CardContent className="p-4">
          <div className="animate-pulse space-y-3">
            <div className="flex items-center gap-2">
              <div className="w-4 h-4 bg-gray-700 rounded"></div>
              <div className="w-16 h-3 bg-gray-700 rounded"></div>
            </div>
            <div className="space-y-2">
              <div className="w-full h-3 bg-gray-700 rounded"></div>
              <div className="w-3/4 h-3 bg-gray-700 rounded"></div>
              <div className="w-1/2 h-3 bg-gray-700 rounded"></div>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );

  return (
    <div className="flex flex-col h-full bg-[#0F0F0F] overflow-hidden">
      {/* Messages */}
      <div className="flex-1 overflow-y-auto no-scrollbar px-4 md:px-6 py-6 space-y-6 bg-[#0F0F0F] min-h-0">
        {messages.length === 0 && !isProcessing && (
          <div className="flex flex-col items-center justify-center h-full text-center space-y-4">
            <div className="w-16 h-16 bg-gradient-to-br from-purple-500 to-pink-500 rounded-2xl flex items-center justify-center">
              <Bot className="w-8 h-8 text-white" />
            </div>
            <div className="space-y-2">
              <h3 className="text-xl font-semibold text-white">
                {t("chat.welcomeTitle")}
              </h3>
              <p className="text-white/60 max-w-md">
                {t("chat.welcomeDescription")}
              </p>
            </div>
            <Button
              onClick={onUploadClick}
              className="bg-gradient-to-r from-purple-500 to-pink-500 hover:from-purple-600 hover:to-pink-600"
            >
              <FileText className="mr-2 h-4 w-4" />
              {t("navigation.uploadDocument")}
            </Button>
          </div>
        )}

        {messages.map((message) => (
          <div key={message.id} className="flex w-full">
            {message.role === "assistant" ? (
              <div className="mr-auto max-w-[85%] group">
                <Card className="bg-[#121212] border-white/10 hover:border-white/20 transition-colors">
                  <CardContent className="p-3">
                    {/* Header */}
                    <div className="flex items-center justify-between mb-3">
                      <div className="flex items-center gap-2 text-white/70">
                        <div className="w-6 h-6 bg-gradient-to-br from-purple-500 to-pink-500 rounded-full flex items-center justify-center">
                          <Bot className="w-3 h-3 text-white" />
                        </div>
                        <span className="text-sm font-medium">
                          {t("chat.assistant")}
                        </span>
                        {message.timestamp && (
                          <span className="text-xs text-white/40">
                            {formatTimestamp(message.timestamp)}
                          </span>
                        )}
                      </div>

                      {/* Status indicator */}
                      <div className="flex items-center gap-1">
                        {message.isLoading ? (
                          <Loader2 className="w-3 h-3 animate-spin text-purple-400" />
                        ) : message.error ? (
                          <AlertCircle className="w-3 h-3 text-red-400" />
                        ) : (
                          <CheckCircle className="w-3 h-3 text-green-400" />
                        )}
                      </div>
                    </div>

                    {/* Content */}
                    <div className="text-sm leading-6 text-white/90">
                      {message.isLoading ? (
                        renderTypingIndicator()
                      ) : (
                        <ChatMarkdown content={message.content} />
                      )}

                      {/* Sources */}
                      {message.sources && message.sources.length > 0 && (
                        <div className="mt-4 p-3 bg-[#0F0F0F] rounded-lg border border-white/10">
                          <div className="text-xs font-medium text-white/70 mb-2">
                            {t("chat.sources")}
                          </div>
                          <div className="space-y-2">
                            {message.sources.map(
                              (
                                source: {
                                  clause_id?: string;
                                  clause_number?: number;
                                  category?: string;
                                  snippet: string;
                                  relevance_score: number;
                                },
                                idx: number
                              ) => (
                                <div
                                  key={idx}
                                  className="text-xs text-white/60 border-l-2 border-purple-500/30 pl-2"
                                >
                                  <div className="flex items-center justify-between mb-1">
                                    <span className="font-medium">
                                      {source.clause_number && source.category
                                        ? `Clause ${source.clause_number} (${source.category})`
                                        : `Source ${idx + 1}`}
                                    </span>
                                    <span className="text-purple-400">
                                      {source.relevance_score > 0
                                        ? `${Math.round(
                                            source.relevance_score * 100
                                          )}%`
                                        : "N/A"}
                                    </span>
                                  </div>
                                  <div>&quot;{source.snippet}&quot;</div>
                                </div>
                              )
                            )}
                          </div>
                        </div>
                      )}
                    </div>

                    {/* Actions */}
                    {!message.isLoading && (
                      <div className="flex items-center justify-between mt-3 pt-3 border-t border-white/5 opacity-0 group-hover:opacity-100 transition-opacity">
                        <div className="flex items-center gap-1">
                          {onRetryMessage && message.error && (
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => onRetryMessage(message.id)}
                              className="h-6 px-2 text-xs"
                            >
                              <RotateCcw className="w-3 h-3" />
                            </Button>
                          )}
                        </div>
                      </div>
                    )}
                  </CardContent>
                </Card>
              </div>
            ) : message.role === "user" ? (
              <div className="ml-auto max-w-[85%] group">
                <Card
                  className={`bg-gradient-to-br from-[#1a1a1a] to-[#18181B] border-white/10 ${
                    message.optimistic
                      ? "opacity-70 border-dashed border-white/20"
                      : ""
                  }`}
                >
                  <CardContent className="p-3">
                    <div className="flex items-center justify-end gap-2 text-white mb-2">
                      {message.optimistic && (
                        <Clock className="w-3 h-3 text-white/50" />
                      )}
                      {message.timestamp && (
                        <span className="text-xs text-white/40">
                          {formatTimestamp(message.timestamp)}
                        </span>
                      )}
                      <span className="text-sm font-medium">
                        {t("chat.you")}
                      </span>
                      <div className="w-6 h-6 bg-gradient-to-br from-blue-500 to-cyan-500 rounded-full flex items-center justify-center">
                        <User className="w-3 h-3 text-white" />
                      </div>
                    </div>
                    <div className="text-sm leading-6 text-white">
                      <ChatMarkdown content={message.content} />
                    </div>
                  </CardContent>
                </Card>
              </div>
            ) : (
              // System messages
              <div className="mx-auto max-w-[75%]">
                <div className="text-center text-xs text-white/50 bg-[#0F0F0F] px-3 py-2 rounded-full border border-white/10">
                  {message.content}
                </div>
              </div>
            )}
          </div>
        ))}

        {/* Show skeleton when processing but no loading message */}
        {isProcessing &&
          !messages.some((m) => m.isLoading) &&
          renderMessageSkeleton()}

        <div ref={messagesEndRef} />
      </div>

      {/* Context bar and Composer */}
      <div className="border-t border-white/10 bg-[#0B0B0B] p-4 shrink-0">
        {/* Context chips */}
        <div className="mb-3">
          <div className="flex flex-wrap items-center gap-2">
            {selectedDocuments.length > 0 ? (
              <>
                <span className="text-xs font-medium text-white/60 uppercase tracking-wide">
                  {t("chat.context")}
                </span>
                {selectedDocuments.map((doc) => (
                  <div
                    key={doc.id}
                    className="inline-flex items-center gap-2 rounded-full border border-purple-500/30 bg-purple-500/10 px-3 py-1 text-xs backdrop-blur-sm"
                  >
                    <FileText className="h-3 w-3 text-purple-400" />
                    <span className="text-white/90">{doc.name}</span>
                    {doc.status && (
                      <span className="text-purple-300/60">• {doc.status}</span>
                    )}
                    <button
                      className="ml-1 text-white/60 hover:text-white transition-colors"
                      onClick={() => onRemoveDocument(doc.id)}
                      aria-label={`Remove ${doc.name}`}
                    >
                      ×
                    </button>
                  </div>
                ))}
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={onClearContext}
                  className="h-6 px-2 text-xs text-white/60 hover:text-white"
                >
                  <Trash2 className="mr-1 h-3 w-3" />
                  {t("chat.clear")}
                </Button>
              </>
            ) : (
              <div className="text-xs text-white/40">
                {t("chat.noDocumentsSelected")}
              </div>
            )}
          </div>
        </div>

        {/* Composer */}
        <div className="relative">
          <div className="rounded-2xl border border-white/20 bg-gradient-to-r from-[#0F0F0F] to-[#1a1a1a] p-3 shadow-lg backdrop-blur-sm">
            <div className="flex items-end gap-3">
              <Button
                variant="ghost"
                size="icon"
                onClick={onUploadClick}
                className="shrink-0 h-8 w-8 text-white/60 hover:text-white hover:bg-white/10"
                disabled={disabled}
              >
                <Paperclip className="h-4 w-4" />
              </Button>

              <div className="flex-1 relative">
                <textarea
                  ref={textareaRef}
                  rows={1}
                  value={input}
                  onChange={(e) => {
                    setInput(e.target.value);
                    setIsComposing(e.target.value.length > 0);

                    // Handle typing hint logic
                    if (e.target.value.length > 10 && !disabled) {
                      setShowTypingHint(true);

                      // Clear existing timer
                      if (typingTimer) {
                        clearTimeout(typingTimer);
                      }

                      // Set new timer to hide hint after 3 seconds of no typing
                      const newTimer = setTimeout(() => {
                        setShowTypingHint(false);
                      }, 3000);
                      setTypingTimer(newTimer);
                    } else {
                      setShowTypingHint(false);
                      if (typingTimer) {
                        clearTimeout(typingTimer);
                        setTypingTimer(null);
                      }
                    }
                  }}
                  onKeyDown={handleKeyDown}
                  placeholder={disabled ? t("chat.pleaseWait") : placeholder}
                  disabled={disabled}
                  className="w-full resize-none bg-transparent text-sm outline-none placeholder:text-white/40 text-white max-h-[120px] leading-5"
                  style={{ minHeight: "20px" }}
                />

                {/* Character count for long messages */}
                {input.length > 500 && (
                  <div className="absolute bottom-0 right-0 text-xs text-white/40">
                    {input.length}/2000
                  </div>
                )}
              </div>

              <Button
                onClick={handleSend}
                disabled={!input.trim() || disabled || isProcessing}
                className="shrink-0 h-8 bg-gradient-to-r from-purple-500 to-pink-500 hover:from-purple-600 hover:to-pink-600 disabled:from-gray-600 disabled:to-gray-600 transition-all duration-200"
                size="sm"
              >
                {isProcessing ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Send className="h-4 w-4" />
                )}
              </Button>
            </div>
          </div>

          {/* Typing indicator */}
          {showTypingHint && !disabled && (
            <div className="absolute -top-8 left-3 text-xs text-white/40 bg-[#0F0F0F] px-2 py-1 rounded border border-white/5 transition-opacity duration-200">
              <Clock className="w-3 h-3 inline mr-1" />
              {t("chat.typingHint")}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
