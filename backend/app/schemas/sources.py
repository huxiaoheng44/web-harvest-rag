from pydantic import BaseModel


class ManagedSource(BaseModel):
    id: str
    title: str
    url: str
    type: str
    category: str


class BuildStatus(BaseModel):
    state: str
    summary: str
    startedAt: str | None = None
    finishedAt: str | None = None
    logPath: str | None = None


class SourcesResponse(BaseModel):
    name: str
    sources: list[ManagedSource]
    buildStatus: BuildStatus


class SourceTextRequest(BaseModel):
    text: str
    runIngestion: bool = False


class RemoveSourceRequest(BaseModel):
    id: str
