import { useState, useCallback } from "react";
import {
  useChatAwareAskQuestion,
  useCreateChatSession,
  useUpdateDocumentContext,
} from "./useDocuments";
import { ChatMessage } from "@/components/ChatInterface";

export interface UseChatMessagesParams {
  currentDocId: string | null;
  selectedDocs: string[];
  negotiationContext: {
    panelOpen: boolean;
    buildFullContext: () => string;
    buildSelectedContext: () => string;
  };
  welcomeMessage: string;
  newChatMessage: string;
}

export interface UseChatMessagesReturn {
  messages: ChatMessage[];
  currentChatSessionId: string | null;
  sendMessage: (content: string) => Promise<void>;
  handleFeedback: (
    messageId: string,
    feedback: "positive" | "negative"
  ) => void;
  handleRetry: (messageId: string) => void;
  newChat: () => Promise<void>;
  addMessage: (message: ChatMessage) => void;
  updateProcessingMessage: (status: string, clauseCount?: number) => void;
}

/**
 * Hook for managing chat messages and interactions with the AI assistant
 */
export const useChatMessages = ({
  currentDocId,
  selectedDocs,
  negotiationContext,
  welcomeMessage,
  newChatMessage,
}: UseChatMessagesParams): UseChatMessagesReturn => {
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: "m1",
      role: "assistant",
      content: welcomeMessage,
      timestamp: new Date(),
    },
  ]);

  const [currentChatSessionId, setCurrentChatSessionId] = useState<
    string | null
  >(null);

  const askQuestionMutation = useChatAwareAskQuestion();
  const createChatSessionMutation = useCreateChatSession();
  const updateDocumentContextMutation = useUpdateDocumentContext();

  const newChat = async () => {
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
          content: newChatMessage,
          timestamp: new Date(),
        },
      ]);

      // Keep selected docs for context continuity
    } catch (error) {
      console.error("Failed to create new chat session:", error);
      // Fallback to old behavior if chat session creation fails
      setMessages([
        {
          id: "m-welcome",
          role: "assistant",
          content: newChatMessage,
          timestamp: new Date(),
        },
      ]);
    }
  };

  const sendMessage = async (content: string) => {
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
      if (negotiationContext.panelOpen) {
        enhancedQuestion = content + negotiationContext.buildFullContext();
      }
      // Priority 2: If alternatives were selected recently, include brief context
      else {
        const selectedContext = negotiationContext.buildSelectedContext();
        if (selectedContext) {
          enhancedQuestion = content + selectedContext;
        }
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
          (error as { response?: { data?: { detail?: string } } })?.response
            ?.data?.detail ||
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
  };

  // Handle feedback on messages
  const handleFeedback = (
    messageId: string,
    feedback: "positive" | "negative"
  ) => {
    setMessages((prev) =>
      prev.map((msg) => (msg.id === messageId ? { ...msg, feedback } : msg))
    );
  };

  // Handle retry for failed messages
  const handleRetry = (messageId: string) => {
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
  };

  // Add a message to the chat (for automated messages like negotiation updates)
  const addMessage = useCallback((message: ChatMessage) => {
    setMessages((prev) => [...prev, message]);
  }, []);

  // Update processing message when document status changes
  const updateProcessingMessage = useCallback(
    (status: string, clauseCount?: number) => {
      if (status === "completed" && clauseCount! > 0) {
        setMessages((prev) =>
          prev.map((msg) => {
            // Find the processing message for this document
            if (
              msg.content.includes("Processing document...") &&
              msg.role === "assistant"
            ) {
              return {
                ...msg,
                content: `Document processed successfully! Found ${clauseCount} clauses. You can now ask questions about the document.`,
                isLoading: false,
              };
            }
            return msg;
          })
        );
      } else if (status === "failed") {
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
    },
    []
  );

  return {
    messages,
    currentChatSessionId,
    sendMessage,
    handleFeedback,
    handleRetry,
    newChat,
    addMessage,
    updateProcessingMessage,
  };
};
