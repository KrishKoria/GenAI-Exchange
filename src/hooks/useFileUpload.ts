import { useRef, useState, useEffect } from "react";
import {
  useDocumentWorkflow,
  useBatchDocumentUpload,
  useDocumentStatus,
} from "./useDocuments";
import { validateFileBasics } from "@/lib/fileValidation";
import { useToast, createToast } from "@/components/ui/toast";
import { Document } from "./useDocumentManagement";

export interface UploadCard {
  filename: string;
  fileSize: number;
  pageCount?: number;
  status: "uploading" | "processing" | "completed" | "failed";
  error?: string;
  progress?: number;
  estimatedTime?: number;
  clauseCount?: number;
}

export interface UseFileUploadParams {
  onDocumentAdded: (doc: Document) => void;
  onDocumentsAdded: (docs: Document[]) => void;
  onDocumentSelected: (docIds: string[]) => void;
  currentDocId: string | null;
  onUpdateDocumentStatus: (docId: string, status: string) => void;
  onUpdateProcessingMessage: (status: string, clauseCount?: number) => void;
}

export interface UseFileUploadReturn {
  uploadCards: { [key: string]: UploadCard };
  handleUploadClick: () => void;
  handleFilesSelected: (files: FileList | null) => Promise<void>;
  dismissUploadCard: (cardId: string) => void;
  fileInputRef: React.RefObject<HTMLInputElement | null>;
}

/**
 * Hook for managing file uploads and upload card UI state
 */
export const useFileUpload = ({
  onDocumentAdded,
  onDocumentsAdded,
  onDocumentSelected,
  currentDocId,
  onUpdateDocumentStatus,
  onUpdateProcessingMessage,
}: UseFileUploadParams): UseFileUploadReturn => {
  const { toast } = useToast();
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const [uploadCards, setUploadCards] = useState<{
    [key: string]: UploadCard;
  }>({});
  const [autoDismissTimers, setAutoDismissTimers] = useState<{
    [key: string]: NodeJS.Timeout;
  }>({});

  const { upload: uploadDocument } = useDocumentWorkflow();
  const batchUploadDocuments = useBatchDocumentUpload();
  const statusQuery = useDocumentStatus(currentDocId);
  const documentStatus = statusQuery.data;

  const handleUploadClick = () => {
    fileInputRef.current?.click();
  };

  const handleFilesSelected = async (files: FileList | null) => {
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

        onDocumentAdded(newDoc);
        onDocumentSelected([response.doc_id]);

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
          onDocumentsAdded(newDocs);
          onDocumentSelected(newDocs.map((doc) => doc.id));
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
      const errorResponse = (
        error as { response?: { status?: number; data?: { detail?: string } } }
      )?.response;
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
  };

  const dismissUploadCard = (cardId: string) => {
    // Clear auto-dismiss timer if it exists
    const timerId = autoDismissTimers[cardId];
    if (timerId) {
      clearTimeout(timerId);
      setAutoDismissTimers((timers) => {
        // eslint-disable-next-line @typescript-eslint/no-unused-vars
        const { [cardId]: _removed, ...restTimers } = timers;
        return restTimers;
      });
    }

    // Remove the card
    setUploadCards((prev) => {
      // eslint-disable-next-line @typescript-eslint/no-unused-vars
      const { [cardId]: _removed, ...rest } = prev;
      return rest;
    });
  };

  // Monitor document status and update UI when processing completes
  useEffect(() => {
    if (!documentStatus || !currentDocId) return;

    // Update document status
    onUpdateDocumentStatus(currentDocId, documentStatus.status);

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
                const { [cardId]: _removed, ...rest } = currentCards;
                return rest;
              });
              // Clean up timer from state
              setAutoDismissTimers((timers) => {
                // eslint-disable-next-line @typescript-eslint/no-unused-vars
                const { [cardId]: _removedTimer, ...restTimers } = timers;
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
      onUpdateProcessingMessage("completed", documentStatus.clause_count);
    } else if (documentStatus.status === "failed") {
      onUpdateProcessingMessage("failed");
    }
  }, [
    documentStatus,
    currentDocId,
    onUpdateDocumentStatus,
    onUpdateProcessingMessage,
  ]);

  // Cleanup timers on unmount
  useEffect(() => {
    return () => {
      // Clear all auto-dismiss timers on unmount to prevent memory leaks
      Object.values(autoDismissTimers).forEach((timerId) => {
        clearTimeout(timerId);
      });
    };
  }, [autoDismissTimers]);

  return {
    uploadCards,
    handleUploadClick,
    handleFilesSelected,
    dismissUploadCard,
    fileInputRef,
  };
};
