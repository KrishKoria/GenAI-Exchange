/**
 * File validation utilities for PDF uploads
 */

export interface FileValidationResult {
  isValid: boolean;
  fileSize: number;
  errors: string[];
  warnings: string[];
}

/**
 * Validates basic file requirements (type, size)
 * @param file - File to validate
 * @returns Validation result with errors and warnings
 */
export const validateFileBasics = (file: File): FileValidationResult => {
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
