/* eslint-disable @typescript-eslint/no-explicit-any */
"use client";

import { useRef, useState, useEffect, useMemo } from "react";
import {
  Menu,
  Plus,
  Upload,
  Search,
  FileText,
  Flame,
  BarChart3,
  X,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  useDocumentWorkflow,
  useDocumentWithClauses,
  useCreateChatSession,
  useChatAwareAskQuestion,
  useUpdateDocumentContext,
} from "@/hooks/useDocuments";
import { getTopRiskyClauses } from "@/lib/api";
import { RiskHeatmap } from "@/components/RiskHeatmap";
import { ChatInterface, ChatMessage } from "@/components/ChatInterface";
import { UploadSuccessCard } from "@/components/UploadSuccessCard";
import { ReadabilityPanel } from "@/components/ReadabilityPanel";
import { LanguageSelector } from "@/components/LanguageSelector";
import { useTranslations } from "next-intl";
// Simple client-side file validation helpers
const validateFileBasics = (file: File) => {
  const errors: string[] = [];
  const warnings: string[] = [];

  // Check file type
  if (file.type !== "application/pdf") {
    errors.push("Only PDF files are supported.");
  }

  // Check file size (10MB limit)
  const fileSizeMB = file.size / (1024 * 1024);
  if (fileSizeMB > 10) {
    errors.push(
      `File size (${fileSizeMB.toFixed(1)}MB) exceeds the 10MB limit.`
    );
  }

  // Size warnings
  if (fileSizeMB > 8) {
    warnings.push(
      `Large file (${fileSizeMB.toFixed(1)}MB). Processing may take longer.`
    );
  }

  return {
    isValid: errors.length === 0,
    fileSize: file.size,
    errors,
    warnings,
  };
};
import { useToast, createToast } from "@/components/ui/toast";

// ChatGPT-like dashboard for legal document assistant
// - Left: sidebar with New Chat, Upload, Recent Docs + search
// - Center: chat thread with composer, context chips for selected docs
// - Right: risk heatmap panel for the current thread

export const Dashboard = () => {
  const t = useTranslations();
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: "m1",
      role: "assistant",
      content: t("chat.welcomeMessage"),
      timestamp: new Date(),
    },
  ]);

  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [rightPanelOpen, setRightPanelOpen] = useState(false);
  const [recentDocs, setRecentDocs] = useState<
    { id: string; name: string; date: string; status?: string }[]
  >([]);
  const [docQuery, setDocQuery] = useState("");
  const [selectedDocs, setSelectedDocs] = useState<string[]>([]);
  const [currentDocId, setCurrentDocId] = useState<string | null>(null);

  // Chat session state
  const [currentChatSessionId, setCurrentChatSessionId] = useState<
    string | null
  >(null);

  const [uploadCards, setUploadCards] = useState<{
    [key: string]: {
      filename: string;
      fileSize: number;
      pageCount?: number;
      status: "uploading" | "processing" | "completed" | "failed";
      error?: string;
      progress?: number;
      estimatedTime?: number;
      clauseCount?: number;
    };
  }>({});
  const [autoDismissTimers, setAutoDismissTimers] = useState<{
    [key: string]: NodeJS.Timeout;
  }>({});

  const { toast } = useToast();

  // API hooks
  const { upload: uploadDocument } = useDocumentWorkflow();
  const askQuestionMutation = useChatAwareAskQuestion();
  const createChatSessionMutation = useCreateChatSession();
  const updateDocumentContextMutation = useUpdateDocumentContext(); // Use the composite hook for better data management
  const { status: statusQuery, clauses: clausesQuery } =
    useDocumentWithClauses(currentDocId);

  const documentStatus = statusQuery.data;
  const clauses = useMemo(() => clausesQuery.data || [], [clausesQuery.data]);
  const clausesLoading = clausesQuery.isLoading;
  const clausesError = clausesQuery.error;
  const clausesSuccess = clausesQuery.isSuccess;

  const filteredDocs = recentDocs.filter((d) =>
    d.name.toLowerCase().includes(docQuery.toLowerCase())
  );

  function handleUploadClick() {
    fileInputRef.current?.click();
  }

  async function handleFilesSelected(files: FileList | null) {
    if (!files || files.length === 0) return;

    const file = files[0];
    const cardId = `upload-${Date.now()}`;

    try {
      // Basic client-side validation
      const basicValidation = validateFileBasics(file);
      if (!basicValidation.isValid) {
        toast(
          createToast.error("Invalid File", basicValidation.errors.join(" "))
        );
        return;
      }

      // Show warnings if any
      if (basicValidation.warnings.length > 0) {
        toast(
          createToast.warning(
            "File Upload Warning",
            basicValidation.warnings.join(" ")
          )
        );
      }

      // Create upload card
      setUploadCards((prev) => ({
        ...prev,
        [cardId]: {
          filename: file.name,
          fileSize: file.size,
          status: "uploading",
          progress: 25,
        },
      }));

      // Upload the document (server will validate page count)
      const response = await uploadDocument.mutateAsync({
        file,
        sessionId: `session-${Date.now()}`,
      });

      // Add to recent docs
      const newDoc = {
        id: response.doc_id,
        name: response.filename,
        date: new Date().toISOString().slice(0, 10),
        status: response.status,
      };

      setRecentDocs((prev) => [newDoc, ...prev]);
      setSelectedDocs([response.doc_id]);
      setCurrentDocId(response.doc_id);

      // Update upload card to processing
      setUploadCards((prev) => ({
        ...prev,
        [cardId]: {
          ...prev[cardId],
          status: "processing",
          progress: 75,
        },
      }));

      toast(
        createToast.success(
          "Upload Successful",
          `${file.name} uploaded successfully and is being processed.`
        )
      );
    } catch (error: unknown) {
      console.error("Upload failed:", error);

      // Extract error details for better UX
      const errorResponse = (error as any)?.response;
      const errorMessage =
        errorResponse?.data?.detail ||
        (error as Error)?.message ||
        "An unexpected error occurred while uploading your document.";

      const isValidationError =
        errorResponse?.status === 422 || errorResponse?.status === 413;

      // Update upload card to failed
      setUploadCards((prev) => ({
        ...prev,
        [cardId]: {
          ...prev[cardId],
          status: "failed",
          error: errorMessage,
        },
      }));

      toast(
        createToast.error(
          isValidationError ? "Document Validation Failed" : "Upload Failed",
          errorMessage,
          {
            action: {
              label: "Try Again",
              onClick: () => handleFilesSelected(files),
            },
          }
        )
      );
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

  async function newChat() {
    try {
      // Create a new chat session
      const newSession = await createChatSessionMutation.mutateAsync({
        selected_document_ids:
          selectedDocs.length > 0 ? selectedDocs : undefined,
      });

      // Set the new session as current
      setCurrentChatSessionId(newSession.session_id);

      // Clear messages and reset to welcome state
      setMessages([
        {
          id: "m-welcome",
          role: "assistant",
          content:
            "New chat session started. Upload a document or pick from Recent Docs, then ask your questions.",
          timestamp: new Date(),
        },
      ]);

      // Keep selected docs for context continuity
      // setSelectedDocs([]);
    } catch (error) {
      console.error("Failed to create new chat session:", error);
      // Fallback to old behavior if chat session creation fails
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

    // Create chat session if we don't have one
    let sessionId = currentChatSessionId;
    if (!sessionId) {
      try {
        const newSession = await createChatSessionMutation.mutateAsync({
          selected_document_ids:
            selectedDocs.length > 0 ? selectedDocs : [currentDocId],
        });
        sessionId = newSession.session_id;
        setCurrentChatSessionId(sessionId);
      } catch (error) {
        console.error("Failed to create chat session:", error);
        // Continue without chat session for fallback
      }
    }

    // Update document context if needed
    if (sessionId && selectedDocs.length > 0) {
      try {
        await updateDocumentContextMutation.mutateAsync({
          sessionId,
          docIds: selectedDocs,
        });
      } catch (error) {
        console.error("Failed to update document context:", error);
        // Continue anyway
      }
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
      // Ask the question using the chat-aware API
      const response = await askQuestionMutation.mutateAsync({
        doc_id: currentDocId,
        question: content,
        session_id: `session-${Date.now()}`, // Keep for backward compatibility
        chat_session_id: sessionId || undefined,
        use_conversation_memory: !!sessionId, // Use memory if we have a session
      });

      // Format the response with sources
      const answerContent = response.answer;
      const sources = response.sources?.map((source) => ({
        clause_id: source.clause_id,
        clause_number: source.clause_number,
        category: source.category,
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

    // Update upload cards when processing completes
    setUploadCards((prev) => {
      const updatedCards = { ...prev };
      Object.keys(updatedCards).forEach((cardId) => {
        const card = updatedCards[cardId];
        if (card.status === "processing") {
          if (documentStatus.status === "completed") {
            updatedCards[cardId] = {
              ...card,
              status: "completed",
              progress: 100,
              clauseCount: documentStatus.clause_count || 0,
            };

            // Start auto-dismiss timer for completed cards (5 seconds)
            const timerId = setTimeout(() => {
              setUploadCards((currentCards) => {
                // eslint-disable-next-line @typescript-eslint/no-unused-vars
                const { [cardId]: removed, ...rest } = currentCards;
                return rest;
              });
              // Clean up timer from state
              setAutoDismissTimers((timers) => {
                // eslint-disable-next-line @typescript-eslint/no-unused-vars
                const { [cardId]: removedTimer, ...restTimers } = timers;
                return restTimers;
              });
            }, 5000);

            // Store the timer ID
            setAutoDismissTimers((timers) => ({
              ...timers,
              [cardId]: timerId,
            }));
          } else if (documentStatus.status === "failed") {
            updatedCards[cardId] = {
              ...card,
              status: "failed",
              error: "Document processing failed on the server.",
            };
          }
        }
      });
      return updatedCards;
    });

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

  // Cleanup timers on unmount
  useEffect(() => {
    return () => {
      // Clear all auto-dismiss timers on unmount to prevent memory leaks
      Object.values(autoDismissTimers).forEach((timerId) => {
        clearTimeout(timerId);
      });
    };
  }, [autoDismissTimers]);

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
        } md:flex w-64 shrink-0 flex-col border-r border-white/10 bg-[#111111] h-full overflow-hidden`}
      >
        <div className="p-4 flex flex-col gap-4 h-full overflow-hidden">
          {/* Brand + Language Selector + Mobile toggle */}
          <div className="flex items-center justify-between shrink-0">
            <div className="text-xl font-semibold bg-gradient-to-r from-purple-400 to-pink-500 bg-clip-text text-transparent">
              {t("app.title").split(" - ")[0]}
            </div>
            <div className="flex items-center gap-2">
              <LanguageSelector />
              <Button
                className="md:hidden"
                variant="ghost"
                size="icon"
                onClick={() => setSidebarOpen(false)}
              >
                <Menu className="h-5 w-5" />
              </Button>
            </div>
          </div>

          <div className="flex gap-2 shrink-0">
            <Button className="flex-1" onClick={newChat}>
              <Plus className="mr-2 h-4 w-4" /> {t("navigation.newChat")}
            </Button>
            <Button variant="secondary" onClick={handleUploadClick}>
              <Upload className="mr-2 h-4 w-4" /> {t("navigation.upload")}
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

            <div className="mt-3 overflow-y-auto no-scrollbar flex-1 pr-1 space-y-1">
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
          <Button
            variant="ghost"
            size="icon"
            onClick={() => setRightPanelOpen(true)}
            className={currentDocId ? "" : "opacity-50"}
            disabled={!currentDocId}
          >
            <BarChart3 className="h-5 w-5" />
          </Button>
        </div>

        {/* Desktop analysis panel toggle */}
        <div className="hidden lg:flex xl:hidden fixed top-4 right-4 z-10">
          <Button
            variant="secondary"
            size="sm"
            onClick={() => setRightPanelOpen(!rightPanelOpen)}
            className={currentDocId ? "" : "opacity-50"}
            disabled={!currentDocId}
          >
            <BarChart3 className="h-4 w-4 mr-2" />
            Analysis
          </Button>
        </div>

        {/* Upload Cards */}
        {Object.entries(uploadCards).length > 0 && (
          <div className="p-4 space-y-3 border-b border-white/10">
            {Object.entries(uploadCards).map(([cardId, card]) => (
              <UploadSuccessCard
                key={cardId}
                filename={card.filename}
                fileSize={card.fileSize}
                pageCount={card.pageCount}
                processingStatus={card.status}
                error={card.error}
                uploadProgress={card.progress}
                estimatedTime={card.estimatedTime}
                clauseCount={card.clauseCount}
                onRetry={() => fileInputRef.current?.click()}
                onDismiss={() => {
                  // Clear auto-dismiss timer if it exists
                  const timerId = autoDismissTimers[cardId];
                  if (timerId) {
                    clearTimeout(timerId);
                    setAutoDismissTimers((timers) => {
                      // eslint-disable-next-line @typescript-eslint/no-unused-vars
                      const { [cardId]: removedTimer, ...restTimers } = timers;
                      return restTimers;
                    });
                  }

                  // Remove the card
                  setUploadCards((prev) => {
                    // eslint-disable-next-line @typescript-eslint/no-unused-vars
                    const { [cardId]: removed, ...rest } = prev;
                    return rest;
                  });
                }}
              />
            ))}
          </div>
        )}

        {/* Chat Interface - Independent Scroll Area */}
        <div className="flex-1 w-full bg-[#0B0B0B] h-full overflow-hidden px-4">
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

      {/* Mobile Overlay Background */}
      {rightPanelOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-20 xl:hidden"
          onClick={() => setRightPanelOpen(false)}
        />
      )}

      {/* Right Analysis Panel */}
      <aside
        className={`
        ${rightPanelOpen ? "flex" : "hidden"}
        xl:flex w-[28rem] shrink-0 flex-col border-l border-white/10 bg-[#111111] h-full overflow-hidden
        fixed xl:relative top-0 right-0 z-30 xl:z-auto
      `}
      >
        <div className="p-4 flex flex-col h-full overflow-hidden">
          {/* Panel Header with Close Button */}
          <div className="flex items-center justify-between mb-4 xl:hidden">
            <h2 className="text-lg font-semibold text-white">
              Document Analysis
            </h2>
            <Button
              variant="ghost"
              size="icon"
              onClick={() => setRightPanelOpen(false)}
            >
              <X className="h-5 w-5" />
            </Button>
          </div>

          {/* Document info */}
          {currentDocId && (
            <div className="mb-4 p-3 rounded-lg bg-[#0F0F0F] border border-white/10 shrink-0">
              <div className="text-xs text-white/60 mb-1">Active Document</div>
              <div className="text-sm text-white/90 font-medium">
                {recentDocs.find((d) => d.id === currentDocId)?.name ||
                  "Loading..."}
              </div>
              <div className="text-xs text-white/50 mt-1">
                {clauses.length} clauses analyzed
              </div>
            </div>
          )}

          {/* Scrollable content area */}
          <div className="flex-1 overflow-y-auto no-scrollbar space-y-6 pr-2">
            {/* Risk Analysis Section */}
            <div>
              <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold uppercase tracking-wide text-white/70">
                <Flame className="h-4 w-4 text-red-500" /> Risk Analysis
              </h3>

              <div className="space-y-4">
                {/* Risk Heatmap */}
                <RiskHeatmap
                  clauses={clauses || []}
                  isLoading={clausesLoading}
                  error={clausesError}
                />

                {/* Top risky clauses */}
                <div>
                  <div className="text-xs uppercase tracking-wide text-white/60 mb-2">
                    High-Risk Clauses ({topRiskyClauses.length})
                  </div>
                  <div className="space-y-2 max-h-48 overflow-y-auto">
                    {clausesLoading ? (
                      <div className="space-y-2">
                        {[...Array(3)].map((_, i) => (
                          <div key={i} className="animate-pulse">
                            <div className="h-8 bg-gray-700 rounded-lg"></div>
                          </div>
                        ))}
                      </div>
                    ) : clausesError ? (
                      <div className="text-xs text-red-400 p-3 rounded bg-red-500/10">
                        Failed to load clause analysis. Please refresh or try
                        again.
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
            </div>

            {/* Readability Analysis Section */}
            <div>
              <ReadabilityPanel
                clauses={clauses || []}
                isLoading={clausesLoading}
                error={clausesError}
              />
            </div>
          </div>
        </div>
      </aside>
    </div>
  );
};
