import { UploadSuccessCard } from "@/components/UploadSuccessCard";
import { UploadCard } from "@/hooks/useFileUpload";

export interface UploadCardsContainerProps {
  uploadCards: { [key: string]: UploadCard };
  onRetry: () => void;
  onDismiss: (cardId: string) => void;
}

/**
 * Container for rendering upload progress cards
 */
export const UploadCardsContainer = ({
  uploadCards,
  onRetry,
  onDismiss,
}: UploadCardsContainerProps) => {
  const cardEntries = Object.entries(uploadCards);

  if (cardEntries.length === 0) {
    return null;
  }

  return (
    <div className="p-4 space-y-3 border-b border-white/10">
      {cardEntries.map(([cardId, card]) => (
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
          onRetry={onRetry}
          onDismiss={() => onDismiss(cardId)}
        />
      ))}
    </div>
  );
};
