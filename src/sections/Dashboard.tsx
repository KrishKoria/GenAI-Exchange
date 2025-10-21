"use client";

import { useState, useMemo, useCallback, useRef, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { BarChart3 } from "lucide-react";
import {
  useDocumentWithClauses,
  useMultipleDocumentsClauses,
} from "@/hooks/useDocuments";
import { ChatInterface } from "@/components/ChatInterface";
import { useTranslations } from "next-intl";
import { useDocumentManagement } from "@/hooks/useDocumentManagement";
import { useNegotiationState } from "@/hooks/useNegotiationState";
import { useFileUpload } from "@/hooks/useFileUpload";
import { useChatMessages } from "@/hooks/useChatMessages";
import { Sidebar } from "@/components/Sidebar";
import { MobileHeader } from "@/components/MobileHeader";
import { UploadCardsContainer } from "@/components/UploadCardsContainer";
import { AnalysisPanel } from "@/components/AnalysisPanel";

export const Dashboard = () => {
  const t = useTranslations();

  // UI state
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [rightPanelOpen, setRightPanelOpen] = useState(false);

  // Document management hook
  const documentManagement = useDocumentManagement();

  // Create a ref to store the updateProcessingMessage function to avoid circular dependency
  const updateProcessingMessageRef = useRef<
    (status: string, clauseCount?: number) => void
  >(() => {});

  // Memoize the callback to ensure stable reference
  const handleUpdateProcessingMessage = useCallback(
    (status: string, clauseCount?: number) => {
      updateProcessingMessageRef.current(status, clauseCount);
    },
    []
  );

  // File upload hook
  const fileUpload = useFileUpload({
    onDocumentAdded: documentManagement.addDocument,
    onDocumentsAdded: documentManagement.addDocuments,
    onDocumentSelected: documentManagement.setSelectedDocs,
    currentDocId: documentManagement.currentDocId,
    onUpdateDocumentStatus: documentManagement.updateDocumentStatus,
    onUpdateProcessingMessage: handleUpdateProcessingMessage,
  });

  // Fetch clause data (single or multiple documents)
  const { clauses: singleClausesQuery } = useDocumentWithClauses(
    documentManagement.currentDocId
  );
  const multiClausesQuery = useMultipleDocumentsClauses(
    documentManagement.selectedDocs
  );

  // Use multi-document clauses for analysis, fall back to single document if only one selected
  const clauses = useMemo(() => {
    if (documentManagement.selectedDocs.length > 1) {
      return multiClausesQuery.data || [];
    } else {
      return singleClausesQuery.data || [];
    }
  }, [
    documentManagement.selectedDocs.length,
    multiClausesQuery.data,
    singleClausesQuery.data,
  ]);

  const clausesLoading =
    documentManagement.selectedDocs.length > 1
      ? multiClausesQuery.isLoading
      : singleClausesQuery.isLoading;
  const clausesError =
    documentManagement.selectedDocs.length > 1
      ? multiClausesQuery.error
      : singleClausesQuery.error;

  // Negotiation state hook
  const negotiationState = useNegotiationState({
    currentDocId: documentManagement.currentDocId,
    clauses: clauses,
    onAddChatMessage: (
      clauseCategory,
      alternativeType,
      strategicBenefit,
      messageType
    ) => {
      // Add automated negotiation message to chat
      const message =
        messageType === "generated"
          ? {
              id: `negotiation-gen-${Date.now()}`,
              role: "assistant" as const,
              content: `🎯 **AI Negotiation Alternatives Generated**\n\nI've created 3 strategic alternatives for your **${clauseCategory}** clause. Each alternative offers a different approach:\n\n• **Balanced** - Middle-ground solution\n\n• **Protective** - Maximum risk reduction\n\n• **Simplified** - Clearer, more direct language\n\nReview them in the right panel and select the one that best fits your negotiation strategy. Feel free to ask me questions about any of the alternatives!`,
              timestamp: new Date(),
            }
          : {
              id: `negotiation-sel-${Date.now()}`,
              role: "assistant" as const,
              content: `✅ **Alternative Selected!**\n\nYou've chosen the **${alternativeType}** alternative for your **${clauseCategory}** clause.\n\n**Strategic Benefit:**\n${strategicBenefit}\n\n💡 **Next Steps:**\n• Ask me to compare it with the original clause\n• Request an explanation of legal implications\n• Get help drafting a proposal email\n• Inquire about how this affects other clauses\n\nWhat would you like to know about your selection?`,
              timestamp: new Date(),
            };

      chatMessages.addMessage(message);
    },
  });

  // Chat messages hook
  const chatMessages = useChatMessages({
    currentDocId: documentManagement.currentDocId,
    selectedDocs: documentManagement.selectedDocs,
    negotiationContext: {
      panelOpen: negotiationState.negotiationPanelOpen,
      buildFullContext: negotiationState.buildFullNegotiationContext,
      buildSelectedContext: negotiationState.buildSelectedAlternativesContext,
    },
    welcomeMessage: t("chat.welcomeMessage"),
    newChatMessage: t("chat.newChatStarted"),
  });

  // Update the ref with the actual function after chatMessages is initialized
  useEffect(() => {
    updateProcessingMessageRef.current = chatMessages.updateProcessingMessage;
  }, [chatMessages.updateProcessingMessage]);

  // Convert selected docs to the format expected by ChatInterface
  const selectedDocuments = documentManagement.selectedDocs
    .map((id) => {
      const doc = documentManagement.recentDocs.find((d) => d.id === id);
      return doc
        ? { id: doc.id, name: doc.name, status: doc.status }
        : { id, name: "Loading...", status: undefined };
    })
    .filter(Boolean);

  return (
    <div className="flex h-screen w-full bg-[#0B0B0B] text-white antialiased overflow-hidden">
      {/* Left Sidebar */}
      <Sidebar
        sidebarOpen={sidebarOpen}
        setSidebarOpen={setSidebarOpen}
        onNewChat={chatMessages.newChat}
        onUploadClick={fileUpload.handleUploadClick}
        filteredDocs={documentManagement.filteredDocs}
        selectedDocs={documentManagement.selectedDocs}
        docQuery={documentManagement.docQuery}
        onDocQueryChange={documentManagement.setDocQuery}
        onToggleDoc={documentManagement.toggleSelectDoc}
        appTitle={t("app.title").split(" - ")[0]}
        newChatLabel={t("navigation.newChat")}
        uploadLabel={t("navigation.upload")}
        recentDocumentsLabel={t("navigation.recentDocuments")}
        searchPlaceholder={t("navigation.searchDocuments")}
        noDocumentsText={t("documents.noDocumentsFound")}
      />

      {/* Center Chat Column */}
      <section className="flex min-w-0 flex-1 flex-col bg-[#0B0B0B] h-full overflow-hidden">
        {/* Mobile Header */}
        <MobileHeader
          onOpenSidebar={() => setSidebarOpen(true)}
          onToggleRightPanel={() => setRightPanelOpen(true)}
          currentDocId={documentManagement.currentDocId}
          appTitle="LegalEase AI"
        />

        {/* Desktop analysis panel toggle */}
        <div className="hidden lg:flex xl:hidden fixed top-4 right-4 z-10">
          <Button
            variant="secondary"
            size="sm"
            onClick={() => setRightPanelOpen(!rightPanelOpen)}
            className={documentManagement.currentDocId ? "" : "opacity-50"}
            disabled={!documentManagement.currentDocId}
          >
            <BarChart3 className="h-4 w-4 mr-2" />
            {t("navigation.analysis")}
          </Button>
        </div>

        {/* Upload Cards */}
        <UploadCardsContainer
          uploadCards={fileUpload.uploadCards}
          onRetry={fileUpload.handleUploadClick}
          onDismiss={fileUpload.dismissUploadCard}
        />

        {/* Chat Interface - Independent Scroll Area */}
        <div className="flex-1 w-full bg-[#0B0B0B] h-full overflow-hidden px-4">
          <ChatInterface
            messages={chatMessages.messages}
            onSendMessage={chatMessages.sendMessage}
            onRetryMessage={chatMessages.handleRetry}
            onFeedback={chatMessages.handleFeedback}
            selectedDocuments={selectedDocuments}
            onRemoveDocument={(docId) =>
              documentManagement.toggleSelectDoc(docId)
            }
            onClearContext={documentManagement.clearContext}
            onUploadClick={fileUpload.handleUploadClick}
            isProcessing={false}
            disabled={false}
          />
        </div>

        {/* Hidden file input */}
        <input
          ref={fileUpload.fileInputRef}
          type="file"
          className="hidden"
          multiple
          onChange={(e) => fileUpload.handleFilesSelected(e.target.files)}
        />
      </section>

      {/* Right Analysis Panel */}
      <AnalysisPanel
        rightPanelOpen={rightPanelOpen}
        setRightPanelOpen={setRightPanelOpen}
        clauses={clauses}
        clausesLoading={clausesLoading}
        clausesError={clausesError}
        negotiationState={negotiationState}
        selectedClauseForNegotiation={
          negotiationState.selectedClauseForNegotiation
        }
        onCopyAlternative={(altId) => {
          console.log("Copied alternative:", altId);
        }}
        analysisTitle={t("analysis.title")}
        riskAnalysisTitle={t("analysis.riskAnalysis")}
        negotiationTitle="AI Negotiation Assistant"
        closeLabel="Close"
        showNegotiationLabel="Show Negotiation Alternatives"
      />
    </div>
  );
};
