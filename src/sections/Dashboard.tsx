"use client";

import { useRef, useState } from "react";
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

// ChatGPT-like dashboard for legal document assistant
// - Left: sidebar with New Chat, Upload, Recent Docs + search
// - Center: chat thread with composer, context chips for selected docs
// - Right: risk heatmap panel for the current thread

export const Dashboard = () => {
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const [messages, setMessages] = useState<
    { id: string; role: "user" | "assistant"; content: string }[]
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
    { id: string; name: string; date: string }[]
  >([
    { id: "d1", name: "Rental_Agreement.pdf", date: "2025-08-28" },
    { id: "d2", name: "Loan_Contract.pdf", date: "2025-08-15" },
    { id: "d3", name: "SaaS_ToS.docx", date: "2025-07-22" },
  ]);
  const [docQuery, setDocQuery] = useState("");
  const [selectedDocs, setSelectedDocs] = useState<string[]>([]);

  const filteredDocs = recentDocs.filter((d) =>
    d.name.toLowerCase().includes(docQuery.toLowerCase())
  );

  function handleUploadClick() {
    fileInputRef.current?.click();
  }

  function handleFilesSelected(files: FileList | null) {
    if (!files || files.length === 0) return;
    const added = Array.from(files).map((f, i) => ({
      id: `u-${Date.now()}-${i}`,
      name: f.name,
      date: new Date().toISOString().slice(0, 10),
    }));
    setRecentDocs((prev) => [...added, ...prev]);
    setSelectedDocs((prev) => [...added.map((a) => a.id), ...prev]);
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

  function sendMessage() {
    const content = chatInput.trim();
    if (!content) return;
    const userMsg = { id: `u-${Date.now()}`, role: "user" as const, content };
    // Immediate optimistic render
    setMessages((prev) => [...prev, userMsg]);
    setChatInput("");

    // Placeholder assistant response (wire to backend later)
    const ctx = selectedDocs
      .map((id) => recentDocs.find((d) => d.id === id)?.name)
      .filter(Boolean)
      .join(", ");

    const assistantMsg = {
      id: `a-${Date.now()}`,
      role: "assistant" as const,
      content:
        ctx
          ? `Analyzing your question *with context*: ${ctx}.\n\n(Backend hook TBD) Here I would summarize relevant clauses, explain risks, and answer in plain English.`
          : `(Backend hook TBD) I’ll answer and summarize once a document is selected or uploaded. You can still ask general questions about legal terms.`,
    };
    setMessages((prev) => [...prev, assistantMsg]);
  }

  // Simple risk matrix (placeholder). In real app, fill from model output.
  const riskMatrix = [
    [0.2, 0.4, 0.1, 0.6, 0.8, 0.3],
    [0.1, 0.5, 0.7, 0.2, 0.4, 0.9],
    [0.3, 0.2, 0.6, 0.5, 0.7, 0.4],
    [0.6, 0.8, 0.2, 0.3, 0.5, 0.7],
  ];

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
          <label className="text-xs uppercase tracking-wide text-white/60">Recent documents</label>
          <div className="mt-2 flex items-center gap-2">
            <Input
              placeholder="Search documents"
              value={docQuery}
              onChange={(e) => setDocQuery(e.target.value)}
              className="bg-[#0F0F0F] border-white/10"
            />
            <Button variant="ghost" size="icon" className="border border-white/10">
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
                      <div className="text-[10px] text-white/50">{doc.date}</div>
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
          <Button variant="ghost" size="icon" onClick={() => setSidebarOpen(true)}>
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
                      <div className="whitespace-pre-wrap">{m.content}</div>
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
              <div className="text-xs text-white/50">No documents selected. Upload or choose from sidebar.</div>
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
              <Button onClick={sendMessage}>
                <Send className="mr-2 h-4 w-4" /> Send
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
          <div className="text-xs uppercase tracking-wide text-white/60">Top clauses</div>
          {[
            { k: "Termination without cause", risk: 0.86 },
            { k: "Unilateral fee change", risk: 0.78 },
            { k: "Broad indemnity", risk: 0.72 },
          ].map((c) => (
            <div
              key={c.k}
              className="flex items-center justify-between rounded-lg border border-white/10 bg-[#0F0F0F] px-3 py-2"
            >
              <div className="text-sm">{c.k}</div>
              <div className="text-xs text-white/60">{Math.round(c.risk * 100)}%</div>
            </div>
          ))}
        </div>
      </aside>
    </div>
  );
}
