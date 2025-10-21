import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Menu, Plus, Upload, Search, FileText } from "lucide-react";
import { LanguageSelector } from "@/components/LanguageSelector";
import { Document } from "@/hooks/useDocumentManagement";

export interface SidebarProps {
  sidebarOpen: boolean;
  setSidebarOpen: (open: boolean) => void;
  onNewChat: () => void;
  onUploadClick: () => void;
  filteredDocs: Document[];
  selectedDocs: string[];
  docQuery: string;
  onDocQueryChange: (query: string) => void;
  onToggleDoc: (id: string) => void;
  appTitle: string;
  newChatLabel: string;
  uploadLabel: string;
  recentDocumentsLabel: string;
  searchPlaceholder: string;
  noDocumentsText: string;
}

/**
 * Sidebar component with document list and navigation
 */
export const Sidebar = ({
  sidebarOpen,
  setSidebarOpen,
  onNewChat,
  onUploadClick,
  filteredDocs,
  selectedDocs,
  docQuery,
  onDocQueryChange,
  onToggleDoc,
  appTitle,
  newChatLabel,
  uploadLabel,
  recentDocumentsLabel,
  searchPlaceholder,
  noDocumentsText,
}: SidebarProps) => {
  return (
    <aside
      className={`${
        sidebarOpen ? "flex" : "hidden"
      } md:flex w-64 shrink-0 flex-col border-r border-white/10 bg-[#111111] h-full overflow-hidden`}
    >
      <div className="p-4 flex flex-col gap-4 h-full overflow-hidden">
        {/* Brand + Language Selector + Mobile toggle */}
        <div className="flex items-center justify-between shrink-0">
          <div className="text-xl font-semibold bg-gradient-to-r from-purple-400 to-pink-500 bg-clip-text text-transparent">
            {appTitle}
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
          <Button className="flex-1" onClick={onNewChat}>
            <Plus className="mr-2 h-4 w-4" /> {newChatLabel}
          </Button>
          <Button variant="secondary" onClick={onUploadClick}>
            <Upload className="mr-2 h-4 w-4" /> {uploadLabel}
          </Button>
        </div>

        <div className="flex flex-col min-h-0 flex-1">
          <label className="text-xs uppercase tracking-wide text-white/60 shrink-0">
            {recentDocumentsLabel}
          </label>
          <div className="mt-2 flex items-center gap-2 shrink-0">
            <Input
              placeholder={searchPlaceholder}
              value={docQuery}
              onChange={(e) => onDocQueryChange(e.target.value)}
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
              <div className="text-xs text-white/50">{noDocumentsText}</div>
            )}
            {filteredDocs.map((doc) => {
              const checked = selectedDocs.includes(doc.id);
              return (
                <button
                  key={doc.id}
                  onClick={() => onToggleDoc(doc.id)}
                  className={`group flex w-full items-center justify-between rounded-lg border px-3 py-2 text-left transition-all duration-200 transform ${
                    checked
                      ? "border-purple-500/70 bg-gradient-to-r from-purple-500/20 to-purple-600/10 ring-2 ring-purple-500/40 shadow-lg shadow-purple-500/20 scale-[1.02]"
                      : "border-white/5 bg-[#0F0F0F] hover:border-white/20 hover:bg-white/5"
                  }`}
                >
                  <div className="flex items-center gap-2">
                    <FileText
                      className={`h-4 w-4 transition-colors duration-200 ${
                        checked ? "text-purple-400" : "text-white/70"
                      }`}
                    />
                    <div>
                      <div
                        className={`text-sm leading-tight transition-colors duration-200 ${
                          checked ? "text-white" : "text-white/90"
                        }`}
                      >
                        {doc.name}
                      </div>
                      <div
                        className={`text-[10px] transition-colors duration-200 ${
                          checked ? "text-purple-200/80" : "text-white/50"
                        }`}
                      >
                        {doc.date} {doc.status && `• ${doc.status}`}
                      </div>
                    </div>
                  </div>
                  <div
                    className={`relative h-4 w-4 rounded-full border-2 transition-all duration-200 ${
                      checked
                        ? "bg-purple-500 border-purple-400 shadow-md shadow-purple-500/50"
                        : "bg-transparent border-white/30 group-hover:border-white/50"
                    }`}
                  >
                    {checked && (
                      <svg
                        className="absolute inset-0 w-full h-full p-0.5 text-white"
                        fill="currentColor"
                        viewBox="0 0 20 20"
                      >
                        <path
                          fillRule="evenodd"
                          d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                          clipRule="evenodd"
                        />
                      </svg>
                    )}
                  </div>
                </button>
              );
            })}
          </div>
        </div>
      </div>
    </aside>
  );
};
