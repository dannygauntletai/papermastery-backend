# PDF URL Endpoint Test Summary

## Endpoint Information
- **Endpoint:** `/api/v1/papers/pdf-url?arxiv_id={arxiv_id}`
- **Method:** GET
- **Authentication:** Not required (public)
- **Response Format:** `{"url": "filename.pdf"}`

## Test Results

### Initial Implementation Issue
The initial implementation of the endpoint returned a simplified filename based on the arXiv ID (e.g., `2412.06769.pdf`), but the actual files in Supabase storage have a more complex naming format that includes a timestamp and unique ID (e.g., `20250321181139_e433e99f_2412.06769.pdf`).

This caused the frontend to be unable to access the files using the `@supabase-storage` directive because the filenames didn't match.

### Corrected Implementation
The endpoint was updated to extract the actual filename from the paper's source URL stored in the database. This ensures that the frontend receives the correct filename that can be used with `@supabase-storage` to access the PDF file.

### Test Validation
We created a test script (`test_supabase_storage_access.py`) to validate that:

1. The endpoint returns the correct filename from the database
2. A URL constructed using this filename and Supabase storage parameters is accessible
3. The URL matches the actual source URL stored in the database

**Test Results for arXiv ID `2412.06769`:**
- ✅ API returns the correct filename: `20250321181139_e433e99f_2412.06769.pdf`
- ✅ URL constructed with this filename is accessible with status code 200
- ✅ URL matches the actual source URL in the database

## Frontend Implementation Example

Here's how the frontend can use this endpoint:

```typescript
async function getPdfUrl(arxivId: string): Promise<string> {
  // Call the API to get the PDF filename
  const response = await fetch(`/api/v1/papers/pdf-url?arxiv_id=${arxivId}`);
  const data = await response.json();
  
  // Return the complete URL for use with Supabase storage
  return data.url;
}

// In a React component using @supabase-storage
const PdfViewer = ({ arxivId }) => {
  const [pdfFilename, setPdfFilename] = useState(null);
  
  useEffect(() => {
    const loadPdf = async () => {
      // Get the filename from the API
      const filename = await getPdfUrl(arxivId);
      setPdfFilename(filename);
    };
    
    loadPdf();
  }, [arxivId]);
  
  if (!pdfFilename) return <div>Loading PDF...</div>;
  
  return (
    <div>
      {/* The @supabase-storage directive will construct the full URL */}
      <PdfViewerComponent
        url={`@supabase-storage:${pdfFilename}`}
      />
    </div>
  );
};
```

## Conclusion
The `/api/v1/papers/pdf-url` endpoint is now correctly implemented and ready for use by the frontend. It returns the actual filename from Supabase storage, which can be used with the `@supabase-storage` directive to construct the full URL for accessing PDF files. 