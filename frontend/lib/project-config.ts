// config/ is shared with scraper.py and the FastAPI backend, so it stays
// at the repo root instead of moving into frontend/ with everything else -
// relative import instead of the @/ alias.
import projectConfig from "../../config/project.json";

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
