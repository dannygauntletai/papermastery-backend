# PDF URL Construction Fix

## Issue Identified
We've tracked down the error in the PDF viewer:
```TypeError: Failed to construct 'URL': Invalid URL
    at EnhancedPdfHighlighter.tsx:574:7
```

## Root Cause
The backend `/api/v1/papers/pdf-url` endpoint is working correctly and returning a proper response:
```json
{ "url": "20250325082034_e78e4a41_1911.05661.pdf" }
```

However, this is just the filename, not a complete URL. The frontend code is trying to construct a URL object directly from this filename, which fails because it's not a valid URL.

## Fix Required
Update the code in `EnhancedPdfHighlighter.tsx` around line 574 to properly construct a full Supabase storage URL:

```typescript
// CURRENT CODE (problematic):
const response = await fetch(`/api/v1/papers/pdf-url?arxiv_id=${arxivId}`);
const data = await response.json();
const pdfUrl = new URL(data.url); // FAILS: data.url is just a filename

// CORRECTED CODE:
const response = await fetch(`/api/v1/papers/pdf-url?arxiv_id=${arxivId}`);
const data = await response.json();
const filename = data.url;

// Option 1: Use Supabase storage client
const pdfUrl = supabaseClient
  .storage
  .from('papers')
  .getPublicUrl(filename).data.publicUrl;

// Option 2: Construct URL manually
const pdfUrl = `https://hnvrjaepddkpapdtetyu.supabase.co/storage/v1/object/public/papers/${filename}`;
```

The backend is intentionally returning just the filename (following separation of concerns), and the frontend needs to construct the complete URL based on your Supabase storage configuration.

## Additional Context
Our logs confirm the backend is working correctly:
```
2025-03-25 03:33:54 - [ARXIV ERROR] Extracted filename for arXiv ID 1911.05661: 20250325082034_e78e4a41_1911.05661.pdf
2025-03-25 03:33:54 - [ARXIV ERROR] Returning response for arXiv ID 1911.05661: {'url': '20250325082034_e78e4a41_1911.05661.pdf'}
INFO:     127.0.0.1:61842 - "GET /api/v1/papers/pdf-url?arxiv_id=1911.05661 HTTP/1.1" 200 OK
```

This is a frontend-only fix that doesn't require any backend changes. Let me know if you have any questions about implementing this solution.
