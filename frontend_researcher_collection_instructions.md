# Frontend Implementation: Researcher Data Collection Form

## Overview
We've implemented Sprints 1-3 of the consulting feature backend, which includes data collection services for researchers. This document provides instructions for creating a frontend interface to test these endpoints. The main functionality allows users to input researcher information and enrich it using our data collection services.

## API Endpoint Details

### Main Endpoint
```
POST /api/v1/consulting/researchers/collect
```

### Request Model
```typescript
interface ResearcherCollectionRequest {
  name: string;                  // Required: Researcher's full name
  affiliation: string;           // Required: University or organization
  paper_title?: string;          // Optional: Title of related research paper
  position?: string;             // Optional: Academic position (e.g., "Professor")
  email?: string;                // Optional: If known, otherwise will be discovered
  researcher_id?: string;        // Optional: If updating existing researcher
  run_in_background: boolean;    // Whether to process in background (default: false)
}
```

### Response Model
```typescript
interface ResearcherCollectionResponse {
  success: boolean;
  message: string;
  data: {
    status: string;              // "complete" or "background_started"
    researcher_id?: string;      // UUID if researcher was created/found
    name: string;
    email?: string;
    affiliation: string;
    expertise?: string[];
    achievements?: string[];
    bio?: string;
    publications?: {
      title: string;
      details: string;
    }[];
    collection_sources?: string[];
    collected_at?: string;
  }
}
```

## Implementation Tasks

### 1. Create API Service Method

Add a new method to `src/services/apiClient.ts`:

```typescript
// Add to src/services/apiClient.ts
export const collectResearcherData = async (data: ResearcherCollectionRequest): Promise<ResearcherCollectionResponse> => {
  const response = await api.post('/consulting/researchers/collect', data);
  return response.data;
};
```

### 2. Create Types

Add these types to `src/services/types.ts`:

```typescript
// Researcher Collection Types
export interface ResearcherCollectionRequest {
  name: string;
  affiliation: string;
  paper_title?: string;
  position?: string;
  email?: string;
  researcher_id?: string;
  run_in_background: boolean;
}

export interface ResearcherPublication {
  title: string;
  details: string;
}

export interface ResearcherCollectionResponse {
  success: boolean;
  message: string;
  data: {
    status: string;
    researcher_id?: string;
    name: string;
    email?: string;
    affiliation: string;
    expertise?: string[];
    achievements?: string[];
    bio?: string;
    publications?: ResearcherPublication[];
    collection_sources?: string[];
    collected_at?: string;
  }
}
```

### 3. Create Form Component

Create a new file at `src/components/consulting/ResearcherCollectionForm.tsx`:

```tsx
import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import * as z from "zod";
import { ResearcherCollectionRequest } from "../../services/types";
import { collectResearcherData } from "../../services/apiClient";

import { Button } from "../ui/button";
import { Card } from "../ui/card";
import { Checkbox } from "../ui/checkbox";
import { Form, FormControl, FormDescription, FormField, FormItem, FormLabel } from "../ui/form";
import { Input } from "../ui/input";
import { Loader2 } from "lucide-react";
import { ResearcherDataDisplay } from "./ResearcherDataDisplay";

// Form validation schema
const formSchema = z.object({
  name: z.string().min(2, { message: "Name must be at least 2 characters" }),
  affiliation: z.string().min(2, { message: "Affiliation is required" }),
  paper_title: z.string().optional(),
  position: z.string().optional(),
  email: z.string().email().optional().or(z.literal("")),
  researcher_id: z.string().optional().or(z.literal("")),
  run_in_background: z.boolean().default(false),
});

interface ResearcherCollectionFormProps {
  onSuccess?: (data: any) => void;
}

export function ResearcherCollectionForm({ onSuccess }: ResearcherCollectionFormProps) {
  const [isLoading, setIsLoading] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  const form = useForm<z.infer<typeof formSchema>>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      name: "",
      affiliation: "",
      paper_title: "",
      position: "",
      email: "",
      researcher_id: "",
      run_in_background: false,
    },
  });

  async function onSubmit(values: z.infer<typeof formSchema>) {
    setIsLoading(true);
    setError(null);
    setResult(null);

    try {
      // Convert empty strings to undefined for optional fields
      const requestData: ResearcherCollectionRequest = {
        ...values,
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

  return (
    <div className="space-y-8">
      <Card className="p-6">
        <h2 className="text-2xl font-bold mb-6">Researcher Data Collection</h2>
        
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-6">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <FormField
                control={form.control}
                name="name"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Name</FormLabel>
                    <FormControl>
                      <Input placeholder="John Smith" {...field} />
                    </FormControl>
                  </FormItem>
                )}
              />
              
              <FormField
                control={form.control}
                name="affiliation"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Affiliation</FormLabel>
                    <FormControl>
                      <Input placeholder="Stanford University" {...field} />
                    </FormControl>
                  </FormItem>
                )}
              />
              
              <FormField
                control={form.control}
                name="position"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Position</FormLabel>
                    <FormControl>
                      <Input placeholder="Associate Professor" {...field} />
                    </FormControl>
                  </FormItem>
                )}
              />
              
              <FormField
                control={form.control}
                name="email"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Email (optional)</FormLabel>
                    <FormControl>
                      <Input placeholder="researcher@university.edu" type="email" {...field} />
                    </FormControl>
                    <FormDescription>
                      Leave blank to discover via RocketReach
                    </FormDescription>
                  </FormItem>
                )}
              />
            </div>
            
            <FormField
              control={form.control}
              name="paper_title"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Paper Title</FormLabel>
                  <FormControl>
                    <Input placeholder="Deep Learning Applications in Computational Biology" {...field} />
                  </FormControl>
                  <FormDescription>
                    Helps improve search accuracy
                  </FormDescription>
                </FormItem>
              )}
            />
            
            <FormField
              control={form.control}
              name="researcher_id"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Researcher ID (optional)</FormLabel>
                  <FormControl>
                    <Input placeholder="Only if updating existing researcher" {...field} />
                  </FormControl>
                </FormItem>
              )}
            />
            
            <FormField
              control={form.control}
              name="run_in_background"
              render={({ field }) => (
                <FormItem className="flex flex-row items-start space-x-3 space-y-0 rounded-md border p-4">
                  <FormControl>
                    <Checkbox
                      checked={field.value}
                      onCheckedChange={field.onChange}
                    />
                  </FormControl>
                  <div className="space-y-1 leading-none">
                    <FormLabel>Process in background</FormLabel>
                    <FormDescription>
                      Enable for larger data collection jobs that might take longer to complete
                    </FormDescription>
                  </div>
                </FormItem>
              )}
            />
            
            {error && (
              <div className="bg-red-50 text-red-800 p-3 rounded-md">
                {error}
              </div>
            )}
            
            <Button type="submit" disabled={isLoading} className="w-full">
              {isLoading ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Collecting Data...
                </>
              ) : (
                "Collect Researcher Data"
              )}
            </Button>
          </form>
        </Form>
      </Card>
      
      {result && (
        <ResearcherDataDisplay data={result} />
      )}
    </div>
  );
}
```

### 4. Create Results Display Component

Create a new file at `src/components/consulting/ResearcherDataDisplay.tsx`:

```tsx
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../ui/card";
import { Badge } from "../ui/badge";
import { ResearcherCollectionResponse } from "../../services/types";

interface ResearcherDataDisplayProps {
  data: ResearcherCollectionResponse;
}

export function ResearcherDataDisplay({ data }: ResearcherDataDisplayProps) {
  if (!data.success) {
    return (
      <Card className="border-red-300">
        <CardHeader>
          <CardTitle className="text-red-600">Collection Failed</CardTitle>
          <CardDescription>{data.message}</CardDescription>
        </CardHeader>
      </Card>
    );
  }

  const result = data.data;
  
  if (result.status === "background_started") {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Data Collection Started</CardTitle>
          <CardDescription>
            The data collection process has been started in the background.
            Results will be stored in the database.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <h3 className="font-semibold mb-1">Name</h3>
              <p>{result.name}</p>
            </div>
            <div>
              <h3 className="font-semibold mb-1">Affiliation</h3>
              <p>{result.affiliation}</p>
            </div>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Researcher Data</CardTitle>
        <CardDescription>{data.message}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <h3 className="font-semibold mb-1">Name</h3>
            <p>{result.name}</p>
          </div>
          <div>
            <h3 className="font-semibold mb-1">Affiliation</h3>
            <p>{result.affiliation}</p>
          </div>
          <div>
            <h3 className="font-semibold mb-1">Email</h3>
            <p>{result.email || "Not found"}</p>
          </div>
          <div>
            <h3 className="font-semibold mb-1">ID</h3>
            <p className="font-mono text-sm">{result.researcher_id || "Not assigned"}</p>
          </div>
        </div>

        {result.bio && (
          <div>
            <h3 className="font-semibold mb-1">Biography</h3>
            <p className="text-sm">{result.bio}</p>
          </div>
        )}

        {result.expertise && result.expertise.length > 0 && (
          <div>
            <h3 className="font-semibold mb-1">Expertise</h3>
            <div className="flex flex-wrap gap-2">
              {result.expertise.map((item, index) => (
                <Badge key={index} variant="outline">{item}</Badge>
              ))}
            </div>
          </div>
        )}

        {result.achievements && result.achievements.length > 0 && (
          <div>
            <h3 className="font-semibold mb-1">Achievements</h3>
            <ul className="list-disc pl-5 text-sm space-y-1">
              {result.achievements.map((item, index) => (
                <li key={index}>{item}</li>
              ))}
            </ul>
          </div>
        )}

        {result.publications && result.publications.length > 0 && (
          <div>
            <h3 className="font-semibold mb-1">Publications</h3>
            <ul className="list-disc pl-5 text-sm space-y-2">
              {result.publications.map((pub, index) => (
                <li key={index}>
                  <div className="font-medium">{pub.title}</div>
                  <div className="text-xs text-gray-500">{pub.details}</div>
                </li>
              ))}
            </ul>
          </div>
        )}

        {result.collection_sources && (
          <div className="pt-4 border-t">
            <h3 className="font-semibold mb-1 text-sm">Data Sources</h3>
            <div className="flex flex-wrap gap-1">
              {result.collection_sources.map((source, index) => (
                <Badge key={index} variant="secondary" className="text-xs">
                  {source}
                </Badge>
              ))}
            </div>
            {result.collected_at && (
              <p className="text-xs text-gray-500 mt-2">
                Collected at: {new Date(result.collected_at).toLocaleString()}
              </p>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
```

### 5. Create Page Component

Create a new file at `src/pages/ResearcherCollection.tsx`:

```tsx
import { ResearcherCollectionForm } from "../components/consulting/ResearcherCollectionForm";

export default function ResearcherCollection() {
  return (
    <div className="container mx-auto py-8">
      <h1 className="text-3xl font-bold mb-8">Researcher Data Collection</h1>
      <p className="mb-8 text-gray-600">
        Use this form to collect and enrich researcher data. The system will search for 
        information about the researcher using Firecrawl, RocketReach, and Tavily services.
      </p>
      <ResearcherCollectionForm />
    </div>
  );
}
```

### 6. Update Routing

Add this page to your router configuration (if using React Router):

```tsx
// In your router configuration
import ResearcherCollection from "./pages/ResearcherCollection";

// Inside your routes array/configuration
{
  path: "consulting/researcher-collection",
  element: <ResearcherCollection />
}
```

## Testing Instructions

1. Navigate to `/consulting/researcher-collection` in the application
2. Fill out the form with a researcher's details:
   - Start with a known researcher (e.g., a professor from a major university)
   - Include their name and affiliation (required)
   - Optionally add their position and a paper title they've authored
3. Submit the form and observe the results
4. Test different scenarios:
   - Known researchers with complete information
   - Researchers with minimal information (just name and affiliation)
   - Toggle the "Process in background" option to test both synchronous and asynchronous processing

## Technical Notes

1. The backend uses three main services:
   - **Firecrawl**: Web scraping to find researcher profiles
   - **RocketReach**: API to discover researcher email addresses
   - **Tavily**: AI-powered data enrichment for expertise and achievements

2. Processing time may vary depending on:
   - How well-known the researcher is
   - Quality of the search terms provided
   - Current load on the external services

3. Background processing:
   - When enabled, the API will return immediately with status "background_started"
   - Results will be stored in the database and can be retrieved later

4. The API returns HTTP status codes:
   - `200 OK`: Request processed successfully
   - `500 Internal Server Error`: Error in data collection process

## Example Researchers for Testing

For initial testing, try these examples:

1. **Well-known researcher**
   - Name: Geoffrey Hinton
   - Affiliation: University of Toronto
   - Position: Professor Emeritus
   - Paper: "Deep Learning"

2. **Moderate visibility**
   - Name: Danqi Chen
   - Affiliation: Princeton University
   - Paper Title: "Reading Wikipedia to Answer Open-Domain Questions"

3. **Specific domain expert**
   - Name: Jennifer Doudna
   - Affiliation: UC Berkeley
   - Paper Title: "A programmable dual-RNA-guided DNA endonuclease in adaptive bacterial immunity"

Please report any issues, inconsistencies, or suggestions for improving the researcher data collection process. 