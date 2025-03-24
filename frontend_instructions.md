# PDF Loading Guide for Frontend Team

## How to Load PDFs into react-pdf-highlighter

Our backend provides a specialized endpoint for retrieving PDF locations that works with our Supabase storage setup. Follow these instructions to properly implement PDF loading in your React application.

## Step 1: Use our dedicated PDF URL endpoint

❌ **IMPORTANT: Do NOT use ArXiv URLs directly** ❌
- Direct ArXiv links will not work with our storage system
- Always use our `/api/v1/papers/pdf-url` endpoint to get the correct filename

## Step 2: Fetch the PDF filename

```typescript
// Function to get the PDF filename from our API
const getPdfFilename = async (paperId: string): Promise<string | null> => {
  try {
    // First, get the paper details to find the arxivId
    const paperResponse = await fetch(`/api/v1/papers/${paperId}`);
    if (!paperResponse.ok) {
      throw new Error(`Error fetching paper: ${paperResponse.statusText}`);
    }
    
    const paperData = await paperResponse.json();
    const arxivId = paperData.arxiv_id;
    
    if (!arxivId) {
      throw new Error("Paper has no arXiv ID");
    }
    
    // Then use the arxivId to get the PDF filename
    const pdfResponse = await fetch(`/api/v1/papers/pdf-url?arxiv_id=${arxivId}`);
    if (!pdfResponse.ok) {
      throw new Error(`Error fetching PDF URL: ${pdfResponse.statusText}`);
    }
    
    const pdfData = await pdfResponse.json();
    return pdfData.url; // This is just the filename, not the full URL
  } catch (error) {
    console.error("Error fetching PDF filename:", error);
    return null;
  }
};
```

## Step 3: Construct the full URL for Supabase storage

```typescript
// Constants for Supabase storage
const SUPABASE_URL = "https://hnvrjaepddkpapdtetyu.supabase.co";
const SUPABASE_BUCKET = "papers";

// Function to build the complete PDF URL
const buildPdfUrl = (filename: string): string => {
  return `${SUPABASE_URL}/storage/v1/object/public/${SUPABASE_BUCKET}/${filename}`;
};
```

## Step 4: Implement the PDF Viewer with react-pdf-highlighter

```tsx
import React, { useState, useEffect } from 'react';
import { PdfLoader, PdfHighlighter, Tip, Highlight, Popup, AreaHighlight } from 'react-pdf-highlighter';

// You may need to import additional types depending on your setup

type Props = {
  paperId: string;
};

const PaperPdfViewer: React.FC<Props> = ({ paperId }) => {
  const [pdfUrl, setPdfUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const loadPdf = async () => {
      try {
        setLoading(true);
        
        // Step 1: Get the PDF filename
        const filename = await getPdfFilename(paperId);
        
        if (!filename) {
          throw new Error("Could not retrieve PDF filename");
        }
        
        // Step 2: Build the full URL
        const fullUrl = buildPdfUrl(filename);
        setPdfUrl(fullUrl);
      } catch (err: any) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };

    if (paperId) {
      loadPdf();
    }
  }, [paperId]);

  if (loading) return <div>Loading PDF...</div>;
  if (error) return <div>Error: {error}</div>;
  if (!pdfUrl) return <div>PDF not available</div>;

  return (
    <div style={{ height: "100vh" }}>
      <PdfLoader url={pdfUrl} beforeLoad={<div>Loading PDF...</div>}>
        {(pdfDocument) => (
          <PdfHighlighter
            pdfDocument={pdfDocument}
            enableAreaSelection={(event) => event.altKey}
            // Add your onSelectionFinished, highlights, and other props here
            // For example:
            // onSelectionFinished={(selection) => handleHighlightCreated(selection)}
            // highlights={highlights}
          />
        )}
      </PdfLoader>
    </div>
  );
};

export default PaperPdfViewer;
```

## Step 5: Error Handling and Edge Cases

- Handle loading states appropriately 
- Display user-friendly error messages
- Implement retry logic if needed
- Cache PDF URLs to minimize API calls

## Common Mistakes to Avoid

1. **DO NOT** try to load PDFs directly from ArXiv URLs. These won't work with our system.
2. **DO NOT** construct PDF URLs manually. Always use the endpoint to get the filename.
3. **DO NOT** pass invalid paperId or arxivId values to the API.
4. **DO NOT** forget to handle loading states and errors.

## When to Use Which Parameter:

1. When you have a paper ID (UUID):
   - First get the paper details via `/api/v1/papers/{paper_id}`
   - Extract the arxivId from the response
   - Use the arxivId with the `/api/v1/papers/pdf-url` endpoint

2. When you have an arXiv ID directly:
   - Use it directly with `/api/v1/papers/pdf-url?arxiv_id={arxiv_id}`

3. When you have an arXiv URL (not recommended):
   - Use `/api/v1/papers/pdf-url?arxiv_url={encoded_arxiv_url}`
   - Note: This is less efficient and may be deprecated in the future

## Testing Your Implementation

To verify your PDF loading works correctly:
1. Try different paper IDs to ensure robust loading
2. Test error handling by using invalid IDs
3. Check PDF viewing performance with larger documents
4. Verify highlighting functionality works with loaded PDFs
