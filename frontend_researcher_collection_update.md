# Frontend Updates for Researcher Collection Form

## New Communication Pattern (March 2025)

We've made a significant architectural change to how researcher data is retrieved:

1. **Background-Only Processing**: The API endpoint now **always** processes researcher data collection in the background
2. **Minimal Response**: The endpoint returns immediately with only status and researcher ID (if already exists)
3. **Supabase Realtime Updates**: Clients must subscribe to Supabase realtime updates to receive full researcher data
4. **Improved UX**: This allows for better user experience as users don't need to wait for the API call to complete

## Recent Backend Fixes (March 2025)

We've identified and fixed critical issues with the researcher data extraction process:

1. **Root Cause Identified**: The API endpoint was using a different extraction method than our test script, leading to inconsistent results
2. **Backend Fixes**:
   - Unified extraction method across all components
   - Now using direct Firecrawl extraction with web search enabled, which is more reliable
   - Fixed response data handling to correctly return the extracted information
   - Alignment of field names (handling both snake_case and camelCase)
   - Fixed the URL handling to focus exclusively on Google search
   - Moved to background-only processing with Supabase realtime updates
   - Simplified API response to include only status and researcher ID

3. **Expected Results**: The extraction now works consistently, providing complete researcher profiles including:
   - Biography/description
   - Email address
   - Affiliation and position
   - Publications (typically 50-150 entries)
   - Expertise areas (5-15 categories)
   - Achievements (5-10 items)

## Overview of Backend Changes

We've identified and fixed several issues with the data collection services based on your testing:

1. **Database Schema Update**: Added an `additional_emails` column to the researchers table to store multiple email addresses
2. **API Fixes**:
   - Updated Firecrawl API endpoints to use the correct paths
   - Removed Google Scholar searches which were causing errors
   - Fixed RocketReach API to use GET instead of POST
   - Added limit on Tavily API query length
   - Made affiliation field optional in the backend model

## Required Frontend Changes

### 1. Update Request Model Type

In `src/services/types.ts`, update the `ResearcherCollectionRequest` interface:

```typescript
export interface ResearcherCollectionRequest {
  name: string;                  // Required: Researcher's full name
  affiliation?: string;          // Optional: University or institution
  paper_title?: string;          // Optional: Title of related research paper
  position?: string;             // Optional: Academic position
  email?: string;                // Optional: If known
  researcher_id?: string;        // Optional: If updating existing
}
```

### 2. Update Response Model Type

Also in `src/services/types.ts`, update the `ResearcherCollectionResponse` to reflect the simplified response:

```typescript
export interface ResearcherCollectionResponse {
  success: boolean;
  message: string;
  data: {
    status: string;              // "processing" or "error"
    researcher_id?: string;      // Present if researcher already exists
  }
}
```

### 3. Update Form Validation

In `src/components/consulting/ResearcherCollectionForm.tsx`, update the Zod schema to make affiliation optional:

```typescript
const formSchema = z.object({
  name: z.string().min(2, { message: "Name must be at least 2 characters" }),
  affiliation: z.string().optional().or(z.literal("")), // Make optional like email
  paper_title: z.string().optional().or(z.literal("")),
  position: z.string().optional().or(z.literal("")),
  email: z.string().email().optional().or(z.literal("")),
  researcher_id: z.string().optional().or(z.literal("")),
  run_in_background: z.boolean().default(false),
});
```

### 4. Update Form Component

Update the form submit function to handle optional affiliation:

```typescript
async function onSubmit(values: z.infer<typeof formSchema>) {
  setIsLoading(true);
  setError(null);
  setResult(null);

  try {
    // Convert empty strings to undefined for optional fields
    const requestData: ResearcherCollectionRequest = {
      ...values,
      affiliation: values.affiliation || undefined, // Add this line
      paper_title: values.paper_title || undefined,
      position: values.position || undefined,
      email: values.email || undefined,
      researcher_id: values.researcher_id || undefined,
    };

    const response = await collectResearcherData(requestData);
    setResult(response);
    
    if (onSuccess) {
      onSuccess(response);
    }
  } catch (err: any) {
    setError(err.message || "An error occurred while collecting researcher data");
    console.error("Error collecting researcher data:", err);
  } finally {
    setIsLoading(false);
  }
}
```

### 5. Update Form Labels/Descriptions

```tsx
<FormField
  control={form.control}
  name="affiliation"
  render={({ field }) => (
    <FormItem>
      <FormLabel>Affiliation (optional)</FormLabel>
      <FormControl>
        <Input placeholder="Stanford University" {...field} />
      </FormControl>
      <FormDescription>
        University or organization, if known
      </FormDescription>
    </FormItem>
  )}
/>
```

### 6. Update Results Display Component

In `src/components/consulting/ResearcherDataDisplay.tsx`, update to handle complex affiliation objects and publication formats:

```tsx
{/* Email display */}
{result.email || result.additional_emails?.length ? (
  <div>
    <h3 className="font-semibold mb-1">Email</h3>
    <p>{result.email || "Not specified"}</p>
    
    {result.additional_emails && result.additional_emails.length > 0 && (
      <div className="mt-1">
        <h4 className="text-sm font-medium">Additional Emails:</h4>
        <ul className="text-sm list-disc pl-5">
          {result.additional_emails.map((email, index) => (
            <li key={index}>{email}</li>
          ))}
        </ul>
      </div>
    )}
  </div>
) : null}

{/* Affiliation display - handle both string and object types */}
{result.affiliation && (
  <div>
    <h3 className="font-semibold mb-1">Affiliation</h3>
    {typeof result.affiliation === 'string' ? (
      <p>{result.affiliation}</p>
    ) : (
      <div>
        {result.affiliation.institution && <p><strong>Institution:</strong> {result.affiliation.institution}</p>}
        {result.affiliation.department && <p><strong>Department:</strong> {result.affiliation.department}</p>}
      </div>
    )}
  </div>
)}

{/* Publications display - handle both string array and object array */}
{result.publications && result.publications.length > 0 && (
  <div>
    <h3 className="font-semibold mb-1">Publications ({result.publications.length})</h3>
    <ul className="text-sm list-disc pl-5 max-h-60 overflow-y-auto">
      {result.publications.map((pub, index) => (
        <li key={index} className="mb-1">
          {typeof pub === 'string' ? pub : (
            <>
              <span className="font-medium">{pub.title}</span>
              {pub.venue && <span className="text-gray-600"> ({pub.venue})</span>}
              {pub.year && <span className="text-gray-600">, {pub.year}</span>}
            </>
          )}
        </li>
      ))}
    </ul>
  </div>
)}
```

### 7. Update API Client

In `src/services/apiClient.ts`, update the `collectResearcherData` function:

```typescript
export async function collectResearcherData(
  requestData: ResearcherCollectionRequest
): Promise<ResearcherCollectionResponse> {
  const response = await api.post('/api/v1/consulting/researchers/collect', requestData);
  return response.data;
  // Note: This will now only return minimal information with status "background_started"
}
```

### 8. Add Supabase Realtime Subscription

Create a new hook in `src/hooks/useResearcherRealtime.ts`:

```typescript
import { useState, useEffect } from 'react';
import { supabase } from '../integrations/supabase/client';

export function useResearcherRealtime(researcherName: string) {
  const [researcher, setResearcher] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!researcherName) return;
    
    setLoading(true);
    
    // Set up realtime subscription
    const subscription = supabase
      .channel('researcher-updates')
      .on(
        'postgres_changes',
        {
          event: '*',
          schema: 'public',
          table: 'researchers',
          filter: `name=eq.${researcherName}`,
        },
        (payload) => {
          console.log('Received realtime update:', payload);
          setResearcher(payload.new);
          setLoading(false);
        }
      )
      .subscribe();
    
    // Initial fetch for current data
    const fetchInitialData = async () => {
      try {
        const { data, error } = await supabase
          .from('researchers')
          .select('*')
          .eq('name', researcherName)
          .single();
          
        if (error) throw error;
        
        if (data) {
          setResearcher(data);
        }
      } catch (err: any) {
        console.error('Error fetching researcher:', err);
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };
    
    fetchInitialData();
    
    // Cleanup
    return () => {
      subscription.unsubscribe();
    };
  }, [researcherName]);
  
  return { researcher, loading, error };
}
```

### 9. Update Form Component

In your form component, integrate the new pattern:

```tsx
import { useState } from 'react';
import { useResearcherRealtime } from '../hooks/useResearcherRealtime';
import { collectResearcherData } from '../services/apiClient';

function ResearcherCollection() {
  const [searchedName, setSearchedName] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const { researcher, loading, error } = useResearcherRealtime(searchedName);
  
  async function handleSubmit(values) {
    setIsSubmitting(true);
    try {
      const response = await collectResearcherData(values);
      // Now we just store the name to start listening for updates
      setSearchedName(values.name);
      // No need to wait for the full response
    } catch (err) {
      console.error('Error:', err);
    } finally {
      setIsSubmitting(false);
    }
  }
  
  return (
    <div>
      {/* Form components here */}
      
      {searchedName && (
        <div>
          {loading ? (
            <div>
              <p>Processing data for {searchedName}...</p>
              <p>This typically takes 2-5 minutes. You can continue using the app while we find the researcher.</p>
              {/* Show a loading spinner */}
            </div>
          ) : researcher ? (
            <div>
              <h3>Researcher Found!</h3>
              {/* Display researcher data */}
              <pre>{JSON.stringify(researcher, null, 2)}</pre>
            </div>
          ) : error ? (
            <p>Error: {error}</p>
          ) : (
            <p>Still searching for {searchedName}...</p>
          )}
        </div>
      )}
    </div>
  );
}
```

## Expected API Response

The API now returns only minimal information immediately:

```json
{
  "success": true,
  "message": "Researcher data collection started for Yoshua Bengio",
  "data": {
    "status": "processing",
    "researcher_id": null
  }
}
```

If the researcher already exists by email, you'll get the researcher ID:

```json
{
  "success": true,
  "message": "Researcher data collection started for Yoshua Bengio",
  "data": {
    "status": "processing",
    "researcher_id": "7567e94d-8ec4-4222-ba10-e22bb95dfb25"
  }
}
```

## Expected Supabase Realtime Update (After Processing)

After processing is complete (typically 2-5 minutes), your realtime subscription will receive the full researcher data:

```json
{
  "id": "7567e94d-8ec4-4222-ba10-e22bb95dfb25",
  "name": "Yoshua Bengio",
  "email": "yoshua.bengio@umontreal.ca",
  "additional_emails": ["bengioy@iro.umontreal.ca"],
  "affiliation": "University of Montreal",
  "position": "Full Professor",
  "expertise": ["Deep learning", "Machine learning", "Neural networks"],
  "achievements": ["A.M. Turing Award 2018", "CIFAR Program Director"],
  "bio": "Yoshua Bengio is recognized worldwide as a leading expert in AI...",
  "publications": ["Deep Learning", "Neural Machine Translation by Jointly Learning to Align and Translate"],
  "created_at": "2025-03-16T14:45:30.123456",
  "updated_at": "2025-03-16T14:50:45.123456"
}
```

## Important Implementation Notes

1. **Supabase Realtime Configuration**:
   - Ensure your Supabase project has realtime enabled for the `researchers` table
   - Enable all change operations (INSERT, UPDATE, DELETE)
   - Set appropriate security policies to allow reading from the `researchers` table

2. **Error Handling**:
   - Set reasonable timeouts for the realtime subscription (e.g., 10 minutes)
   - Provide feedback to users about the status of the data collection
   - Consider implementing a "Check Status" button if no updates are received

3. **UX Considerations**:
   - Show appropriate loading states
   - Allow users to continue using the app while data is collected
   - Provide notifications when data collection is complete

## Testing Instructions

When testing the updated form, please note:

1. **Name is the only required field** - You can now search with just a name, though adding at least a paper title will improve results
2. **Provide good examples** - For best results, use either:
   - Name + paper title, or
   - Name + affiliation

3. **Example researchers for testing**:
   - Name: Yoshua Bengio (affiliation: University of Montreal)
   - Name: Geoffrey Hinton (add either University of Toronto or a paper title)
   - Name: Andrew Ng (add Stanford University for better results)
   - Name: Danqi Chen (add either Princeton University or a paper title)
   - Name: Jennifer Doudna (add either UC Berkeley or a paper title)

4. **API Limits**:
   - The APIs have rate limits, so avoid rapid successive requests (limit to one request every few minutes)

## Error Reporting

When reporting errors, please include:
1. The full API response or error message
2. The input values you used
3. Timestamps of when the request was made
4. Whether you received any realtime updates

## Next Steps

These changes represent a significant shift in how we handle researcher data collection. After implementing these updates, please test thoroughly and report any issues with the realtime functionality. Once validated, we'll finalize the researcher data collection feature for production use. 