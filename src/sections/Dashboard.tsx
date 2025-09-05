/* eslint-disable @typescript-eslint/no-explicit-any */
"use client";

import { useRef, useState, useEffect, useMemo } from "react";
import { Menu, Plus, Upload, Search, FileText, Flame } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  useDocumentWorkflow,
  useAskQuestion,
  useDocumentClauses,
  useDocumentStatus,
} from "@/hooks/useDocuments";
import { getTopRiskyClauses } from "@/lib/api";
import { RiskHeatmap } from "@/components/RiskHeatmap";
import { ChatInterface, ChatMessage } from "@/components/ChatInterface";

// ChatGPT-like dashboard for legal document assistant
// - Left: sidebar with New Chat, Upload, Recent Docs + search
// - Center: chat thread with composer, context chips for selected docs
// - Right: risk heatmap panel for the current thread

export const Dashboard = () => {
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: "m1",
      role: "assistant",
      content:
        "Hi! Upload a legal document and ask me anything. I'll summarize, flag risky clauses, and answer questions in simple language.",
      timestamp: new Date(),
    },
  ]);

  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [recentDocs, setRecentDocs] = useState<
    { id: string; name: string; date: string; status?: string }[]
  >([]);
  const [docQuery, setDocQuery] = useState("");
  const [selectedDocs, setSelectedDocs] = useState<string[]>([]);
  const [currentDocId, setCurrentDocId] = useState<string | null>(null);

  // API hooks
  const { upload: uploadDocument } = useDocumentWorkflow();
  const askQuestionMutation = useAskQuestion();

  // Get document status for current document
  const { data: documentStatus } = useDocumentStatus(
    currentDocId,
    !!currentDocId
  );

  // Get clauses for the current document
  const {
    data: clauses = [],
    isLoading: clausesLoading,
    error: clausesError,
    isSuccess: clausesSuccess,
  } = useDocumentClauses(currentDocId, !!currentDocId);

  const filteredDocs = recentDocs.filter((d) =>
    d.name.toLowerCase().includes(docQuery.toLowerCase())
  );

  function handleUploadClick() {
    fileInputRef.current?.click();
  }

  async function handleFilesSelected(files: FileList | null) {
    if (!files || files.length === 0) return;

    try {
      // For now, handle single file upload (can be extended for multiple files)
      const file = files[0];

      // Add upload status message
      const uploadMsg: ChatMessage = {
        id: `upload-${Date.now()}`,
        role: "assistant",
        content: `Uploading ${file.name}... This may take a moment.`,
        isLoading: true,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, uploadMsg]);

      // Upload the document
      const response = await uploadDocument.mutateAsync({
        file,
        sessionId: `session-${Date.now()}`,
      });

      // Add the document to recent docs
      const newDoc = {
        id: response.doc_id,
        name: response.filename,
        date: new Date().toISOString().slice(0, 10),
        status: response.status,
      };

      setRecentDocs((prev) => [newDoc, ...prev]);
      setSelectedDocs([response.doc_id]);
      setCurrentDocId(response.doc_id);

      // Update message to show processing started
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === uploadMsg.id
            ? {
                ...msg,
                content: `${response.filename} uploaded successfully! Processing document...`,
                isLoading: false,
              }
            : msg
        )
      );
    } catch (error: unknown) {
      console.error("Upload failed:", error);

      // Show error message
      setMessages((prev) => [
        ...prev.filter((msg) => !msg.isLoading),
        {
          id: `error-${Date.now()}`,
          role: "assistant",
          content: `Sorry, there was an error uploading your document: ${
            (error as any)?.response?.data?.detail ||
            (error as Error)?.message ||
            "Unknown error"
          }`,
          error: true,
          timestamp: new Date(),
        },
      ]);
    }
  }

  function toggleSelectDoc(id: string) {
    setSelectedDocs((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [id, ...prev]
    );
  }

  function clearContext() {
    setSelectedDocs([]);
  }

  function newChat() {
    setMessages([
      {
        id: "m-welcome",
        role: "assistant",
        content:
          "New chat started. Upload a document or pick from Recent Docs, then ask your questions.",
        timestamp: new Date(),
      },
    ]);
    setSelectedDocs([]);
  }

  async function sendMessage(content: string) {
    // Check if we have a document selected
    if (!currentDocId) {
      const errorMsg: ChatMessage = {
        id: `error-${Date.now()}`,
        role: "assistant",
        content:
          "Please upload and select a document first before asking questions.",
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, errorMsg]);
      return;
    }

    const userMsg: ChatMessage = {
      id: `u-${Date.now()}`,
      role: "user",
      content,
      timestamp: new Date(),
    };
    const loadingMsg: ChatMessage = {
      id: `loading-${Date.now()}`,
      role: "assistant",
      content: "Analyzing your question and searching through the document...",
      isLoading: true,
      timestamp: new Date(),
    };

    // Immediate optimistic render
    setMessages((prev) => [...prev, userMsg, loadingMsg]);

    try {
      // Ask the question using the API
      const response = await askQuestionMutation.mutateAsync({
        doc_id: currentDocId,
        question: content,
        session_id: `session-${Date.now()}`,
      });

      // Format the response with sources
      const answerContent = response.answer;
      const sources = response.sources?.map((source) => ({
        snippet: source.snippet,
        relevance_score: source.relevance_score,
      }));

      const assistantMsg: ChatMessage = {
        id: `a-${Date.now()}`,
        role: "assistant",
        content: answerContent,
        sources,
        timestamp: new Date(),
      };

      // Replace loading message with actual response
      setMessages((prev) =>
        prev.map((msg) => (msg.id === loadingMsg.id ? assistantMsg : msg))
      );
    } catch (error: unknown) {
      console.error("Question failed:", error);

      const errorMsg: ChatMessage = {
        id: `error-${Date.now()}`,
        role: "assistant",
        content: `Sorry, I couldn't process your question: ${
          (error as any)?.response?.data?.detail ||
          (error as Error)?.message ||
          "Unknown error"
        }`,
        error: true,
        timestamp: new Date(),
      };

      // Replace loading message with error
      setMessages((prev) =>
        prev.map((msg) => (msg.id === loadingMsg.id ? errorMsg : msg))
      );
    }
  }

  // Handle feedback on messages
  function handleFeedback(
    messageId: string,
    feedback: "positive" | "negative"
  ) {
    setMessages((prev) =>
      prev.map((msg) => (msg.id === messageId ? { ...msg, feedback } : msg))
    );
  }

  // Handle retry for failed messages
  function handleRetry(messageId: string) {
    const message = messages.find((m) => m.id === messageId);
    if (message && message.role === "assistant") {
      // Find the user message that prompted this response
      const messageIndex = messages.findIndex((m) => m.id === messageId);
      const userMessage = messageIndex > 0 ? messages[messageIndex - 1] : null;

      if (userMessage && userMessage.role === "user") {
        // Retry the question
        sendMessage(userMessage.content);
      }
    }
  }

  // Generate top risky clauses - memoized for performance
  const topRiskyClauses = useMemo(() => getTopRiskyClauses(clauses), [clauses]);

  // Update current document when selection changes
  useEffect(() => {
    if (selectedDocs.length > 0) {
      setCurrentDocId(selectedDocs[0]);
    } else {
      setCurrentDocId(null);
    }
  }, [selectedDocs]);

  // Monitor document status and update UI when processing completes
  useEffect(() => {
    if (!documentStatus || !currentDocId) return;

    // Update document status in recentDocs
    setRecentDocs((prev) =>
      prev.map((doc) =>
        doc.id === currentDocId
          ? { ...doc, status: documentStatus.status }
          : doc
      )
    );

    // Update processing message when status changes
    if (
      documentStatus.status === "completed" &&
      documentStatus.clause_count! > 0
    ) {
      setMessages((prev) =>
        prev.map((msg) => {
          // Find the processing message for this document
          if (
            msg.content.includes("Processing document...") &&
            msg.role === "assistant"
          ) {
            return {
              ...msg,
              content: `Document processed successfully! Found ${documentStatus.clause_count} clauses. You can now ask questions about the document.`,
              isLoading: false,
            };
          }
          return msg;
        })
      );
    } else if (documentStatus.status === "failed") {
      setMessages((prev) =>
        prev.map((msg) => {
          if (
            msg.content.includes("Processing document...") &&
            msg.role === "assistant"
          ) {
            return {
              ...msg,
              content: `Document processing failed. Please try uploading again or contact support if the issue persists.`,
              isLoading: false,
              error: true,
            };
          }
          return msg;
        })
      );
    }
  }, [documentStatus, currentDocId]);

  // Debug effect to track clauses data changes
  useEffect(() => {
    if (currentDocId && clauses.length > 0) {
      console.log(`Clauses loaded for document ${currentDocId}:`, {
        count: clauses.length,
        hasRiskLevels: clauses.every((c) => c.risk_level),
        riskLevels: clauses.map((c) => c.risk_level),
        categories: clauses.map((c) => c.category),
      });
    }
  }, [currentDocId, clauses]);

  // Convert selected docs to the format expected by ChatInterface
  const selectedDocuments = selectedDocs
    .map((id) => {
      const doc = recentDocs.find((d) => d.id === id);
      return doc
        ? { id: doc.id, name: doc.name, status: doc.status }
        : { id, name: "Loading...", status: undefined };
    })
    .filter(Boolean);

  return (
    <div className="flex h-screen w-full bg-[#0B0B0B] text-white antialiased overflow-hidden">
      {/* Left Sidebar */}
      <aside
        className={`${
          sidebarOpen ? "flex" : "hidden"
        } md:flex w-72 shrink-0 flex-col border-r border-white/10 bg-[#111111] h-full overflow-hidden`}
      >
        <div className="p-4 flex flex-col gap-4 h-full overflow-hidden">
          {/* Brand + Mobile toggle */}
          <div className="flex items-center justify-between shrink-0">
            <div className="text-xl font-semibold bg-gradient-to-r from-purple-400 to-pink-500 bg-clip-text text-transparent">
              LegalEase AI
            </div>
            <Button
              className="md:hidden"
              variant="ghost"
              size="icon"
              onClick={() => setSidebarOpen(false)}
            >
              <Menu className="h-5 w-5" />
            </Button>
          </div>

          <div className="flex gap-2 shrink-0">
            <Button className="flex-1" onClick={newChat}>
              <Plus className="mr-2 h-4 w-4" /> New Chat
            </Button>
            <Button variant="secondary" onClick={handleUploadClick}>
              <Upload className="mr-2 h-4 w-4" /> Upload
            </Button>
            <input
              ref={fileInputRef}
              type="file"
              className="hidden"
              multiple
              onChange={(e) => handleFilesSelected(e.target.files)}
            />
          </div>

          <div className="flex flex-col min-h-0 flex-1">
            <label className="text-xs uppercase tracking-wide text-white/60 shrink-0">
              Recent documents
            </label>
            <div className="mt-2 flex items-center gap-2 shrink-0">
              <Input
                placeholder="Search documents"
                value={docQuery}
                onChange={(e) => setDocQuery(e.target.value)}
                className="bg-[#0F0F0F] border-white/10"
              />
              <Button
                variant="ghost"
                size="icon"
                className="border border-white/10"
              >
                <Search className="h-4 w-4" />
              </Button>
            </div>

            <div className="mt-3 overflow-y-auto flex-1 pr-1 space-y-1">
              {filteredDocs.length === 0 && (
                <div className="text-xs text-white/50">No documents found.</div>
              )}
              {filteredDocs.map((doc) => {
                const checked = selectedDocs.includes(doc.id);
                return (
                  <button
                    key={doc.id}
                    onClick={() => toggleSelectDoc(doc.id)}
                    className={`group flex w-full items-center justify-between rounded-lg border border-white/5 bg-[#0F0F0F] px-3 py-2 text-left hover:border-white/20 ${
                      checked ? "ring-1 ring-purple-500/50" : ""
                    }`}
                  >
                    <div className="flex items-center gap-2">
                      <FileText className="h-4 w-4 text-white/70" />
                      <div>
                        <div className="text-sm leading-tight">{doc.name}</div>
                        <div className="text-[10px] text-white/50">
                          {doc.date} {doc.status && `• ${doc.status}`}
                        </div>
                      </div>
                    </div>
                    <div
                      className={`h-3 w-3 rounded-full ${
                        checked ? "bg-purple-500" : "bg-white/20"
                      }`}
                    />
                  </button>
                );
              })}
            </div>
          </div>
        </div>
      </aside>

      {/* Center Chat Column */}
      <section className="flex min-w-0 flex-1 flex-col bg-[#0B0B0B] h-full overflow-hidden">
        {/* Mobile top bar */}
        <div className="flex w-full items-center justify-between border-b border-white/10 bg-[#111111] px-4 py-3 md:hidden shrink-0">
          <Button
            variant="ghost"
            size="icon"
            onClick={() => setSidebarOpen(true)}
          >
            <Menu className="h-5 w-5" />
          </Button>
          <div className="text-base font-semibold bg-gradient-to-r from-purple-400 to-pink-500 bg-clip-text text-transparent">
            LegalEase AI
          </div>
          <div className="w-9" />
        </div>

        {/* Chat Interface - Independent Scroll Area */}
        <div className="flex-1 w-full max-w-3xl mx-auto bg-[#0B0B0B] h-full overflow-hidden">
          <ChatInterface
            messages={messages}
            onSendMessage={sendMessage}
            onRetryMessage={handleRetry}
            onFeedback={handleFeedback}
            selectedDocuments={selectedDocuments}
            onRemoveDocument={(docId) => toggleSelectDoc(docId)}
            onClearContext={clearContext}
            onUploadClick={handleUploadClick}
            isProcessing={askQuestionMutation.isPending}
            disabled={askQuestionMutation.isPending}
          />
        </div>
      </section>

      {/* Right Heatmap Panel */}
      <aside className="hidden xl:flex w-80 shrink-0 flex-col border-l border-white/10 bg-[#111111] h-full overflow-hidden">
        <div className="p-4 flex flex-col h-full overflow-hidden">
          <h3 className="mb-4 flex items-center gap-2 text-sm font-semibold uppercase tracking-wide text-white/70 shrink-0">
            <Flame className="h-4 w-4 text-red-500" /> Risk Heatmap
          </h3>

          {/* Document info */}
          {currentDocId && (
            <div className="mb-4 p-2 rounded-lg bg-[#0F0F0F] border border-white/10 shrink-0">
              <div className="text-xs text-white/60">Document</div>
              <div className="text-sm text-white/90">
                {recentDocs.find((d) => d.id === currentDocId)?.name ||
                  "Loading..."}
              </div>
              <div className="text-xs text-white/50">
                {clauses.length} clauses analyzed
              </div>
            </div>
          )}

          {/* Risk Heatmap */}
          <div className="shrink-0">
            <RiskHeatmap
              clauses={clauses || []}
              isLoading={clausesLoading}
              error={clausesError}
            />
          </div>

          {/* Top risky clauses */}
          <div className="mt-6 flex flex-col min-h-0 flex-1">
            <div className="text-xs uppercase tracking-wide text-white/60 shrink-0">
              Top risky clauses ({topRiskyClauses.length})
            </div>
            <div className="mt-2 overflow-y-auto flex-1 space-y-2">
              {clausesLoading ? (
                <div className="space-y-2">
                  {[...Array(3)].map((_, i) => (
                    <div key={i} className="animate-pulse">
                      <div className="h-8 bg-gray-700 rounded-lg"></div>
                    </div>
                  ))}
                </div>
              ) : clausesError ? (
                <div className="text-xs text-red-400 p-3">
                  Failed to load clause analysis. Please refresh or try again.
                </div>
              ) : topRiskyClauses.length > 0 ? (
                topRiskyClauses.map((c, index) => (
                  <div
                    key={c.clauseId || `${c.k}-${index}`}
                    className="flex items-center justify-between rounded-lg border border-white/10 bg-[#0F0F0F] px-3 py-2 hover:border-white/20 transition-colors"
                  >
                    <div className="text-sm truncate">{c.k}</div>
                    <div className="text-xs text-white/60 ml-2">
                      {Math.round(c.risk * 100)}%
                    </div>
                  </div>
                ))
              ) : (
                <div className="text-xs text-white/50 p-3">
                  {currentDocId && clausesSuccess && clauses.length === 0
                    ? "No clauses found in document"
                    : currentDocId
                    ? "No high-risk clauses found"
                    : "Upload a document to see risk analysis"}
                </div>
              )}
            </div>
          </div>
        </div>
      </aside>
    </div>
  );
};
