import { useState, useEffect, useMemo, useCallback } from "react";

export interface Document {
  id: string;
  name: string;
  date: string;
  status?: string;
}

export interface UseDocumentManagementReturn {
  recentDocs: Document[];
  selectedDocs: string[];
  currentDocId: string | null;
  docQuery: string;
  filteredDocs: Document[];
  setDocQuery: (query: string) => void;
  toggleSelectDoc: (id: string) => void;
  clearContext: () => void;
  addDocument: (doc: Document) => void;
  addDocuments: (docs: Document[]) => void;
  setSelectedDocs: (docs: string[]) => void;
  setCurrentDocId: (id: string | null) => void;
  updateDocumentStatus: (docId: string, status: string) => void;
}

// localStorage key for document persistence
const STORAGE_KEY = "clausecompass_documents";

// Helper function to safely load documents from localStorage
const loadDocumentsFromStorage = (): Document[] => {
  if (typeof window === "undefined") return [];

  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (!stored) return [];

    const parsed = JSON.parse(stored);
    return Array.isArray(parsed) ? parsed : [];
  } catch (error) {
    console.error("Failed to load documents from localStorage:", error);
    return [];
  }
};

// Helper function to safely save documents to localStorage
const saveDocumentsToStorage = (docs: Document[]): void => {
  if (typeof window === "undefined") return;

  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(docs));
  } catch (error) {
    console.error("Failed to save documents to localStorage:", error);
  }
};

/**
 * Hook for managing document selection, filtering, and state.
 *
 * Documents are persisted to localStorage for privacy - raw documents are NEVER
 * stored on the backend. Only analysis results (clauses, risk scores) are stored
 * in Firestore, not the original document content.
 */
export const useDocumentManagement = (): UseDocumentManagementReturn => {
  // Initialize with empty array to avoid hydration mismatch
  // Load from localStorage after mount in useEffect
  const [recentDocs, setRecentDocs] = useState<Document[]>([]);
  const [selectedDocs, setSelectedDocs] = useState<string[]>([]);
  const [currentDocId, setCurrentDocId] = useState<string | null>(null);
  const [docQuery, setDocQuery] = useState("");

  // Load documents from localStorage after component mounts (client-side only)
  useEffect(() => {
    const storedDocs = loadDocumentsFromStorage();
    if (storedDocs.length > 0) {
      setRecentDocs(storedDocs);
    }
  }, []); // Run once on mount

  // Filter documents based on search query
  const filteredDocs = useMemo(() => {
    return recentDocs.filter((d) =>
      d.name.toLowerCase().includes(docQuery.toLowerCase())
    );
  }, [recentDocs, docQuery]);

  // Toggle document selection
  const toggleSelectDoc = useCallback((id: string) => {
    setSelectedDocs((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [id, ...prev]
    );
  }, []);

  // Clear all selected documents
  const clearContext = useCallback(() => {
    setSelectedDocs([]);
  }, []);

  // Add single document to recent docs
  const addDocument = useCallback((doc: Document) => {
    setRecentDocs((prev) => [doc, ...prev]);
  }, []);

  // Add multiple documents to recent docs
  const addDocuments = useCallback((docs: Document[]) => {
    setRecentDocs((prev) => [...docs, ...prev]);
  }, []);

  // Update document status
  const updateDocumentStatus = useCallback((docId: string, status: string) => {
    setRecentDocs((prev) =>
      prev.map((doc) => (doc.id === docId ? { ...doc, status } : doc))
    );
  }, []);

  // Persist documents to localStorage whenever recentDocs changes
  useEffect(() => {
    saveDocumentsToStorage(recentDocs);
  }, [recentDocs]);

  // Update current document when selection changes
  useEffect(() => {
    if (selectedDocs.length > 0) {
      setCurrentDocId(selectedDocs[0]);
    } else {
      setCurrentDocId(null);
    }
  }, [selectedDocs]);

  return {
    recentDocs,
    selectedDocs,
    currentDocId,
    docQuery,
    filteredDocs,
    setDocQuery,
    toggleSelectDoc,
    clearContext,
    addDocument,
    addDocuments,
    setSelectedDocs,
    setCurrentDocId,
    updateDocumentStatus,
  };
};
