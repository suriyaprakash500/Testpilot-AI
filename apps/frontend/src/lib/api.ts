const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:3001";

export interface ApiErrorResponse {
  success?: boolean;
  error?: {
    message?: string;
    code?: string;
  };
  detail?: string;
}

export function getErrorMessage(error: unknown, defaultMessage = "An unexpected error occurred"): string {
  if (error instanceof Error) {
    return error.message;
  }
  if (typeof error === "string") {
    return error;
  }
  return defaultMessage;
}

async function fetchApi<T>(path: string, options: RequestInit = {}): Promise<{ success?: boolean; data: T }> {
  const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
  const headers = new Headers(options.headers);
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  headers.set("Content-Type", "application/json");

  const response = await fetch(`${BACKEND_URL}${path}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    let errorMessage = `API request failed (${response.status})`;
    try {
      const errorData = (await response.json()) as ApiErrorResponse;
      errorMessage = errorData.error?.message || errorData.detail || errorMessage;
    } catch {
      // Body is not JSON, retain default error message
    }
    throw new Error(errorMessage);
  }

  return response.json();
}

export interface Project {
  id: string;
  name: string;
  repoUrl: string;
  websiteUrl: string;
  testEmail?: string | null;
  status: string;
  createdAt: string;
}

export interface CreateProjectInput {
  repoUrl: string;
  websiteUrl: string;
  name?: string;
  testEmail?: string;
  testPassword?: string;
}

export interface UpdateProjectInput {
  testEmail?: string;
  testPassword?: string;
}

export type RunStatus =
  | "pending"
  | "analyzing"
  | "repo_analysis"
  | "page_inspection"
  | "code_analysis"
  | "app_understanding"
  | "test_planning"
  | "playwright_gen"
  | "live_verify"
  | "execution"
  | "executing"
  | "evaluating"
  | "analyzing_failures"
  | "repairing"
  | "retrying"
  | "creating_pr"
  | "completed"
  | "failed"
  | "cancelled"
  | "cancelling"
  | "completed_with_failures";

export interface TimelineEvent {
  node: string;
  status: string;
  elapsedSec: number;
}

export interface TestRun {
  id: string;
  projectId: string;
  status: RunStatus;
  trigger: "manual" | "webhook" | "schedule";
  startedAt: string | null;
  completedAt: string | null;
  prUrl?: string | null;
  createdAt: string;
  // Run summary (populated at pipeline completion)
  plannedTotal?: number | null;
  passedFirstPass?: number | null;
  failedFirstPass?: number | null;
  passedFinal?: number | null;
  failedFinal?: number | null;
  inconclusiveFinal?: number | null;
  repairedCount?: number | null;
  appBugCount?: number | null;
  retryCount?: number | null;
  liveVerifiedCount?: number | null;
  liveCorrectedCount?: number | null;
  liveUnverifiedCount?: number | null;
  timeline?: TimelineEvent[] | string | null;
}

export interface TestCase {
  id: string;
  testRunId: string;
  name: string;
  status: "passed" | "failed" | "skipped";
  duration: number;
  error: string | null;
  logs: string | null;
  code?: string;
  screenshotUrl: string | null;
  createdAt: string;
}

export interface UserProfile {
  id: string;
  name: string;
  email: string;
  avatarUrl?: string;
}

export interface PipelineRunDetails {
  id: string;
  status: string;
  createdAt: string;
  completedAt: string | null;
  casesCount: number;
  passedCount: number;
  failedCount: number;
}

export interface PipelinesData {
  manual: PipelineRunDetails | null;
  webhook: PipelineRunDetails | null;
  schedule: PipelineRunDetails | null;
}

export interface AnalyticsProjectSummary {
  id: string;
  name: string;
  websiteUrl: string;
  totalRuns: number;
  passRate: number;
  status: string;
}

export interface AnalyticsRecentRun {
  id: string;
  projectName: string;
  status: string;
  passedCases: number;
  failedCases: number;
  createdAt: string;
}

export interface AnalyticsData {
  averagePassRate: number;
  totalTimeSavedMs: number;
  failedRunAlerts: number;
  totalRuns: number;
  totalCases: number;
  projects: AnalyticsProjectSummary[];
  recentRuns: AnalyticsRecentRun[];
}

export interface ActiveAgentsData {
  repoAnalysis: boolean;
  testPlanning: boolean;
  playwrightGen: boolean;
  browserExecution: boolean;
  failureAnalysis: boolean;
  githubIntegration: boolean;
}

export interface RepositoryMetadata {
  projectId: string;
  repoUrl: string;
  repoName: string;
  projectName: string;
  framework: string;
  language: string;
  analyzedAt: string | null;
}

export interface ActiveSessionData {
  runId: string;
  status: string;
  projectName: string;
  websiteUrl: string;
  testCaseName: string;
}

export const api = {
  getProjects: async (): Promise<Project[]> => {
    const response = await fetchApi<Project[]>("/api/projects");
    return response.data;
  },

  getProject: async (projectId: string): Promise<Project> => {
    const response = await fetchApi<Project>(`/api/projects/${projectId}`);
    return response.data;
  },

  createProject: async (input: CreateProjectInput): Promise<Project> => {
    const response = await fetchApi<Project>("/api/projects", {
      method: "POST",
      body: JSON.stringify(input),
    });
    return response.data;
  },

  deleteProject: async (projectId: string): Promise<void> => {
    await fetchApi<{ deleted: boolean }>(`/api/projects/${projectId}`, {
      method: "DELETE",
    });
  },

  updateProject: async (projectId: string, input: UpdateProjectInput): Promise<Project> => {
    const response = await fetchApi<Project>(`/api/projects/${projectId}`, {
      method: "PATCH",
      body: JSON.stringify(input),
    });
    return response.data;
  },

  deleteRun: async (runId: string): Promise<void> => {
    await fetchApi<{ deleted: boolean }>(`/api/test-runs/run/${runId}`, {
      method: "DELETE",
    });
  },

  cancelRun: async (runId: string): Promise<{ status: string }> => {
    const response = await fetchApi<{ status: string }>(`/api/test-runs/run/${runId}/cancel`, {
      method: "POST",
    });
    return response.data;
  },

  getRuns: async (projectId: string): Promise<TestRun[]> => {
    const response = await fetchApi<TestRun[]>(`/api/test-runs/${projectId}`);
    return response.data;
  },

  getRunDetails: async (runId: string): Promise<{ run: TestRun; testCases: TestCase[] }> => {
    const response = await fetchApi<{ run: TestRun; testCases: TestCase[] }>(`/api/test-runs/run/${runId}`);
    return response.data;
  },

  triggerRun: async (projectId: string, payload?: { websiteUrl?: string; repoUrl?: string }): Promise<{ runId: string; status: string }> => {
    const response = await fetchApi<{ runId: string; status: string }>(`/api/test-runs/${projectId}/start`, {
      method: "POST",
      body: payload ? JSON.stringify(payload) : undefined,
    });
    return response.data;
  },

  getCurrentUser: async (): Promise<UserProfile> => {
    const response = await fetchApi<UserProfile>("/api/auth/me");
    return response.data;
  },

  getAnalytics: async (): Promise<AnalyticsData> => {
    const response = await fetchApi<AnalyticsData>("/api/projects/analytics");
    return response.data;
  },

  getActiveAgents: async (): Promise<ActiveAgentsData> => {
    const response = await fetchApi<ActiveAgentsData>("/api/projects/active-agents");
    return response.data;
  },

  getPipelines: async (): Promise<PipelinesData> => {
    const response = await fetchApi<PipelinesData>("/api/projects/pipelines");
    return response.data;
  },

  getActiveSession: async (): Promise<ActiveSessionData | null> => {
    const response = await fetchApi<ActiveSessionData | null>("/api/projects/active-session");
    return response.data;
  },

  getRepositories: async (): Promise<RepositoryMetadata[]> => {
    const response = await fetchApi<RepositoryMetadata[]>("/api/projects/repositories");
    return response.data;
  },
};
