const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:3001";

async function fetchApi(path: string, options: RequestInit = {}) {
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
    let errMsg = "API request failed";
    try {
      const errData = await response.json();
      errMsg = errData.error?.message || errMsg;
    } catch {
      // ignore
    }
    throw new Error(errMsg);
  }

  return response.json();
}

export interface Project {
  id: string;
  name: string;
  repoUrl: string;
  websiteUrl: string;
  status: string;
  createdAt: string;
}

export interface TestRun {
  id: string;
  projectId: string;
  status: "pending" | "executing" | "completed" | "failed";
  trigger: "manual" | "webhook" | "schedule";
  startedAt: string | null;
  completedAt: string | null;
  createdAt: string;
}

export interface TestCase {
  id: string;
  testRunId: string;
  name: string;
  status: "passed" | "failed" | "skipped";
  duration: number;
  error: string | null;
  logs: string | null;
  screenshotUrl: string | null;
  createdAt: string;
}

export const api = {
  getProjects: async (): Promise<Project[]> => {
    const res = await fetchApi("/api/projects");
    return res.data;
  },
  getProject: async (id: string): Promise<Project> => {
    const res = await fetchApi(`/api/projects/${id}`);
    return res.data;
  },
  createProject: async (data: { repoUrl: string; websiteUrl: string; testEmail?: string; testPassword?: string }): Promise<Project> => {
    const res = await fetchApi("/api/projects", {
      method: "POST",
      body: JSON.stringify(data),
    });
    return res.data;
  },
  deleteProject: async (id: string): Promise<void> => {
    await fetchApi(`/api/projects/${id}`, {
      method: "DELETE",
    });
  },
  deleteRun: async (runId: string): Promise<void> => {
    await fetchApi(`/api/test-runs/run/${runId}`, {
      method: "DELETE",
    });
  },
  getRuns: async (projectId: string): Promise<TestRun[]> => {
    const res = await fetchApi(`/api/test-runs/${projectId}`);
    return res.data;
  },
  getRunDetails: async (runId: string): Promise<{ run: TestRun; testCases: TestCase[] }> => {
    const res = await fetchApi(`/api/test-runs/run/${runId}`);
    return res.data;
  },
  triggerRun: async (projectId: string): Promise<{ runId: string }> => {
    const res = await fetchApi(`/api/test-runs/${projectId}/start`, {
      method: "POST",
    });
    return res.data;
  },
  getCurrentUser: async () => {
    const res = await fetchApi("/api/auth/me");
    return res.data;
  },
  getAnalytics: async (): Promise<AnalyticsData> => {
    const res = await fetchApi("/api/projects/analytics");
    return res.data;
  },
  getActiveAgents: async (): Promise<{
    repoAnalysis: boolean;
    testPlanning: boolean;
    playwrightGen: boolean;
    browserExecution: boolean;
    failureAnalysis: boolean;
    githubIntegration: boolean;
  }> => {
    const res = await fetchApi("/api/projects/active-agents");
    return res.data;
  },
  getPipelines: async (): Promise<PipelinesData> => {
    const res = await fetchApi("/api/projects/pipelines");
    return res.data;
  },
  getActiveSession: async (): Promise<{
    runId: string;
    status: string;
    projectName: string;
    websiteUrl: string;
    testCaseName: string;
  } | null> => {
    const res = await fetchApi("/api/projects/active-session");
    return res.data;
  },
  getRepositories: async (): Promise<Array<{
    projectId: string;
    repoUrl: string;
    repoName: string;
    projectName: string;
    framework: string;
    language: string;
    analyzedAt: string | null;
  }>> => {
    const res = await fetchApi("/api/projects/repositories");
    return res.data;
  }
};

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

export interface AnalyticsData {
  averagePassRate: number;
  totalTimeSavedMs: number;
  failedRunAlerts: number;
  totalRuns: number;
  totalCases: number;
  projects: Array<{
    id: string;
    name: string;
    websiteUrl: string;
    totalRuns: number;
    passRate: number;
    status: string;
  }>;
  recentRuns: Array<{
    id: string;
    projectName: string;
    status: string;
    passedCases: number;
    failedCases: number;
    createdAt: string;
  }>;
}
