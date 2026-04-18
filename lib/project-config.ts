import projectConfig from "@/config/project.json";

type ProjectConfig = {
  appName: string;
  assistantName: string;
  brandMark: string;
  description: string;
  knowledgeBaseLabel: string;
  emptyStateTitle: string;
  emptyStateDescription: string;
  chatInputPlaceholder: string;
};

export const appConfig = projectConfig as ProjectConfig;
