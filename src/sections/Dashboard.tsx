/* eslint-disable @typescript-eslint/no-explicit-any */
"use client";

import { useRef, useState, useEffect } from "react";
import {
  Menu,
  Plus,
  Upload,
  Search,
  FileText,
  MessageSquare,
  Paperclip,
  Send,
  Trash2,
  Flame,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  useDocumentWorkflow,
  useAskQuestion,
  useDocumentClauses,
  useDocumentStatus,
} from "@/hooks/useDocuments";
import { generateRiskHeatmap, getTopRiskyClauses } from "@/lib/api";

// ChatGPT-like dashboard for legal document assistant
// - Left: sidebar with New Chat, Upload, Recent Docs + search
// - Center: chat thread with composer, context chips for selected docs
// - Right: risk heatmap panel for the current thread

export const Dashboard = () => {
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const [messages, setMessages] = useState<
    {
      id: string;
      role: "user" | "assistant";
      content: string;
      isLoading?: boolean;
    }[]
  >([
    {
      id: "m1",
      role: "assistant",
      content:
        "Hi! Upload a legal document and ask me anything. I’ll summarize, flag risky clauses, and answer questions in simple language.",
    },
  ]);

  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [chatInput, setChatInput] = useState("");
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
  const { data: clauses = [], isLoading: clausesLoading } = useDocumentClauses(
    currentDocId,
    !!currentDocId
  );

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
      const uploadMsg = {
        id: `upload-${Date.now()}`,
        role: "assistant" as const,
        content: `Uploading ${file.name}... This may take a moment.`,
        isLoading: true,
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
      },
    ]);
    setSelectedDocs([]);
    setChatInput("");
  }

  async function sendMessage() {
    const content = chatInput.trim();
    if (!content) return;

    // Check if we have a document selected
    if (!currentDocId) {
      const errorMsg = {
        id: `error-${Date.now()}`,
        role: "assistant" as const,
        content:
          "Please upload and select a document first before asking questions.",
      };
      setMessages((prev) => [...prev, errorMsg]);
      return;
    }

    const userMsg = { id: `u-${Date.now()}`, role: "user" as const, content };
    const loadingMsg = {
      id: `loading-${Date.now()}`,
      role: "assistant" as const,
      content: "Analyzing your question and searching through the document...",
      isLoading: true,
    };

    // Immediate optimistic render
    setMessages((prev) => [...prev, userMsg, loadingMsg]);
    setChatInput("");

    try {
      // Ask the question using the API
      const response = await askQuestionMutation.mutateAsync({
        doc_id: currentDocId,
        question: content,
        session_id: `session-${Date.now()}`,
      });

      // Format the response with sources
      let answerContent = response.answer;
      if (response.sources && response.sources.length > 0) {
        answerContent += "\n\n**Sources:**\n";
        response.sources.forEach((source, index) => {
          answerContent += `${index + 1}. "${
            source.snippet
          }" (Relevance: ${Math.round(source.relevance_score * 100)}%)\n`;
        });
      }

      const assistantMsg = {
        id: `a-${Date.now()}`,
        role: "assistant" as const,
        content: answerContent,
      };

      // Replace loading message with actual response
      setMessages((prev) =>
        prev.map((msg) => (msg.id === loadingMsg.id ? assistantMsg : msg))
      );
    } catch (error: unknown) {
      console.error("Question failed:", error);

      const errorMsg = {
        id: `error-${Date.now()}`,
        role: "assistant" as const,
        content: `Sorry, I couldn't process your question: ${
          (error as any)?.response?.data?.detail ||
          (error as Error)?.message ||
          "Unknown error"
        }`,
      };

      // Replace loading message with error
      setMessages((prev) =>
        prev.map((msg) => (msg.id === loadingMsg.id ? errorMsg : msg))
      );
    }
  }

  // Generate risk matrix from actual clause data
  const riskMatrix = generateRiskHeatmap(clauses);
  const topRiskyClauses = getTopRiskyClauses(clauses);

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
            };
          }
          return msg;
        })
      );
    }
  }, [documentStatus, currentDocId]);

  return (
    <div className="flex h-screen w-full bg-[#0B0B0B] text-white antialiased">
      {/* Left Sidebar */}
      <aside
        className={`$${
          sidebarOpen ? "flex" : "hidden"
        } md:flex w-72 shrink-0 flex-col border-r border-white/10 bg-[#111111] p-4 gap-4`}
      >
        {/* Brand + Mobile toggle */}
        <div className="flex items-center justify-between">
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

        <div className="flex gap-2">
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

        <div className="mt-2">
          <label className="text-xs uppercase tracking-wide text-white/60">
            Recent documents
          </label>
          <div className="mt-2 flex items-center gap-2">
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

          <div className="mt-3 overflow-y-auto max-h-[56vh] pr-1 space-y-1">
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
      </aside>

      {/* Center Chat Column */}
      <section className="flex min-w-0 flex-1 flex-col items-center">
        {/* Mobile top bar */}
        <div className="flex w-full items-center justify-between border-b border-white/10 bg-[#111111] px-4 py-3 md:hidden">
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

        {/* Messages */}
        <div className="flex-1 w-full max-w-3xl overflow-y-auto px-4 md:px-6 py-6 space-y-4">
          {messages.map((m) => (
            <div key={m.id} className="flex w-full">
              {m.role === "assistant" ? (
                <div className="mr-auto max-w-[85%]">
                  <Card className="bg-[#121212] border-white/10">
                    <CardContent className="p-4 text-sm leading-6 text-white/90">
                      <div className="mb-2 flex items-center gap-2 text-white/70">
                        <MessageSquare className="h-4 w-4" /> Assistant
                      </div>
                      <div className="whitespace-pre-wrap">
                        {m.content}
                        {m.isLoading && (
                          <div className="mt-2 flex items-center gap-2">
                            <div className="h-2 w-2 bg-purple-400 rounded-full animate-pulse"></div>
                            <div className="h-2 w-2 bg-purple-400 rounded-full animate-pulse delay-75"></div>
                            <div className="h-2 w-2 bg-purple-400 rounded-full animate-pulse delay-150"></div>
                          </div>
                        )}
                      </div>
                    </CardContent>
                  </Card>
                </div>
              ) : (
                <div className="ml-auto max-w-[85%]">
                  <Card className="bg-[#18181B] border-white/10">
                    <CardContent className="p-4 text-sm leading-6">
                      <div className="mb-2 flex items-center justify-end gap-2 text-white/60">
                        You
                      </div>
                      <div className="whitespace-pre-wrap">{m.content}</div>
                    </CardContent>
                  </Card>
                </div>
              )}
            </div>
          ))}
        </div>

        {/* Context chips + Composer */}
        <div className="w-full max-w-3xl px-4 md:px-6 pb-4">
          {/* Context bar */}
          <div className="mb-2 flex flex-wrap items-center gap-2">
            {selectedDocs.length > 0 ? (
              <>
                {selectedDocs.map((id) => {
                  const d = recentDocs.find((x) => x.id === id);
                  if (!d) return null;
                  return (
                    <span
                      key={id}
                      className="inline-flex items-center gap-2 rounded-full border border-purple-500/30 bg-purple-500/10 px-3 py-1 text-xs"
                    >
                      <FileText className="h-3 w-3" /> {d.name}
                      <button
                        className="ml-1 text-white/60 hover:text-white"
                        onClick={() => toggleSelectDoc(id)}
                        aria-label={`Remove ${d.name}`}
                      >
                        ×
                      </button>
                    </span>
                  );
                })}
                <Button variant="ghost" size="sm" onClick={clearContext}>
                  <Trash2 className="mr-1 h-3 w-3" /> Clear context
                </Button>
              </>
            ) : (
              <div className="text-xs text-white/50">
                No documents selected. Upload or choose from sidebar.
              </div>
            )}
          </div>

          {/* Composer */}
          <div className="rounded-2xl border border-white/10 bg-[#0F0F0F] p-2">
            <div className="flex items-end gap-2">
              <Button variant="ghost" size="icon" onClick={handleUploadClick}>
                <Paperclip className="h-5 w-5" />
              </Button>
              <textarea
                rows={1}
                value={chatInput}
                onChange={(e) => setChatInput(e.target.value)}
                placeholder="Ask about clauses, risks, or a plain-English summary…"
                className="flex-1 resize-none bg-transparent px-2 py-2 text-sm outline-none placeholder:text-white/40"
              />
              <Button
                onClick={sendMessage}
                disabled={!chatInput.trim() || askQuestionMutation.isPending}
              >
                <Send className="mr-2 h-4 w-4" />
                {askQuestionMutation.isPending ? "Asking..." : "Send"}
              </Button>
            </div>
          </div>
        </div>
      </section>

      {/* Right Heatmap Panel */}
      <aside className="hidden xl:flex w-80 shrink-0 flex-col border-l border-white/10 bg-[#111111] p-4">
        <h3 className="mb-4 flex items-center gap-2 text-sm font-semibold uppercase tracking-wide text-white/70">
          <Flame className="h-4 w-4 text-red-500" /> Risk Heatmap
        </h3>

        {/* Heatmap grid (placeholder) */}
        <div className="grid grid-cols-6 gap-1 rounded-xl border border-white/10 bg-[#0F0F0F] p-2">
          {riskMatrix.flat().map((v, i) => {
            let bg = "bg-emerald-700";
            if (v > 0.7) bg = "bg-red-600";
            else if (v > 0.5) bg = "bg-orange-600";
            else if (v > 0.35) bg = "bg-yellow-600";
            else if (v > 0.2) bg = "bg-lime-700";
            return (
              <div
                key={i}
                className={`aspect-square rounded-sm ${bg} opacity-80`}
                title={`Risk ${(v * 100).toFixed(0)}%`}
              />
            );
          })}
        </div>

        {/* Legend */}
        <div className="mt-3 flex items-center justify-between text-[11px] text-white/60">
          <span>Low</span>
          <span>Medium</span>
          <span>High</span>
        </div>

        {/* Top risky clauses (placeholder) */}
        <div className="mt-6 space-y-2">
          <div className="text-xs uppercase tracking-wide text-white/60">
            Top clauses
          </div>
          {topRiskyClauses.length > 0 ? (
            topRiskyClauses.map((c) => (
              <div
                key={c.k}
                className="flex items-center justify-between rounded-lg border border-white/10 bg-[#0F0F0F] px-3 py-2"
              >
                <div className="text-sm">{c.k}</div>
                <div className="text-xs text-white/60">
                  {Math.round(c.risk * 100)}%
                </div>
              </div>
            ))
          ) : (
            <div className="text-xs text-white/50 p-3">
              {clausesLoading
                ? "Loading risk analysis..."
                : "Upload a document to see risk analysis"}
            </div>
          )}
        </div>
      </aside>
    </div>
  );
};
