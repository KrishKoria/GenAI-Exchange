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
  Sparkles,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  useDocumentWorkflow,
  useDocumentWithClauses,
  useMultipleDocumentsClauses,
  useCreateChatSession,
  useChatAwareAskQuestion,
  useUpdateDocumentContext,
  useBatchDocumentUpload,
} from "@/hooks/useDocuments";
import { RiskHeatmap } from "@/components/RiskHeatmap";
import { ChatInterface, ChatMessage } from "@/components/ChatInterface";
import { UploadSuccessCard } from "@/components/UploadSuccessCard";
import { ReadabilityPanel } from "@/components/ReadabilityPanel";
import { LanguageSelector } from "@/components/LanguageSelector";
import { NegotiationPanel } from "@/components/NegotiationPanel";
import { useNegotiation } from "@/hooks/useNegotiation";
import { useTranslations } from "next-intl";
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

  // Negotiation feature state
  const [negotiationPanelOpen, setNegotiationPanelOpen] = useState(false);
  const [selectedClauseForNegotiation, setSelectedClauseForNegotiation] =
    useState<{
      clause_id: string;
      clause_text: string;
      clause_category: string;
      risk_level: string;
    } | null>(null);

  // Track selected alternatives for chat integration
  const [selectedAlternatives, setSelectedAlternatives] = useState<{
    [clauseId: string]: {
      alternativeId: string;
      alternativeType: string;
      clauseCategory: string;
      strategicBenefit: string;
      selectedAt: Date;
    };
  }>({});

  const { toast } = useToast();

  // API hooks
  const { upload: uploadDocument } = useDocumentWorkflow();
  const batchUploadDocuments = useBatchDocumentUpload();
  const askQuestionMutation = useChatAwareAskQuestion();
  const createChatSessionMutation = useCreateChatSession();
  const updateDocumentContextMutation = useUpdateDocumentContext();

  // Negotiation hooks
  const negotiation = useNegotiation(currentDocId);

  // Keep single document hook for backward compatibility (status info, etc.)
  const { status: statusQuery, clauses: singleClausesQuery } =
    useDocumentWithClauses(currentDocId);

  // New multi-document hook for risk and readability analysis
  const multiClausesQuery = useMultipleDocumentsClauses(selectedDocs);

  const documentStatus = statusQuery.data;

  // Use multi-document clauses for analysis, fall back to single document if only one selected
  const clauses = useMemo(() => {
    if (selectedDocs.length > 1) {
      return multiClausesQuery.data || [];
    } else {
      return singleClausesQuery.data || [];
    }
  }, [selectedDocs.length, multiClausesQuery.data, singleClausesQuery.data]);

  const clausesLoading =
    selectedDocs.length > 1
      ? multiClausesQuery.isLoading
      : singleClausesQuery.isLoading;
  const clausesError =
    selectedDocs.length > 1
      ? multiClausesQuery.error
      : singleClausesQuery.error;

  const filteredDocs = recentDocs.filter((d) =>
    d.name.toLowerCase().includes(docQuery.toLowerCase())
  );

  function handleUploadClick() {
    fileInputRef.current?.click();
  }

  async function handleFilesSelected(files: FileList | null) {
    if (!files || files.length === 0) return;

    const filesArray = Array.from(files);
    const sessionId = `session-${Date.now()}`;

    // Validate all files first
    const validationResults = filesArray.map((file) => ({
      file,
      validation: validateFileBasics(file),
    }));

    // Check if any files have validation errors
    const invalidFiles = validationResults.filter(
      (result) => !result.validation.isValid
    );
    if (invalidFiles.length > 0) {
      const errorMessages = invalidFiles.map(
        (result) => `${result.file.name}: ${result.validation.errors.join(" ")}`
      );
      toast(
        createToast.error(
          `Invalid File${invalidFiles.length > 1 ? "s" : ""}`,
          errorMessages.join("\n")
        )
      );
      return;
    }

    // Show warnings for any files with warnings
    const filesWithWarnings = validationResults.filter(
      (result) => result.validation.warnings.length > 0
    );
    if (filesWithWarnings.length > 0) {
      const warningMessages = filesWithWarnings.map(
        (result) =>
          `${result.file.name}: ${result.validation.warnings.join(" ")}`
      );
      toast(
        createToast.warning(
          `File Upload Warning${filesWithWarnings.length > 1 ? "s" : ""}`,
          warningMessages.join("\n")
        )
      );
    }

    // Create upload cards for all files
    const uploadCardIds = filesArray.map((file, index) => {
      const cardId = `upload-${Date.now()}-${index}`;
      setUploadCards((prev) => ({
        ...prev,
        [cardId]: {
          filename: file.name,
          fileSize: file.size,
          status: "uploading",
          progress: 25,
        },
      }));
      return { cardId, file };
    });

    try {
      // Use batch upload for multiple files, single upload for one file
      if (filesArray.length === 1) {
        const file = filesArray[0];
        const cardId = uploadCardIds[0].cardId;

        const response = await uploadDocument.mutateAsync({
          file,
          sessionId,
        });

        // Add to recent docs and select
        const newDoc = {
          id: response.doc_id,
          name: response.filename,
          date: new Date().toISOString().slice(0, 10),
          status: response.status,
        };

        setRecentDocs((prev) => [newDoc, ...prev]);
        setSelectedDocs([response.doc_id]);
        setCurrentDocId(response.doc_id);

        // Update upload card
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
      } else {
        // Batch upload for multiple files
        const response = await batchUploadDocuments.mutateAsync({
          files: filesArray,
          sessionId,
        });

        // Defensive check for response structure
        if (
          !response ||
          !response.uploads ||
          !Array.isArray(response.uploads)
        ) {
          console.error("Invalid batch upload response:", response);
          throw new Error("Invalid response from batch upload");
        }

        // Process successful uploads
        const newDocs = response.uploads
          .filter((upload) => upload.status !== "failed")
          .map((upload) => ({
            id: upload.doc_id,
            name: upload.filename,
            date: new Date().toISOString().slice(0, 10),
            status: upload.status,
          }));

        // Add all successful docs to recent docs
        if (newDocs.length > 0) {
          setRecentDocs((prev) => [...newDocs, ...prev]);
          setSelectedDocs(newDocs.map((doc) => doc.id));
          setCurrentDocId(newDocs[0].id);
        }

        // Update upload cards based on results
        uploadCardIds.forEach(({ cardId, file }) => {
          const uploadResult = response.uploads?.find(
            (upload) => upload.filename === file.name
          );

          setUploadCards((prev) => ({
            ...prev,
            [cardId]: {
              ...prev[cardId],
              status:
                uploadResult?.status === "failed" ? "failed" : "processing",
              progress: uploadResult?.status === "failed" ? 0 : 75,
              error:
                uploadResult?.status === "failed"
                  ? uploadResult.message
                  : undefined,
            },
          }));
        });

        // Show batch upload results
        toast(
          createToast.success(
            "Batch Upload Completed",
            `${response.successful_count || 0}/${
              response.total_count || filesArray.length
            } files uploaded successfully. ${
              (response.failed_count || 0) > 0
                ? `${response.failed_count} files failed.`
                : "All documents are being processed."
            }`
          )
        );

        // Show failed uploads if any
        if ((response.failed_count || 0) > 0 && response.uploads) {
          const failedUploads = response.uploads.filter(
            (upload) => upload.status === "failed"
          );
          const failedMessages = failedUploads.map(
            (upload) =>
              `${upload.filename}: ${upload.message || "Unknown error"}`
          );

          toast(
            createToast.error(
              `Failed Upload${failedUploads.length > 1 ? "s" : ""}`,
              failedMessages.join("\n")
            )
          );
        }
      }
    } catch (error: unknown) {
      console.error("Upload failed:", error);

      // Extract error details for better UX
      const errorResponse = (error as any)?.response;
      const errorMessage =
        errorResponse?.data?.detail ||
        (error as Error)?.message ||
        "An unexpected error occurred while uploading your documents.";

      const isValidationError =
        errorResponse?.status === 422 || errorResponse?.status === 413;

      // Update all upload cards to failed
      uploadCardIds.forEach(({ cardId }) => {
        setUploadCards((prev) => ({
          ...prev,
          [cardId]: {
            ...prev[cardId],
            status: "failed",
            error: errorMessage,
          },
        }));
      });

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
          content: t("chat.newChatStarted"),
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
          content: t("chat.newChatStarted"),
          timestamp: new Date(),
        },
      ]);
      setSelectedDocs([]);
    }
  }

  async function sendMessage(content: string) {
    // Create user message immediately for optimistic UI
    const userMsg: ChatMessage = {
      id: `u-${Date.now()}`,
      role: "user",
      content,
      timestamp: new Date(),
    };

    // Add user message immediately (optimistic update)
    setMessages((prev) => [...prev, userMsg]);

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

    // Create loading message for assistant response
    const loadingMsg: ChatMessage = {
      id: `loading-${Date.now()}`,
      role: "assistant",
      content:
        "✨ Analyzing your question and searching through the document...",
      isLoading: true,
      timestamp: new Date(),
    };

    // Add loading message
    setMessages((prev) => [...prev, loadingMsg]);

    try {
      // Create chat session if we don't have one (async, non-blocking)
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

      // Update document context if needed (async, non-blocking)
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

      // Inject negotiation context - prioritize open negotiation over past selections
      let enhancedQuestion = content;

      // Priority 1: If negotiation panel is open, include full context with all alternatives
      if (negotiationPanelOpen && negotiation.generateAlternatives.data) {
        enhancedQuestion = content + buildFullNegotiationContext();
      }
      // Priority 2: If alternatives were selected recently, include brief context
      else if (Object.keys(selectedAlternatives).length > 0) {
        enhancedQuestion = content + buildSelectedAlternativesContext();
      }

      // Ask the question using the chat-aware API
      const response = await askQuestionMutation.mutateAsync({
        doc_id: currentDocId,
        question: enhancedQuestion,
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
        content: `❌ Sorry, I couldn't process your question: ${
          (error as any)?.response?.data?.detail ||
          (error as Error)?.message ||
          "Network error. Please check your connection and try again."
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

  // Handle generating negotiation alternatives
  async function handleGenerateAlternatives(
    clauseId: string,
    clauseCategory: string,
    riskLevel: string
  ) {
    if (!currentDocId) {
      toast(
        createToast.error(
          "No Document Selected",
          "Please select a document first."
        )
      );
      return;
    }

    try {
      // Find the clause in our local data first for quick display
      const clause = clauses.find((c) => c.clause_id === clauseId);
      if (!clause) {
        throw new Error("Clause not found");
      }

      // Store the clause details and open the panel
      setSelectedClauseForNegotiation({
        clause_id: clauseId,
        clause_text: clause.summary, // Use summary as placeholder until we get full text
        clause_category: clauseCategory,
        risk_level: riskLevel,
      });
      setNegotiationPanelOpen(true);

      // Generate alternatives - the backend will fetch the original_text
      await negotiation.generateAlternatives.mutateAsync({
        clause_text: clause.summary, // Backend can use clause_id to fetch original_text
        clause_category: clauseCategory,
        clause_id: clauseId,
        doc_id: currentDocId,
        risk_level: riskLevel as any,
      });

      // Add automated message to chat about the generated alternatives
      addNegotiationMessageToChat(
        clauseCategory,
        undefined,
        undefined,
        "generated"
      );

      toast(
        createToast.success(
          "Alternatives Generated",
          "AI has generated 3 strategic alternatives for your clause."
        )
      );
    } catch (error: unknown) {
      console.error("Failed to generate alternatives:", error);
      toast(
        createToast.error(
          "Generation Failed",
          (error as Error)?.message ||
            "Failed to generate alternatives. Please try again."
        )
      );
    }
  }

  function closeNegotiationPanel() {
    setNegotiationPanelOpen(false);
  }

  // Reopen negotiation panel
  function reopenNegotiationPanel() {
    setNegotiationPanelOpen(true);
  }

  // Add automated negotiation message to chat
  function addNegotiationMessageToChat(
    clauseCategory: string,
    alternativeType?: string,
    strategicBenefit?: string,
    messageType: "generated" | "selected" = "generated"
  ) {
    const message: ChatMessage =
      messageType === "generated"
        ? {
            id: `negotiation-gen-${Date.now()}`,
            role: "assistant",
            content: `🎯 **AI Negotiation Alternatives Generated**\n\nI've created 3 strategic alternatives for your **${clauseCategory}** clause. Each alternative offers a different approach:\n\n• **Balanced** - Middle-ground solution\n\n• **Protective** - Maximum risk reduction\n\n• **Simplified** - Clearer, more direct language\n\nReview them in the right panel and select the one that best fits your negotiation strategy. Feel free to ask me questions about any of the alternatives!`,
            timestamp: new Date(),
          }
        : {
            id: `negotiation-sel-${Date.now()}`,
            role: "assistant",
            content: `✅ **Alternative Selected!**\n\nYou've chosen the **${alternativeType}** alternative for your **${clauseCategory}** clause.\n\n**Strategic Benefit:**\n${strategicBenefit}\n\n💡 **Next Steps:**\n• Ask me to compare it with the original clause\n• Request an explanation of legal implications\n• Get help drafting a proposal email\n• Inquire about how this affects other clauses\n\nWhat would you like to know about your selection?`,
            timestamp: new Date(),
          };

    setMessages((prev) => [...prev, message]);
  }

  // Build comprehensive negotiation context for chatbot (when panel is open)
  function buildFullNegotiationContext(): string {
    if (
      !negotiation.generateAlternatives.data ||
      !selectedClauseForNegotiation
    ) {
      return "";
    }

    const data = negotiation.generateAlternatives.data;
    const selectedId = Object.values(selectedAlternatives).find(
      (alt) =>
        alt.clauseCategory === selectedClauseForNegotiation.clause_category
    )?.alternativeId;

    let context = `\n\n[NEGOTIATION CONTEXT for ${selectedClauseForNegotiation.clause_category} Clause:\n\n`;
    context += `ORIGINAL CLAUSE:\n"${data.original_clause}"\n\n`;
    context += `GENERATED ALTERNATIVES:\n\n`;

    data.alternatives.forEach((alt, index) => {
      const altType =
        alt.alternative_type.charAt(0).toUpperCase() +
        alt.alternative_type.slice(1);
      const isSelected = alt.alternative_id === selectedId;

      context += `${index + 1}. ${altType.toUpperCase()} Alternative${
        isSelected ? " (SELECTED)" : ""
      }:\n`;
      context += `"${alt.alternative_text}"\n`;
      context += `Strategic Benefit: ${alt.strategic_benefit}\n`;
      context += `Risk Reduction: ${alt.risk_reduction}\n\n`;
    });

    context += `]`;
    return context;
  }

  // Build brief context for selected alternatives (when panel is closed)
  function buildSelectedAlternativesContext(): string {
    const recentSelections = Object.entries(selectedAlternatives).filter(
      ([, alt]) => {
        const minutesAgo =
          (new Date().getTime() - alt.selectedAt.getTime()) / (1000 * 60);
        return minutesAgo < 30; // Only include selections from last 30 minutes
      }
    );

    if (recentSelections.length === 0) {
      return "";
    }

    let context = `\n\n[RECENT NEGOTIATION DECISIONS:\n\n`;
    recentSelections.forEach(([, alt]) => {
      context += `• Selected "${alt.alternativeType}" alternative for ${alt.clauseCategory} clause\n`;
      context += `  Strategic Benefit: ${alt.strategicBenefit}\n\n`;
    });
    context += `]`;

    return context;
  }

  // Handle selecting an alternative
  async function handleSelectAlternative(alternativeId: string) {
    if (
      !negotiation.generateAlternatives.data?.negotiation_id ||
      !selectedClauseForNegotiation
    ) {
      return;
    }

    try {
      await negotiation.saveFeedback(
        negotiation.generateAlternatives.data.negotiation_id,
        selectedClauseForNegotiation.clause_id,
        alternativeId,
        true
      );

      // Find the selected alternative details
      const selectedAlt =
        negotiation.generateAlternatives.data.alternatives.find(
          (alt) => alt.alternative_id === alternativeId
        );

      if (selectedAlt) {
        // Track the selection in state
        setSelectedAlternatives((prev) => ({
          ...prev,
          [selectedClauseForNegotiation.clause_id]: {
            alternativeId: alternativeId,
            alternativeType:
              selectedAlt.alternative_type.charAt(0).toUpperCase() +
              selectedAlt.alternative_type.slice(1),
            clauseCategory: selectedClauseForNegotiation.clause_category,
            strategicBenefit: selectedAlt.strategic_benefit,
            selectedAt: new Date(),
          },
        }));

        // Add automated message to chat about the selection
        addNegotiationMessageToChat(
          selectedClauseForNegotiation.clause_category,
          selectedAlt.alternative_type.charAt(0).toUpperCase() +
            selectedAlt.alternative_type.slice(1),
          selectedAlt.strategic_benefit,
          "selected"
        );
      }

      toast(
        createToast.success(
          "Alternative Saved",
          "Your selection has been recorded and added to the chat."
        )
      );
    } catch (error) {
      console.error("Failed to save alternative:", error);
    }
  }

  // Generate top risky clauses - memoized for performance

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
              {t("navigation.recentDocuments")}
            </label>
            <div className="mt-2 flex items-center gap-2 shrink-0">
              <Input
                placeholder={t("navigation.searchDocuments")}
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
                <div className="text-xs text-white/50">
                  {t("documents.noDocumentsFound")}
                </div>
              )}
              {filteredDocs.map((doc) => {
                const checked = selectedDocs.includes(doc.id);
                return (
                  <button
                    key={doc.id}
                    onClick={() => toggleSelectDoc(doc.id)}
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
            {t("navigation.analysis")}
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
              {t("analysis.title")}
            </h2>
            <Button
              variant="ghost"
              size="icon"
              onClick={() => setRightPanelOpen(false)}
            >
              <X className="h-5 w-5" />
            </Button>
          </div>

          {/* Scrollable content area */}
          <div className="flex-1 overflow-y-auto no-scrollbar space-y-6 pr-2">
            {/* Risk Analysis Section */}
            <div>
              <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold uppercase tracking-wide text-white/70">
                <Flame className="h-4 w-4 text-red-500" />{" "}
                {t("analysis.riskAnalysis")}
              </h3>

              <div className="space-y-4">
                {/* Risk Heatmap */}
                <RiskHeatmap
                  clauses={clauses || []}
                  isLoading={clausesLoading}
                  error={clausesError}
                  onGenerateAlternatives={handleGenerateAlternatives}
                />

                {/* Reopen Negotiation Button (when panel closed but data exists) */}
                {!negotiationPanelOpen && selectedClauseForNegotiation && (
                  <Button
                    onClick={reopenNegotiationPanel}
                    variant="outline"
                    size="sm"
                    className="w-full border-purple-500/30 bg-purple-500/10 hover:bg-purple-500/20 text-purple-300 hover:text-purple-200"
                  >
                    <Sparkles className="h-4 w-4 mr-2" />
                    Show Negotiation Alternatives
                  </Button>
                )}
              </div>
            </div>

            {/* AI Negotiation Assistant Section */}
            {negotiationPanelOpen && selectedClauseForNegotiation && (
              <div>
                <div className="mb-3 flex items-center justify-between">
                  <h3 className="flex items-center gap-2 text-sm font-semibold uppercase tracking-wide text-white/70">
                    <Sparkles className="h-4 w-4 text-purple-500" />
                    AI Negotiation Assistant
                  </h3>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={closeNegotiationPanel}
                    className="h-6 text-xs"
                  >
                    Close
                  </Button>
                </div>

                <div className="bg-[#0F0F0F] border border-white/10 rounded-lg p-4">
                  <div className="mb-4 pb-4 border-b border-white/10">
                    <div className="text-xs text-white/50 mb-1">
                      Original Clause (
                      {selectedClauseForNegotiation.clause_category})
                    </div>
                    <div className="text-sm text-white/90">
                      {selectedClauseForNegotiation.clause_text}
                    </div>
                    <div className="mt-2 text-xs">
                      <span
                        className={`px-2 py-1 rounded ${
                          selectedClauseForNegotiation.risk_level ===
                          "attention"
                            ? "bg-red-500/20 text-red-300"
                            : "bg-yellow-500/20 text-yellow-300"
                        }`}
                      >
                        {selectedClauseForNegotiation.risk_level === "attention"
                          ? "High Risk"
                          : "Moderate Risk"}
                      </span>
                    </div>
                  </div>

                  <NegotiationPanel
                    negotiationResponse={
                      negotiation.generateAlternatives.data ?? null
                    }
                    isLoading={negotiation.generateAlternatives.isPending}
                    error={negotiation.generateAlternatives.error}
                    onSelectAlternative={handleSelectAlternative}
                    onCopyAlternative={(altId) => {
                      console.log("Copied alternative:", altId);
                    }}
                  />
                </div>
              </div>
            )}

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
